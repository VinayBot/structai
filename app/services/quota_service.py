from datetime import UTC, datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RateLimitError
from app.models.usage import QuotaUsage


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def check_and_increment(session: AsyncSession, *, scope: str, key: str, limit: int) -> None:
    """Atomically increments today's usage counter and raises once it exceeds limit.

    Uses a single INSERT ... ON CONFLICT DO UPDATE statement rather than a
    read-then-write pair, so two concurrent requests for the same scope/key
    can't both see "no row yet" and then both try to insert one - which
    previously raised an unhandled UNIQUE-constraint IntegrityError under
    real concurrent load instead of a clean 429.
    """
    day = _today()
    stmt = (
        sqlite_insert(QuotaUsage)
        .values(scope=scope, key=key, day=day, count=1)
        .on_conflict_do_update(
            index_elements=[QuotaUsage.scope, QuotaUsage.key, QuotaUsage.day],
            set_={"count": QuotaUsage.count + 1},
        )
        .returning(QuotaUsage.count)
    )
    result = await session.execute(stmt)
    new_count = result.scalar_one()
    await session.commit()

    if new_count > limit:
        raise RateLimitError(f"daily quota exceeded for {scope}")
