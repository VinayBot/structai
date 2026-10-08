"""RedisBackend (task 1.7) against fakeredis - never a real Redis server, so this
backend is fully exercised without the default test suite depending on one."""

import sys

import fakeredis.aioredis
import pytest

from app.config import Settings
from app.guardrails.rate_limit import (
    InMemoryBackend,
    RateLimitExceededError,
    RedisBackend,
    _build_backend,
    _build_redis_backend,
)


def _fake_client() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_allows_up_to_the_limit_then_rejects():
    backend = RedisBackend(_fake_client(), fail_open=True)
    await backend.check("user-1", 2)
    await backend.check("user-1", 2)
    with pytest.raises(RateLimitExceededError):
        await backend.check("user-1", 2)


@pytest.mark.asyncio
async def test_identical_timestamps_do_not_collide_into_one_member():
    """Two hits landing in the same millisecond must still each count - a unique
    member per request (timestamp + uuid), not just the timestamp, is what the
    task calls for."""
    backend = RedisBackend(_fake_client(), fail_open=True, clock=lambda: 1000.0)
    await backend.check("user-1", 2)
    await backend.check("user-1", 2)
    with pytest.raises(RateLimitExceededError):
        await backend.check("user-1", 2)


@pytest.mark.asyncio
async def test_rejected_hits_are_not_counted_against_the_window():
    backend = RedisBackend(_fake_client(), fail_open=True, clock=lambda: 1000.0)
    await backend.check("user-1", 1)
    for _ in range(5):
        with pytest.raises(RateLimitExceededError):
            await backend.check("user-1", 1)

    card = await backend._redis.zcard("ratelimit:user-1")
    assert card == 1  # still just the one real hit - the 5 rejections never got added


@pytest.mark.asyncio
async def test_keys_are_independent():
    backend = RedisBackend(_fake_client(), fail_open=True)
    await backend.check("user-1", 1)
    await backend.check("user-2", 1)  # different key, same instance - own budget


@pytest.mark.asyncio
async def test_window_slides_with_injected_clock():
    now = [0.0]
    backend = RedisBackend(_fake_client(), fail_open=True, clock=lambda: now[0])
    await backend.check("user-1", 1)
    with pytest.raises(RateLimitExceededError):
        await backend.check("user-1", 1)

    now[0] += 61.0
    await backend.check("user-1", 1)  # the first hit has aged out of the window


@pytest.mark.asyncio
async def test_sets_a_ttl_on_the_key():
    client = _fake_client()
    backend = RedisBackend(client, fail_open=True)
    await backend.check("user-1", 5)

    ttl_ms = await client.pttl("ratelimit:user-1")
    assert 0 < ttl_ms <= 60_000


class _AlwaysBrokenScript:
    async def __call__(self, *args, **kwargs):
        raise ConnectionError("simulated redis outage")


@pytest.mark.asyncio
async def test_fail_open_falls_back_to_in_memory_when_redis_is_unreachable():
    backend = RedisBackend(_fake_client(), fail_open=True)
    backend._script = _AlwaysBrokenScript()

    await backend.check("user-1", 1)  # falls back to in-memory, allowed
    with pytest.raises(RateLimitExceededError):
        await backend.check("user-1", 1)  # in-memory fallback now over budget too


@pytest.mark.asyncio
async def test_fail_closed_rejects_when_redis_is_unreachable():
    """The auth limiter's policy: an unreachable Redis must not silently remove
    rate limiting on a security-sensitive endpoint."""
    backend = RedisBackend(_fake_client(), fail_open=False)
    backend._script = _AlwaysBrokenScript()

    with pytest.raises(RateLimitExceededError):
        await backend.check("user-1", 1000)  # limit is irrelevant - it fails closed


def test_build_backend_defaults_to_in_memory():
    settings = Settings(rate_limit_backend="memory")
    backend = _build_backend(settings, fail_open=True)
    assert isinstance(backend, InMemoryBackend)


def test_build_backend_selects_redis_when_configured(monkeypatch):
    settings = Settings(rate_limit_backend="redis", redis_url="redis://example.invalid:6379/0")

    class _FakeRedisAsyncioModule:
        @staticmethod
        def from_url(url):
            assert url == "redis://example.invalid:6379/0"
            return _fake_client()

    monkeypatch.setitem(sys.modules, "redis.asyncio", _FakeRedisAsyncioModule())

    backend = _build_backend(settings, fail_open=True)
    assert isinstance(backend, RedisBackend)


def test_build_redis_backend_raises_a_clear_error_when_the_redis_extra_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "redis.asyncio", None)  # forces ImportError on import
    settings = Settings(rate_limit_backend="redis")

    with pytest.raises(RuntimeError, match="redis.*extra"):
        _build_redis_backend(settings, fail_open=True)
