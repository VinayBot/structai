from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.builder import SchemaDef


class ExpectedCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    equals: str | None = None
    contains: str | None = None
    one_of: list[str] | None = None


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    prompt: str
    schema_def: SchemaDef
    tier: Literal["fast", "smart"] = "fast"
    checks: list[ExpectedCheck] = []


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    passed: bool
    reason: str | None = None
    provider: str | None = None
    model: str | None = None
    attempts: int | None = None
    latency_ms: float
    data: dict | None = None
    trace_id: str | None = None


class CategorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    passed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: str
    finished_at: str
    concurrency: int
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    avg_attempts: float
    by_category: dict[str, CategorySummary]
    results: list[CaseResult]
