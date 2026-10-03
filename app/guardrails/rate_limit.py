import time
from collections.abc import Callable
from functools import lru_cache

from app.config import get_settings


class RateLimitExceededError(Exception):
    """Raised when a key has exceeded its per-minute request budget."""

    def __init__(self, message: str, *, retry_after_seconds: float):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RateLimiter:
    def __init__(self, limit_per_minute: int, *, clock: Callable[[], float] = time.monotonic):
        self.limit_per_minute = limit_per_minute
        self._clock = clock
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        now = self._clock()
        window_start = now - 60.0
        hits = [t for t in self._hits.get(key, []) if t > window_start]
        if len(hits) >= self.limit_per_minute:
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


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().rate_limit_per_min)


def reset_rate_limiter_cache() -> None:
    get_rate_limiter.cache_clear()
