import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.core.deps import enforce_daily_quota, enforce_rate_limit, get_current_user
from app.core.errors import (
    GenerationError,
    OutputGuardrailError,
    OutputPiiDetectedError,
)
from app.gateway.factory import get_gateway
from app.gateway.router import ModelGateway
from app.guardrails.pii import PiiScanResult
from app.guardrails.prompt_guard import guard_prompt
from app.models.user import User
from app.schemas.structured import (
    GuardrailsMeta,
    PiiMeta,
    StructuredAnswerRequest,
    StructuredAnswerResponse,
)
from app.services import structured_service

router = APIRouter(prefix="/structured", tags=["structured"])


def _merge_pii_meta(input_scan: PiiScanResult, output_scan: PiiScanResult) -> GuardrailsMeta:
    categories = sorted(set(input_scan.categories) | set(output_scan.categories))
    counts: dict[str, int] = dict(input_scan.counts)
    for category, count in output_scan.counts.items():
        counts[category] = counts.get(category, 0) + count
    return GuardrailsMeta(pii=PiiMeta(found=bool(categories), categories=categories, counts=counts))


@router.post(
    "/answer",
    response_model=StructuredAnswerResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(enforce_daily_quota)],
)
async def answer_endpoint(
    body: StructuredAnswerRequest,
    _user: User = Depends(get_current_user),
    gateway: ModelGateway = Depends(get_gateway),
    settings: Settings = Depends(get_settings),
) -> StructuredAnswerResponse:
    prompt, input_scan = guard_prompt(body.prompt, settings)
    try:
        result = await structured_service.answer(
            gateway,
            prompt=prompt,
            schema=body.schema_def,
            tier=body.tier,
            max_attempts=settings.structured_max_attempts,
            timeout=settings.structured_timeout_seconds,
            pii_mode=settings.pii_mode,
        )
    except structured_service.OutputLeakDetectedError as exc:
        raise OutputGuardrailError(str(exc)) from exc
    except structured_service.OutputPiiDetectedError as exc:
        raise OutputPiiDetectedError(str(exc)) from exc
    except structured_service.StructuredAnswerError as exc:
        raise GenerationError(str(exc)) from exc

    return StructuredAnswerResponse(
        data=result.data,
        provider=result.provider,
        model=result.model,
        attempts=result.attempts,
        meta=_merge_pii_meta(input_scan, result.output_pii),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


@router.post(
    "/answer/stream",
    dependencies=[Depends(enforce_rate_limit), Depends(enforce_daily_quota)],
)
async def answer_stream_endpoint(
    body: StructuredAnswerRequest,
    _user: User = Depends(get_current_user),
    gateway: ModelGateway = Depends(get_gateway),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    prompt, input_scan = guard_prompt(body.prompt, settings)

    async def event_source():
        async for event in structured_service.run_structured_loop(
            gateway,
            prompt=prompt,
            schema=body.schema_def,
            tier=body.tier,
            max_attempts=settings.structured_max_attempts,
            timeout=settings.structured_timeout_seconds,
            pii_mode=settings.pii_mode,
        ):
            payload: dict = {"stage": event.stage, "attempt": event.attempt}
            if event.detail is not None:
                payload["detail"] = event.detail
            if event.result is not None:
                payload["data"] = event.result.data
                payload["provider"] = event.result.provider
                payload["model"] = event.result.model
                payload["attempts"] = event.result.attempts
                meta = _merge_pii_meta(input_scan, event.result.output_pii)
                payload["meta"] = meta.model_dump()
                payload["prompt_tokens"] = event.result.prompt_tokens
                payload["completion_tokens"] = event.result.completion_tokens
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
