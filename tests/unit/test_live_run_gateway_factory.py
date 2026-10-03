from app.config import Settings
from app.gateway.factory import build_live_run_gateway

_SETTINGS = Settings(
    ollama_fast_model="ollama-fast",
    ollama_smart_model="ollama-smart",
    groq_fast_model="groq-fast",
    groq_smart_model="groq-smart",
)


def _candidates(gateway, tier="fast"):
    return gateway._tiers[tier]


def test_auto_uses_both_providers_in_default_order():
    gateway = build_live_run_gateway(
        provider="auto", model=None, tier="fast", strict_provider=False, settings=_SETTINGS
    )
    candidates = _candidates(gateway)
    assert [c.provider.name for c in candidates] == ["ollama", "groq"]
    assert [c.model for c in candidates] == ["ollama-fast", "groq-fast"]


def test_pinned_provider_without_strict_mode_keeps_the_other_as_fallback():
    gateway = build_live_run_gateway(
        provider="groq", model=None, tier="smart", strict_provider=False, settings=_SETTINGS
    )
    candidates = _candidates(gateway, "smart")
    assert [c.provider.name for c in candidates] == ["groq", "ollama"]
    assert [c.model for c in candidates] == ["groq-smart", "ollama-smart"]


def test_strict_provider_mode_drops_the_fallback_candidate():
    gateway = build_live_run_gateway(
        provider="ollama", model=None, tier="fast", strict_provider=True, settings=_SETTINGS
    )
    candidates = _candidates(gateway)
    assert [c.provider.name for c in candidates] == ["ollama"]


def test_model_override_applies_only_to_the_pinned_provider():
    gateway = build_live_run_gateway(
        provider="ollama",
        model="custom-model",
        tier="fast",
        strict_provider=False,
        settings=_SETTINGS,
    )
    candidates = _candidates(gateway)
    assert [c.model for c in candidates] == ["custom-model", "groq-fast"]


def test_model_override_is_ignored_for_auto_provider():
    gateway = build_live_run_gateway(
        provider="auto",
        model="custom-model",
        tier="fast",
        strict_provider=False,
        settings=_SETTINGS,
    )
    candidates = _candidates(gateway)
    assert [c.model for c in candidates] == ["ollama-fast", "groq-fast"]
