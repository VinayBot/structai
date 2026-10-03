import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.eval import (
    EvalDashboardResponse,
    EvalRunDetail,
    EvalRunRequest,
    EvalRunSummary,
)
from app.services import eval_service
from eval.runner import run_eval
from eval.schemas import EvalReport, GoldenCase

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.get("/cases", response_model=list[GoldenCase])
async def list_cases(_user: User = Depends(get_current_user)) -> list[GoldenCase]:
    return eval_service.load_available_cases()


@router.post("/run", response_model=EvalReport)
async def run_eval_endpoint(
    body: EvalRunRequest,
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> EvalReport:
    cases = eval_service.select_cases(body.case_ids)
    gateway = eval_service.build_gateway_for(body.provider, settings)
    report = await run_eval(cases, gateway, concurrency=body.concurrency)
    await eval_service.persist_run(session, report, provider=body.provider, cases=cases)
    return report


@router.post("/run/stream")
async def run_eval_stream_endpoint(
    body: EvalRunRequest,
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    cases = eval_service.select_cases(body.case_ids)
    gateway = eval_service.build_gateway_for(body.provider, settings)

    async def event_source():
        async for event in eval_service.stream_cases(cases, gateway, concurrency=body.concurrency):
            payload: dict[str, object]
            if event.stage == "case_done" and event.case_result is not None:
                payload = {"stage": "case_done", "result": event.case_result.model_dump()}
            else:
                report = event.report.model_dump() if event.report else None
                if event.report is not None:
                    await eval_service.persist_run(
                        session, event.report, provider=body.provider, cases=cases
                    )
                payload = {"stage": "done", "report": report}
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/runs", response_model=list[EvalRunSummary])
async def list_runs(
    limit: int = Query(default=20, ge=1, le=200),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[EvalRunSummary]:
    runs = await eval_service.list_runs(session, limit=limit)
    return [EvalRunSummary.model_validate(r, from_attributes=True) for r in runs]


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def get_run(
    run_id: str,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EvalRunDetail:
    return await eval_service.get_run_detail(session, run_id)


@router.get("/dashboard", response_model=EvalDashboardResponse)
async def get_dashboard(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EvalDashboardResponse:
    return await eval_service.get_dashboard(session)
