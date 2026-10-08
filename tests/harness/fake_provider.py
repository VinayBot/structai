import asyncio

from app.gateway.providers.base import GenerationResult, ModelProvider, ProviderError


class FakeProvider(ModelProvider):
    def __init__(
        self,
        name: str = "fake",
        responses: list[str] | None = None,
        fail_times: int = 0,
        delay: float = 0.0,
        raises: Exception | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ):
        self.name = name
        self.responses = responses
        self.fail_times = fail_times
        self.delay = delay
        self.raises = raises
        # Default 0 (not simulated) so existing tests that don't care about token
        # accounting see the exact same behavior as before it existed; tests that do
        # care pass these explicitly.
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.calls = 0
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    async def generate(
        self, *, system: str | None, prompt: str, model: str, timeout: float
    ) -> GenerationResult:
        self.calls += 1
        self.prompts.append(prompt)
        self.systems.append(system)

        if self.delay:
            await asyncio.sleep(self.delay)

        if self.raises is not None:
            raise self.raises

        if self.calls <= self.fail_times:
            raise ProviderError(f"{self.name} scripted failure #{self.calls}")

        text = "{}"
        if self.responses:
            index = (self.calls - self.fail_times - 1) % len(self.responses)
            text = self.responses[index]

        return GenerationResult(
            text=text,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        )
