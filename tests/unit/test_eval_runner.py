import asyncio
from datetime import datetime

import pytest

from app.gateway.router import ModelGateway, ProviderCandidate
from eval.runner import check_result, run_case, run_eval
from eval.schemas import ExpectedCheck, GoldenCase
from tests.harness.fake_provider import FakeProvider


def make_clock():
    state = {"now": 0.0}

    def clock() -> float:
        state["now"] += 1.0
        return state["now"]

    return clock


def _case(case_id: str = "c1", checks: list[ExpectedCheck] | None = None) -> GoldenCase:
    return GoldenCase(
        id=case_id,
        category="facts",
        prompt="what is it",
        schema_def={"fields": [{"name": "answer", "type": "string"}]},
        checks=checks or [],
    )


def _gateway(responses: list[str] | None = None, fail_times: int = 0) -> ModelGateway:
    provider = FakeProvider(responses=responses, fail_times=fail_times)
    candidate = ProviderCandidate(provider, "fake-model")
    return ModelGateway({"fast": [candidate], "smart": [candidate]})


def test_check_result_equals_pass():
    passed, reason = check_result(
        {"answer": "Paris"}, [ExpectedCheck(field="answer", equals="paris")]
    )
    assert passed is True
    assert reason is None


def test_check_result_equals_numeric_formatting():
    passed, _ = check_result({"degrees": 0.0}, [ExpectedCheck(field="degrees", equals="0")])
    assert passed is True

    passed, _ = check_result({"result": 100.0}, [ExpectedCheck(field="result", equals="100")])
    assert passed is True


def test_check_result_equals_fail():
    passed, reason = check_result(
        {"answer": "London"}, [ExpectedCheck(field="answer", equals="paris")]
    )
    assert passed is False
    assert "London" in reason


def test_check_result_contains():
    passed, _ = check_result(
        {"author": "William Shakespeare"}, [ExpectedCheck(field="author", contains="shakespeare")]
    )
    assert passed is True


def test_check_result_one_of():
    passed, _ = check_result(
        {"sentiment": "positive"},
        [ExpectedCheck(field="sentiment", one_of=["positive", "neutral"])],
    )
    assert passed is True

    failed, reason = check_result(
        {"sentiment": "negative"}, [ExpectedCheck(field="sentiment", one_of=["positive"])]
    )
    assert failed is False
    assert reason is not None


def test_check_result_missing_field():
    passed, reason = check_result({}, [ExpectedCheck(field="answer", equals="paris")])
    assert passed is False
    assert "missing field" in reason


@pytest.mark.asyncio
async def test_run_case_pass():
    gateway = _gateway(responses=['{"answer": "Paris"}'])
    case = _case(checks=[ExpectedCheck(field="answer", equals="paris")])

    result = await run_case(gateway, case, semaphore=asyncio.Semaphore(1), clock=make_clock())

    assert result.passed is True
    assert result.provider == "fake"
    assert result.attempts == 1
    assert result.latency_ms > 0


@pytest.mark.asyncio
async def test_run_case_fails_check():
    gateway = _gateway(responses=['{"answer": "London"}'])
    case = _case(checks=[ExpectedCheck(field="answer", equals="paris")])

    result = await run_case(gateway, case, semaphore=asyncio.Semaphore(1), clock=make_clock())

    assert result.passed is False
    assert "London" in result.reason
    assert result.data == {"answer": "London"}


@pytest.mark.asyncio
async def test_run_case_gateway_failure():
    gateway = _gateway(fail_times=99)
    case = _case()

    result = await run_case(
        gateway, case, semaphore=asyncio.Semaphore(1), max_attempts=1, clock=make_clock()
    )

    assert result.passed is False
    assert result.provider is None
    assert result.reason is not None


@pytest.mark.asyncio
async def test_run_eval_assigns_distinct_trace_id_per_case():
    gateway = _gateway(responses=['{"answer": "Paris"}'])
    cases = [_case("c1"), _case("c2"), _case("c3")]

    report = await run_eval(cases, gateway, concurrency=3, clock=make_clock())

    trace_ids = [r.trace_id for r in report.results]
    assert all(trace_ids)
    assert len(set(trace_ids)) == len(cases)


@pytest.mark.asyncio
async def test_run_eval_aggregates_by_category():
    gateway = _gateway(responses=['{"answer": "Paris"}'])
    cases = [
        _case("pass-1", checks=[ExpectedCheck(field="answer", equals="paris")]),
        _case("fail-1", checks=[ExpectedCheck(field="answer", equals="london")]),
    ]

    report = await run_eval(
        cases,
        gateway,
        concurrency=2,
        clock=make_clock(),
        wall_clock=lambda: datetime(2026, 1, 1),
    )

    assert report.total == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.pass_rate == pytest.approx(0.5)
    assert report.by_category["facts"].total == 2
    assert report.by_category["facts"].passed == 1
    assert report.started_at == report.finished_at == "2026-01-01T00:00:00"
