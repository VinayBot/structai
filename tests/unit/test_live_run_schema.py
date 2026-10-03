import pytest
from pydantic import ValidationError

from app.schemas.live_run import LiveRunRequest

_SCHEMA_DEF = {"fields": [{"name": "title", "type": "string"}]}


def test_strict_provider_requires_a_pinned_provider():
    with pytest.raises(ValidationError):
        LiveRunRequest(
            prompt="hi",
            schema_def=_SCHEMA_DEF,
            provider="auto",
            strict_provider=True,
        )


def test_strict_provider_with_a_pinned_provider_is_valid():
    req = LiveRunRequest(
        prompt="hi",
        schema_def=_SCHEMA_DEF,
        provider="ollama",
        strict_provider=True,
    )
    assert req.strict_provider is True


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        LiveRunRequest(
            prompt="hi",
            schema_def=_SCHEMA_DEF,
            unexpected_field="nope",
        )
