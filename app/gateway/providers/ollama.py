import httpx

from app.gateway.providers.base import ModelProvider, ProviderError


class OllamaProvider(ModelProvider):
    name = "ollama"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def generate(self, *, system: str | None, prompt: str, model: str, timeout: float) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"ollama request failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama list_models failed: {exc}") from exc
