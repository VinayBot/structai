from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeKind = Literal[
    "client",
    "edge",
    "guardrail",
    "service",
    "gateway",
    "provider",
    "data",
    "observability",
    "mcp",
    "infra",
]

GroupColor = Literal["gold", "purple", "neutral"]

VisualKind = Literal["tile", "engine", "cloud"]

StatusKey = Literal["ollama", "groq", "mcp", "persistence", "backend_runtime"]

NodeState = Literal["healthy", "degraded", "failed", "idle"]

ScenarioId = Literal[
    "happy_path_fast",
    "happy_path_smart",
    "ollama_down_groq_fallback",
    "validation_retry",
    "all_providers_fail",
    "prompt_injection_blocked",
    "rate_limit_exceeded",
    "mcp_tool_call",
    "no_token",
    "expired_token",
    "bad_schema",
    "email_blocked",
    "pii_redacted",
]

ScenarioBadge = Literal["real_call", "fault_injection"]

StepStatus = Literal["ok", "error", "skipped"]

ConfigValue = str | int | float | bool


class ArchGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    tag: str
    color: GroupColor
    order: int
    row: int
    parent: str | None = None
    is_extra: bool = False


class ArchEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    summary: str
    auth_required: bool
    tags: list[str] = Field(default_factory=list)


class ArchNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    kind: NodeKind
    group: str
    summary: str
    contract: str
    code_path: str
    icon: str
    visual_kind: VisualKind
    guardrails: list[str] = Field(default_factory=list)
    telemetry: str
    status_key: StatusKey | None = None
    tag: str | None = None
    endpoints: list[ArchEndpoint] = Field(default_factory=list)
    trace_spans: list[str] = Field(default_factory=list)
    is_extra: bool = False


class ArchEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    target: str
    label: str
    kind: Literal["sync", "async", "observability", "feedback"]
    contract: str


class ScenarioInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ScenarioId
    label: str
    description: str
    expected_http_status: int | None = None
    expected_error_code: str | None = None
    primary: bool = False
    is_extra: bool = False


class GraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[ArchNode]
    edges: list[ArchEdge]
    groups: list[ArchGroup]
    scenarios: list[ScenarioInfo]


class ProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    available: bool
    latency_ms: float | None
    detail: str
    models: list[str] = Field(default_factory=list)


class NodeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    state: NodeState
    last_latency_ms: float | None = None
    last_error: str | None = None
    last_checked_at: str | None = None
    config: dict[str, ConfigValue] = Field(default_factory=dict)


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ollama: ProviderStatus
    groq: ProviderStatus
    mcp: ProviderStatus
    checked_at: str
    nodes: dict[str, NodeStatus] = Field(default_factory=dict)


class TestRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: ScenarioId


class ScenarioStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    edge_id: str | None
    label: str
    status: StepStatus
    detail: str
    duration_ms: float
    http_status: int | None = None
    error_code: str | None = None
    request: dict | None = None
    response: dict | None = None


class AssertionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    expected: str
    actual: str
    passed: bool


class ContractCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class TestRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: ScenarioId
    label: str
    passed: bool
    summary: str
    steps: list[ScenarioStep]
    total_duration_ms: float
    badge: ScenarioBadge
    assertions: list[AssertionResult] = Field(default_factory=list)
    contract: ContractCheckResult
