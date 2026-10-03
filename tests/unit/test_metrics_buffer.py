from app.core.metrics_buffer import RequestRecord, RequestRingBuffer


def _record(ts: float, path: str = "/health") -> RequestRecord:
    return RequestRecord(ts=ts, method="GET", path=path, status_code=200, duration_ms=1.0)


def test_recent_returns_all_records_when_since_ts_omitted():
    buffer = RequestRingBuffer(maxlen=10)
    buffer.record(_record(1.0))
    buffer.record(_record(2.0))

    assert [r.ts for r in buffer.recent()] == [1.0, 2.0]


def test_recent_filters_by_since_ts():
    buffer = RequestRingBuffer(maxlen=10)
    buffer.record(_record(1.0))
    buffer.record(_record(2.0))
    buffer.record(_record(3.0))

    assert [r.ts for r in buffer.recent(since_ts=2.0)] == [2.0, 3.0]


def test_buffer_wraps_at_maxlen():
    buffer = RequestRingBuffer(maxlen=3)
    for i in range(5):
        buffer.record(_record(float(i)))

    assert [r.ts for r in buffer.recent()] == [2.0, 3.0, 4.0]
