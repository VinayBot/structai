from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import RateLimitError, UnauthorizedError
from app.core.metrics import RATE_LIMIT_HITS_TOTAL
from app.core.security import TokenError, decode_token
from app.db import get_session
from app.guardrails.rate_limit import RateLimiter, RateLimitExceededError, get_rate_limiter
from app.models.user import User
from app.services import quota_service


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise UnauthorizedError("invalid or expired access token") from exc

    user = await session.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise UnauthorizedError("user not found or inactive")
    return user


async def enforce_rate_limit(
    user: User = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    try:
        limiter.check(user.id)
    except RateLimitExceededError as exc:
        RATE_LIMIT_HITS_TOTAL.inc()
        raise RateLimitError(str(exc), retry_after_seconds=exc.retry_after_seconds) from exc


async def enforce_daily_quota(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    await quota_service.check_and_increment(
        session, scope="user", key=user.id, limit=settings.daily_quota_user
    )
