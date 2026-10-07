import pytest

from app.core.metrics import (
    OUTPUT_LEAK_BLOCKS_TOTAL,
    OUTPUT_PII_BLOCKS_TOTAL,
    STRUCTURED_ANSWER_ATTEMPTS,
    STRUCTURED_ANSWER_FAILURES_TOTAL,
)
from app.core.metrics_buffer import RequestRecord, get_request_buffer
from app.gateway.providers.base import ProviderError
from app.gateway.router import ModelGateway, ProviderCandidate
from app.guardrails.pii import scan_pii
from app.services.metrics_service import build_summary
from tests.harness.fake_provider import FakeProvider


def _record(ts: float, method: str, path: str, status_code: int, duration_ms: float) -> None:
    get_request_buffer().record(
        RequestRecord(
            ts=ts, method=method, path=path, status_code=status_code, duration_ms=duration_ms
        )
    )


def test_totals_and_by_endpoint_from_ring_buffer():
    _record(1000.0, "GET", "/health", 200, 10.0)
    _record(1000.0, "GET", "/health", 200, 20.0)
    _record(1000.0, "POST", "/api/v1/structured/answer", 500, 100.0)

    summary = build_summary(now=1000.0)

    assert summary.totals.requests == 3
    assert summary.totals.errors == 1
    assert summary.totals.error_rate == pytest.approx(1 / 3)
    assert summary.totals.client_errors == 0

    by_endpoint = {(e.method, e.path): e for e in summary.by_endpoint}
    health = by_endpoint[("GET", "/health")]
    assert health.count == 2
    assert health.error_count == 0

    structured = by_endpoint[("POST", "/api/v1/structured/answer")]
    assert structured.count == 1
    assert structured.error_count == 1


def test_client_errors_are_split_from_server_errors():
    _record(1000.0, "GET", "/a", 200, 5.0)
    _record(1000.0, "GET", "/b", 404, 5.0)
    _record(1000.0, "GET", "/c", 429, 5.0)
    _record(1000.0, "GET", "/d", 500, 5.0)

    summary = build_summary(now=1000.0)

    assert summary.totals.requests == 4
    assert summary.totals.errors == 1
    assert summary.totals.client_errors == 2
    assert summary.totals.error_rate == pytest.approx(1 / 4)


def test_by_status_buckets_and_by_code():
    _record(1000.0, "GET", "/a", 200, 5.0)
    _record(1000.0, "GET", "/b", 404, 5.0)
    _record(1000.0, "GET", "/c", 500, 5.0)

    summary = build_summary(now=1000.0)

    assert summary.by_status.twoxx == 1
    assert summary.by_status.fourxx == 1
    assert summary.by_status.fivexx == 1
    assert summary.by_status.by_code == {"200": 1, "404": 1, "500": 1}


def test_timeseries_buckets_by_minute_and_zero_fills():
    now = 120.0
    _record(now, "GET", "/health", 200, 1.0)
    _record(now - 60.0, "GET", "/health", 200, 1.0)
    _record(now - 60.0, "GET", "/health", 500, 1.0)

    summary = build_summary(now=now)

    assert len(summary.timeseries) == 60
    assert summary.timeseries[-1].requests == 1
    assert summary.timeseries[-1].errors == 0
    assert summary.timeseries[-2].requests == 2
    assert summary.timeseries[-2].errors == 1
    assert all(p.requests == 0 for p in summary.timeseries[:-2])


def test_empty_buffer_produces_zeroed_totals():
    summary = build_summary(now=1000.0)

    assert summary.totals.requests == 0
    assert summary.totals.error_rate == 0.0
    assert summary.totals.client_errors == 0
    assert summary.by_endpoint == []
    assert summary.by_status.by_code == {}


def test_totals_are_scoped_to_the_60_minute_window():
    _record(1000.0, "GET", "/stale", 500, 1.0)

    summary = build_summary(now=1000.0 + 3600.0 + 60.0)

    assert summary.totals.requests == 0
    assert summary.totals.errors == 0


@pytest.mark.asyncio
async def test_providers_section_reflects_real_gateway_calls():
    primary = FakeProvider(name="metrics-svc-primary", raises=ProviderError("boom"))
    secondary = FakeProvider(name="metrics-svc-secondary", responses=["ok"])
    gateway = ModelGateway(
        {
            "fast": [
                ProviderCandidate(primary, "model-a"),
                ProviderCandidate(secondary, "model-b"),
            ]
        }
    )

    await gateway.generate(tier="fast", system=None, prompt="hi")

    summary = build_summary(now=1000.0)
    providers = {(p.provider, p.model): p for p in summary.providers}

    primary_stat = providers[("metrics-svc-primary", "model-a")]
    assert primary_stat.calls == 1
    assert primary_stat.failures == 1

    secondary_stat = providers[("metrics-svc-secondary", "model-b")]
    assert secondary_stat.calls == 1
    assert secondary_stat.failures == 0
    assert secondary_stat.fallbacks == 1
    assert secondary_stat.avg_latency_ms >= 0.0


def test_guardrails_pii_redactions_reflect_real_scan_pii_calls():
    before = build_summary(now=1000.0).guardrails.pii_redactions

    scan_pii("reach me at someone@example.com")

    after = build_summary(now=1000.0).guardrails.pii_redactions
    assert after == before + 1


def test_structured_attempts_histogram_reflects_real_observations():
    before = build_summary(now=1000.0).structured.attempts_histogram.get("2", 0)

    STRUCTURED_ANSWER_ATTEMPTS.observe(2)

    after = build_summary(now=1000.0).structured.attempts_histogram.get("2", 0)
    assert after == before + 1


def test_failed_runs_aggregates_all_failure_reasons():
    before = build_summary(now=1000.0).failed_runs

    STRUCTURED_ANSWER_FAILURES_TOTAL.labels(reason="gateway_error").inc()
    STRUCTURED_ANSWER_FAILURES_TOTAL.labels(reason="invalid_output").inc()
    OUTPUT_LEAK_BLOCKS_TOTAL.inc()
    OUTPUT_PII_BLOCKS_TOTAL.inc()

    after = build_summary(now=1000.0).failed_runs

    assert after.total == before.total + 4
    assert after.by_reason["gateway_error"] == before.by_reason["gateway_error"] + 1
    assert after.by_reason["invalid_output"] == before.by_reason["invalid_output"] + 1
    assert after.by_reason["output_leak"] == before.by_reason["output_leak"] + 1
    assert after.by_reason["output_pii"] == before.by_reason["output_pii"] + 1
