import json
import re
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.config import get_settings
from app.core.metrics import (
    OUTPUT_LEAK_BLOCKS_TOTAL,
    OUTPUT_PII_BLOCKS_TOTAL,
    STRUCTURED_ANSWER_ATTEMPTS,
    STRUCTURED_ANSWER_FAILURES_TOTAL,
)
from app.core.tracing import get_tracer
from app.gateway.router import GatewayError, ModelGateway
from app.guardrails.pii import PiiScanResult, scan_pii_in_data
from app.prompts.registry import get_prompt_registry
from app.schemas.builder import SchemaDef, build_model

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-z0-9]+")
_LEAK_NGRAM_SIZE = 8
_NO_PII = PiiScanResult(redacted_text="")


class StructuredAnswerError(Exception):
    """Raised when no attempt produced a schema-valid answer."""


class OutputLeakDetectedError(StructuredAnswerError):
    """Raised when a model's output appears to leak the system prompt."""


class OutputPiiDetectedError(StructuredAnswerError):
    """Raised when PII_MODE=block and a model's output contains PII."""


@dataclass
class StructuredResult:
    data: dict
    provider: str
    model: str
    attempts: int
    output_pii: PiiScanResult = field(default_factory=lambda: _NO_PII)
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class StageEvent:
    stage: str
    attempt: int
    detail: str | None = None
    result: StructuredResult | None = None


def _extract_json(text: str) -> dict:
    stripped = _CODE_FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("response JSON must be an object")
    return data


def _build_system_prompt(schema_json: dict, canary: str, examples: list[dict] | None = None) -> str:
    return get_prompt_registry().render_structured_system(
        version=get_settings().prompt_template_version,
        schema_json=schema_json,
        canary=canary,
        examples=examples,
    )


def _ngrams(words: list[str], size: int) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + size]) for i in range(len(words) - size + 1)}


def _looks_like_leak(output: str, system_prompt: str, canary: str) -> bool:
    """Defense in depth: catch a model echoing its system prompt back to the user.

    Checks the exact canary token embedded in this call's system prompt, plus any
    shared 8-word run between the output and the system prompt - robust to the
    model paraphrasing, partially quoting, or reordering the leaked text.
    """
    if canary in output:
        return True
    output_words = _WORD_RE.findall(output.lower())
    system_words = _WORD_RE.findall(system_prompt.lower())
    if len(output_words) < _LEAK_NGRAM_SIZE or len(system_words) < _LEAK_NGRAM_SIZE:
        return False
    return bool(_ngrams(output_words, _LEAK_NGRAM_SIZE) & _ngrams(system_words, _LEAK_NGRAM_SIZE))


async def run_structured_loop(
    gateway: ModelGateway,
    *,
    prompt: str,
    schema: SchemaDef,
    tier: str = "fast",
    max_attempts: int = 3,
    timeout: float = 30.0,
    pii_mode: str = "redact",
) -> AsyncIterator[StageEvent]:
    model_cls = build_model(schema)
    canary = secrets.token_hex(8)
    system = _build_system_prompt(model_cls.model_json_schema(), canary, examples=schema.examples)
    feedback: str | None = None
    tracer = get_tracer()

    async with tracer.start_span(
        "structured.loop", tier=tier, max_attempts=max_attempts
    ) as loop_span:
        for attempt in range(1, max_attempts + 1):
            yield StageEvent("generating", attempt)

            user_prompt = prompt
            if feedback is not None:
                user_prompt = (
                    f"{prompt}\n\nYour previous response was invalid: {feedback}\n"
                    "Return ONLY a corrected JSON object matching the schema."
                )

            try:
                async with tracer.start_span(
                    "gateway.generate", tier=tier, attempt=attempt
                ) as gen_span:
                    gen_result = await gateway.generate(
                        tier=tier, system=system, prompt=user_prompt, timeout=timeout
                    )
                    text = gen_result.text
                    provider_name = gen_result.provider
                    model_name = gen_result.model
                    gen_span.attributes["provider"] = provider_name
                    gen_span.attributes["model"] = model_name
            except GatewayError as exc:
                loop_span.attributes["outcome"] = "error"
                STRUCTURED_ANSWER_FAILURES_TOTAL.labels(reason="gateway_error").inc()
                yield StageEvent("error", attempt, detail=str(exc))
                return

            if _looks_like_leak(text, system, canary):
                loop_span.attributes["outcome"] = "output_leak"
                OUTPUT_LEAK_BLOCKS_TOTAL.inc()
                yield StageEvent(
                    "output_leak", attempt, detail="output blocked: system prompt leak detected"
                )
                return

            yield StageEvent("validating", attempt)

            try:
                parsed = _extract_json(text)
                validated = model_cls(**parsed)
            except (ValueError, ValidationError) as exc:
                feedback = str(exc)
                if attempt == max_attempts:
                    loop_span.attributes["outcome"] = "error"
                    STRUCTURED_ANSWER_FAILURES_TOTAL.labels(reason="invalid_output").inc()
                    yield StageEvent("error", attempt, detail=feedback)
                    return
                yield StageEvent("retrying", attempt, detail=feedback)
                continue

            output_data = validated.model_dump()
            redacted_data, output_pii = scan_pii_in_data(output_data)
            if output_pii.found and pii_mode == "block":
                loop_span.attributes["outcome"] = "output_pii"
                OUTPUT_PII_BLOCKS_TOTAL.inc()
                yield StageEvent(
                    "output_pii", attempt, detail="output blocked: PII detected in model output"
                )
                return
            final_data = redacted_data if pii_mode == "redact" else output_data

            loop_span.attributes["outcome"] = "done"
            loop_span.attributes["attempts"] = attempt
            STRUCTURED_ANSWER_ATTEMPTS.observe(attempt)
            yield StageEvent(
                "done",
                attempt,
                result=StructuredResult(
                    data=final_data,
                    provider=provider_name,
                    model=model_name,
                    attempts=attempt,
                    output_pii=output_pii,
                    prompt_tokens=gen_result.prompt_tokens,
                    completion_tokens=gen_result.completion_tokens,
                ),
            )
            return


async def answer(
    gateway: ModelGateway,
    *,
    prompt: str,
    schema: SchemaDef,
    tier: str = "fast",
    max_attempts: int = 3,
    timeout: float = 30.0,
    pii_mode: str = "redact",
) -> StructuredResult:
    async for event in run_structured_loop(
        gateway,
        prompt=prompt,
        schema=schema,
        tier=tier,
        max_attempts=max_attempts,
        timeout=timeout,
        pii_mode=pii_mode,
    ):
        if event.stage == "done" and event.result is not None:
            return event.result
        if event.stage == "output_leak":
            raise OutputLeakDetectedError(
                event.detail or "output blocked: system prompt leak detected"
            )
        if event.stage == "output_pii":
            raise OutputPiiDetectedError(
                event.detail or "output blocked: PII detected in model output"
            )
        if event.stage == "error":
            raise StructuredAnswerError(
                event.detail or "failed to generate a valid structured answer"
            )

    raise StructuredAnswerError("structured answer loop ended without a result")
