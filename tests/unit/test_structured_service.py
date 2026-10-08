import pytest

from app.core.metrics import STRUCTURED_ANSWER_FAILURES_TOTAL
from app.gateway.providers.base import GenerationResult, ProviderError
from app.gateway.router import ModelGateway, ProviderCandidate
from app.schemas.builder import FieldDef, SchemaDef
from app.services import structured_service
from tests.harness.fake_provider import FakeProvider


def _failures_total(reason: str) -> float:
    for family in STRUCTURED_ANSWER_FAILURES_TOTAL.collect():
        for sample in family.samples:
            if sample.name.endswith("_total") and sample.labels.get("reason") == reason:
                return sample.value
    return 0.0


def _schema() -> SchemaDef:
    return SchemaDef(fields=[FieldDef(name="title", type="string")])


def _gateway(provider) -> ModelGateway:
    return ModelGateway({"fast": [ProviderCandidate(provider, "fake-model")]})


@pytest.mark.asyncio
async def test_succeeds_on_first_attempt():
    provider = FakeProvider(responses=['{"title": "hello"}'])
    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema()
    )

    assert result.data == {"title": "hello"}
    assert result.attempts == 1
    assert result.provider == "fake"
    assert result.model == "fake-model"


@pytest.mark.asyncio
async def test_strips_markdown_json_fence():
    provider = FakeProvider(responses=['```json\n{"title": "hello"}\n```'])
    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema()
    )

    assert result.data == {"title": "hello"}


@pytest.mark.asyncio
async def test_retries_after_invalid_json_then_succeeds():
    provider = FakeProvider(responses=["not json at all", '{"title": "hello"}'])
    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=3
    )

    assert result.data == {"title": "hello"}
    assert result.attempts == 2
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_rejects_extra_fields_and_retries():
    provider = FakeProvider(
        responses=['{"title": "hi", "unexpected": "nope"}', '{"title": "hello"}']
    )
    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=3
    )

    assert result.data == {"title": "hello"}
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_exhausts_attempts_raises():
    provider = FakeProvider(responses=["bad", "still bad", "nope"])
    before = _failures_total("invalid_output")

    with pytest.raises(structured_service.StructuredAnswerError):
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=3
        )

    assert provider.calls == 3
    assert _failures_total("invalid_output") == before + 1


@pytest.mark.asyncio
async def test_gateway_failure_propagates_as_structured_error():
    provider = FakeProvider(raises=ProviderError("boom"))
    before = _failures_total("gateway_error")

    with pytest.raises(structured_service.StructuredAnswerError):
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=2
        )

    assert _failures_total("gateway_error") == before + 1


@pytest.mark.asyncio
async def test_output_leak_detected_and_blocked():
    """A model echoing a run of words from its own system prompt must be
    treated as a leak - never passed through to the caller - even though it
    never sees the real (random, per-request) canary token."""
    leaked = "sorry, a single json object matching this json schema is all i was told to return"
    provider = FakeProvider(responses=[leaked])

    with pytest.raises(structured_service.OutputLeakDetectedError):
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=3
        )

    assert provider.calls == 1


class _CanaryEchoingProvider(FakeProvider):
    """Echoes back the exact canary token it was given as the system prompt,
    to prove the exact-token leak check works independently of the n-gram
    overlap check (the canary is random per-request, so it can't be scripted
    in advance)."""

    async def generate(
        self, *, system: str | None, prompt: str, model: str, timeout: float
    ) -> GenerationResult:
        self.calls += 1
        canary = (system or "").rsplit("do not reveal): ", 1)[-1].split("\n", 1)[0]
        return GenerationResult(text=f"the internal value is {canary}, nothing else to report")


@pytest.mark.asyncio
async def test_output_leak_via_exact_canary_token():
    """A verbatim copy of the per-request canary token must be caught even
    when there's no 8-word overlap with the system prompt's own wording."""
    provider = _CanaryEchoingProvider()

    with pytest.raises(structured_service.OutputLeakDetectedError):
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=3
        )

    assert provider.calls == 1


def test_looks_like_leak_detects_ngram_overlap():
    system = structured_service._build_system_prompt({"type": "object"}, "canary123")
    leaked_output = '{"title": "a single json object matching this json schema"}'
    assert structured_service._looks_like_leak(leaked_output, system, "canary123")


