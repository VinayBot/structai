from pydantic import BaseModel, ConfigDict


class SpanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    start_time: float
    duration_ms: float | None
    status: str
    error: str | None
    attributes: dict
