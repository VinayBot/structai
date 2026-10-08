from functools import lru_cache

import httpx

from app.config import get_settings


@lru_cache
def get_http_client() -> httpx.AsyncClient:
    """One long-lived, connection-pooled client shared by every provider (and the
    arch-service health check), instead of each call opening its own. Lazily created
    on first access - same lru_cache singleton pattern as app.db's engine/session-maker
    - and explicitly warmed by the app lifespan so the pool is ready before the first
    real request rather than paying setup cost on whichever request happens to ask
    first."""
    settings = get_settings()
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
        )
    )


async def aclose_http_client() -> None:
    """Called from the app lifespan on shutdown. A no-op if nothing ever actually
    created the client (e.g. the process never served a request that needed one)."""
    if get_http_client.cache_info().currsize:
        await get_http_client().aclose()
    get_http_client.cache_clear()


def reset_http_client_cache() -> None:
    """Test hook, mirrors app.db.reset_db_caches/app.gateway.factory.reset_gateway_cache.
    Forgets the cached client WITHOUT closing it - httpx.AsyncClient is bound to the
    event loop it was created in, and each test may run in a different loop, so the
    cache must be cleared between tests rather than reusing one client everywhere."""
    get_http_client.cache_clear()
