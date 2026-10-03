import time
from datetime import UTC, datetime

from prometheus_client import Counter

from app.core.metrics import (
    GATEWAY_CALL_DURATION_SECONDS,
    GATEWAY_CALLS_TOTAL,
    GATEWAY_FALLBACKS_TOTAL,
    GUARDRAIL_BLOCKS_TOTAL,
    OUTPUT_LEAK_BLOCKS_TOTAL,
    OUTPUT_PII_BLOCKS_TOTAL,
    RATE_LIMIT_HITS_TOTAL,
    STRUCTURED_ANSWER_ATTEMPTS,
    STRUCTURED_ANSWER_FAILURES_TOTAL,
)
from app.core.metrics_buffer import RequestRecord, get_request_buffer
from app.core.stats import percentile
from app.schemas.metrics import (
    EndpointStat,
    FailedRunStats,
    GuardrailStats,
    MetricsSummaryResponse,
    MetricsTotals,
    ProviderStat,
    StatusBucket,
    StructuredStats,
    TimeseriesPoint,
)

_TIMESERIES_WINDOW_MINUTES = 60
_BUCKET_SECONDS = 60


def _sum_counter(metric: Counter, **label_filter: str) -> float:
    total = 0.0
    for family in metric.collect():
        for sample in family.samples:
            if not sample.name.endswith("_total"):
                continue
            if all(sample.labels.get(k) == v for k, v in label_filter.items()):
                total += sample.value
    return total


def _gateway_calls_by_provider_model() -> dict[tuple[str, str], dict[str, float]]:
    result: dict[tuple[str, str], dict[str, float]] = {}
    for family in GATEWAY_CALLS_TOTAL.collect():
        for sample in family.samples:
            if not sample.name.endswith("_total"):
                continue
            key = (sample.labels["provider"], sample.labels["model"])
            bucket = result.setdefault(key, {})
            outcome = sample.labels["outcome"]
            bucket[outcome] = bucket.get(outcome, 0.0) + sample.value
    return result


def _gateway_latency_by_provider_model() -> dict[tuple[str, str], tuple[float, float]]:
    sums: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], float] = {}
    for family in GATEWAY_CALL_DURATION_SECONDS.collect():
        for sample in family.samples:
            key = (sample.labels.get("provider", ""), sample.labels.get("model", ""))
            if sample.name.endswith("_sum"):
                sums[key] = sample.value
            elif sample.name.endswith("_count"):
                counts[key] = sample.value
    return {key: (sums.get(key, 0.0), counts.get(key, 0.0)) for key in {*sums, *counts}}


def _fallbacks_by_to_provider() -> dict[str, float]:
    totals: dict[str, float] = {}
    for family in GATEWAY_FALLBACKS_TOTAL.collect():
        for sample in family.samples:
            if not sample.name.endswith("_total"):
                continue
            to_provider = sample.labels["to_provider"]
            totals[to_provider] = totals.get(to_provider, 0.0) + sample.value
    return totals


def _build_providers() -> list[ProviderStat]:
    calls_by_key = _gateway_calls_by_provider_model()
    latency_by_key = _gateway_latency_by_provider_model()
    fallbacks_by_provider = _fallbacks_by_to_provider()

    # GATEWAY_FALLBACKS_TOTAL carries no model dimension, so its count is attributed
    # to whichever (provider, model) row has the most calls for that provider - the
    # realistic case has exactly one model per provider anyway.
    best_model_for_provider: dict[str, str] = {}
    best_calls_for_provider: dict[str, float] = {}
    for (provider, model), outcomes in calls_by_key.items():
        total_calls = outcomes.get("success", 0.0) + outcomes.get("failure", 0.0)
        if total_calls > best_calls_for_provider.get(provider, -1.0):
            best_calls_for_provider[provider] = total_calls
            best_model_for_provider[provider] = model

    stats: list[ProviderStat] = []
    for provider, model in sorted(calls_by_key):
        outcomes = calls_by_key[(provider, model)]
        failures = outcomes.get("failure", 0.0)
        calls = outcomes.get("success", 0.0) + failures
        duration_sum, duration_count = latency_by_key.get((provider, model), (0.0, 0.0))
        avg_latency_ms = (duration_sum / duration_count * 1000) if duration_count else 0.0
        fallbacks = (
            fallbacks_by_provider.get(provider, 0.0)
            if best_model_for_provider.get(provider) == model
            else 0.0
        )
        stats.append(
            ProviderStat(
                provider=provider,
                model=model,
                calls=int(calls),
                failures=int(failures),
                fallbacks=int(fallbacks),
                avg_latency_ms=avg_latency_ms,
            )
        )
    return stats


def _build_guardrails() -> GuardrailStats:
    return GuardrailStats(
        injection_blocks=int(_sum_counter(GUARDRAIL_BLOCKS_TOTAL, reason="injection")),
        pii_redactions=int(_sum_counter(GUARDRAIL_BLOCKS_TOTAL, reason="pii")),
        rate_limit_hits=int(_sum_counter(RATE_LIMIT_HITS_TOTAL)),
        email_blocks=int(_sum_counter(GUARDRAIL_BLOCKS_TOTAL, reason="email")),
    )


