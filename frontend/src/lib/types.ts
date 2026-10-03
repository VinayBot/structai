export type FieldType = 'string' | 'integer' | 'number' | 'boolean' | 'string_list' | 'integer_list'

export const FIELD_TYPES: FieldType[] = [
  'string',
  'integer',
  'number',
  'boolean',
  'string_list',
  'integer_list',
]

export interface FieldDef {
  name: string
  type: FieldType
  description: string
  required: boolean
}

export interface SchemaDef {
  fields: FieldDef[]
}

export interface SchemaValidateResponse {
  valid: boolean
  json_schema: Record<string, unknown>
}

export type Tier = 'fast' | 'smart'

export interface StructuredAnswerRequest {
  prompt: string
  schema_def: SchemaDef
  tier: Tier
}

export interface PiiMeta {
  found: boolean
  categories: string[]
  counts: Record<string, number>
}

export interface GuardrailsMeta {
  pii: PiiMeta
}

export interface StructuredAnswerResponse {
  data: Record<string, unknown>
  provider: string
  model: string
  attempts: number
  meta: GuardrailsMeta
}

export type StreamStage =
  | 'generating'
  | 'validating'
  | 'retrying'
  | 'output_leak'
  | 'output_pii'
  | 'done'
  | 'error'

export interface StreamEvent {
  stage: StreamStage
  attempt: number
  detail?: string
  data?: Record<string, unknown>
  provider?: string
  model?: string
  attempts?: number
  meta?: GuardrailsMeta
}

export interface User {
  id: string
  email: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface Project {
  id: string
  name: string
  created_at: string
}

export interface Chat {
  id: string
  title: string
  project_id: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  chat_id: string
  role: 'user' | 'assistant'
  content: string
  structured_data: Record<string, unknown> | null
  provider: string | null
  model: string | null
  created_at: string
}

export interface ChatDetail extends Chat {
  messages: Message[]
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    request_id: string | null
    retry_after_seconds?: number | null
    suggestion?: string | null
  }
}

export interface EmailCheckResponse {
  valid: boolean
  message: string | null
  suggestion: string | null
  warning: string | null
}

export interface Span {
  span_id: string
  trace_id: string
  parent_span_id: string | null
  name: string
  start_time: number
  duration_ms: number | null
  status: string
  error: string | null
  attributes: Record<string, unknown>
}

export interface ExpectedCheck {
  field: string
  equals?: string | null
  contains?: string | null
  one_of?: string[] | null
}

export interface GoldenCase {
  id: string
  category: string
  prompt: string
  schema_def: SchemaDef
  tier: Tier
  checks: ExpectedCheck[]
}

export interface CaseResult {
  case_id: string
  category: string
  passed: boolean
  reason: string | null
  provider: string | null
  model: string | null
  attempts: number | null
  latency_ms: number
  data: Record<string, unknown> | null
  trace_id: string | null
}

export interface CategorySummary {
  total: number
  passed: number
}

export interface EvalReport {
  started_at: string
  finished_at: string
  concurrency: number
  total: number
  passed: number
  failed: number
  pass_rate: number
  avg_latency_ms: number
  p95_latency_ms: number
  avg_attempts: number
  by_category: Record<string, CategorySummary>
  results: CaseResult[]
}

export type EvalProvider = 'gateway' | 'ollama' | 'groq'

export interface EvalRunRequest {
  case_ids?: string[] | null
  provider?: EvalProvider
  concurrency?: number
}

export type EvalStreamEvent =
  | { stage: 'case_done'; result: CaseResult }
  | { stage: 'done'; report: EvalReport | null }

export interface EvalRunSummary {
  id: string
  provider: string
  model: string | null
  tier: string
  source: 'api' | 'imported'
  created_at: string
  total: number
  passed: number
  failed: number
  pass_rate: number
  avg_latency_ms: number
  p95_latency_ms: number
  avg_attempts: number
}

