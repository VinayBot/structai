from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db import get_session
from app.gateway.factory import get_live_run_gateway
from app.gateway.router import ModelGateway
from app.guardrails.rate_limit import RateLimiter, get_rate_limiter
from app.models.user import User
from app.schemas.arch import GraphResponse, StatusResponse, TestRunRequest, TestRunResponse
from app.schemas.live_run import LiveRunRequest
from app.services import arch_service, live_run_service

router = APIRouter(prefix="/arch", tags=["architecture"])


@router.get("/graph", response_model=GraphResponse)
async def get_graph(request: Request, _user: User = Depends(get_current_user)) -> GraphResponse:
    return arch_service.get_graph(request.app.openapi())


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StatusResponse:
    return await arch_service.check_status(settings)


@router.post("/test-run", response_model=TestRunResponse)
async def run_test(
    body: TestRunRequest,
    _user: User = Depends(get_current_user),
) -> TestRunResponse:
    return await arch_service.run_scenario(body.scenario_id)


@router.post("/live-run")
async def live_run(
    body: LiveRunRequest,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    gateway: ModelGateway = Depends(get_live_run_gateway),
    limiter: RateLimiter = Depends(get_rate_limiter),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    async def event_source():
        async for event in live_run_service.run_live_stream(
            user=user,
            session=session,
            gateway=gateway,
            settings=settings,
            limiter=limiter,
            body=body,
        ):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
