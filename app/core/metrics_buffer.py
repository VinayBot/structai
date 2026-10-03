from collections import deque
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class RequestRecord:
    ts: float
    method: str
    path: str
    status_code: int
    duration_ms: float


class RequestRingBuffer:
    def __init__(self, maxlen: int = 5000):
        self._records: deque[RequestRecord] = deque(maxlen=maxlen)

    def record(self, record: RequestRecord) -> None:
        self._records.append(record)

    def recent(self, since_ts: float | None = None) -> list[RequestRecord]:
        if since_ts is None:
            return list(self._records)
        return [r for r in self._records if r.ts >= since_ts]


@lru_cache
def get_request_buffer() -> RequestRingBuffer:
    return RequestRingBuffer()


def reset_request_buffer_cache() -> None:
    get_request_buffer.cache_clear()
