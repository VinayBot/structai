import httpx

from app.gateway.providers.base import ModelProvider, ProviderError


class OllamaProvider(ModelProvider):
    name = "ollama"

    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client

    async def generate(self, *, system: str | None, prompt: str, model: str, timeout: float) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            # timeout is passed per-request, not baked into the shared client, so
            # each candidate's own configured timeout still applies even though the
            # underlying connection pool is shared across every provider/request.
            resp = await self._http_client.post(
                f"{self.base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"ollama request failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            resp = await self._http_client.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama list_models failed: {exc}") from exc
