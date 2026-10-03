import pytest

from app.core.tracing import Tracer


def make_clock():
    state = {"now": 0.0}

    def clock() -> float:
        state["now"] += 1.0
        return state["now"]

    return clock


@pytest.mark.asyncio
async def test_span_records_duration_and_attributes():
    tracer = Tracer(clock=make_clock())

    async with tracer.start_span("do_thing", foo="bar") as span:
        span.attributes["extra"] = "value"

    recorded = tracer.recent()
    assert len(recorded) == 1
    assert recorded[0].name == "do_thing"
    assert recorded[0].status == "ok"
    assert recorded[0].attributes == {"foo": "bar", "extra": "value"}
    assert recorded[0].duration_ms == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_span_records_error_status_and_reraises():
    tracer = Tracer(clock=make_clock())

    with pytest.raises(ValueError):
        async with tracer.start_span("do_thing"):
            raise ValueError("boom")

    recorded = tracer.recent()
    assert recorded[0].status == "error"
    assert recorded[0].error == "boom"


@pytest.mark.asyncio
async def test_nested_spans_track_parent():
    tracer = Tracer(clock=make_clock())

    async with tracer.start_span("outer") as outer:
        async with tracer.start_span("inner"):
            pass

    recorded = {s.name: s for s in tracer.recent()}
    assert recorded["inner"].parent_span_id == outer.span_id
    assert recorded["outer"].parent_span_id is None


@pytest.mark.asyncio
async def test_recent_respects_limit_and_ring_buffer_cap():
    tracer = Tracer(max_spans=2, clock=make_clock())

    for i in range(5):
        async with tracer.start_span(f"span-{i}"):
            pass

    recorded = tracer.recent()
    assert len(recorded) == 2
    assert [s.name for s in recorded] == ["span-4", "span-3"]


@pytest.mark.asyncio
async def test_recent_limit_parameter():
    tracer = Tracer(clock=make_clock())

    for i in range(3):
        async with tracer.start_span(f"span-{i}"):
            pass

    recorded = tracer.recent(limit=1)
    assert len(recorded) == 1
    assert recorded[0].name == "span-2"
