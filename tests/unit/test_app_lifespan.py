import pytest

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
