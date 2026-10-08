import httpx
import pytest

from app.core.http_client import aclose_http_client, get_http_client, reset_http_client_cache
from app.gateway.providers.groq import GroqProvider
from app.gateway.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_get_http_client_returns_the_same_instance_across_calls():
    reset_http_client_cache()
    try:
        first = get_http_client()
        second = get_http_client()
        assert first is second
    finally:
        await aclose_http_client()


@pytest.mark.asyncio
async def test_aclose_http_client_closes_the_cached_client_and_resets_the_cache():
    reset_http_client_cache()
    client = get_http_client()
    assert client.is_closed is False

    await aclose_http_client()
    assert client.is_closed is True

    # A fresh get_http_client() after close builds a brand new, open client - the
    # old, now-closed one is never handed back out again.
    new_client = get_http_client()
    assert new_client is not client
    assert new_client.is_closed is False
    await aclose_http_client()


@pytest.mark.asyncio
async def test_aclose_http_client_is_a_noop_if_never_created():
    reset_http_client_cache()
    await aclose_http_client()  # must not raise just because nothing used it yet


def _mock_transport(capture: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        capture.append(request)
        path = request.url.path
        if path.endswith("/api/chat"):
            return httpx.Response(200, json={"message": {"content": "hi from ollama"}})
        if path.endswith("/chat/completions"):
            return httpx.Response(200, json={"choices": [{"message": {"content": "hi from groq"}}]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_ollama_and_groq_providers_share_the_same_injected_client_instance():
    """The gateway factory builds every provider with one shared client (task 1.4) -
    this proves a single httpx.AsyncClient really is usable by, and reused across,
    both provider implementations rather than each wanting its own."""
    requests: list[httpx.Request] = []
    client = httpx.AsyncClient(transport=_mock_transport(requests))

    ollama = OllamaProvider("http://ollama.local", client)
    groq = GroqProvider("test-key", client)

    ollama_text = await ollama.generate(system=None, prompt="hi", model="m", timeout=5)
    groq_text = await groq.generate(system=None, prompt="hi", model="m", timeout=5)

    assert ollama_text == "hi from ollama"
    assert groq_text == "hi from groq"
    assert ollama._http_client is client
    assert groq._http_client is client
    assert len(requests) == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_provider_call_passes_its_own_timeout_on_the_shared_client():
    """A shared client has one connection pool but must not flatten every call to one
    global timeout - each generate() call's own `timeout` has to reach the actual
    request, not just whatever the client was constructed with."""
    seen_timeouts: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # httpx attaches the resolved per-request timeout here regardless of
        # transport - this is the real value that would govern the request, not an
        # indirect proxy for it.
        seen_timeouts.append(request.extensions.get("timeout", {}))
        return httpx.Response(200, json={"message": {"content": "ok"}})

    transport = httpx.MockTransport(handler)
    # The client's own default is deliberately far from the per-call value below -
    # if generate() ever stopped passing its own timeout, this is the value that
    # would leak through instead, and the assertion would catch it.
    client = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(999))

    provider = OllamaProvider("http://ollama.local", client)
    await provider.generate(system=None, prompt="hi", model="m", timeout=12.5)

    assert seen_timeouts[-1]["read"] == 12.5
    await client.aclose()
