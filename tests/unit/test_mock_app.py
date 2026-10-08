"""tests/harness/mock_app.py (task 1.8) - the FastAPI entrypoint CI's e2e job
launches via uvicorn, wired to mock_provider.MockModelProvider instead of a real
gateway.

build_mock_app() permanently monkeypatches app.gateway.factory's and
app.services.eval_service's gateway-construction functions - correct for its real
use case (a dedicated uvicorn process started fresh for e2e), but it must not leak
into the rest of this pytest session, which runs in one shared process. Every test
below that actually calls build_mock_app() goes through the `mock_client` fixture,
which snapshots those module attributes first and restores them afterward.
mock_app.py's own module-level `app` is lazy (PEP 562 `__getattr__`) specifically so
that importing build_mock_app here, by itself, triggers none of this."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.gateway.factory as gateway_factory
import app.services.eval_service as eval_service_module
from app.config import get_settings
from app.db import Base, get_engine
from tests.harness.mock_app import build_mock_app


def test_build_mock_app_requires_use_fake_gateway(monkeypatch):
    monkeypatch.setenv("USE_FAKE_GATEWAY", "false")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="USE_FAKE_GATEWAY"):
        build_mock_app()


@pytest_asyncio.fixture
async def mock_client(monkeypatch):
    monkeypatch.setenv("USE_FAKE_GATEWAY", "true")
    get_settings.cache_clear()

    originals = (
        gateway_factory.build_gateway,
        gateway_factory.build_single_provider_gateway,
        gateway_factory.build_live_run_gateway,
        eval_service_module.build_gateway,
        eval_service_module.build_single_provider_gateway,
    )
    application = build_mock_app()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        (
            gateway_factory.build_gateway,
            gateway_factory.build_single_provider_gateway,
            gateway_factory.build_live_run_gateway,
            eval_service_module.build_gateway,
            eval_service_module.build_single_provider_gateway,
        ) = originals


async def _mock_auth_headers(client: AsyncClient) -> dict[str, str]:
    email = "mock-app-user@example.com"
    password = "password1"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_structured_answer_uses_the_mock_provider_not_a_real_gateway(mock_client):
    headers = await _mock_auth_headers(mock_client)

    resp = await mock_client.post(
        "/api/v1/structured/answer",
        json={
            "prompt": "whatever",
            "schema_def": {"fields": [{"name": "title", "type": "string"}]},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "mock"
    assert isinstance(body["data"]["title"], str)


@pytest.mark.asyncio
async def test_eval_run_uses_the_mock_provider_too(mock_client):
    """eval_service.build_gateway_for bypasses the get_gateway dependency entirely
    (it's called directly from app/routes/eval.py, not resolved through FastAPI's
    DI) - this is the path that needed its own, separate patch in mock_app.py."""
    headers = await _mock_auth_headers(mock_client)

    cases_resp = await mock_client.get("/api/v1/eval/cases", headers=headers)
    case_id = cases_resp.json()[0]["id"]

    resp = await mock_client.post(
        "/api/v1/eval/run",
        json={"provider": "gateway", "case_ids": [case_id], "concurrency": 1},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["passed"] == 1  # the mock answers every golden case correctly
    assert body["results"][0]["provider"] == "mock"
