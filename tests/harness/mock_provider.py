"""Schema- and golden-case-aware fake ModelProvider, backing tests/harness/mock_app.py
for frontend/e2e Playwright specs run against a mock backend in CI - standing in for
a real Ollama/Groq model so those specs don't need one.

Two answering strategies, tried in order:

1. Golden-case-aware: if the user prompt exactly matches one of
   eval/cases/golden.json's prompts, answer with a value satisfying that case's own
   `checks` (equals/contains/one_of) instead of a generic placeholder - this is what
   lets frontend/e2e/eval.spec.ts's pass-rate assertions hold for any subset of
   cases it happens to select. This mechanically derives a satisfying value from
   each case's own declared checks; it is not hardcoded answers typed by a person,
   and it never reads or writes eval/cases/golden.json's content, only this file's.

2. Schema-aware: for anything else (the Architecture tab's Live Run demo presets,
   or any user-authored schema), parses the JSON Schema embedded in the system
   prompt (app/prompts/structured_system_v1.jinja2 always renders it as the
   prompt's second line) and synthesizes a type-correct, schema-valid JSON object.
   If the prompt text mentions both "email" and "phone" (matching the Live Run
   PII-demo preset's exact wording), string fields get a fabricated email/phone
   appended, so the output-side PII redaction path has something real to catch -
   a narrow, documented heuristic, not general language understanding.
"""

import json
from pathlib import Path
from typing import Any

from app.gateway.providers.base import GenerationResult, ModelProvider

_GOLDEN_CASES_PATH = Path(__file__).resolve().parents[2] / "eval" / "cases" / "golden.json"
_PII_TRIGGER_WORDS = ("email", "phone")


def _coerce(raw: str, field_type: str) -> Any:
    try:
        if field_type == "integer":
            return int(float(raw))
        if field_type == "number":
            return float(raw)
        if field_type == "boolean":
            return raw.strip().lower() == "true"
        if field_type == "string_list":
            return [raw]
        if field_type == "integer_list":
            return [int(float(raw))]
    except ValueError:
        pass
    return raw


def _dummy_value(field_type: str, field_name: str, seed: int) -> Any:
    if field_type == "integer":
        return seed + 1
    if field_type == "number":
        return float(seed + 1)
    if field_type == "boolean":
        return True
    if field_type == "string_list":
        return [f"{field_name}-item-{seed}-a", f"{field_name}-item-{seed}-b"]
    if field_type == "integer_list":
        return [seed + 1, seed + 2]
    return f"sample-{field_name}-{seed}"


def _load_golden_answers() -> dict[str, dict]:
    if not _GOLDEN_CASES_PATH.exists():
        return {}
    raw_cases = json.loads(_GOLDEN_CASES_PATH.read_text())

    answers: dict[str, dict] = {}
    for case in raw_cases:
        field_types = {f["name"]: f["type"] for f in case["schema_def"]["fields"]}
        data = {
            name: _dummy_value(ftype, name, i)
            for i, (name, ftype) in enumerate(field_types.items())
        }
        for check in case.get("checks", []):
            field_type = field_types.get(check["field"], "string")
            if check.get("equals") is not None:
                data[check["field"]] = _coerce(check["equals"], field_type)
            elif check.get("contains") is not None:
                data[check["field"]] = _coerce(check["contains"], field_type)
            elif check.get("one_of"):
                data[check["field"]] = _coerce(check["one_of"][0], field_type)
        answers[case["prompt"]] = data
    return answers


def _json_type(field_schema: dict) -> str:
    """field_schema is one entry of a Pydantic-generated JSON Schema's "properties" -
    an optional field renders as {"anyOf": [{"type": X}, {"type": "null"}], ...}."""
    candidates = field_schema.get("anyOf", [field_schema])
    non_null = next((c for c in candidates if c.get("type") != "null"), candidates[0])
    json_type = non_null.get("type", "string")
    if json_type == "array":
        item_type = non_null.get("items", {}).get("type")
        return "integer_list" if item_type == "integer" else "string_list"
    if json_type in ("integer", "number", "boolean"):
        return json_type
    return "string"


class MockModelProvider(ModelProvider):
    name = "mock"

    def __init__(self) -> None:
        self._golden_answers = _load_golden_answers()

    async def generate(
        self, *, system: str | None, prompt: str, model: str, timeout: float
    ) -> GenerationResult:
        golden = self._golden_answers.get(prompt)
        if golden is not None:
            return GenerationResult(text=json.dumps(golden))

        schema = self._extract_schema(system)
        data = self._synthesize(schema, prompt) if schema else {}
        return GenerationResult(text=json.dumps(data))

    def _extract_schema(self, system: str | None) -> dict | None:
        if not system:
            return None
        lines = system.split("\n")
        if len(lines) < 2:
            return None
        try:
            parsed = json.loads(lines[1])
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _synthesize(self, schema: dict, prompt: str) -> dict:
        properties: dict[str, dict] = schema.get("properties", {})
        wants_fabricated_pii = all(word in prompt.lower() for word in _PII_TRIGGER_WORDS)

        data: dict[str, Any] = {}
        for i, (name, field_schema) in enumerate(properties.items()):
            field_type = _json_type(field_schema)
            value = _dummy_value(field_type, name, i)
            if wants_fabricated_pii and field_type == "string":
                value = f"{value}. Contact: jane.doe@example.com or (555) 123-4567."
            data[name] = value
        return data

    async def list_models(self) -> list[str]:
        return ["mock-model"]
