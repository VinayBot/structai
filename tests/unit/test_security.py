import asyncio

import pytest

from app.core.security import (
    hash_password,
    hash_password_async,
    verify_password,
    verify_password_async,
)


@pytest.mark.asyncio
async def test_hash_and_verify_async_roundtrip():
    hashed = await hash_password_async("correct-password1")
    assert await verify_password_async("correct-password1", hashed) is True


@pytest.mark.asyncio
async def test_verify_async_rejects_wrong_password():
    hashed = await hash_password_async("correct-password1")
    assert await verify_password_async("wrong-password1", hashed) is False


@pytest.mark.asyncio
async def test_verify_async_rejects_malformed_hash():
    assert await verify_password_async("whatever", "not-a-real-bcrypt-hash") is False


@pytest.mark.asyncio
async def test_hash_async_is_interoperable_with_the_sync_primitive():
    """hash_password_async/verify_password_async wrap the exact same bcrypt call via
    to_thread - same cost factor, same hash format - not a different scheme, so a hash
    produced by one side must verify correctly on the other."""
    async_hashed = await hash_password_async("correct-password1")
    assert verify_password("correct-password1", async_hashed) is True

    sync_hashed = hash_password("correct-password1")
    assert await verify_password_async("correct-password1", sync_hashed) is True


@pytest.mark.asyncio
async def test_concurrent_hashing_does_not_block_the_event_loop():
    """If hash_password_async regressed to a direct (blocking) bcrypt call, this
    heartbeat coroutine would stall for the duration of the hashing instead of ticking
    continuously throughout it - proving the loop stays responsive during real bcrypt
    work, not just that the function returns the right value."""
    ticks = 0
    stop = False

    async def heartbeat():
        nonlocal ticks
        while not stop:
            ticks += 1
            await asyncio.sleep(0)

    heartbeat_task = asyncio.create_task(heartbeat())
    await asyncio.sleep(0)  # let the heartbeat start accumulating ticks

    ticks_before = ticks
    await asyncio.gather(*[hash_password_async(f"password-{i}") for i in range(8)])
    ticks_after = ticks

    stop = True
    await heartbeat_task

    assert ticks_after - ticks_before > 20, (
        f"heartbeat only ticked {ticks_after - ticks_before} times during concurrent "
        "hashing - the event loop looks blocked"
    )