export interface EvalCaseResultOut {
  case_id: string
  category: string
  prompt: string
  schema_def: SchemaDef
  passed: boolean
  reason: string | null
  provider: string | null
  model: string | null
  attempts: number | null
  latency_ms: number
  data: Record<string, unknown> | null
  trace_id: string | null
}

export interface EvalRunDetail extends EvalRunSummary {
  by_category: Record<string, CategorySummary>
  results: EvalCaseResultOut[]
}

export interface EvalLeaderboardEntry {
  provider: string
  model: string | null
  runs: number
  avg_pass_rate: number
  avg_latency_ms: number
}

export interface EvalDeltas {
  pass_rate_delta: number
  avg_latency_ms_delta: number
  p95_latency_ms_delta: number
}

export interface EvalDashboardResponse {
  latest: EvalRunSummary | null
  history: EvalRunSummary[]
  leaderboard: EvalLeaderboardEntry[]
  deltas: EvalDeltas | null
}

export interface FileAttachment {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  chat_id: string | null
  created_at: string
}

export type ArchNodeKind =
  | 'client'
  | 'edge'
  | 'guardrail'
  | 'service'
  | 'gateway'
  | 'provider'
  | 'data'
  | 'observability'
  | 'mcp'
  | 'infra'

export type ArchVisualKind = 'tile' | 'engine' | 'cloud'

export type ArchGroupColor = 'gold' | 'purple' | 'neutral'

export type ArchStatusKey = 'ollama' | 'groq' | 'mcp' | 'persistence' | 'backend_runtime'

export type ArchNodeState = 'healthy' | 'degraded' | 'failed' | 'idle'

export type ArchScenarioId =
  | 'happy_path_fast'
  | 'happy_path_smart'
  | 'ollama_down_groq_fallback'
  | 'validation_retry'
  | 'all_providers_fail'
  | 'prompt_injection_blocked'
  | 'rate_limit_exceeded'
  | 'mcp_tool_call'
  | 'no_token'
  | 'expired_token'
  | 'bad_schema'
  | 'email_blocked'
  | 'pii_redacted'

export type ArchScenarioBadge = 'real_call' | 'fault_injection'

export type ArchStepStatus = 'ok' | 'error' | 'skipped'

export type ArchConfigValue = string | number | boolean

export interface ArchGroup {
  id: string
  label: string
  tag: string
  color: ArchGroupColor
  order: number
  row: number
  parent: string | null
  is_extra: boolean
}

export interface ArchEndpoint {
  method: string
  path: string
  summary: string
  auth_required: boolean
  tags: string[]
}

export interface ArchNode {
  id: string
  label: string
  kind: ArchNodeKind
  group: string
  summary: string
  contract: string
  code_path: string
  icon: string
  visual_kind: ArchVisualKind
  guardrails: string[]
  telemetry: string
  status_key: ArchStatusKey | null
  tag: string | null
  endpoints: ArchEndpoint[]
  trace_spans: string[]
  is_extra: boolean
}

export interface ArchEdge {
  id: string
  source: string
  target: string
  label: string
  kind: 'sync' | 'async' | 'observability' | 'feedback'
  contract: string
}

export interface ArchScenarioInfo {
  id: ArchScenarioId
  label: string
  description: string
  expected_http_status: number | null
  expected_error_code: string | null
  primary: boolean
  is_extra: boolean
}

export interface ArchGraphResponse {
  nodes: ArchNode[]
  edges: ArchEdge[]
  groups: ArchGroup[]
  scenarios: ArchScenarioInfo[]
}

export interface ArchProviderStatus {
  name: string
  available: boolean
  latency_ms: number | null
  detail: string
  models: string[]
}

export interface ArchNodeStatus {
  node_id: string
  state: ArchNodeState
  last_latency_ms: number | null
  last_error: string | null
  last_checked_at: string | null
  config: Record<string, ArchConfigValue>
}

