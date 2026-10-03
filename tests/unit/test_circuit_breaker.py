from app.gateway.router import CircuitBreaker


def make_clock():
    state = {"now": 0.0}

    def clock() -> float:
        return state["now"]

    def advance(seconds: float) -> None:
        state["now"] += seconds

    return clock, advance


def test_circuit_closed_initially():
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)
    assert breaker.is_open("p") is False


def test_circuit_opens_after_threshold():
    clock, _ = make_clock()
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30, clock=clock)

    breaker.record_failure("p")
    breaker.record_failure("p")
    assert breaker.is_open("p") is False

    breaker.record_failure("p")
    assert breaker.is_open("p") is True


def test_circuit_closes_after_cooldown():
    clock, advance = make_clock()
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10, clock=clock)

    breaker.record_failure("p")
    assert breaker.is_open("p") is True

    advance(10.01)
    assert breaker.is_open("p") is False


def test_success_resets_failure_count():
    clock, _ = make_clock()
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=30, clock=clock)

    breaker.record_failure("p")
    breaker.record_success("p")
    breaker.record_failure("p")
    assert breaker.is_open("p") is False
