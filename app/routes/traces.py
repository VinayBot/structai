from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.core.tracing import get_tracer
from app.models.user import User
from app.schemas.traces import SpanResponse

router = APIRouter(tags=["observability"])


@router.get("/traces", response_model=list[SpanResponse])
async def list_traces(
    limit: int = Query(default=50, ge=1, le=500),
    _user: User = Depends(get_current_user),
) -> list[SpanResponse]:
    spans = get_tracer().recent(limit=limit)
    return [SpanResponse.model_validate(s, from_attributes=True) for s in spans]
