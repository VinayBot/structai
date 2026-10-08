import httpx

from app.gateway.providers.base import GenerationResult, ModelProvider, ProviderError


class GroqProvider(ModelProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api.groq.com/openai/v1",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client

    async def generate(
        self, *, system: str | None, prompt: str, model: str, timeout: float
    ) -> GenerationResult:
        if not self.api_key:
            raise ProviderError("groq api key not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            # timeout is passed per-request, not baked into the shared client, so
            # each candidate's own configured timeout still applies even though the
            # underlying connection pool is shared across every provider/request.
            resp = await self._http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "messages": messages},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # usage is OpenAI-shaped (data["usage"]["prompt_tokens"/"completion_tokens"]),
            # but some gateways/models omit it or only report one side - never let
            # token accounting fail the actual generation, default each side to 0.
            usage = data.get("usage") or {}
            return GenerationResult(
                text=data["choices"][0]["message"]["content"],
                prompt_tokens=usage.get("prompt_tokens", 0) or 0,
                completion_tokens=usage.get("completion_tokens", 0) or 0,
            )
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"groq request failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            resp = await self._http_client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]
        except httpx.HTTPError as exc:
            raise ProviderError(f"groq list_models failed: {exc}") from exc
