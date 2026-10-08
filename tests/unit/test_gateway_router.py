import pytest
from prometheus_client import REGISTRY

from app.gateway.providers.base import ProviderError
from app.gateway.router import (
    CircuitBreaker,
    GatewayError,
    ModelGateway,
    ProviderCandidate,
    estimate_cost_usd,
)
from tests.harness.fake_provider import FakeProvider


def _tokens_consumed(provider: str, model: str, token_type: str) -> float:
    value = REGISTRY.get_sample_value(
        "structai_tokens_consumed_total",
        {"provider": provider, "model": model, "type": token_type},
    )
    return value or 0.0


def _estimated_cost(provider: str, model: str) -> float:
    value = REGISTRY.get_sample_value(
        "structai_estimated_cost_usd_total", {"provider": provider, "model": model}
    )
    return value or 0.0


@pytest.mark.asyncio
async def test_primary_success():
    primary = FakeProvider(name="primary", responses=["ok"], prompt_tokens=11, completion_tokens=4)
    gateway = ModelGateway({"fast": [ProviderCandidate(primary, "model-a")]})

    result = await gateway.generate(tier="fast", system=None, prompt="hi")

    assert result.text == "ok"
    assert result.provider == "primary"
    assert result.model == "model-a"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 4
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

    result = await gateway.generate(tier="fast", system=None, prompt="hi")

    assert result.text == "fallback-ok"
    assert result.provider == "secondary"


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

    result = await gateway.generate(tier="fast", system=None, prompt="hi", timeout=0.05)

    assert result.text == "fast-ok"
    assert result.provider == "fast"


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


@pytest.mark.asyncio
async def test_successful_call_increments_tokens_consumed_metric():
    provider = FakeProvider(
        name="token-metric-provider", responses=["ok"], prompt_tokens=30, completion_tokens=12
    )
    gateway = ModelGateway({"fast": [ProviderCandidate(provider, "model-a")]})

    before_prompt = _tokens_consumed("token-metric-provider", "model-a", "prompt")
    before_completion = _tokens_consumed("token-metric-provider", "model-a", "completion")

    await gateway.generate(tier="fast", system=None, prompt="hi")

    assert _tokens_consumed("token-metric-provider", "model-a", "prompt") == before_prompt + 30
    assert (
        _tokens_consumed("token-metric-provider", "model-a", "completion") == before_completion + 12
    )


@pytest.mark.asyncio
async def test_zero_token_result_does_not_touch_tokens_consumed_metric():
    """FakeProvider's default (no usage simulated) must behave exactly as if token
    accounting didn't exist - no metric sample recorded at all, not a sample of 0."""
    provider = FakeProvider(name="zero-token-provider", responses=["ok"])
    gateway = ModelGateway({"fast": [ProviderCandidate(provider, "model-a")]})

    await gateway.generate(tier="fast", system=None, prompt="hi")

    assert (
        REGISTRY.get_sample_value(
            "structai_tokens_consumed_total",
            {"provider": "zero-token-provider", "model": "model-a", "type": "prompt"},
        )
        is None
    )


@pytest.mark.asyncio
async def test_cost_counter_increments_when_price_table_configured():
    provider = FakeProvider(
        name="priced-provider", responses=["ok"], prompt_tokens=1000, completion_tokens=1000
    )
    gateway = ModelGateway(
        {"fast": [ProviderCandidate(provider, "model-a")]},
        price_table={"priced-provider:model-a": {"prompt": 0.5, "completion": 1.0}},
    )

    before = _estimated_cost("priced-provider", "model-a")
    await gateway.generate(tier="fast", system=None, prompt="hi")

    # 1000 prompt tokens @ $0.50/1K + 1000 completion tokens @ $1.00/1K = $1.50
    assert _estimated_cost("priced-provider", "model-a") == pytest.approx(before + 1.5)


@pytest.mark.asyncio
async def test_cost_counter_not_touched_when_model_is_unpriced():
    provider = FakeProvider(
        name="unpriced-provider", responses=["ok"], prompt_tokens=1000, completion_tokens=1000
    )
    gateway = ModelGateway({"fast": [ProviderCandidate(provider, "model-a")]})  # no price_table

    await gateway.generate(tier="fast", system=None, prompt="hi")

    assert (
        REGISTRY.get_sample_value(
            "structai_estimated_cost_usd_total",
            {"provider": "unpriced-provider", "model": "model-a"},
        )
        is None
    )


class TestEstimateCostUsd:
    def test_unpriced_model_costs_zero(self):
        cost = estimate_cost_usd(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            prompt_tokens=10_000,
            completion_tokens=10_000,
            price_table={},
        )
        assert cost == 0.0

    def test_priced_model_computes_per_1k_token_cost(self):
        cost = estimate_cost_usd(
            provider="groq",
            model="openai/gpt-oss-20b",
            prompt_tokens=2000,
            completion_tokens=500,
            price_table={"groq:openai/gpt-oss-20b": {"prompt": 0.1, "completion": 0.2}},
        )
        # 2000/1000 * 0.1 + 500/1000 * 0.2 = 0.2 + 0.1
        assert cost == pytest.approx(0.3)

    def test_partially_priced_entry_treats_missing_side_as_zero(self):
        cost = estimate_cost_usd(
            provider="groq",
            model="openai/gpt-oss-20b",
            prompt_tokens=1000,
            completion_tokens=1000,
            price_table={"groq:openai/gpt-oss-20b": {"prompt": 1.0}},  # no "completion" key
        )
        assert cost == pytest.approx(1.0)
