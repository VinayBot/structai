import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    """Raised when a key has exceeded its per-minute request budget."""

    def __init__(self, message: str, *, retry_after_seconds: float):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RateLimitBackend(ABC):
    @abstractmethod
    async def check(self, key: str, limit_per_minute: int) -> None:
        """Raises RateLimitExceededError if `key` is already at its budget for this
        window; otherwise records this hit and returns."""
        raise NotImplementedError


class InMemoryBackend(RateLimitBackend):
    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[str, list[float]] = {}

    async def check(self, key: str, limit_per_minute: int) -> None:
        now = self._clock()
        window_start = now - 60.0
        hits = [t for t in self._hits.get(key, []) if t > window_start]
        if len(hits) >= limit_per_minute:
            # Normally there's an oldest hit whose aging-out ends the wait. A non-positive
            # limit has no hits to age out (every call is rejected before being recorded),
            # so fall back to the full window as the retry hint.
            retry_after_seconds = max(0.0, hits[0] + 60.0 - now) if hits else 60.0
            raise RateLimitExceededError(
                "rate limit exceeded; try again in a minute",
                retry_after_seconds=retry_after_seconds,
            )
        hits.append(now)
        self._hits[key] = hits


# Sorted-set sliding window, keyed per rate-limit key. Trimming expired entries,
# checking the count, and adding this hit all happen in one Lua round-trip, so two
# app instances racing on the same key can't both observe "under limit" and both add
# themselves past it. The ZADD only runs on the branch that allows the request, so a
# rejected hit is never added - it doesn't count against the window it was rejected
# from. Returns -1 if the request is allowed, or the oldest in-window hit's
# timestamp (ms) if rejected, so the caller can compute retry_after_seconds without a
# second round-trip.
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if oldest[2] then
        return tonumber(oldest[2])
    end
    return now_ms
end

redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
return -1
"""

_WINDOW_MS = 60_000


class RedisBackend(RateLimitBackend):
    """Shared, multi-instance-safe limiter on a Redis sorted set.

    `fail_open` governs what happens if Redis itself is unreachable:
    - True: log loudly and fall back to a per-instance InMemoryBackend until Redis
      recovers. Appropriate for an abuse/cost control (the general per-user limiter)
      where staying available matters more than perfect cross-instance accounting
      during an outage.
    - False: raise RateLimitExceededError immediately (fail closed). Appropriate for
      a security control (the per-IP auth limiter guarding register/login/refresh/
      github-callback) - a Redis outage must not silently remove brute-force
      protection.
    """

    def __init__(
        self,
        redis_client: Any,
        *,
        fail_open: bool,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._redis = redis_client
        self._fail_open = fail_open
        self._clock = clock
        self._script = redis_client.register_script(_SLIDING_WINDOW_SCRIPT)
        self._fallback = InMemoryBackend(clock=clock) if fail_open else None

    async def check(self, key: str, limit_per_minute: int) -> None:
        now_ms = int(self._clock() * 1000)
        member = f"{now_ms}:{uuid.uuid4().hex}"

        try:
            oldest_ms = await self._script(
                keys=[f"ratelimit:{key}"],
                args=[now_ms, _WINDOW_MS, limit_per_minute, member],
            )
        except Exception:
            if self._fallback is not None:
                logger.error(
                    "redis rate limiter unreachable - falling back to in-memory "
                    "limiting on this instance until it recovers",
                    exc_info=True,
                )
                await self._fallback.check(key, limit_per_minute)
                return
            logger.error(
                "redis rate limiter unreachable - failing closed on a security-sensitive limiter",
                exc_info=True,
            )
            raise RateLimitExceededError(
                "rate limiting is temporarily unavailable; try again shortly",
                retry_after_seconds=5.0,
            ) from None

        if oldest_ms != -1:
            retry_after_seconds = max(0.0, (oldest_ms + _WINDOW_MS - now_ms) / 1000)
            raise RateLimitExceededError(
                "rate limit exceeded; try again in a minute",
                retry_after_seconds=retry_after_seconds,
            )


class RateLimiter:
    def __init__(
        self,
        limit_per_minute: int,
        *,
        backend: RateLimitBackend | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.limit_per_minute = limit_per_minute
        self._backend = backend or InMemoryBackend(clock=clock)

    async def check(self, key: str) -> None:
        await self._backend.check(key, self.limit_per_minute)


def _build_redis_backend(settings: Settings, *, fail_open: bool) -> RedisBackend:
    try:
        import redis.asyncio as redis_asyncio
    except ImportError as exc:
        raise RuntimeError(
            "RATE_LIMIT_BACKEND=redis requires the 'redis' extra - install with "
            "`uv sync --extra redis` (or `pip install structai[redis]`)"
        ) from exc
    client = redis_asyncio.from_url(settings.redis_url)
    return RedisBackend(client, fail_open=fail_open)


def _build_backend(settings: Settings, *, fail_open: bool) -> RateLimitBackend:
    if settings.rate_limit_backend == "redis":
        return _build_redis_backend(settings, fail_open=fail_open)
    return InMemoryBackend()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return RateLimiter(
        settings.rate_limit_per_min, backend=_build_backend(settings, fail_open=True)
    )


@lru_cache
def get_auth_rate_limiter() -> RateLimiter:
    """Separate instance (own limit, own hit-tracking) from get_rate_limiter() -
    a burst of login attempts shouldn't spend the same budget as structured-answer
    calls, and vice versa. Fails closed (fail_open=False): see RedisBackend's
    docstring for why the auth limiter's failure policy differs from the general one."""
    settings = get_settings()
    return RateLimiter(
        settings.auth_rate_limit_per_min, backend=_build_backend(settings, fail_open=False)
    )


def reset_rate_limiter_cache() -> None:
    get_rate_limiter.cache_clear()
    get_auth_rate_limiter.cache_clear()
