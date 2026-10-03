import os

import pytest

from app.gateway.factory import get_gateway
from app.gateway.router import ModelGateway, ProviderCandidate
from tests.harness.fake_provider import FakeProvider

_SCHEMA_BODY = {"fields": [{"name": "title", "type": "string"}]}


@pytest.mark.asyncio
async def test_requests_beyond_the_per_minute_limit_are_rejected(app, client, auth_headers):
    os.environ["RATE_LIMIT_PER_MIN"] = "2"
    from app.config import get_settings

    get_settings.cache_clear()
    from app.guardrails.rate_limit import reset_rate_limiter_cache

    reset_rate_limiter_cache()

    fake = FakeProvider(responses=['{"title": "hello"}'] * 10)
    app.dependency_overrides[get_gateway] = lambda: ModelGateway(
        {"fast": [ProviderCandidate(fake, "fake-model")]}
    )

    body = {"prompt": "say hello", "schema_def": _SCHEMA_BODY}
    first = await client.post("/structured/answer", json=body, headers=auth_headers)
    second = await client.post("/structured/answer", json=body, headers=auth_headers)
    third = await client.post("/structured/answer", json=body, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"

    retry_after_seconds = third.json()["error"]["retry_after_seconds"]
    assert retry_after_seconds is not None and 0.0 <= retry_after_seconds <= 60.0
    assert int(third.headers["retry-after"]) >= 1

    del os.environ["RATE_LIMIT_PER_MIN"]