export interface ArchStatusResponse {
  ollama: ArchProviderStatus
  groq: ArchProviderStatus
  mcp: ArchProviderStatus
  checked_at: string
  nodes: Record<string, ArchNodeStatus>
}

export interface ArchTestRunRequest {
  scenario_id: ArchScenarioId
}

export interface ArchScenarioStep {
  node_id: string
  edge_id: string | null
  label: string
  status: ArchStepStatus
  detail: string
  duration_ms: number
  http_status: number | null
  error_code: string | null
  request: Record<string, unknown> | null
  response: Record<string, unknown> | null
}

export interface ArchAssertionResult {
  name: string
  expected: string
  actual: string
  passed: boolean
}

export interface ArchContractCheckResult {
  valid: boolean
  errors: string[]
}

export interface OpenApiOperation {
  summary?: string
  requestBody?: { content?: Record<string, { schema?: unknown }> }
  responses?: Record<string, { description?: string; content?: Record<string, { schema?: unknown }> }>
}

export interface OpenApiDoc {
  paths: Record<string, Record<string, OpenApiOperation>>
  components?: { schemas?: Record<string, unknown> }
}

export interface ArchTestRunResponse {
  scenario_id: ArchScenarioId
  label: string
  passed: boolean
  summary: string
  steps: ArchScenarioStep[]
  total_duration_ms: number
  badge: ArchScenarioBadge
  assertions: ArchAssertionResult[]
  contract: ArchContractCheckResult
}

export interface UsageResponse {
  user_count_today: number
  user_limit: number
}

export interface HealthResponse {
  status: string
  git_commit: string
  build_time: string
}

export interface MetricsTotals {
  requests: number
  errors: number
  error_rate: number
  client_errors: number
  p50_ms: number
  p95_ms: number
}

export interface EndpointStat {
  method: string
  path: string
  count: number
  error_count: number
  p50_ms: number
  p95_ms: number
}

export interface StatusBucket {
  '2xx': number
  '4xx': number
  '5xx': number
  by_code: Record<string, number>
}

export interface GuardrailStats {
  injection_blocks: number
  pii_redactions: number
  rate_limit_hits: number
  email_blocks: number
}

export interface ProviderStat {
  provider: string
  model: string
  calls: number
  failures: number
  fallbacks: number
  avg_latency_ms: number
}

export interface StructuredStats {
  attempts_histogram: Record<string, number>
  retry_rate: number
  first_try_valid_pct: number
}

export interface TimeseriesPoint {
  minute: string
  requests: number
  errors: number
}

export interface FailedRunStats {
  total: number
  by_reason: Record<string, number>
}

export interface MetricsSummaryResponse {
  generated_at: string
  totals: MetricsTotals
  by_endpoint: EndpointStat[]
  by_status: StatusBucket
  guardrails: GuardrailStats
  providers: ProviderStat[]
  structured: StructuredStats
  failed_runs: FailedRunStats
  timeseries: TimeseriesPoint[]
}

export type ArchLiveRunProvider = 'ollama' | 'groq' | 'auto'

export type ArchLiveRunStatus = 'running' | 'passed' | 'failed' | 'skipped' | 'modified'

export type ArchPiiMode = 'redact' | 'block'

export interface ArchLiveRunRequest {
  prompt: string
  schema_def: SchemaDef
  tier: Tier
  provider: ArchLiveRunProvider
  model?: string | null
  strict_provider: boolean
  pii_mode?: ArchPiiMode | null
}

export interface ArchLiveRunEvent {
  node_id: string
  status: ArchLiveRunStatus
  latency_ms: number | null
  input_summary: string | null
  output_summary: string | null
  http_status: number | null
  error_code: string | null
  retry_after_seconds: number | null
  trace_id: string | null
  span_id: string | null
  data: Record<string, unknown> | null
  provider: string | null
  model: string | null
  attempts: number | null
  edge_ids: string[]
}
