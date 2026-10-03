import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.metrics import (
    GATEWAY_CALL_DURATION_SECONDS,
    GATEWAY_CALLS_TOTAL,
    GATEWAY_FALLBACKS_TOTAL,
)
from app.gateway.providers.base import ModelProvider, ProviderError


class GatewayError(Exception):
    """Raised when every candidate provider for a tier fails."""


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    opened_until: float = 0.0


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._state: dict[str, _CircuitState] = {}

    def _get(self, provider_name: str) -> _CircuitState:
        return self._state.setdefault(provider_name, _CircuitState())

    def is_open(self, provider_name: str) -> bool:
        return self._get(provider_name).opened_until > self._clock()

    def record_success(self, provider_name: str) -> None:
        state = self._get(provider_name)
        state.consecutive_failures = 0
        state.opened_until = 0.0

    def record_failure(self, provider_name: str) -> None:
        state = self._get(provider_name)
        state.consecutive_failures += 1
        if state.consecutive_failures >= self.failure_threshold:
            state.opened_until = self._clock() + self.cooldown_seconds


@dataclass
class ProviderCandidate:
    provider: ModelProvider
    model: str
    concurrency: int = 4


class ModelGateway:
    def __init__(
        self,
        tiers: dict[str, list[ProviderCandidate]],
        *,
        breaker: CircuitBreaker | None = None,
    ):
        self._tiers = tiers
        self._breaker = breaker or CircuitBreaker()
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _semaphore_for(self, candidate: ProviderCandidate) -> asyncio.Semaphore:
        key = candidate.provider.name
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(candidate.concurrency)
        return self._semaphores[key]

    async def generate(
        self, *, tier: str, system: str | None, prompt: str, timeout: float = 30.0
    ) -> tuple[str, str, str]:
        candidates = self._tiers.get(tier)
        if not candidates:
            raise GatewayError(f"unknown tier: {tier}")

        errors: list[str] = []
        first_provider_name = candidates[0].provider.name
        for candidate in candidates:
            provider_name = candidate.provider.name
            if self._breaker.is_open(provider_name):
                errors.append(f"{provider_name}: circuit open")
                continue

            call_start = time.monotonic()
            try:
                async with self._semaphore_for(candidate):
                    text = await asyncio.wait_for(
                        candidate.provider.generate(
                            system=system,
                            prompt=prompt,
                            model=candidate.model,
                            timeout=timeout,
                        ),
                        timeout=timeout,
                    )
            except (ProviderError, TimeoutError) as exc:
                GATEWAY_CALL_DURATION_SECONDS.labels(
                    provider=provider_name, model=candidate.model
                ).observe(time.monotonic() - call_start)
                self._breaker.record_failure(provider_name)
                GATEWAY_CALLS_TOTAL.labels(
                    provider=provider_name, model=candidate.model, outcome="failure"
                ).inc()
                errors.append(f"{provider_name}: {exc}")
                continue

            GATEWAY_CALL_DURATION_SECONDS.labels(
                provider=provider_name, model=candidate.model
            ).observe(time.monotonic() - call_start)
            self._breaker.record_success(provider_name)
            GATEWAY_CALLS_TOTAL.labels(
                provider=provider_name, model=candidate.model, outcome="success"
            ).inc()
            if provider_name != first_provider_name:
                GATEWAY_FALLBACKS_TOTAL.labels(
                    from_provider=first_provider_name, to_provider=provider_name
                ).inc()
            return text, provider_name, candidate.model

        raise GatewayError(f"all providers failed for tier '{tier}': {'; '.join(errors)}")
