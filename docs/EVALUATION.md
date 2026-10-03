# Evaluation

StructAI ships two complementary ways to measure "does this actually work," plus a web UI that drives the first one live.

## 1. Golden-case harness (`eval/`)

`eval/cases/golden.json` holds 25 hand-written cases across 6 categories:

| Category | Cases | What it checks |
|---|---|---|
| `facts` | 8 | Factual recall (capitals, dates, simple trivia) |
| `math` | 4 | Arithmetic / numeric answers |
| `lists` | 4 | `string_list` / multi-item fields |
| `boolean` | 2 | `boolean` fields |
| `classification` | 4 | Picking one label from a closed set |
| `multi_field` | 3 | Schemas with 3+ fields in one response |

Each case is a prompt + the exact `schema_def` shape `/schemas/validate` and `/structured/answer` accept, plus one or more content checks (`equals` / `contains` / `one_of`) run against the validated response fields — not just "did it validate," but "did it answer correctly."

`eval/runner.py::run_eval()` drives all 25 cases concurrently (bounded by an `asyncio.Semaphore`) through either the real multi-provider `ModelGateway` or a single pinned provider, and aggregates pass rate, average/p95 latency, and average retry-loop attempts, overall and per-category.

### Running it

```bash
.venv/bin/python3 scripts/run_eval.py                 # default gateway (ollama -> groq fallback)
.venv/bin/python3 scripts/run_eval.py --compare        # ollama vs. groq, side by side
.venv/bin/python3 scripts/run_eval.py --provider groq  # pin to one provider
.venv/bin/python3 scripts/run_eval.py --out eval/reports/my-run.json
```

### Latest real numbers (2026-10-03, `eval/reports/compare-20261003T051203Z.json`)

| Provider | Model | Pass rate | Avg latency | p95 latency | Avg attempts |
|---|---|---|---|---|---|
| Ollama (local) | `qwen2.5:7b-instruct` | 25/25 (100%) | 11.8s | 20.2s | 1.12 |
| Groq (free tier) | `openai/gpt-oss-20b` / `openai/gpt-oss-120b` | 24/25 (96%) | 3.0s | 4.3s | 1.00 |

The one Groq miss (`basic-profile`, a `multi_field` case) was a transient `429 Too Many Requests` from Groq's free-tier rate limit, not a model-quality failure — the request never got a chance to run. Ollama passed every case this run. Both numbers are consistent with the baseline captured when this harness first shipped, which caught two real bugs at the time (a numeric string-equality bug in `check_result`, and a Groq model-name drift after the free-tier model list changed).

Per-category breakdown is identical for both providers except `multi_field` (Ollama 3/3, Groq 2/3 due to the rate-limit miss above) — every other category is a clean sweep for both.

### HTTP-level load test (`scripts/load_test.py`)

Separate from the in-process harness above, `load_test.py` fires concurrent real HTTP requests at a *running* server — exercising auth, guardrails, and rate limiting, not just the gateway/retry loop:

```bash
.venv/bin/python3 scripts/load_test.py --base-url http://localhost:8000 --requests 15 --concurrency 5
```

Latest run: 15/15 succeeded, 0 rate-limited, 0 errors, p50 2.4s / p95 4.3s / max 4.3s, 3.5 req/s throughput against the live Groq-backed default gateway. A 429 from the rate limiter is treated as an expected guardrail response in this tool, not a failure — it's measuring whether the whole stack holds up under concurrency, not just raw throughput.

## 2. In-app Evaluation tab

The **Evaluation** tab in the web app (`frontend/src/pages/EvaluationPage.tsx`) is the same harness, live: pick which of the 25 golden cases to run, a provider (`gateway` / `ollama` / `groq`), and a concurrency level, then press Run. Results stream in via `POST /eval/run/stream` (Server-Sent Events) — each case flips to pass/fail with its latency as soon as it finishes, rather than waiting for all 25 — and a final report (pass rate, avg/p95 latency, avg attempts, by-category breakdown) renders once the run completes. Cancel aborts the in-flight stream via `AbortController`.

This is the fastest way to re-check the numbers above after changing a prompt, a model default, or the gateway's retry logic, without leaving the browser.

## Known limitations

- Golden cases are hand-written and English-only; there's no held-out "unseen" set, so passing 25/25 means "matches our own expectations," not "generalizes to novel inputs."
- The in-process harness (`eval/runner.py`) calls services directly — fast, but doesn't exercise the HTTP/auth/guardrail layer. `load_test.py` covers that separately, but the two tools don't share a single combined report.
- `--compare` only compares Ollama vs. Groq as configured providers, not individual model variants within a provider (e.g. it won't A/B two different Groq models in one run).
- `/eval/*` has no rate limit or daily quota (a deliberate scope decision, since it's treated as an authenticated operator/demo tool, not end-user traffic).
