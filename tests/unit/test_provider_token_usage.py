"""Token-usage extraction (task 1.5) for both real providers, via httpx.MockTransport
so no live Ollama/Groq is needed. Covers the normal case and - the actually
interesting part - a provider reporting no usage at all, or only half of it, which
must default to 0 rather than crash the whole generate() call."""

import httpx
import pytest

from app.gateway.providers.groq import GroqProvider
from app.gateway.providers.ollama import OllamaProvider


def _client(json_body: dict) -> httpx.AsyncClient:
    handler = lambda _request: httpx.Response(200, json=json_body)  # noqa: E731
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_ollama_extracts_prompt_and_completion_token_counts():
    client = _client({"message": {"content": "hi"}, "prompt_eval_count": 12, "eval_count": 7})
    provider = OllamaProvider("http://ollama.local", client)

    result = await provider.generate(system=None, prompt="hi", model="m", timeout=5)

    assert result.text == "hi"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 7
    await client.aclose()


@pytest.mark.asyncio
async def test_ollama_defaults_to_zero_when_usage_fields_are_entirely_absent():
    """An older Ollama version (or any response shape that just doesn't include
    these fields) must not crash generate() - token accounting is best-effort."""
    client = _client({"message": {"content": "hi"}})
    provider = OllamaProvider("http://ollama.local", client)

    result = await provider.generate(system=None, prompt="hi", model="m", timeout=5)

    assert result.text == "hi"
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_groq_extracts_prompt_and_completion_token_counts():
    client = _client(
        {
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 9},
        }
    )
    provider = GroqProvider("test-key", client)

    result = await provider.generate(system=None, prompt="hi", model="m", timeout=5)

    assert result.text == "hi"
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 9
    await client.aclose()


@pytest.mark.asyncio
async def test_groq_defaults_to_zero_when_usage_key_is_entirely_absent():
    client = _client({"choices": [{"message": {"content": "hi"}}]})
    provider = GroqProvider("test-key", client)

    result = await provider.generate(system=None, prompt="hi", model="m", timeout=5)

    assert result.text == "hi"
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_groq_defaults_to_zero_when_usage_is_only_partially_reported():
    """Half-reported usage (seen from some OpenAI-compatible gateways) must fill in
    0 for the missing side rather than KeyError-ing the whole call."""
    client = _client(
        {
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 15},
        }
    )
    provider = GroqProvider("test-key", client)

    result = await provider.generate(system=None, prompt="hi", model="m", timeout=5)

    assert result.prompt_tokens == 15
    assert result.completion_tokens == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_groq_defaults_to_zero_when_usage_value_is_explicitly_null():
    """Some gateways send "usage": null rather than omitting the key - `or {}`
    in the provider must handle that too, not just a missing key."""
    client = _client({"choices": [{"message": {"content": "hi"}}], "usage": None})
    provider = GroqProvider("test-key", client)

    result = await provider.generate(system=None, prompt="hi", model="m", timeout=5)

    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    await client.aclose()
