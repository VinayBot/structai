import time
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.errors import RateLimitError
from app.core.tracing import Tracer, get_tracer
from app.gateway.router import ModelGateway
from app.guardrails.injection import is_prompt_injection
from app.guardrails.pii import scan_pii
from app.guardrails.rate_limit import RateLimiter, RateLimitExceededError
from app.models.user import User
from app.schemas.builder import SchemaBuildError, build_model
from app.schemas.live_run import LiveRunEvent, LiveRunRequest, LiveRunStatus
from app.services import quota_service, structured_service

_PIPELINE_NODES = [
    "jwt_auth",
    "request_validation",
    "rate_limiter",
    "injection_screen",
    "pii_redaction",
    "schema_builder",
    "router",
    "validator_retry",
    "output_guardrails",
]


def _truncate(text: str, limit: int = 160) -> str:
    return text if len(text) <= limit else f"{text[:limit]}…"


def _skipped_after(node_id: str) -> list[LiveRunEvent]:
    start = _PIPELINE_NODES.index(node_id) + 1
    return [LiveRunEvent(node_id=n, status="skipped") for n in _PIPELINE_NODES[start:]]


async def _event(
    tracer: Tracer, node_id: str, status: LiveRunStatus, start: float, **fields
) -> LiveRunEvent:
    async with tracer.start_span(f"live_run.{node_id}") as span:
        trace_id, span_id = span.trace_id, span.span_id
    return LiveRunEvent(
        node_id=node_id,
        status=status,
        latency_ms=(time.monotonic() - start) * 1000,
        trace_id=trace_id,
        span_id=span_id,
        **fields,
    )


