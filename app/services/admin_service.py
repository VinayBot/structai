from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.usage import QuotaUsage
from app.models.user import User
from app.services.quota_service import _today


async def list_users(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[User], int]:
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    result = await session.scalars(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.all()), total


async def set_user_role(
    session: AsyncSession, *, admin: User, target_user_id: str, role: str
) -> User:
    if target_user_id == admin.id:
        raise ConflictError("admins cannot change their own role")

    user = await session.get(User, target_user_id)
    if user is None:
        raise NotFoundError("user not found")

    user.role = role
    await session.commit()
    return user


async def list_usage_today(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[tuple[str, str, int]], int]:
    day = _today()
    base = (
        select(User.id, User.email, QuotaUsage.count)
        .join(QuotaUsage, QuotaUsage.key == User.id)
        .where(QuotaUsage.scope == "user", QuotaUsage.day == day)
    )

    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await session.execute(base.order_by(QuotaUsage.count.desc()).limit(limit).offset(offset))
    return [(row[0], row[1], row[2]) for row in rows], total
