# Guardrails

Everything between a user's prompt and a model call, and between a model's answer and the user. Five layers, each independently testable (`tests/unit/test_guardrails.py` et al.) and each with an explicit, documented limit to what it actually protects against.

## Request-flow summary (the structured-answer paths, most heavily guarded)

`POST /api/v1/structured/answer` and `POST /api/v1/structured/answer/stream` both run the same shared `guard_prompt()` chain (`app/guardrails/prompt_guard.py`) in order:

1. `get_current_user` — JWT auth.
2. `enforce_rate_limit` — per-user, 20 requests/min.
3. `enforce_daily_quota` — per-user 30/day.
4. `guard_prompt()` — prompt-injection screen (400 if flagged), then PII scan/redact-or-block per `PII_MODE`.
5. The *clean* prompt is handed to the model gateway (`structured_service.answer()`).

## 1. Prompt-injection screening

**File:** `app/guardrails/injection.py` — `detect_prompt_injection(text: str) -> InjectionMatch | None`, called by the shared `guard_prompt()` helper.

A case-insensitive regex/keyword heuristic — no ML classifier. Flags prompts matching patterns like "ignore previous/prior/above instructions," "disregard the system prompt," "you are now a/an/no longer...," "reveal your/the system/hidden prompt," "new instructions:," "act as an unfiltered...," "do anything now," or "jailbreak," each tagged with a category (e.g. `override`, `exfiltration`, `roleplay`, `jailbreak`).

On trigger: raises `GuardrailError` → **HTTP 400**, `code: "guardrail_blocked"`, and increments both `structai_guardrail_blocks_total{reason="injection"}` and `structai_injection_blocks_total{category}`.

Runs in the route handler *before* any provider call — on both `/api/v1/structured/answer` and `/api/v1/structured/answer/stream`, via `guard_prompt()`. For the streaming endpoint specifically, the check happens before the `StreamingResponse` is constructed at all, since Starlette sends the HTTP status line before the body generator first runs — a check inside the generator couldn't surface as a clean 400.

**Known limitation:** the MCP server's `ask_structured`/`send_message` tools use their own, separate `_guard_prompt()` in `app/mcp/server.py`, still on the legacy `is_prompt_injection() -> bool` check with only the aggregate metric, not the categorized one above — a pre-existing inconsistency not yet unified with the shared helper.

**Why:** first line of defense against jailbreak/system-prompt-exfiltration attempts, before any model is ever called. Explicitly documented as "not exhaustive — sufficient as a first line of defense, not a guarantee," not a claim of complete coverage.

## 2. PII redaction

**File:** `app/guardrails/pii.py` — `scan_pii(text: str) -> PiiScanResult`, called by the shared `guard_prompt()` helper (`app/guardrails/prompt_guard.py`).

Detects, in priority order (longest/checksum-gated/label-gated first, so a looser pattern never re-matches digits a stricter one already consumed):

| Category | Detection | Substitution |
|---|---|---|
| Credit card | 13–19 digit run, Luhn checksum | `[REDACTED_CARD]` |
| Aadhaar (Indian national ID) | 12-digit run, Verhoeff checksum | `[REDACTED_AADHAAR]` |
| PAN (Indian tax ID) | fixed 10-char pattern | `[REDACTED_PAN]` |
| IFSC (Indian bank branch code) | fixed pattern, only when "IFSC" appears nearby | `[REDACTED_IFSC]` |
| Passport number | fixed pattern, only when "passport" appears nearby | `[REDACTED_PASSPORT]` |
| Bank account number | 9–18 digit run, only when "account no./number" appears nearby | `[REDACTED_BANK_ACCOUNT]` |
| SSN (`\d{3}-\d{2}-\d{4}`) | fixed pattern | `[REDACTED_SSN]` |
| Indian mobile number | `+91`/`0` prefix + 10 digits starting 6–9 | `[REDACTED_PHONE_IN]` |
| Other phone numbers (international + US) | digit-adjacency match, not `\b` (so `+919876543210` with no separators still matches) | `[REDACTED_PHONE]` |
| Email (plain + obfuscated "name at example dot com") | regex | `[REDACTED_EMAIL]` |

