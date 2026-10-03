from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.usage import UsageResponse
from app.services import usage_service

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
async def get_usage(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UsageResponse:
    usage = await usage_service.get_usage(
        session, user_id=user.id, user_limit=settings.daily_quota_user
    )
    return UsageResponse(**usage)
