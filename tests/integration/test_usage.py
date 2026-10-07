import pytest


@pytest.mark.asyncio
async def test_usage_starts_at_zero(client, auth_headers):
    resp = await client.get("/api/v1/usage", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_count_today"] == 0
    assert body["user_limit"] > 0


@pytest.mark.asyncio
async def test_usage_counts_structured_calls(app, client, auth_headers):
    from app.gateway.factory import get_gateway
    from app.gateway.router import ModelGateway, ProviderCandidate
    from tests.harness.fake_provider import FakeProvider

    fake = FakeProvider(responses=['{"title": "hi"}'])
    app.dependency_overrides[get_gateway] = lambda: ModelGateway(
        {"fast": [ProviderCandidate(fake, "fake-model")]}
    )

    body = {"prompt": "say hi", "schema_def": {"fields": [{"name": "title", "type": "string"}]}}
    await client.post("/api/v1/structured/answer", json=body, headers=auth_headers)

    resp = await client.get("/api/v1/usage", headers=auth_headers)
    assert resp.json()["user_count_today"] == 1
