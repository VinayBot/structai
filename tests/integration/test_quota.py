import os

import pytest

from app.gateway.factory import get_gateway
from app.gateway.router import ModelGateway, ProviderCandidate
from tests.harness.fake_provider import FakeProvider

_SCHEMA_BODY = {"fields": [{"name": "title", "type": "string"}]}


@pytest.mark.asyncio
async def test_daily_quota_blocks_once_exceeded(app, client, auth_headers):
    os.environ["DAILY_QUOTA_USER"] = "2"
    from app.config import get_settings

    get_settings.cache_clear()

    fake = FakeProvider(responses=['{"title": "hello"}'] * 10)
    app.dependency_overrides[get_gateway] = lambda: ModelGateway(
        {"fast": [ProviderCandidate(fake, "fake-model")]}
    )

    body = {"prompt": "say hello", "schema_def": _SCHEMA_BODY}
    first = await client.post("/api/v1/structured/answer", json=body, headers=auth_headers)
    second = await client.post("/api/v1/structured/answer", json=body, headers=auth_headers)
    third = await client.post("/api/v1/structured/answer", json=body, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"

    del os.environ["DAILY_QUOTA_USER"]