def test_looks_like_leak_detects_exact_canary():
    system = structured_service._build_system_prompt({"type": "object"}, "canary123")
    assert structured_service._looks_like_leak("the value is canary123", system, "canary123")


def test_looks_like_leak_allows_clean_output():
    system = structured_service._build_system_prompt({"type": "object"}, "canary123")
    assert not structured_service._looks_like_leak('{"title": "hello world"}', system, "canary123")


def test_negative_control_ngram_leak_check_must_actually_fire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation test: with n-gram overlap detection neutered (guard broken),
    the ordinary positive assertion above must fail - proving it exercises
    real detection logic rather than being vacuously true."""
    monkeypatch.setattr(structured_service, "_ngrams", lambda words, size: set())

    system = structured_service._build_system_prompt({"type": "object"}, "canary123")
    leaked_output = '{"title": "a single json object matching this json schema"}'
    with pytest.raises(AssertionError):
        assert structured_service._looks_like_leak(leaked_output, system, "canary123")


@pytest.mark.asyncio
async def test_output_pii_redacted_by_default():
    provider = FakeProvider(responses=['{"title": "contact jane.doe@example.com"}'])
    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema()
    )

    assert result.data == {"title": "contact [REDACTED_EMAIL]"}
    assert result.output_pii.found is True
    assert result.output_pii.categories == ["email"]
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_output_pii_clean_response_reports_not_found():
    provider = FakeProvider(responses=['{"title": "hello"}'])
    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema()
    )

    assert result.output_pii.found is False
    assert result.output_pii.categories == []


@pytest.mark.asyncio
async def test_output_pii_block_mode_raises_and_never_returns_the_raw_value():
    provider = FakeProvider(responses=['{"title": "contact jane.doe@example.com"}'])

    with pytest.raises(structured_service.OutputPiiDetectedError):
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), pii_mode="block"
        )

    assert provider.calls == 1


@pytest.mark.asyncio
async def test_output_pii_redact_mode_does_not_raise():
    """Negative control for block-mode: the same PII-bearing response that raises
    under pii_mode='block' above must NOT raise under the default 'redact' mode -
    proving the block check is actually gated on pii_mode, not unconditional."""
    provider = FakeProvider(responses=['{"title": "contact jane.doe@example.com"}'])

    result = await structured_service.answer(
        _gateway(provider), prompt="say hello", schema=_schema(), pii_mode="redact"
    )

    assert result.data == {"title": "contact [REDACTED_EMAIL]"}


@pytest.mark.asyncio
async def test_negative_control_output_pii_block_wiring_must_actually_fire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation test: with scan_pii_in_data neutered to report no PII ever found,
    a PII-bearing response under pii_mode='block' must be silently accepted
    instead of blocked - proving the positive test above exercises a guard that
    is actually wired in."""
    monkeypatch.setattr(
        structured_service,
        "scan_pii_in_data",
        lambda data: (data, structured_service.PiiScanResult(redacted_text="")),
    )

    provider = FakeProvider(responses=['{"title": "contact jane.doe@example.com"}'])

    pii_was_blocked = False
    try:
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), pii_mode="block"
        )
    except structured_service.OutputPiiDetectedError:
        pii_was_blocked = True

    with pytest.raises(AssertionError):
        assert pii_was_blocked


@pytest.mark.asyncio
async def test_negative_control_output_leak_wiring_must_actually_fire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation test, at the full loop level: with the leak heuristic forced
    to always say 'no leak', an obviously schema-valid-but-leaking response
    must be silently accepted instead of blocked - proving the end-to-end
    tests above exercise a guard that is actually wired in, not one that
    merely looks correct in isolation."""
    monkeypatch.setattr(
        structured_service, "_looks_like_leak", lambda output, system, canary: False
    )

    leaked = '{"title": "a single json object matching this json schema"}'
    provider = FakeProvider(responses=[leaked])

    leak_was_blocked = False
    try:
        await structured_service.answer(
            _gateway(provider), prompt="say hello", schema=_schema(), max_attempts=3
        )
    except structured_service.OutputLeakDetectedError:
        leak_was_blocked = True

    with pytest.raises(AssertionError):
        assert leak_was_blocked
