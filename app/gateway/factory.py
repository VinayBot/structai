from functools import lru_cache

from fastapi import Depends

from app.config import Settings, get_settings
from app.gateway.providers.groq import GroqProvider
from app.gateway.providers.ollama import OllamaProvider
from app.gateway.router import ModelGateway, ProviderCandidate
from app.schemas.live_run import LiveRunRequest


def build_gateway(settings: Settings) -> ModelGateway:
    ollama = OllamaProvider(settings.ollama_base_url)
    groq = GroqProvider(settings.groq_api_key)

    return ModelGateway(
        {
            "fast": [
                ProviderCandidate(ollama, settings.ollama_fast_model),
                ProviderCandidate(groq, settings.groq_fast_model),
            ],
            "smart": [
                ProviderCandidate(ollama, settings.ollama_smart_model),
                ProviderCandidate(groq, settings.groq_smart_model),
            ],
        }
    )


@lru_cache
def get_gateway() -> ModelGateway:
    return build_gateway(get_settings())


def reset_gateway_cache() -> None:
    get_gateway.cache_clear()


def build_single_provider_gateway(name: str, settings: Settings) -> ModelGateway:
    if name == "ollama":
        candidate = ProviderCandidate(
            OllamaProvider(settings.ollama_base_url), settings.ollama_fast_model
        )
    elif name == "groq":
        candidate = ProviderCandidate(GroqProvider(settings.groq_api_key), settings.groq_fast_model)
    else:
        raise ValueError(f"unknown provider: {name}")
    return ModelGateway({"fast": [candidate], "smart": [candidate]})


def build_live_run_gateway(
    *, provider: str, model: str | None, tier: str, strict_provider: bool, settings: Settings
) -> ModelGateway:
    """Caller-controlled gateway for the Architecture tab's Live Run feature.

    `provider` pins a preferred candidate ("ollama"/"groq"); `strict_provider` decides
    whether the other provider is kept as a fallback candidate or dropped entirely.
    `provider="auto"` always uses both, in the same order as `build_gateway`.
    """
    ollama = OllamaProvider(settings.ollama_base_url)
    groq = GroqProvider(settings.groq_api_key)

    ollama_default = settings.ollama_fast_model if tier == "fast" else settings.ollama_smart_model
    groq_default = settings.groq_fast_model if tier == "fast" else settings.groq_smart_model

    ollama_candidate = ProviderCandidate(
        ollama, model if provider == "ollama" and model else ollama_default
    )
    groq_candidate = ProviderCandidate(
        groq, model if provider == "groq" and model else groq_default
    )

    if provider == "ollama":
        candidates = [ollama_candidate] if strict_provider else [ollama_candidate, groq_candidate]
    elif provider == "groq":
        candidates = [groq_candidate] if strict_provider else [groq_candidate, ollama_candidate]
    else:
        candidates = [ollama_candidate, groq_candidate]

    return ModelGateway({tier: candidates})


async def get_live_run_gateway(
    body: LiveRunRequest, settings: Settings = Depends(get_settings)
) -> ModelGateway:
    return build_live_run_gateway(
        provider=body.provider,
        model=body.model,
        tier=body.tier,
        strict_provider=body.strict_provider,
        settings=settings,
    )
