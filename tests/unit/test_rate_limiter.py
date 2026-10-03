import pytest

from app.guardrails.rate_limit import RateLimiter, RateLimitExceededError


def test_allows_requests_under_limit():
    limiter = RateLimiter(limit_per_minute=3)
    limiter.check("user-1")
    limiter.check("user-1")
    limiter.check("user-1")


def test_blocks_requests_over_limit():
    limiter = RateLimiter(limit_per_minute=2)
    limiter.check("user-1")
    limiter.check("user-1")
    with pytest.raises(RateLimitExceededError):
        limiter.check("user-1")


def test_keys_are_independent():
    limiter = RateLimiter(limit_per_minute=1)
    limiter.check("user-1")
    limiter.check("user-2")


def test_window_slides_with_injected_clock():
    now = [0.0]
    limiter = RateLimiter(limit_per_minute=1, clock=lambda: now[0])
    limiter.check("user-1")
    with pytest.raises(RateLimitExceededError):
        limiter.check("user-1")

    now[0] += 61.0
    limiter.check("user-1")


def test_exceeded_error_carries_real_retry_after_seconds():
    now = [10.0]
    limiter = RateLimiter(limit_per_minute=1, clock=lambda: now[0])
    limiter.check("user-1")

    now[0] += 25.0
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check("user-1")

    # oldest hit was at t=10, window ages out at t=70, now is t=35 -> 35s left
    assert exc_info.value.retry_after_seconds == pytest.approx(35.0)


def test_retry_after_seconds_shrinks_as_window_ages_out():
    now = [0.0]
    limiter = RateLimiter(limit_per_minute=1, clock=lambda: now[0])
    limiter.check("user-1")

    now[0] = 59.9  # just before the oldest hit ages out of the 60s window
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check("user-1")

    assert 0.0 <= exc_info.value.retry_after_seconds <= 0.11


def test_zero_limit_reports_full_window_with_no_hits_recorded():
    limiter = RateLimiter(limit_per_minute=0)
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check("user-1")

    assert exc_info.value.retry_after_seconds == 60.0
