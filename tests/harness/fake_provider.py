import asyncio

from app.gateway.providers.base import ModelProvider, ProviderError


class FakeProvider(ModelProvider):
    def __init__(
        self,
        name: str = "fake",
        responses: list[str] | None = None,
        fail_times: int = 0,
        delay: float = 0.0,
        raises: Exception | None = None,
    ):
        self.name = name
        self.responses = responses
        self.fail_times = fail_times
        self.delay = delay
        self.raises = raises
        self.calls = 0
        self.prompts: list[str] = []

    async def generate(self, *, system: str | None, prompt: str, model: str, timeout: float) -> str:
        self.calls += 1
        self.prompts.append(prompt)

        if self.delay:
            await asyncio.sleep(self.delay)

        if self.raises is not None:
            raise self.raises

        if self.calls <= self.fail_times:
            raise ProviderError(f"{self.name} scripted failure #{self.calls}")

        if not self.responses:
            return "{}"

        index = (self.calls - self.fail_times - 1) % len(self.responses)
        return self.responses[index]
