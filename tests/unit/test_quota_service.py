import asyncio

import pytest

from app.core.errors import RateLimitError
from app.db import get_session_maker
from app.services.quota_service import check_and_increment


@pytest.mark.asyncio
async def test_allows_until_limit(app):
    session_maker = get_session_maker()
    async with session_maker() as session:
        await check_and_increment(session, scope="user", key="u1", limit=2)
        await check_and_increment(session, scope="user", key="u1", limit=2)

    async with session_maker() as session:
        with pytest.raises(RateLimitError):
            await check_and_increment(session, scope="user", key="u1", limit=2)


@pytest.mark.asyncio
async def test_concurrent_requests_increment_atomically_without_crashing(app):
    session_maker = get_session_maker()

    async def _call():
        async with session_maker() as session:
            await check_and_increment(session, scope="user", key="concurrent-user", limit=100)

    # Reproduces the real race: multiple separate sessions all see "no row yet"
    # at once. Before the atomic-upsert fix, this raised an unhandled
    # IntegrityError (UNIQUE constraint) instead of just counting correctly.
    await asyncio.gather(*[_call() for _ in range(10)])

    async with session_maker() as session:
        with pytest.raises(RateLimitError):
            for _ in range(91):
                await check_and_increment(session, scope="user", key="concurrent-user", limit=100)
