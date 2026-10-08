"""tests/harness/mock_provider.py (task 1.8) - the fake model backing e2e specs run
against a mock backend in CI. The most important property: every golden.json case's
own checks must actually pass against this provider's synthesized answer, checked
with the real eval/runner.py::check_result - not just trusted."""

import json

import pytest

from app.prompts.registry import get_prompt_registry
from eval.runner import check_result, load_cases
from tests.harness.mock_provider import _GOLDEN_CASES_PATH, MockModelProvider


@pytest.mark.asyncio
async def test_every_golden_case_check_passes_against_the_mock_answer():
    provider = MockModelProvider()
    cases = load_cases(_GOLDEN_CASES_PATH)
    assert len(cases) > 10  # sanity: didn't just load an empty/truncated file

    failures = []
    for case in cases:
        result = await provider.generate(
            system=None, prompt=case.prompt, model="mock-model", timeout=5
        )
        data = json.loads(result.text)
        passed, reason = check_result(data, case.checks)
        if not passed:
            failures.append(f"{case.id}: {reason} (got {data})")

    assert failures == [], "\n".join(failures)


@pytest.mark.asyncio
async def test_unmatched_prompt_falls_back_to_schema_aware_synthesis():
    provider = MockModelProvider()
    registry = get_prompt_registry()
    system = registry.render_structured_system(
        version="v1",
        schema_json={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "key_points"],
        },
        canary="abc",
    )

    result = await provider.generate(
        system=system, prompt="some prompt not in golden.json", model="m", timeout=5
    )
    data = json.loads(result.text)

    assert isinstance(data["summary"], str)
    assert isinstance(data["key_points"], list)
    assert all(isinstance(x, str) for x in data["key_points"])


@pytest.mark.asyncio
async def test_optional_field_rendered_as_anyof_is_still_synthesized():
    provider = MockModelProvider()
    registry = get_prompt_registry()
    system = registry.render_structured_system(
        version="v1",
        schema_json={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "hobby": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            },
            "required": ["name"],
        },
        canary="abc",
    )

    result = await provider.generate(system=system, prompt="whatever", model="m", timeout=5)
    data = json.loads(result.text)

    assert isinstance(data["name"], str)
    assert isinstance(data["hobby"], str)  # synthesized a real value, not null


@pytest.mark.asyncio
async def test_prompt_mentioning_email_and_phone_gets_fabricated_pii_in_string_fields():
    provider = MockModelProvider()
    registry = get_prompt_registry()
    system = registry.render_structured_system(
        version="v1",
        schema_json={
            "type": "object",
            "properties": {"ticket_body": {"type": "string"}},
            "required": ["ticket_body"],
        },
        canary="abc",
    )

    result = await provider.generate(
        system=system,
        prompt=(
            "Invent a fictional customer support ticket. Include a made-up customer "
            "email address and a made-up US phone number in the ticket body text."
        ),
        model="m",
        timeout=5,
    )
    data = json.loads(result.text)

    assert "@" in data["ticket_body"]
    assert any(ch.isdigit() for ch in data["ticket_body"])


@pytest.mark.asyncio
async def test_prompt_without_both_trigger_words_does_not_fabricate_pii():
    provider = MockModelProvider()
    registry = get_prompt_registry()
    system = registry.render_structured_system(
        version="v1",
        schema_json={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
        canary="abc",
    )

    result = await provider.generate(
        system=system,
        prompt="Summarize the benefits of structured LLM outputs in two sentences.",
        model="m",
        timeout=5,
    )
    data = json.loads(result.text)

    assert "@" not in data["summary"]


@pytest.mark.asyncio
async def test_no_system_prompt_returns_an_empty_object_rather_than_raising():
    provider = MockModelProvider()
    result = await provider.generate(system=None, prompt="whatever", model="m", timeout=5)
    assert json.loads(result.text) == {}


@pytest.mark.asyncio
async def test_list_models_returns_a_non_empty_list():
    provider = MockModelProvider()
    assert await provider.list_models() == ["mock-model"]
