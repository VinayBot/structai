from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.builder import SchemaDef

LiveRunProvider = Literal["ollama", "groq", "auto"]

LiveRunStatus = Literal["running", "passed", "modified", "failed", "skipped"]


class LiveRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    schema_def: SchemaDef
    tier: Literal["fast", "smart"] = "fast"
    provider: LiveRunProvider = "auto"
    model: str | None = None
    strict_provider: bool = False
    pii_mode: Literal["redact", "block"] | None = None

    @model_validator(mode="after")
    def _strict_requires_a_specific_provider(self) -> "LiveRunRequest":
        if self.strict_provider and self.provider == "auto":
            raise ValueError(
                "strict_provider requires provider to be 'ollama' or 'groq', not 'auto'"
            )
        return self


class LiveRunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    status: LiveRunStatus
    latency_ms: float | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    retry_after_seconds: float | None = None
    trace_id: str | None = None
    span_id: str | None = None
    data: dict | None = None
    provider: str | None = None
    model: str | None = None
    attempts: int | None = None
    edge_ids: list[str] = Field(default_factory=list)
