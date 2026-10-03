from fastapi import APIRouter, Depends, Response

from app.core.deps import get_current_user
from app.core.metrics import render_metrics
from app.models.user import User
from app.schemas.metrics import MetricsSummaryResponse
from app.services.metrics_service import build_summary

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(_user: User = Depends(get_current_user)) -> MetricsSummaryResponse:
    return build_summary()
