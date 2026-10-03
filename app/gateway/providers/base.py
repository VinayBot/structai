from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Raised when a provider fails to produce a response."""


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, *, system: str | None, prompt: str, model: str, timeout: float) -> str:
        raise NotImplementedError
