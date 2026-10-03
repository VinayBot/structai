import pytest

from app.gateway.providers.base import ProviderError
from app.gateway.router import CircuitBreaker, GatewayError, ModelGateway, ProviderCandidate
from tests.harness.fake_provider import FakeProvider


@pytest.mark.asyncio
async def test_primary_success():
    primary = FakeProvider(name="primary", responses=["ok"])
    gateway = ModelGateway({"fast": [ProviderCandidate(primary, "model-a")]})

    text, provider_name, model = await gateway.generate(tier="fast", system=None, prompt="hi")

    assert text == "ok"
    assert provider_name == "primary"
    assert model == "model-a"
    assert primary.calls == 1


@pytest.mark.asyncio
async def test_fallback_to_second_provider_on_failure():
    primary = FakeProvider(name="primary", raises=ProviderError("boom"))
    secondary = FakeProvider(name="secondary", responses=["fallback-ok"])
    gateway = ModelGateway(
        {
            "fast": [
                ProviderCandidate(primary, "model-a"),
                ProviderCandidate(secondary, "model-b"),
            ]
        }
    )

    text, provider_name, _ = await gateway.generate(tier="fast", system=None, prompt="hi")

    assert text == "fallback-ok"
    assert provider_name == "secondary"


@pytest.mark.asyncio
async def test_all_providers_fail_raises_gateway_error():
    primary = FakeProvider(name="primary", raises=ProviderError("boom-1"))
    secondary = FakeProvider(name="secondary", raises=ProviderError("boom-2"))
    gateway = ModelGateway(
        {
            "fast": [
                ProviderCandidate(primary, "model-a"),
                ProviderCandidate(secondary, "model-b"),
            ]
        }
    )

    with pytest.raises(GatewayError):
        await gateway.generate(tier="fast", system=None, prompt="hi")


@pytest.mark.asyncio
async def test_unknown_tier_raises_gateway_error():
    gateway = ModelGateway({"fast": [ProviderCandidate(FakeProvider(), "m")]})

    with pytest.raises(GatewayError):
        await gateway.generate(tier="nonexistent", system=None, prompt="hi")


@pytest.mark.asyncio
async def test_timeout_triggers_fallback():
    slow = FakeProvider(name="slow", delay=0.2, responses=["too-slow"])
    fast = FakeProvider(name="fast", responses=["fast-ok"])
    gateway = ModelGateway(
        {
            "fast": [
                ProviderCandidate(slow, "model-a"),
                ProviderCandidate(fast, "model-b"),
            ]
        }
    )

    text, provider_name, _ = await gateway.generate(
        tier="fast", system=None, prompt="hi", timeout=0.05
    )

    assert text == "fast-ok"
    assert provider_name == "fast"


@pytest.mark.asyncio
async def test_circuit_breaker_skips_open_provider():
    state = {"now": 0.0}
    clock = lambda: state["now"]  # noqa: E731
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=30, clock=clock)

    primary = FakeProvider(name="primary", raises=ProviderError("boom"))
    secondary = FakeProvider(name="secondary", responses=["ok"])
    gateway = ModelGateway(
        {
            "fast": [
                ProviderCandidate(primary, "model-a"),
                ProviderCandidate(secondary, "model-b"),
            ]
        },
        breaker=breaker,
    )

    await gateway.generate(tier="fast", system=None, prompt="hi")
    assert primary.calls == 1
    assert secondary.calls == 1

    await gateway.generate(tier="fast", system=None, prompt="hi")
    assert primary.calls == 1
    assert secondary.calls == 2
