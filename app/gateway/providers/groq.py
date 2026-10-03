import httpx

from app.gateway.providers.base import ModelProvider, ProviderError


class GroqProvider(ModelProvider):
    name = "groq"

    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def generate(self, *, system: str | None, prompt: str, model: str, timeout: float) -> str:
        if not self.api_key:
            raise ProviderError("groq api key not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": model, "messages": messages},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"groq request failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                return [m["id"] for m in resp.json().get("data", [])]
        except httpx.HTTPError as exc:
            raise ProviderError(f"groq list_models failed: {exc}") from exc
