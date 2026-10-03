import json

import pytest

from app.services import eval_service
from tests.harness.fake_provider import FakeProvider


def _fake_gateway_for(_provider: str, _settings) -> object:
    from app.gateway.router import ModelGateway, ProviderCandidate

    candidate = ProviderCandidate(FakeProvider(responses=['{"answer": "Paris"}']), "fake-model")
    return ModelGateway({"fast": [candidate], "smart": [candidate]})


@pytest.mark.asyncio
async def test_list_cases_requires_auth(client):
    resp = await client.get("/eval/cases")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_cases_returns_golden_cases(client, auth_headers):
    resp = await client.get("/eval/cases", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(eval_service.load_available_cases())
    assert "id" in body[0]
    assert "schema_def" in body[0]


@pytest.mark.asyncio
async def test_run_unknown_case_id_returns_404(client, auth_headers):
    resp = await client.post(
        "/eval/run",
        json={"case_ids": ["no-such-case"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_eval_against_fake_gateway(client, auth_headers, monkeypatch):
    monkeypatch.setattr(eval_service, "build_gateway_for", _fake_gateway_for)
    all_cases = eval_service.load_available_cases()
    case_ids = [c.id for c in all_cases[:2]]

    resp = await client.post(
        "/eval/run",
        json={"case_ids": case_ids, "provider": "ollama", "concurrency": 2},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_run_eval_stream_emits_case_done_then_done(client, auth_headers, monkeypatch):
    monkeypatch.setattr(eval_service, "build_gateway_for", _fake_gateway_for)
    all_cases = eval_service.load_available_cases()
    case_ids = [c.id for c in all_cases[:2]]

    async with client.stream(
        "POST",
        "/eval/run/stream",
        json={"case_ids": case_ids, "provider": "ollama", "concurrency": 2},
        headers=auth_headers,
    ) as resp:
        assert resp.status_code == 200
        lines = [line async for line in resp.aiter_lines() if line.startswith("data: ")]

    stages = [json.loads(line.removeprefix("data: "))["stage"] for line in lines]
    assert stages == ["case_done", "case_done", "done"]


@pytest.mark.asyncio
async def test_run_eval_persists_a_run_row(client, auth_headers, monkeypatch):
    monkeypatch.setattr(eval_service, "build_gateway_for", _fake_gateway_for)
    all_cases = eval_service.load_available_cases()
    case_ids = [c.id for c in all_cases[:2]]

    resp = await client.post(
        "/eval/run",
        json={"case_ids": case_ids, "provider": "ollama", "concurrency": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    runs_resp = await client.get("/eval/runs", headers=auth_headers)
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert len(runs) == 1
    assert runs[0]["total"] == 2
    assert runs[0]["source"] == "api"


@pytest.mark.asyncio
async def test_run_eval_stream_persists_a_run_row(client, auth_headers, monkeypatch):
    monkeypatch.setattr(eval_service, "build_gateway_for", _fake_gateway_for)
    all_cases = eval_service.load_available_cases()
    case_ids = [c.id for c in all_cases[:2]]

    async with client.stream(
        "POST",
        "/eval/run/stream",
        json={"case_ids": case_ids, "provider": "ollama", "concurrency": 2},
        headers=auth_headers,
    ) as resp:
        assert resp.status_code == 200
        async for _ in resp.aiter_lines():
            pass

    runs_resp = await client.get("/eval/runs", headers=auth_headers)
    assert len(runs_resp.json()) == 1


@pytest.mark.asyncio
async def test_list_runs_requires_auth(client):
    resp = await client.get("/eval/runs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_run_detail_404_for_unknown_id(client, auth_headers):
    resp = await client.get("/eval/runs/no-such-run", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_run_detail_returns_full_results(client, auth_headers, monkeypatch):
    monkeypatch.setattr(eval_service, "build_gateway_for", _fake_gateway_for)
    all_cases = eval_service.load_available_cases()
    case_ids = [c.id for c in all_cases[:1]]

    run_resp = await client.post(
        "/eval/run",
        json={"case_ids": case_ids, "provider": "ollama"},
        headers=auth_headers,
    )
    run_id = (await client.get("/eval/runs", headers=auth_headers)).json()[0]["id"]

    detail_resp = await client.get(f"/eval/runs/{run_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["id"] == run_id
    assert len(body["results"]) == 1
    assert run_resp.status_code == 200


@pytest.mark.asyncio
async def test_get_dashboard_returns_latest_and_leaderboard(client, auth_headers, monkeypatch):
    monkeypatch.setattr(eval_service, "build_gateway_for", _fake_gateway_for)
    all_cases = eval_service.load_available_cases()
    case_ids = [c.id for c in all_cases[:1]]

    await client.post(
        "/eval/run",
        json={"case_ids": case_ids, "provider": "ollama"},
        headers=auth_headers,
    )

    resp = await client.get("/eval/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["latest"] is not None
    assert len(body["history"]) == 1
    assert len(body["leaderboard"]) == 1
