import pytest

_SCHEMA_BODY = {"fields": [{"name": "title", "type": "string"}]}


@pytest.mark.asyncio
async def test_metrics_summary_requires_auth(client):
    resp = await client.get("/metrics/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metrics_summary_reflects_real_requests(client, auth_headers):
    await client.get("/health")
    await client.get("/health")

    resp = await client.get("/metrics/summary", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body["totals"]["requests"] >= 2
    endpoint_paths = {e["path"] for e in body["by_endpoint"]}
    assert "/health" in endpoint_paths
    assert "2xx" in body["by_status"]
    assert len(body["timeseries"]) == 60


@pytest.mark.asyncio
async def test_metrics_summary_reports_structured_answer_provider_calls(
    app, client, auth_headers
):
    from app.gateway.factory import get_gateway
    from app.gateway.router import ModelGateway, ProviderCandidate
    from tests.harness.fake_provider import FakeProvider

    fake = FakeProvider(name="metrics-route-fake", responses=['{"title": "hi"}'])
    app.dependency_overrides[get_gateway] = lambda: ModelGateway(
        {"fast": [ProviderCandidate(fake, "fake-model")]}
    )

    body = {"prompt": "say hi", "schema_def": _SCHEMA_BODY}
    answer_resp = await client.post("/structured/answer", json=body, headers=auth_headers)
    assert answer_resp.status_code == 200

    resp = await client.get("/metrics/summary", headers=auth_headers)
    assert resp.status_code == 200

    providers = {(p["provider"], p["model"]) for p in resp.json()["providers"]}
    assert ("metrics-route-fake", "fake-model") in providers


@pytest.mark.asyncio
async def test_metrics_endpoint_byte_for_byte_unaffected(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "structai_http_requests_total" in resp.text
