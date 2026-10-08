import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.logging import request_id_ctx
from app.core.otel import export_span

_current_span_id: ContextVar[str | None] = ContextVar("current_span_id", default=None)


@dataclass
class Span:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    status: str = "ok"
    error: str | None = None
    attributes: dict = field(default_factory=dict)


class Tracer:
    def __init__(self, *, max_spans: int = 500, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._spans: deque[Span] = deque(maxlen=max_spans)

    @asynccontextmanager
    async def start_span(self, name: str, **attributes) -> AsyncIterator[Span]:
        trace_id = request_id_ctx.get()
        if trace_id == "-":
            trace_id = uuid.uuid4().hex[:16]
        parent_span_id = _current_span_id.get()

        span = Span(
            span_id=uuid.uuid4().hex[:16],
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            start_time=self._clock(),
            attributes=dict(attributes),
        )
        _current_span_id.set(span.span_id)
        try:
            yield span
            span.status = "ok"
        except Exception as exc:
            span.status = "error"
            span.error = str(exc)
            raise
        finally:
            _current_span_id.set(parent_span_id)
            span.end_time = self._clock()
            span.duration_ms = (span.end_time - span.start_time) * 1000
            self._spans.append(span)
            export_span(span)

    def recent(self, limit: int = 100) -> list[Span]:
        spans = list(self._spans)[-limit:]
        spans.reverse()
        return spans


@lru_cache
def get_tracer() -> Tracer:
    return Tracer()


def reset_tracer_cache() -> None:
    get_tracer.cache_clear()
