import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.metrics import (
    ESTIMATED_COST_USD_TOTAL,
    GATEWAY_CALL_DURATION_SECONDS,
    GATEWAY_CALLS_TOTAL,
    GATEWAY_FALLBACKS_TOTAL,
    TOKENS_CONSUMED_TOTAL,
)
from app.gateway.providers.base import ModelProvider, ProviderError

PriceTable = dict[str, dict[str, float]]


class GatewayError(Exception):
    """Raised when every candidate provider for a tier fails."""


@dataclass
class GatewayResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    price_table: PriceTable,
) -> float:
    """price_table is keyed "{provider}:{model}" -> {"prompt": $ per 1K tokens,
    "completion": $ per 1K tokens}, supplied entirely via settings.token_price_table -
    no price is ever hardcoded here. A provider/model with no entry (e.g. local
    Ollama, or simply nothing configured) costs 0, not an error."""
    prices = price_table.get(f"{provider}:{model}")
    if not prices:
        return 0.0
    prompt_price = prices.get("prompt", 0.0)
    completion_price = prices.get("completion", 0.0)
    return (prompt_tokens / 1000) * prompt_price + (completion_tokens / 1000) * completion_price


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
        price_table: PriceTable | None = None,
    ):
        self._tiers = tiers
        self._breaker = breaker or CircuitBreaker()
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._price_table = price_table or {}

    def _semaphore_for(self, candidate: ProviderCandidate) -> asyncio.Semaphore:
        key = candidate.provider.name
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(candidate.concurrency)
        return self._semaphores[key]

    async def generate(
        self, *, tier: str, system: str | None, prompt: str, timeout: float = 30.0
    ) -> GatewayResult:
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
                    result = await asyncio.wait_for(
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
            if result.prompt_tokens:
                TOKENS_CONSUMED_TOTAL.labels(
                    provider=provider_name, model=candidate.model, type="prompt"
                ).inc(result.prompt_tokens)
            if result.completion_tokens:
                TOKENS_CONSUMED_TOTAL.labels(
                    provider=provider_name, model=candidate.model, type="completion"
                ).inc(result.completion_tokens)
            cost = estimate_cost_usd(
                provider=provider_name,
                model=candidate.model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                price_table=self._price_table,
            )
            if cost:
                ESTIMATED_COST_USD_TOTAL.labels(provider=provider_name, model=candidate.model).inc(
                    cost
                )
            return GatewayResult(
                text=result.text,
                provider=provider_name,
                model=candidate.model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )

        raise GatewayError(f"all providers failed for tier '{tier}': {'; '.join(errors)}")
