from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "structai_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "structai_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

STRUCTURED_ANSWER_ATTEMPTS = Histogram(
    "structai_structured_answer_attempts",
    "Number of attempts needed to produce a valid structured answer",
    buckets=(1, 2, 3, 4, 5),
)

STRUCTURED_ANSWER_FAILURES_TOTAL = Counter(
    "structai_structured_answer_failures_total",
    "Structured-answer runs that ended without a usable result, by reason",
    ["reason"],
)

GATEWAY_CALLS_TOTAL = Counter(
    "structai_gateway_calls_total",
    "Model provider calls made through the gateway",
    ["provider", "model", "outcome"],
)

GATEWAY_FALLBACKS_TOTAL = Counter(
    "structai_gateway_fallbacks_total",
    "Gateway calls that succeeded on a non-primary provider",
    ["from_provider", "to_provider"],
)

GATEWAY_CALL_DURATION_SECONDS = Histogram(
    "structai_gateway_call_duration_seconds",
    "Model provider call duration in seconds",
    ["provider", "model"],
)

GUARDRAIL_BLOCKS_TOTAL = Counter(
    "structai_guardrail_blocks_total",
    "Requests blocked by a guardrail before reaching a model",
    ["reason"],
)

INJECTION_BLOCKS_TOTAL = Counter(
    "structai_injection_blocks_total",
    "Prompts blocked by the input injection/prompt-extraction screen, by category",
    ["category"],
)

OUTPUT_LEAK_BLOCKS_TOTAL = Counter(
    "structai_output_leak_blocks_total",
    "Model outputs discarded because they appeared to leak the system prompt",
)

PII_REDACTIONS_TOTAL = Counter(
    "structai_pii_redactions_total",
    "PII spans redacted (or blocked) in a prompt or model output, by category",
    ["category"],
)

OUTPUT_PII_BLOCKS_TOTAL = Counter(
    "structai_output_pii_blocks_total",
    "Model outputs discarded (PII_MODE=block) because they contained detected PII",
)

RATE_LIMIT_HITS_TOTAL = Counter(
    "structai_rate_limit_hits_total",
    "Requests rejected by the per-user rate limiter",
)

EMAIL_GUARDRAIL_BLOCKS_TOTAL = Counter(
    "structai_email_guardrail_blocks_total",
    "Registrations rejected by the email guardrail, by reason",
    ["reason"],
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