def _build_structured() -> StructuredStats:
    buckets: dict[str, float] = {}
    total_count = 0.0
    for family in STRUCTURED_ANSWER_ATTEMPTS.collect():
        for sample in family.samples:
            if sample.name.endswith("_bucket"):
                buckets[sample.labels["le"]] = sample.value
            elif sample.name.endswith("_count"):
                total_count = sample.value

    ordered_bounds = sorted((b for b in buckets if b != "+Inf"), key=float)
    prev = 0.0
    attempts_histogram: dict[str, int] = {}
    for bound in ordered_bounds:
        count_at_bound = buckets[bound]
        attempts_histogram[str(int(float(bound)))] = int(count_at_bound - prev)
        prev = count_at_bound
    overflow = buckets.get("+Inf", prev) - prev
    if overflow > 0:
        attempts_histogram["5+"] = int(overflow)

    first_try = attempts_histogram.get("1", 0)
    retried = total_count - first_try
    retry_rate = (retried / total_count) if total_count else 0.0
    first_try_valid_pct = (first_try / total_count * 100) if total_count else 0.0
    return StructuredStats(
        attempts_histogram=attempts_histogram,
        retry_rate=retry_rate,
        first_try_valid_pct=first_try_valid_pct,
    )


_FAILURE_REASONS = ("gateway_error", "invalid_output", "output_leak", "output_pii")


def _build_failed_runs() -> FailedRunStats:
    by_reason: dict[str, int] = dict.fromkeys(_FAILURE_REASONS, 0)
    for family in STRUCTURED_ANSWER_FAILURES_TOTAL.collect():
        for sample in family.samples:
            if not sample.name.endswith("_total"):
                continue
            reason = sample.labels["reason"]
            by_reason[reason] = by_reason.get(reason, 0) + int(sample.value)
    by_reason["output_leak"] += int(_sum_counter(OUTPUT_LEAK_BLOCKS_TOTAL))
    by_reason["output_pii"] += int(_sum_counter(OUTPUT_PII_BLOCKS_TOTAL))
    return FailedRunStats(total=sum(by_reason.values()), by_reason=by_reason)


def _build_from_records(
    records: list[RequestRecord], *, now: float
) -> tuple[MetricsTotals, list[EndpointStat], StatusBucket, list[TimeseriesPoint]]:
    total = len(records)
    error_count = sum(1 for r in records if r.status_code >= 500)
    client_error_count = sum(1 for r in records if 400 <= r.status_code < 500)
    durations = sorted(r.duration_ms for r in records)
    totals = MetricsTotals(
        requests=total,
        errors=error_count,
        error_rate=(error_count / total) if total else 0.0,
        client_errors=client_error_count,
        p50_ms=percentile(durations, 0.5),
        p95_ms=percentile(durations, 0.95),
    )

    by_endpoint_map: dict[tuple[str, str], list[RequestRecord]] = {}
    for r in records:
        by_endpoint_map.setdefault((r.method, r.path), []).append(r)
    by_endpoint = [
        EndpointStat(
            method=method,
            path=path,
            count=len(items),
            error_count=sum(1 for i in items if i.status_code >= 500),
            p50_ms=percentile(sorted(i.duration_ms for i in items), 0.5),
            p95_ms=percentile(sorted(i.duration_ms for i in items), 0.95),
        )
        for (method, path), items in sorted(by_endpoint_map.items())
    ]

    by_code: dict[str, int] = {}
    twoxx = fourxx = fivexx = 0
    for r in records:
        by_code[str(r.status_code)] = by_code.get(str(r.status_code), 0) + 1
        if 200 <= r.status_code < 300:
            twoxx += 1
        elif 400 <= r.status_code < 500:
            fourxx += 1
        elif r.status_code >= 500:
            fivexx += 1
    by_status = StatusBucket.model_validate(
        {"2xx": twoxx, "4xx": fourxx, "5xx": fivexx, "by_code": by_code}
    )

    now_minute = int(now // _BUCKET_SECONDS)
    minute_buckets: dict[int, dict[str, int]] = {}
    for r in records:
        minute = int(r.ts // _BUCKET_SECONDS)
        bucket = minute_buckets.setdefault(minute, {"requests": 0, "errors": 0})
        bucket["requests"] += 1
        if r.status_code >= 500:
            bucket["errors"] += 1

    timeseries = []
    for offset in range(_TIMESERIES_WINDOW_MINUTES - 1, -1, -1):
        minute = now_minute - offset
        bucket = minute_buckets.get(minute, {"requests": 0, "errors": 0})
        label = datetime.fromtimestamp(minute * _BUCKET_SECONDS, tz=UTC).strftime("%H:%M")
        timeseries.append(
            TimeseriesPoint(minute=label, requests=bucket["requests"], errors=bucket["errors"])
        )

    return totals, by_endpoint, by_status, timeseries


def build_summary(*, now: float | None = None) -> MetricsSummaryResponse:
    now = now if now is not None else time.time()
    window_start = now - _TIMESERIES_WINDOW_MINUTES * _BUCKET_SECONDS
    records = get_request_buffer().recent(since_ts=window_start)
    totals, by_endpoint, by_status, timeseries = _build_from_records(records, now=now)
    return MetricsSummaryResponse(
        generated_at=datetime.now(UTC).isoformat(),
        totals=totals,
        by_endpoint=by_endpoint,
        by_status=by_status,
        guardrails=_build_guardrails(),
        providers=_build_providers(),
        structured=_build_structured(),
        failed_runs=_build_failed_runs(),
        timeseries=timeseries,
    )