IFSC/passport/bank-account are **label-gated** (only redacted when their keyword appears within 40 characters) since their raw shapes are too generic on their own — an unrelated digit run (an order id, a phone number) wouldn't otherwise be false-flagged as a bank account just because the message mentions one elsewhere.

A `PII_MODE` setting (`.env`, default `redact`) controls what happens when PII is found: `redact` (default) replaces matches and continues; `block` raises `PiiDetectedError` → **HTTP 400** instead of redacting.

Redaction happens **before the prompt reaches the model**, not just before logging — `guard_prompt()` redacts first and the clean string is what's actually sent to the gateway/provider. Trace span attributes only ever hold `tier`/`attempt`/`provider`/`model`, never prompt text, and nothing in `app/services/*.py` or `app/routes/*.py` logs raw prompt/response content (verified: the only `logging.getLogger()` call anywhere in `app/` is inside `configure_logging()` itself — see [OBSERVABILITY.md](OBSERVABILITY.md#3-structured-logging)).

Applied uniformly to `/api/v1/structured/answer(+stream)` via the shared `guard_prompt()` helper. **Known gap:** chat message persistence (`chat_service.py`) still stores message content as-is — redaction only runs on the generation-request path, not on messages saved directly via `POST /api/v1/chats/{id}/messages` or the MCP `send_message` tool.

**Why:** defense-in-depth so personal data never reaches a third-party model provider (Groq) or ends up in a log/trace, per the project rule to never log raw prompts or PII.

## 3. Rate limiting

**File:** `app/guardrails/rate_limit.py` — `RateLimiter.check(key)`, singleton via `get_rate_limiter()`.

A sliding 60-second window, in-memory, keyed by **user id** (not device, not IP) — see `app/core/deps.py::enforce_rate_limit`. Default limit: **20 requests/minute** (`RATE_LIMIT_PER_MIN` in `.env`). Exceeding it raises `RateLimitExceededError` → **HTTP 429**, `code: "rate_limited"`, and increments `structai_rate_limit_hits_total`.

Applied to `/api/v1/structured/answer(+stream)`. Deliberately **not** applied to `/api/v1/eval/*` — that's treated as an authenticated operator/demo tool, not end-user traffic.

**Known limitation:** in-memory and per-process — doesn't survive a restart and isn't shared across multiple API instances.

## 4. Daily quota

**File:** `app/services/quota_service.py` — `check_and_increment(session, scope, key, limit)`.

Differs from rate limiting in two ways: a **calendar-day** window (not rolling 60s), and real **database persistence** (a `QuotaUsage` row per `(scope, key, day)`) rather than an in-memory counter — so it survives restarts.

Defaults: **30/day per user** (`DAILY_QUOTA_USER`). Exceeding it raises the same `RateLimitError` → **HTTP 429**, `code: "rate_limited"`.

Implemented as a single atomic `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` rather than a read-then-write pair, specifically because the original SELECT-then-INSERT version let two concurrent requests for the same user/day both see "no row yet" and race to insert — which surfaced as a real unhandled `IntegrityError` under `scripts/load_test.py` at concurrency 5 (caught and fixed in Phase 8; see `tests/unit/test_quota_service.py::test_concurrent_requests_increment_atomically_without_crashing`, which reproduces the race with 10 genuinely separate sessions).

Read-only visibility: `GET /api/v1/usage` returns today's user count against its limit.

**Why:** a longer-horizon cost/abuse ceiling independent of short bursts.

## 5. Email guardrail

**File:** `app/guardrails/email.py` — `check_email(email, *, check_mx, mx_timeout, extra_disposable_domains) -> EmailCheckResult`.

Four checks, in order, each cheaper/more certain than the next so an obviously bad address never pays for a DNS round trip:

