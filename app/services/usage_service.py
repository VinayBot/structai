from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import QuotaUsage
from app.services.quota_service import _today


async def get_usage(session: AsyncSession, *, user_id: str, user_limit: int) -> dict:
    day = _today()

    user_row = await session.scalar(
        select(QuotaUsage).where(
            QuotaUsage.scope == "user", QuotaUsage.key == user_id, QuotaUsage.day == day
        )
    )

    return {
        "user_count_today": user_row.count if user_row is not None else 0,
        "user_limit": user_limit,
    }
