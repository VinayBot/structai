from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Raised when a provider fails to produce a response."""


@dataclass
class GenerationResult:
    text: str
    # Token usage is best-effort: a provider that doesn't report it (or reports it
    # only partially) defaults the missing side to 0 rather than failing the call -
    # token accounting is metrics/billing information, not something that should be
    # able to break generation itself.
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self, *, system: str | None, prompt: str, model: str, timeout: float
    ) -> GenerationResult:
        raise NotImplementedError
