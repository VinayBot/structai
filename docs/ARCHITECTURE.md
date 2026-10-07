# Architecture

This diagram and the tables below are generated directly from the same graph data the `/arch/graph` endpoint returns and the Architecture tab in the app renders - run `python scripts/gen_architecture_doc.py` after changing `app/services/arch_service.py` to keep this file in sync.

```mermaid
flowchart LR
  subgraph containerization_ci["Containerization & CI"]
    docker["Dockerfile"]
    compose["docker-compose"]
    ci["GitHub Actions CI"]
  end
  subgraph client_apps["Client Apps"]
    client["React app"]
    chatbot_ui["StructAI Chatbot"]
  end
  subgraph databases["Databases"]
    persistence["SQLite (SQLAlchemy)"]
  end
  subgraph backend_runtime_group["Backend Runtime"]
    backend_runtime["FastAPI Backend"]
    request_id["Request-ID"]
  end
  subgraph security_guardrails["Security & Guardrails"]
    email_guardrail["Email Guardrail"]
    jwt_auth["JWT Auth"]
    rate_limiter["Rate Limiter & Quota"]
    injection_screen["Injection Screen"]
    pii_redaction["PII Redaction"]
    request_validation["Pydantic Request Validation"]
  end
  subgraph file_storage_group["File Storage"]
    file_storage["File Storage"]
  end
  subgraph structai_core["StructAI Core"]
    validator_retry["Validator + Retry Loop"]
    output_guardrails["Output Guardrails"]
    schema_builder["Schema builder"]
    mcp_server["MCP server"]
  end
  subgraph multi_cloud_group["Multi-Cloud"]
    multi_cloud["Multi-Cloud"]
  end
  subgraph gateway_group["Gateway"]
    router["Router (tiers/fallback)"]
    concurrency_queue["Concurrency Queue"]
    circuit_breaker["Circuit Breaker"]
  end
  subgraph observability_evaluation["Observability & Evaluation"]
    tracing["Tracing"]
    metrics["Metrics"]
    logs["Logs"]
    evaluation["Evaluation"]
  end
  subgraph open_models["Open Models"]
    ollama["Ollama"]
    groq["Groq"]
  end
  client -->|HTTPS request| request_id
  request_id -->|request_id stamped| jwt_auth
  client -->|POST /api/v1/auth/register| email_guardrail
  jwt_auth -->|authenticated user| rate_limiter
  jwt_auth -->|authenticated, no rate limit on this route| request_validation
  rate_limiter -->|within budget| injection_screen
  injection_screen -->|not blocked| pii_redaction
  pii_redaction -->|redacted prompt| request_validation
  request_validation -->|validated SchemaDef| schema_builder
  schema_builder -->|compiled model| validator_retry
  validator_retry -->|generate(tier, system, prompt)| router
  router -->|candidate 1 (fast/smart)| ollama
  router -->|candidate 2 (fallback)| groq
  ollama -->|raw reply| output_guardrails
  groq -->|raw reply| output_guardrails
  output_guardrails -.->|chat message row| persistence
  output_guardrails -.->|[obs] span: structured.loop / gateway.generate| tracing
  router -.->|[obs] gateway_calls_total| metrics
  request_id -.->|[obs] structured JSON log line| logs
  evaluation -->|direct in-process call| validator_retry
  validator_retry -.->|[feedback] retry with corrective feedback| router
  validator_retry -.->|[feedback] attempts exhausted -> error response| client
  jwt_auth -->|file request (upload/list/get/delete/content)| file_storage
  mcp_server -->|same screen as HTTP| injection_screen
```

## Groups

### Containerization & CI

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `docker` | Dockerfile | infra | Multi-stage Dockerfile for the API image - not itself part of the request path, just how the backend ships. | `Dockerfile` |
| `compose` | docker-compose | infra | docker-compose.yml wires the API container with its local dependencies for `make up` / `make down` - development/deployment tooling, not a runtime dependency of any request. | `docker-compose.yml` |
| `ci` | GitHub Actions CI | infra | GitHub Actions workflow that lints, type-checks, and runs the test suite on push/PR - runs in GitHub's infrastructure, never in this process. | `.github/workflows/ci.yml` |

### Client Apps

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `client` | React app | client | Vite + React 19 SPA. Holds JWTs in localStorage, drives every call below. | `frontend/src/lib/api.ts` |
| `chatbot_ui` | StructAI Chatbot | client | The chat page itself (frontend/src/pages/ChatPage.tsx) - the client app's primary surface for the structured-answer loop below. | `frontend/src/pages/ChatPage.tsx` |

### Databases

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `persistence` | SQLite (SQLAlchemy) | data | Users, projects, chats, messages, and file metadata. Alembic-migrated. | `app/models/*.py, app/db.py` |

