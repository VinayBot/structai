import pytest

from app.core.errors import NotFoundError
from app.gateway.router import ModelGateway, ProviderCandidate
from app.services import eval_service
from eval.runner import run_eval
from eval.schemas import ExpectedCheck, GoldenCase
from tests.harness.fake_provider import FakeProvider


def _case(case_id: str = "c1", checks: list[ExpectedCheck] | None = None) -> GoldenCase:
    return GoldenCase(
        id=case_id,
        category="facts",
        prompt="what is it",
        schema_def={"fields": [{"name": "answer", "type": "string"}]},
        checks=checks or [],
    )


def test_select_cases_returns_all_when_none():
    cases = eval_service.select_cases(None)
    assert len(cases) == len(eval_service.load_available_cases())


def test_select_cases_filters_by_id():
    all_cases = eval_service.load_available_cases()
    wanted = [all_cases[0].id, all_cases[2].id]

    cases = eval_service.select_cases(wanted)

    assert [c.id for c in cases] == wanted


def test_select_cases_raises_on_unknown_id():
    with pytest.raises(NotFoundError):
        eval_service.select_cases(["no-such-case"])


def test_build_gateway_for_gateway_has_fallback_chain():
    from app.config import get_settings

    gateway = eval_service.build_gateway_for("gateway", get_settings())

    assert len(gateway._tiers["fast"]) == 2
    assert len(gateway._tiers["smart"]) == 2


def test_build_gateway_for_single_provider():
    from app.config import get_settings

    gateway = eval_service.build_gateway_for("ollama", get_settings())

    assert len(gateway._tiers["fast"]) == 1
    assert gateway._tiers["fast"][0].provider.name == "ollama"


@pytest.mark.asyncio
async def test_stream_cases_emits_case_done_then_done():
    provider = FakeProvider(responses=['{"answer": "Paris"}'])
    candidate = ProviderCandidate(provider, "fake-model")
    gateway = ModelGateway({"fast": [candidate], "smart": [candidate]})
    cases = [
        _case("c1", checks=[ExpectedCheck(field="answer", equals="paris")]),
        _case("c2", checks=[ExpectedCheck(field="answer", equals="london")]),
    ]

    events = [event async for event in eval_service.stream_cases(cases, gateway, concurrency=2)]

    case_done = [e for e in events if e.stage == "case_done"]
    done = [e for e in events if e.stage == "done"]
    assert len(case_done) == 2
    assert {e.case_result.case_id for e in case_done} == {"c1", "c2"}
    assert len(done) == 1
    assert done[0].report.total == 2
    assert done[0].report.passed == 1
    assert done[0].report.failed == 1


@pytest.mark.asyncio
async def test_stream_cases_assigns_distinct_trace_id_per_case():
    provider = FakeProvider(responses=['{"answer": "Paris"}'])
    candidate = ProviderCandidate(provider, "fake-model")
    gateway = ModelGateway({"fast": [candidate], "smart": [candidate]})
    cases = [_case("c1"), _case("c2"), _case("c3")]

    events = [event async for event in eval_service.stream_cases(cases, gateway, concurrency=3)]

    trace_ids = [e.case_result.trace_id for e in events if e.stage == "case_done"]
    assert all(trace_ids)
    assert len(set(trace_ids)) == len(cases)


def _fake_gateway() -> ModelGateway:
    provider = FakeProvider(responses=['{"answer": "Paris"}'])
    candidate = ProviderCandidate(provider, "fake-model")
    return ModelGateway({"fast": [candidate], "smart": [candidate]})


@pytest.mark.asyncio
async def test_persist_run_writes_run_and_case_rows(app, db_session):
    cases = [_case("c1", checks=[ExpectedCheck(field="answer", equals="paris")])]
    report = await run_eval(cases, _fake_gateway(), concurrency=1)

    run_id = await eval_service.persist_run(db_session, report, provider="ollama", cases=cases)

    runs = await eval_service.list_runs(db_session)
    assert len(runs) == 1
    assert runs[0].id == run_id
    assert runs[0].provider == "ollama"
    assert runs[0].total == 1
    assert runs[0].passed == 1
    assert runs[0].source == "api"


@pytest.mark.asyncio
async def test_get_run_detail_returns_case_results(app, db_session):
    cases = [_case("c1", checks=[ExpectedCheck(field="answer", equals="paris")])]
    report = await run_eval(cases, _fake_gateway(), concurrency=1)
    run_id = await eval_service.persist_run(db_session, report, provider="ollama", cases=cases)

    detail = await eval_service.get_run_detail(db_session, run_id)

    assert detail.id == run_id
    assert len(detail.results) == 1
    assert detail.results[0].case_id == "c1"
    assert detail.results[0].prompt == "what is it"
    assert "facts" in detail.by_category


@pytest.mark.asyncio
async def test_get_run_detail_raises_not_found(app, db_session):
    with pytest.raises(NotFoundError):
        await eval_service.get_run_detail(db_session, "no-such-run")


@pytest.mark.asyncio
async def test_get_dashboard_computes_leaderboard_and_deltas(app, db_session):
    gateway = _fake_gateway()
    passing = [_case("c1", checks=[ExpectedCheck(field="answer", equals="paris")])]
    failing = [_case("c1", checks=[ExpectedCheck(field="answer", equals="london")])]

    report1 = await run_eval(passing, gateway, concurrency=1)
    await eval_service.persist_run(db_session, report1, provider="ollama", cases=passing)
    report2 = await run_eval(failing, gateway, concurrency=1)
    await eval_service.persist_run(db_session, report2, provider="ollama", cases=failing)

    dashboard = await eval_service.get_dashboard(db_session)

    assert dashboard.latest is not None
    assert len(dashboard.history) == 2
    assert len(dashboard.leaderboard) == 1
    assert dashboard.leaderboard[0].provider == "ollama"
    assert dashboard.leaderboard[0].runs == 2
    assert dashboard.deltas is not None
    assert abs(dashboard.deltas.pass_rate_delta) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_get_dashboard_empty_has_no_latest_or_deltas(app, db_session):
    dashboard = await eval_service.get_dashboard(db_session)

    assert dashboard.latest is None
    assert dashboard.history == []
    assert dashboard.leaderboard == []
    assert dashboard.deltas is None
