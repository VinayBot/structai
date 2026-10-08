import os

import pytest

from app.config import get_settings
from app.core.http_client import get_http_client, reset_http_client_cache
from app.main import create_app, lifespan


@pytest.mark.asyncio
async def test_lifespan_opens_and_closes_the_shared_http_client():
    """The app lifespan (not exercised by the `app` test fixture, which builds the
    FastAPI instance directly without entering it) is what's actually responsible for
    warming the shared client on startup and closing it on shutdown - this drives it
    for real rather than just trusting the two one-line calls inside it."""
    reset_http_client_cache()
    application = create_app()

    async with lifespan(application):
        client = get_http_client()
        assert client.is_closed is False

    assert client.is_closed is True


def test_refuses_to_start_with_fake_gateway_in_production():
    """USE_FAKE_GATEWAY (tests/harness/mock_app.py, for CI e2e runs) must be
    structurally impossible to run against a real deployment. Settings.env reads
    from the ENV var (not ENVIRONMENT) - see .env.example's own ENV=development."""
    os.environ["USE_FAKE_GATEWAY"] = "true"
    os.environ["ENV"] = "production"
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="production"):
            create_app()
    finally:
        del os.environ["USE_FAKE_GATEWAY"]
        del os.environ["ENV"]
        get_settings.cache_clear()


def test_fake_gateway_is_fine_outside_production():
    os.environ["USE_FAKE_GATEWAY"] = "true"
    os.environ["ENV"] = "test"
    get_settings.cache_clear()
    try:
        create_app()  # must not raise
    finally:
        del os.environ["USE_FAKE_GATEWAY"]
        del os.environ["ENV"]
        get_settings.cache_clear()