### Backend Runtime

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `backend_runtime` | FastAPI Backend | infra | The running FastAPI process (app/main.py) that every request below actually executes inside - its own liveness is what GET /health and GET /ready report. | `app/main.py` |
| `request_id` | Request-ID | edge | Stamps (or honors an incoming X-Request-Id) every request before anything else runs, so logs/traces/errors can all be correlated. | `app/core/middleware.py::request_id_middleware` |

### Security & Guardrails

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `email_guardrail` | Email Guardrail | guardrail | Four checks before an account is ever created: RFC syntax (email-validator), a disposable-domain blocklist (built-in list merged with an optional file-configurable extra list), typo detection against popular free-mail providers (Damerau-Levenshtein distance or a mangled TLD, with a safe-list for real look-alikes) that returns a corrected-address suggestion instead of a bare rejection, and an MX/A reachability lookup that hard-blocks a confirmed-nonexistent domain but fails open (warns, doesn't block) on a timeout or resolver error. The same check backs a dedicated POST /api/v1/auth/check-email endpoint so the frontend can validate-on-blur before submit. | `app/guardrails/email.py::check_email` |
| `jwt_auth` | JWT Auth | edge | Verifies the bearer access token's signature, type, and expiry, then loads the active user. Every route except auth/health/metrics depends on this. | `app/core/deps.py::get_current_user, app/core/security.py` |
| `rate_limiter` | Rate Limiter & Quota | edge | Sliding per-minute rate limit plus a daily quota (per user) on the two model-calling endpoints. | `app/core/deps.py::enforce_rate_limit, enforce_daily_quota, app/guardrails/rate_limit.py, app/services/quota_service.py` |
| `injection_screen` | Injection Screen | guardrail | Pattern-screens the prompt for jailbreak/injection attempts before it reaches PII redaction or any model - checked first, so a blocked prompt is never even redacted or logged. Shared by /api/v1/structured/answer and /api/v1/structured/answer/stream via the same guard_prompt() helper. | `app/guardrails/injection.py, app/guardrails/prompt_guard.py` |
| `pii_redaction` | PII Redaction | guardrail | Strips emails, SSNs, Luhn-checked card numbers, Verhoeff-checked Aadhaar numbers, PAN, Indian/international phone numbers, and labeled IFSC/bank account/passport numbers from the prompt before it is sent to any model, logged, or persisted. PII_MODE=block refuses the request instead of redacting it. Applied to both /api/v1/structured/answer and /api/v1/structured/answer/stream via the shared guard_prompt() helper. | `app/guardrails/pii.py` |
| `request_validation` | Pydantic Request Validation | guardrail | Every request body is a Pydantic v2 model with extra='forbid' - unknown fields, wrong types, or failed field validators reject the request before any handler code runs. | `app/schemas/*.py (model_config = {'extra': 'forbid'})` |

### File Storage

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `file_storage` | File Storage | data | Saves uploaded files to disk under a per-user directory and serves them back by id - the real backing store behind every /api/v1/files route. | `app/services/file_service.py::save_file` |

### StructAI Core

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `validator_retry` | Validator + Retry Loop | service | Calls the gateway, parses the reply as JSON, and validates it against the compiled schema. On failure, retries with corrective feedback up to max_attempts before giving up. | `app/services/structured_service.py::run_structured_loop` |
| `output_guardrails` | Output Guardrails | guardrail | The deterministic guarantee: the model's raw reply is parsed as JSON and re-validated against the user's own compiled schema before it's ever returned. | `app/services/structured_service.py::_extract_json` |
| `schema_builder` | Schema builder | guardrail | Turns a user-supplied field list into a real pydantic.create_model(...) class through a fixed type table - the schema is data, never executed as code. | `app/schemas/builder.py` |
| `mcp_server` | MCP server | mcp | A second transport onto the same services, for Claude Desktop/Code or any MCP client - no business logic duplicated, same guardrails/quota apply. | `app/mcp/server.py` |

### Multi-Cloud

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `multi_cloud` | Multi-Cloud | infra | Illustrative only: nothing in this codebase is tied to a specific cloud vendor - the stack (FastAPI + SQLite/Postgres + Docker) runs unmodified on any of them. Not a real dependency and has no edges of its own. | `n/a (illustrative node, no corresponding module)` |

### Gateway

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `router` | Router (tiers/fallback) | gateway | Tries each tier's candidates in order, skipping any provider whose circuit is open, and falls through to the next candidate on failure. | `app/gateway/router.py::ModelGateway.generate` |
| `concurrency_queue` | Concurrency Queue | gateway | A per-provider asyncio.Semaphore caps how many in-flight calls one provider can have at once, so one slow candidate can't starve the others. | `app/gateway/router.py::ModelGateway._semaphore_for` |
| `circuit_breaker` | Circuit Breaker | gateway | Opens a provider's circuit after consecutive failures and skips it for a cooldown window, instead of retrying a provider that's clearly down. | `app/gateway/router.py::CircuitBreaker` |

### Observability & Evaluation

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `tracing` | Tracing | observability | In-process span recorder; the Traces tab reads its ring buffer. | `app/core/tracing.py` |
| `metrics` | Metrics | observability | Prometheus counters/histograms for requests and gateway calls. | `app/core/metrics.py` |
| `logs` | Logs | observability | Every log line is one JSON object tagged with the request's request_id - no raw prompts or secrets are ever logged. | `app/core/logging.py` |
| `evaluation` | Evaluation | service | Runs the golden-case harness against a chosen provider by calling structured_service.answer(...) directly - bypassing HTTP auth/guardrails, since it's an internal tool, not a user-facing path. | `eval/runner.py, app/routes/eval.py` |

### Open Models

| Node | Label | Kind | Summary | Code |
|---|---|---|---|---|
| `ollama` | Ollama | provider | Local model server, OLLAMA_BASE_URL (default http://localhost:11434). | `app/gateway/providers/ollama.py` |
| `groq` | Groq | provider | Free-tier hosted inference API, used as the fallback candidate. | `app/gateway/providers/groq.py` |

## Edges

| Flow | Kind | Label | Contract |
|---|---|---|---|
| `client` → `request_id` | sync | HTTPS request | any method/path |
| `request_id` → `jwt_auth` | sync | request_id stamped | X-Request-Id echoed on response |
| `client` → `email_guardrail` | sync | POST /api/v1/auth/register | RegisterRequest(email, password) -> blocklist check before account creation |
| `jwt_auth` → `rate_limiter` | sync | authenticated user | User |
| `jwt_auth` → `request_validation` | sync | authenticated, no rate limit on this route | User |
| `rate_limiter` → `injection_screen` | sync | within budget | str prompt, pre-screen |
| `injection_screen` → `pii_redaction` | sync | not blocked | str prompt |
| `pii_redaction` → `request_validation` | sync | redacted prompt | (clean_prompt: str, fields: list[FieldDef]) |
| `request_validation` → `schema_builder` | sync | validated SchemaDef | SchemaDef(fields=[FieldDef(...)]) |
| `schema_builder` → `validator_retry` | sync | compiled model | type[BaseModel] |
| `validator_retry` → `router` | sync | generate(tier, system, prompt) | (tier: str, system: str, prompt: str, timeout: float) |
| `router` → `ollama` | sync | candidate 1 (fast/smart) | POST /api/chat |
| `router` → `groq` | sync | candidate 2 (fallback) | POST /chat/completions |
| `ollama` → `output_guardrails` | sync | raw reply | str |
| `groq` → `output_guardrails` | sync | raw reply | str |
| `output_guardrails` → `persistence` | async | chat message row | Message(role, content, structured_data, provider, model) |
| `output_guardrails` → `tracing` | observability | span: structured.loop / gateway.generate | Span(name, attributes, duration_ms, status) |
| `router` → `metrics` | observability | gateway_calls_total | Counter{provider, model, outcome} |
| `request_id` → `logs` | observability | structured JSON log line | {"level","logger","message","request_id"} |
| `evaluation` → `validator_retry` | sync | direct in-process call | structured_service.answer(gateway, prompt, schema, tier) |
| `validator_retry` → `router` | feedback | retry with corrective feedback | invalid JSON/shape -> same prompt + feedback, attempt+1 |
| `validator_retry` → `client` | feedback | attempts exhausted -> error response | 502 generation_failed |
| `jwt_auth` → `file_storage` | sync | file request (upload/list/get/delete/content) | (user_id, file_id?, upload?) -> stored path / metadata |
| `mcp_server` → `injection_screen` | sync | same screen as HTTP | _guard_prompt(prompt) -> str |

## Test scenarios

The Architecture tab's scenario runner drives each of these through the real `structured_service` / guardrail code paths via `POST /arch/test-run`.

| Scenario | Description |
|---|---|
| Valid request | Ollama answers correctly on the first attempt. |
| No token | A protected endpoint is called with no Authorization header at all. |
| Expired token | A real access token is minted with a negative expiry and rejected on decode. |
| Bad schema | A field name that isn't a valid identifier fails Pydantic validation. |
| Injection | A jailbreak-style prompt is rejected before it reaches any model. |
| Rate limit | A second request within the per-minute budget is rejected. |
| Email blocked | Registration with a known disposable-email domain (e.g. mailinator.com) is rejected before an account is ever created. |
| Force Groq fallback | The first candidate fails; the gateway falls through to Groq. |
| Force invalid output | The model's first reply doesn't validate; a corrective retry succeeds. |
| Happy path (smart tier) | Smart tier, multi-field schema, first attempt succeeds. |
| All providers fail | Every candidate errors; the loop raises instead of hanging or guessing. |
| MCP tool call | The same request path, entered from the MCP server instead of HTTP. |
| PII redacted | A prompt containing an email address is redacted before the model ever sees it - asserts the scripted provider's captured input shows [REDACTED_EMAIL], not the raw address. |
