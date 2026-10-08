import pytest
from prometheus_client import REGISTRY

from app.gateway.providers.base import ProviderError
from app.gateway.router import ModelGateway, ProviderCandidate
from tests.harness.fake_provider import FakeProvider


def _calls(provider: str, model: str, outcome: str) -> float:
    value = REGISTRY.get_sample_value(
        "structai_gateway_calls_total",
        {"provider": provider, "model": model, "outcome": outcome},
    )
    return value or 0.0


def _fallbacks(from_provider: str, to_provider: str) -> float:
    value = REGISTRY.get_sample_value(
        "structai_gateway_fallbacks_total",
        {"from_provider": from_provider, "to_provider": to_provider},
    )
    return value or 0.0


@pytest.mark.asyncio
async def test_fallback_to_second_provider_increments_fallback_metric():
    primary = FakeProvider(name="primary-fb", raises=ProviderError("boom"))
    secondary = FakeProvider(name="secondary-fb", responses=["ok"])
    gateway = ModelGateway(
        {
            "fast": [
                ProviderCandidate(primary, "model-a"),
                ProviderCandidate(secondary, "model-b"),
            ]
        }
    )

    failures_before = _calls("primary-fb", "model-a", "failure")
    success_before = _calls("secondary-fb", "model-b", "success")
    fallbacks_before = _fallbacks("primary-fb", "secondary-fb")

    result = await gateway.generate(tier="fast", system=None, prompt="hi")

    assert result.text == "ok"
    assert result.provider == "secondary-fb"
    assert _calls("primary-fb", "model-a", "failure") == failures_before + 1
    assert _calls("secondary-fb", "model-b", "success") == success_before + 1
    assert _fallbacks("primary-fb", "secondary-fb") == fallbacks_before + 1


@pytest.mark.asyncio
async def test_primary_success_does_not_increment_fallback_metric():
    primary = FakeProvider(name="primary-nofb", responses=["ok"])
    gateway = ModelGateway({"fast": [ProviderCandidate(primary, "model-a")]})

    fallbacks_before = _fallbacks("primary-nofb", "primary-nofb")

    await gateway.generate(tier="fast", system=None, prompt="hi")

    assert _fallbacks("primary-nofb", "primary-nofb") == fallbacks_before