1. **Syntax** — `email_validator` (RFC-shape, IDN-aware). Independent of Pydantic's own `EmailStr` field validation on `RegisterRequest.email`/`EmailCheckRequest.email`, which already rejects grossly malformed input (e.g. `not-an-email`) at the schema boundary with FastAPI's own `validation_error` 422 — so a malformed address reaching this module's own syntax check at all is a defense-in-depth backstop, not the primary gate on the HTTP routes.
2. **Disposable domains** — a built-in list of ~56 known throwaway-mail providers, merged with an optional file-configurable extra list (`Settings.email_disposable_domains_file`, one domain per line, `#`-comments and blank lines skipped) so new ones can be added without a code change.
3. **Typo detection against popular providers** — a domain within Damerau-Levenshtein distance 2 of a popular free-mail domain (`gmial.com` → `gmail.com`), or sharing a popular domain's name with a mangled TLD (`gmail.cmo` → `gmail.com`), is flagged with a suggested correction rather than silently accepted or silently rejected. A safe-list of real look-alike domains (`googlemail.com`, regional Microsoft/Yahoo/GMX domains, `qq.com`, `mail.ru`, etc.) is checked first so those are never flagged, and an unrelated business domain never matches unless it's actually close to a popular one.
4. **MX/A reachability** (`dnspython`, default 3s timeout, toggled by `Settings.email_check_mx` / `Settings.email_check_mx_timeout_seconds`) — a confirmed NXDOMAIN, or a domain with no MX record and no A/AAAA fallback either, is rejected. A lookup that merely times out or errors (resolver unreachable, transient network issue, SERVFAIL) fails **open**: the address is accepted with a non-blocking warning, since blocking real signups on a flaky resolver would be worse than letting one bad address through.

Two entry points share this same check:

- `POST /api/v1/auth/register` — `register_user` runs it before creating the account; a failing check raises the error class mapped from `EmailCheckResult.error_code` (see table below) and increments `structai_email_guardrail_blocks_total{reason=<error_code>}` plus the aggregate `structai_guardrail_blocks_total{reason="email"}`. An MX fail-open warning is logged (not raised) and registration proceeds.
- `POST /api/v1/auth/check-email` — same guardrail, read-only (`check_email_address`): never creates an account, never rate-limited or quota-counted on its own. Lets the frontend validate-on-blur before the user submits the form. Response shape: `{"valid", "message", "suggestion", "warning"}`.

**Why:** disposable addresses are a common way to spin up throwaway accounts that bypass the per-user quota guardrail; typo detection catches the far more common case of a legitimate user mistyping their own address and otherwise locking themselves out of their new account with no way to log back in; the MX check catches domains that plainly can't receive mail at all, without turning a flaky DNS resolver into a signup outage.

## Error code reference

All error bodies follow `{"error": {"code", "message", "request_id", "retry_after_seconds", "suggestion"}}` (`app/core/errors.py`); the last two are `null` except where noted.

| Guardrail | Exception | HTTP | `code` |
|---|---|---|---|
| Prompt injection | `GuardrailError` | 400 | `guardrail_blocked` |
| Rate limit | `RateLimitError` | 429 | `rate_limited` |
| Daily quota | `RateLimitError` (reused) | 429 | `rate_limited` |
| Disposable email | `ConflictError` | 409 | `conflict` |
| Malformed email syntax (schema-level) | FastAPI `RequestValidationError` | 422 | `validation_error` |
| Malformed email syntax (guardrail-level) | `InvalidEmailDomainError` | 422 | `invalid_email_domain` |
| Likely email typo | `InvalidEmailDomainError` (`suggestion` populated) | 422 | `invalid_email_domain` |
| Email domain unreachable | `EmailDomainUnreachableError` | 422 | `email_domain_unreachable` |

## Known limitations

- Injection screening is a fixed keyword/regex list — not exhaustive, and easy to evade with paraphrasing; it's a first line of defense, not a guarantee.
- The MCP server's `ask_structured`/`send_message` tools still use their own separate, legacy `_guard_prompt()` (bool-only injection check, no categorized metric) rather than the shared `app/guardrails/prompt_guard.py::guard_prompt()` used by `/api/v1/structured/answer` and `/api/v1/structured/answer/stream` — a pre-existing inconsistency, not yet unified.
- PII redaction isn't applied uniformly: chat message persistence (direct `POST /api/v1/chats/{id}/messages` writes, and the MCP `send_message` tool) still skips it — only `/api/v1/structured/answer(+stream)` is covered.
- Rate limiting is in-memory/per-process, not shared across instances.
- The email guardrail's disposable-domain and popular-provider lists are finite (built-in + optional file); a domain not on either list is neither blocked nor typo-checked.
- `POST /api/v1/auth/check-email` has no rate-limiting or quota of its own — a deliberate scope decision (it's a cheap, side-effect-free read used for inline form validation), but it means it could in principle be hit at a higher rate than `/api/v1/auth/register` itself.
