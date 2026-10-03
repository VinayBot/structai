from fastapi import APIRouter

from app.core.build_info import get_build_info
from app.db import ping_db
from app.schemas.health import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    commit, build_time = get_build_info()
    return HealthResponse(status="ok", git_commit=commit, build_time=build_time)


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    db_ok = await ping_db()
    return ReadyResponse(ready=db_ok, db=db_ok)
