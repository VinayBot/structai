# API Reference

Base URL: wherever the FastAPI app is served, plus `/api/v1` for every router except health and metrics — those two stay unversioned, since infra probes and Prometheus scrape targets are conventionally outside API versioning. See `app/main.py::create_app()` for the exact `include_router(..., prefix=...)` calls. Routers mount in this order: health, metrics, auth, schemas, structured, projects, chats, files, usage, search, traces, eval, arch, admin.

## Error shape

Every error response — from an `AppError` subclass, a Pydantic validation failure, a Starlette HTTP exception, or an unhandled exception — has this exact shape (`app/core/errors.py`):

```json
{ "error": { "code": "string", "message": "string", "request_id": "string-or-null", "retry_after_seconds": "number-or-null", "suggestion": "string-or-null" } }
```

`request_id` comes from the per-request `request_id_ctx` set in `app/core/middleware.py`. `retry_after_seconds` is only non-null on `rate_limited`. `suggestion` is only non-null on `invalid_email_domain` when the email guardrail detected a likely typo — it carries a corrected address the client can offer the user ("did you mean …?").

### Error codes

| Code | HTTP | Raised by | Meaning |
|---|---|---|---|
| `not_found` | 404 | `NotFoundError` | Resource doesn't exist or isn't owned by the caller |
| `unauthorized` | 401 | `UnauthorizedError` | Missing/invalid/expired token, revoked refresh token, bad credentials, inactive user |
| `conflict` | 409 | `ConflictError` | Duplicate email or disposable email domain |
| `generation_failed` | 502 | `GenerationError` | All providers failed, or the structured-answer retry loop exhausted attempts |
| `guardrail_blocked` | 400 | `GuardrailError` | Prompt matched the injection screen |
| `rate_limited` | 429 | `RateLimitError` | Per-minute rate limit or daily quota (user) exceeded |
| `payload_too_large` | 413 | `PayloadTooLargeError` | Upload/generated file exceeds `max_upload_size_bytes` |
| `unsupported_media_type` | 415 | `UnsupportedMediaTypeError` | Upload `content_type` isn't on `allowed_upload_content_types`, or its bytes don't match that claimed type |
| `forbidden` | 403 | `ForbiddenError` | Authenticated, but `require_admin` rejected a non-admin caller |
| `oauth_failed` | 502 | `OAuthError` | GitHub rejected the authorization code, or its API failed unexpectedly |
| `service_unavailable` | 503 | `ServiceUnavailableError` | GitHub login hit while `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` are unset |
| `invalid_schema` | 400 | explicit in `routes/schemas.py` | User-supplied `SchemaDef` can't compile into a model |
| `invalid_email_domain` | 422 | `InvalidEmailDomainError` | Email guardrail: malformed domain, or a likely typo of a popular provider (`suggestion` populated for typos) |
| `email_domain_unreachable` | 422 | `EmailDomainUnreachableError` | Email guardrail: domain has no MX/A/AAAA record (confirmed can't receive mail) |
| `validation_error` | 422 | Pydantic `RequestValidationError` | Request body/query/path failed validation — also what a grossly malformed email (e.g. `not-an-email`) gets, since `EmailStr` on the request schema rejects it before the email guardrail ever runs |
| `http_error` | varies | Starlette HTTP exception | Unknown route, wrong method, etc. |
| `internal_error` | 500 | catch-all | Unhandled server error |

**Every protected route** uses `Depends(get_current_user)` and can return 401 `unauthorized` on a missing/invalid bearer token; this is omitted per-endpoint below. Likewise, 422 `validation_error` is always possible on a route with a request body and is omitted per-endpoint.

---

## Auth (`/api/v1/auth`)

| Endpoint | Auth | Body | Response | Notes |
|---|---|---|---|---|
| `POST /api/v1/auth/register` | none | `{email, password}` (password: 8–128 chars, ≥1 digit) | `201` `{id, email, role}` (`role` is always `"user"` at registration) | `409 conflict`: disposable email domain or duplicate email; `422 invalid_email_domain`: malformed domain or likely typo (`suggestion` populated); `422 email_domain_unreachable`: domain has no mail-handling DNS record |
| `POST /api/v1/auth/check-email` | none | `{email}` | `200` `{valid, message, suggestion, warning}` | Runs the same email guardrail as `/api/v1/auth/register` but never creates an account — for validate-on-blur in the registration form. `valid: false` means `/api/v1/auth/register` would reject this address; a non-null `warning` with `valid: true` is a non-blocking MX fail-open notice. No rate limit of its own. |
| `POST /api/v1/auth/login` | none | `{email, password}` | `200` `{access_token, refresh_token, token_type}` | `401 unauthorized` on bad credentials/disabled account |
| `POST /api/v1/auth/refresh` | none (refresh token is the credential) | `{refresh_token}` | `200` same token shape | Revokes the presented token's `jti`, issues a fresh pair; `401` if expired/revoked/invalid |
| `POST /api/v1/auth/logout` | none (acts on the token) | `{refresh_token}` | `204` | Revokes the token's `jti` |
| `GET /api/v1/auth/me` | required | — | `200` `{id, email, role}` | |
| `GET /api/v1/auth/github/login?state=` | none | — | `200` `{authorize_url}` | `state` (8–128 chars) is generated and later verified by the *caller* (the frontend round-trips it through GitHub via `sessionStorage`) - this endpoint just builds the URL around it, so the backend stays stateless. `503 service_unavailable` if GitHub OAuth isn't configured. |
| `POST /api/v1/auth/github/callback` | none | `{code}` | `200` `{access_token, refresh_token, token_type}` | Exchanges `code` with GitHub, fetches the profile (falling back to `/user/emails` if the primary address is private), and finds-or-creates a `User`. An existing password account with the same verified email gets GitHub linked to it rather than erroring. `502 oauth_failed` if GitHub rejects the code or its API fails; `503 service_unavailable` if not configured. |

`POST /api/v1/auth/register` does **not** return tokens — call `/api/v1/auth/login` separately to obtain them.

`register`, `login`, `refresh`, and `github/callback` share one `429 rate_limited` budget (`AUTH_RATE_LIMIT_PER_MIN`, default 10/min) keyed by caller IP — brute-forcing a password or hammering the token endpoints from one source gets throttled regardless of which of the four it's spread across. `check-email` and `github/login` take no credential, so neither is covered.

**Setting up GitHub login:** register an OAuth App at [github.com/settings/developers](https://github.com/settings/developers) with callback URL `http://localhost:5173/auth/github/callback` (or your deployed frontend origin + `/auth/github/callback`), then set `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET`/`GITHUB_OAUTH_REDIRECT_URI` in `.env`. The login button degrades to a clear `503` error, not a crash, while unconfigured.

---

## Schemas (`/api/v1/schemas`)

### `POST /api/v1/schemas/validate`
Auth: required.

Body — `SchemaDef`:
```json
{
  "fields": [
    { "name": "city", "type": "string", "description": "City name", "required": true },
    { "name": "population", "type": "integer", "description": "Approx. population", "required": false }
  ]
}
```
`type` is one of `string`, `integer`, `number`, `boolean`, `string_list`, `integer_list`. Field names must be valid identifiers, not starting with `_`/`model_`, and unique.

Response `200`:
```json
{
  "valid": true,
  "json_schema": {
    "title": "DynamicAnswer", "type": "object",
    "properties": {
      "city": { "title": "City", "type": "string", "description": "City name" },
      "population": { "anyOf": [{"type": "integer"}, {"type": "null"}], "default": null, "description": "Approx. population", "title": "Population" }
    },
    "required": ["city"], "additionalProperties": false
  }
}
```

Dry-run compiles the field list into a real `pydantic.create_model(...)` class — never `eval`/`exec` — and returns its JSON Schema without calling a model. `400 invalid_schema` on an unknown type or invalid/duplicate field names.

---

## Structured Answers (`/api/v1/structured`)

Both endpoints depend on `enforce_rate_limit` (20/min per user) and `enforce_daily_quota` (30/day per user) in addition to auth.

### `POST /api/v1/structured/answer`
Body — `StructuredAnswerRequest`:
```json
{
  "prompt": "Extract the capital and population of France.",
  "schema_def": { "fields": [
    { "name": "capital", "type": "string", "description": "Capital city", "required": true },
    { "name": "population", "type": "integer", "description": "Approximate population", "required": false }
  ]},
  "tier": "fast"
}
```
`prompt`: 1–4000 chars. `tier`: `"fast" | "smart"`, default `"fast"`.

Response `200`:
```json
{ "data": { "capital": "Paris", "population": 2148000 }, "provider": "ollama", "model": "qwen2.5:7b-instruct", "attempts": 1 }
```

Redacts PII from the prompt, builds the schema into a system prompt, calls the gateway (Ollama → Groq fallback), validates the reply against the compiled schema, and retries with corrective feedback up to `structured_max_attempts` (default 3).

Errors: `400 guardrail_blocked` (injection match, checked before PII redaction), `429 rate_limited`, `502 generation_failed` (all providers failed or no attempt validated within the retry budget).

### `POST /api/v1/structured/answer/stream`
Same body. Response: `200`, `text/event-stream`. Each frame is `data: <json>\n\n`:
```
data: {"stage": "generating", "attempt": 1}

data: {"stage": "validating", "attempt": 1}

data: {"stage": "done", "attempt": 1, "data": {"capital": "Paris", "population": 2148000}, "provider": "ollama", "model": "qwen2.5:7b-instruct", "attempts": 1}
```
`stage` is one of `generating`, `validating`, `retrying`, `error`, `done`. The guardrail/rate-limit/quota checks run **before** the stream opens, so those still come back as normal JSON errors; once streaming starts, a generation failure arrives as an in-stream `{"stage": "error", ...}` event with the HTTP status staying 200.

---

## Projects & Chats

### Projects (`/api/v1/projects`)

| Endpoint | Body | Response |
|---|---|---|
| `POST /api/v1/projects` | `{name}` (1–200 chars) | `201` `{id, name, created_at}` |
| `GET /api/v1/projects?limit=&offset=` | — | `200` `Page[Project]`, newest first (`limit` 1–100, default 20) |
| `GET /api/v1/projects/{id}` | — | `200` `Project` / `404 not_found` |
| `DELETE /api/v1/projects/{id}` | — | `204` / `404 not_found` |

### Chats (`/api/v1/chats`)

| Endpoint | Body | Response |
|---|---|---|
| `POST /api/v1/chats` | `{title, project_id?}` | `201` `{id, title, project_id, created_at, updated_at}`; `404` if `project_id` doesn't resolve |
| `GET /api/v1/chats?project_id=&limit=&offset=` | — | `200` `Page[Chat]`, newest-updated first |
| `GET /api/v1/chats/{id}` | — | `200` chat + full `messages: list[Message]` (not paginated - the detail view always returns the whole conversation) / `404` |
| `DELETE /api/v1/chats/{id}` | — | `204` / `404` |
| `POST /api/v1/chats/{id}/messages` | `{role: "user"\|"assistant", content, structured_data?, provider?, model?}` | `201` `Message`; just stores a message, doesn't call a model |
| `GET /api/v1/chats/{id}/messages?limit=&offset=` | — | `200` `Page[Message]`, oldest first |

---

## Files

### Files (`/api/v1/files`)

| Endpoint | Request | Response |
|---|---|---|
| `POST /api/v1/files` | multipart `file` + query `chat_id?` | `201` `{id, filename, content_type, size_bytes, chat_id, created_at}`; `413 payload_too_large` over `max_upload_size_bytes` (default 10 MiB); `415 unsupported_media_type` if `content_type` isn't on the allowlist, or if the bytes don't actually look like it (magic-byte signature check for images/PDF, UTF-8/JSON-parse check for the text types) — the client-supplied header alone is never trusted |
| `GET /api/v1/files?chat_id=&limit=&offset=` | — | `200` `Page[File]`, newest first |
| `GET /api/v1/files/{id}` | — | `200` metadata / `404` |
| `DELETE /api/v1/files/{id}` | — | `204` / `404` |
| `GET /api/v1/files/{id}/content` | — | `200` raw bytes, `Content-Type` = stored type / `404` |

---

## Search (`/api/v1/search`)

### `GET /api/v1/search?q=<term>`
Auth: required. `q` required, min length 1.

Response `200`:
```json
{ "chats": [ {"id", "title", "project_id", "created_at", "updated_at"} ], "messages": [ {"id", "chat_id", "role", "content", "structured_data", "provider", "model", "created_at"} ] }
```
Case-insensitive substring search over the current user's own chat titles and message contents.

---

## Usage (`/api/v1/usage`)

### `GET /api/v1/usage`
Auth: required.

Response `200`: `{user_count_today, user_limit}`. Reports today's count against the daily quota enforced on `/api/v1/structured/answer(+stream)`.

---

## Observability

| Endpoint | Auth | Response |
|---|---|---|
| `GET /health` | none | `200` `{status: "ok"}` — liveness |
| `GET /ready` | none | `200` `{ready, db}` — readiness; a DB failure shows as `false`, not an HTTP error |
| `GET /metrics` | none | `200` Prometheus text exposition format (not JSON) — see [OBSERVABILITY.md](OBSERVABILITY.md#2-metrics) for the metric list |
| `GET /api/v1/traces?limit=` | required | `200` `list[Span]`, most recent first, `limit` 1–500 (default 50) — see [OBSERVABILITY.md](OBSERVABILITY.md#1-tracing) |

---

## Architecture (`/api/v1/arch`)

Backs the frontend's Architecture tab.

| Endpoint | Body | Response |
|---|---|---|
| `GET /api/v1/arch/graph` | — | `200` static `{nodes, edges, groups, scenarios}` describing the system (15 nodes / 18 edges / 8 groups / 9 scenarios) — hand-authored, not introspected |
| `GET /api/v1/arch/status` | — | `200` `{ollama: {available, latency_ms, models, ...}, groq: {...}, mcp: {...}, checked_at, nodes}` — live reachability probe of Ollama (`/api/tags`), Groq (`/openai/v1/models`), and the in-process MCP server (`list_tools`/`list_resources`) |
| `POST /api/v1/arch/test-run` | `{scenario_id}` (one of 9 fixed literals, e.g. `happy_path_fast`, `ollama_down_groq_fallback`, `prompt_injection_blocked`, `mcp_tool_call`) | `200` `{scenario_id, label, passed, summary, steps: [...], total_duration_ms}` — replays a scripted scenario against the real service/guardrail code with fake in-memory providers (no real network calls) |

---

## Evaluation (`/api/v1/eval`)

| Endpoint | Body | Response |
|---|---|---|
| `GET /api/v1/eval/cases` | — | `200` `list[GoldenCase]` loaded from `eval/cases/golden.json` |
| `POST /api/v1/eval/run` | `{case_ids?, provider: "gateway"\|"ollama"\|"groq", concurrency: 1-20}` | `200` `EvalReport`: `{started_at, finished_at, total, passed, failed, pass_rate, avg_latency_ms, p95_latency_ms, avg_attempts, by_category, results: [...]}`; `404 not_found` if any `case_ids` don't exist |
| `POST /api/v1/eval/run/stream` | same body | `200` `text/event-stream`: a `{"stage": "case_done", "result": {...}}` frame per finished case (out of order — `asyncio.as_completed`), then one final `{"stage": "done", "report": {...}}` |
| `GET /api/v1/eval/runs?limit=&offset=` | — | `200` `Page[EvalRunSummary]`, newest first |

`by_category` entries are `{total, passed}` only — per-category `pass_rate` isn't a serialized field, only the top-level `EvalReport.pass_rate` is.

---

## Admin (`/api/v1/admin`)

Every endpoint here requires `require_admin` (`app/core/deps.py`) in addition to auth: a valid token for a user whose `role` is `"admin"`, or `403 forbidden`. There's no API path to create the *first* admin — see `scripts/promote_admin.py`, which flips a user's role directly in the database.

| Endpoint | Body | Response |
|---|---|---|
| `GET /api/v1/admin/users?limit=&offset=` | — | `200` `Page[AdminUser]`: `{items: [{id, email, role, is_active, created_at}], total, limit, offset}` |
| `PATCH /api/v1/admin/users/{user_id}/role` | `{role: "user"\|"admin"}` | `200` updated `AdminUser` / `404 not_found` / `409 conflict` if the admin targets their own id (self-demotion is blocked) |
| `GET /api/v1/admin/usage?limit=&offset=` | — | `200` `Page[{user_id, email, count_today}]` — today's per-user request count across every account, newest/highest first |

---

## Guard summary

| Guard | Dependency | Applies to |
|---|---|---|
| JWT auth | `get_current_user` | everything except `/api/v1/auth/register`, `/api/v1/auth/check-email`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`, `/api/v1/auth/github/login`, `/api/v1/auth/github/callback`, `/health`, `/ready`, `/metrics` |
| Admin role | `require_admin` | `/api/v1/admin/*` |
| Per-minute rate limit | `enforce_rate_limit` | `POST /api/v1/structured/answer(+stream)` |
| Per-IP auth rate limit | `enforce_auth_rate_limit` | `POST /api/v1/auth/register`, `/login`, `/refresh`, `/github/callback` — one shared budget across all four, since it's keyed by IP, not endpoint |
| Daily quota | `enforce_daily_quota` | same endpoints |
| Prompt-injection screen | `detect_prompt_injection` (via shared `guard_prompt()`) | `POST /api/v1/structured/answer(+stream)` |
| PII redaction | `redact_pii` (via shared `guard_prompt()`) | `POST /api/v1/structured/answer(+stream)` — see [GUARDRAILS.md](GUARDRAILS.md#2-pii-redaction) |
| Email guardrail | `check_email` | `POST /api/v1/auth/register`, `POST /api/v1/auth/check-email` — see [GUARDRAILS.md](GUARDRAILS.md#5-email-guardrail) |

See [GUARDRAILS.md](GUARDRAILS.md) for how each guard works internally, and [OBSERVABILITY.md](OBSERVABILITY.md) for `/metrics` and `/api/v1/traces` detail.