async def run_live_stream(
    *,
    user: User,
    session: AsyncSession,
    gateway: ModelGateway,
    settings: Settings,
    limiter: RateLimiter,
    body: LiveRunRequest,
) -> AsyncIterator[LiveRunEvent]:
    tracer = get_tracer()
    t = time.monotonic()
    pii_mode = body.pii_mode if body.pii_mode is not None else settings.pii_mode

    try:
        yield await _event(
            tracer,
            "jwt_auth",
            "passed",
            t,
            output_summary="authenticated",
            edge_ids=["e_jwt_auth_request_validation"],
        )
        yield await _event(
            tracer, "request_validation", "passed", t, output_summary="body validated"
        )

        try:
            limiter.check(user.id)
            await quota_service.check_and_increment(
                session, scope="user", key=user.id, limit=settings.daily_quota_user
            )
        except RateLimitExceededError as exc:
            yield await _event(
                tracer,
                "rate_limiter",
                "failed",
                t,
                http_status=429,
                error_code="rate_limited",
                retry_after_seconds=exc.retry_after_seconds,
                output_summary=str(exc),
            )
            for ev in _skipped_after("rate_limiter"):
                yield ev
            return
        except RateLimitError as exc:
            yield await _event(
                tracer,
                "rate_limiter",
                "failed",
                t,
                http_status=exc.status_code,
                error_code=exc.code,
                retry_after_seconds=exc.retry_after_seconds,
                output_summary=exc.message,
            )
            for ev in _skipped_after("rate_limiter"):
                yield ev
            return
        yield await _event(
            tracer,
            "rate_limiter",
            "passed",
            t,
            output_summary="within budget",
            edge_ids=["e_rate_limiter_injection"],
        )

        if is_prompt_injection(body.prompt):
            yield await _event(
                tracer,
                "injection_screen",
                "failed",
                t,
                http_status=400,
                error_code="guardrail_blocked",
                output_summary="blocked: matched a known injection pattern",
            )
            for ev in _skipped_after("injection_screen"):
                yield ev
            return
        yield await _event(
            tracer,
            "injection_screen",
            "passed",
            t,
            input_summary=f"{len(body.prompt)} chars",
            output_summary="no match",
            edge_ids=["e_injection_pii"],
        )

        input_scan = scan_pii(body.prompt)
        if input_scan.found and pii_mode == "block":
            yield await _event(
                tracer,
                "pii_redaction",
                "failed",
                t,
                http_status=400,
                error_code="pii_detected",
                output_summary=f"blocked: PII detected ({', '.join(input_scan.categories)})",
            )
            for ev in _skipped_after("pii_redaction"):
                yield ev
            return

        redacted_prompt = input_scan.redacted_text if pii_mode == "redact" else body.prompt
        yield await _event(
            tracer,
            "pii_redaction",
            "modified" if input_scan.found else "passed",
            t,
            output_summary=(
                f"redacted ({', '.join(input_scan.categories)})"
                if input_scan.found
                else "no pii detected"
            ),
        )

        try:
            build_model(body.schema_def)
        except SchemaBuildError as exc:
            yield await _event(
                tracer,
                "schema_builder",
                "failed",
                t,
                http_status=422,
                error_code="validation_error",
                output_summary=_truncate(str(exc)),
            )
            for ev in _skipped_after("schema_builder"):
                yield ev
            return
        yield await _event(
            tracer,
            "schema_builder",
            "passed",
            t,
            output_summary=f"compiled {len(body.schema_def.fields)} field(s)",
        )

        gateway_ok_this_attempt = False
        async for stage_event in structured_service.run_structured_loop(
            gateway,
            prompt=redacted_prompt,
            schema=body.schema_def,
            tier=body.tier,
            max_attempts=settings.structured_max_attempts,
            timeout=settings.structured_timeout_seconds,
            pii_mode=pii_mode,
        ):
            if stage_event.stage == "generating":
                gateway_ok_this_attempt = False
                yield await _event(
                    tracer,
                    "router",
                    "running",
                    t,
                    input_summary=f"tier={body.tier}, attempt={stage_event.attempt}",
                )
            elif stage_event.stage == "validating":
                gateway_ok_this_attempt = True
                yield await _event(
                    tracer, "router", "passed", t, output_summary="candidate responded"
                )
                yield await _event(
                    tracer,
                    "validator_retry",
                    "running",
                    t,
                    input_summary=f"attempt={stage_event.attempt}",
                )
            elif stage_event.stage == "retrying":
                yield await _event(
                    tracer,
                    "validator_retry",
                    "failed",
                    t,
                    output_summary=_truncate(stage_event.detail or ""),
                    edge_ids=["e_feedback_retry"],
                )
            elif stage_event.stage == "output_leak":
                yield await _event(
                    tracer,
                    "output_guardrails",
                    "failed",
                    t,
                    http_status=502,
                    error_code="output_guardrail_blocked",
                    output_summary=(
                        stage_event.detail or "output blocked: system prompt leak detected"
                    ),
                )
                for ev in _skipped_after("output_guardrails"):
                    yield ev
                return
            elif stage_event.stage == "output_pii":
                yield await _event(
                    tracer,
                    "output_guardrails",
                    "failed",
                    t,
                    http_status=502,
                    error_code="output_pii_blocked",
                    output_summary=(
                        stage_event.detail or "output blocked: PII detected in model output"
                    ),
                )
                for ev in _skipped_after("output_guardrails"):
                    yield ev
                return
            elif stage_event.stage == "error":
                failed_node = "validator_retry" if gateway_ok_this_attempt else "router"
                yield await _event(
                    tracer,
                    failed_node,
                    "failed",
                    t,
                    http_status=502,
                    error_code="generation_failed",
                    output_summary=_truncate(stage_event.detail or ""),
                )
                for ev in _skipped_after(failed_node):
                    yield ev
                return
            elif stage_event.stage == "done" and stage_event.result is not None:
                result = stage_event.result
                yield await _event(
                    tracer,
                    "validator_retry",
                    "passed",
                    t,
                    output_summary=f"validated in {result.attempts} attempt(s)",
                    edge_ids=[
                        "e_validator_router",
                        f"e_router_{result.provider}",
                        f"e_{result.provider}_output_guardrails",
                    ],
                )
                yield await _event(
                    tracer,
                    "output_guardrails",
                    "modified" if result.output_pii.found else "passed",
                    t,
                    output_summary=(
                        "output matches schema; pii redacted "
                        f"({', '.join(result.output_pii.categories)})"
                        if result.output_pii.found
                        else "output matches schema"
                    ),
                    data=result.data,
                    provider=result.provider,
                    model=result.model,
                    attempts=result.attempts,
                )
                return
    except Exception as exc:
        yield LiveRunEvent(
            node_id="internal_error",
            status="failed",
            http_status=500,
            error_code="internal_error",
            output_summary=_truncate(str(exc)),
        )
