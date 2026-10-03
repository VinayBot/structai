import pytest

_SCHEMA_BODY = {"fields": [{"name": "title", "type": "string"}]}


@pytest.mark.asyncio
async def test_metrics_endpoint_is_public_and_exposes_known_series(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "structai_http_requests_total" in body
    assert "structai_http_request_duration_seconds" in body


@pytest.mark.asyncio
async def test_metrics_counts_requests(client):
    await client.get("/health")
    resp = await client.get("/metrics")
    body = resp.text
    assert 'path="/health"' in body


@pytest.mark.asyncio
async def test_traces_requires_auth(client):
    resp = await client.get("/traces")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_traces_records_structured_answer_spans(app, client, auth_headers):
    from app.gateway.factory import get_gateway
    from app.gateway.router import ModelGateway, ProviderCandidate
    from tests.harness.fake_provider import FakeProvider

    fake = FakeProvider(responses=['{"title": "hi"}'])
    app.dependency_overrides[get_gateway] = lambda: ModelGateway(
        {"fast": [ProviderCandidate(fake, "fake-model")]}
    )

    body = {"prompt": "say hi", "schema_def": _SCHEMA_BODY}
    await client.post("/structured/answer", json=body, headers=auth_headers)

    resp = await client.get("/traces", headers=auth_headers)
    assert resp.status_code == 200
    spans = resp.json()
    names = {s["name"] for s in spans}
    assert "structured.loop" in names
    assert "gateway.generate" in names

    gen_span = next(s for s in spans if s["name"] == "gateway.generate")
    assert gen_span["attributes"]["provider"] == "fake"
    assert gen_span["status"] == "ok"


@pytest.mark.asyncio
async def test_traces_limit_param(client, auth_headers):
    resp = await client.get("/traces?limit=1", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) <= 1
