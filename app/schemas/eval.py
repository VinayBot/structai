from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.builder import SchemaDef
from eval.schemas import CategorySummary


class EvalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_ids: list[str] | None = None
    provider: Literal["gateway", "ollama", "groq"] = "gateway"
    concurrency: int = Field(default=5, ge=1, le=20)


class EvalRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    model: str | None
    tier: str
    source: Literal["api", "imported"]
    created_at: datetime
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    avg_attempts: float


class EvalCaseResultOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    prompt: str
    schema_def: SchemaDef
    passed: bool
    reason: str | None
    provider: str | None
    model: str | None
    attempts: int | None
    latency_ms: float
    data: dict | None
    trace_id: str | None


class EvalRunDetail(EvalRunSummary):
    by_category: dict[str, CategorySummary]
    results: list[EvalCaseResultOut]


class EvalLeaderboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None
    runs: int
    avg_pass_rate: float
    avg_latency_ms: float


class EvalDeltas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_rate_delta: float
    avg_latency_ms_delta: float
    p95_latency_ms_delta: float


class EvalDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest: EvalRunSummary | None
    history: list[EvalRunSummary]
    leaderboard: list[EvalLeaderboardEntry]
    deltas: EvalDeltas | None
