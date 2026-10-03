from pydantic import BaseModel, ConfigDict, Field


class EndpointStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    count: int
    error_count: int
    p50_ms: float
    p95_ms: float


class StatusBucket(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    twoxx: int = Field(alias="2xx")
    fourxx: int = Field(alias="4xx")
    fivexx: int = Field(alias="5xx")
    by_code: dict[str, int]


class GuardrailStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    injection_blocks: int
    pii_redactions: int
    rate_limit_hits: int
    email_blocks: int


class ProviderStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    calls: int
    failures: int
    fallbacks: int
    avg_latency_ms: float


class StructuredStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempts_histogram: dict[str, int]
    retry_rate: float
    first_try_valid_pct: float


class TimeseriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minute: str
    requests: int
    errors: int


class MetricsTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: int
    errors: int
    error_rate: float
    client_errors: int
    p50_ms: float
    p95_ms: float


class FailedRunStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    by_reason: dict[str, int]


class MetricsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    generated_at: str
    totals: MetricsTotals
    by_endpoint: list[EndpointStat]
    by_status: StatusBucket
    guardrails: GuardrailStats
    providers: list[ProviderStat]
    structured: StructuredStats
    failed_runs: FailedRunStats
    timeseries: list[TimeseriesPoint]
