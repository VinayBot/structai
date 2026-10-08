import os
import tempfile
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_tmp_dir = tempfile.mkdtemp(prefix="structai-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long-for-hs256"
os.environ["UPLOAD_DIR"] = f"{_tmp_dir}/uploads"
# Disabled by default so the suite never depends on live DNS; tests of the MX
# check itself monkeypatch app.guardrails.email._check_mx directly instead.
os.environ["EMAIL_CHECK_MX"] = "false"

from app.config import get_settings  # noqa: E402
from app.core.build_info import reset_build_info_cache  # noqa: E402
from app.core.http_client import reset_http_client_cache  # noqa: E402
from app.core.metrics_buffer import reset_request_buffer_cache  # noqa: E402
from app.core.tracing import reset_tracer_cache  # noqa: E402
from app.db import Base, get_engine, get_session_maker, reset_db_caches  # noqa: E402
from app.gateway.factory import reset_gateway_cache  # noqa: E402
from app.guardrails.rate_limit import reset_rate_limiter_cache  # noqa: E402

get_settings.cache_clear()
reset_db_caches()
reset_gateway_cache()
reset_rate_limiter_cache()
reset_tracer_cache()
reset_build_info_cache()
reset_request_buffer_cache()
reset_http_client_cache()


@pytest_asyncio.fixture
async def app():
    from app.main import create_app

    application = create_app()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield application

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_caches():
    get_settings.cache_clear()
    reset_db_caches()
    reset_gateway_cache()
    reset_rate_limiter_cache()
    reset_tracer_cache()
    reset_build_info_cache()
    reset_request_buffer_cache()
    reset_http_client_cache()
    yield


@pytest_asyncio.fixture
async def db_session(app) -> AsyncIterator[AsyncSession]:
    async with get_session_maker()() as session:
        yield session


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    email = "fixture-user@example.com"
    password = "fixturepass1"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    from app.models.user import User

    email = "fixture-admin@example.com"
    password = "fixturepass1"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = "admin"
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
