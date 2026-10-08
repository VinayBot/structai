"""Entrypoint for a StructAI backend wired to tests/harness/mock_provider.py's fake
model instead of real Ollama/Groq - lets frontend/e2e Playwright specs run in CI
without a reachable gateway. Launch with:

    USE_FAKE_GATEWAY=true ENV=test uv run uvicorn tests.harness.mock_app:app --port 8000

USE_FAKE_GATEWAY must be true (app.main.create_app() refuses to start otherwise -
see the import-time check below, which is a second, independent guard on top of
that one) and ENV must not be "production" (create_app() refuses that combination
outright, regardless of this file).
"""

import app.gateway.factory as gateway_factory
import app.services.eval_service as eval_service
from app.config import get_settings
from app.gateway.router import ModelGateway, ProviderCandidate
from tests.harness.mock_provider import MockModelProvider


def _patch_gateway_construction() -> None:
    """Every real path to a ModelGateway ends up calling one of the three functions
    patched here - app.gateway.factory.build_gateway (get_gateway(), used by
    /structured/answer and /structured/answer/stream), build_live_run_gateway
    (get_live_run_gateway(), used by the Architecture tab's Live Run), and
    build_single_provider_gateway (used by eval_service.build_gateway_for).

    eval_service.py did `from app.gateway.factory import build_gateway,
    build_single_provider_gateway` - a direct name import - so it holds its own
    reference to the original functions; patching app.gateway.factory's attributes
    alone would not reach eval_service's calls, which is why its own module
    attributes are patched too, not just the factory module's.
    """
    provider = MockModelProvider()

    def _mock_gateway(*_args: object, **_kwargs: object) -> ModelGateway:
        candidate = ProviderCandidate(provider, "mock-model")
        return ModelGateway({"fast": [candidate], "smart": [candidate]})

    gateway_factory.build_gateway = _mock_gateway
    gateway_factory.build_single_provider_gateway = _mock_gateway
    gateway_factory.build_live_run_gateway = _mock_gateway
    eval_service.build_gateway = _mock_gateway
    eval_service.build_single_provider_gateway = _mock_gateway


def build_mock_app():
    settings = get_settings()
    if not settings.use_fake_gateway:
        raise RuntimeError(
            "tests.harness.mock_app requires USE_FAKE_GATEWAY=true - it exists only "
            "to run e2e tests against a fake model, never a real deployment"
        )

    # Patched before anything constructs a real app instance - nothing here calls
    # a gateway constructor eagerly today, but there's no reason to rely on that.
    _patch_gateway_construction()

    from app.main import create_app

    return create_app()


def __getattr__(name: str):
    """PEP 562 lazy module attribute: `app` is only built on first access, not on
    import. uvicorn's `tests.harness.mock_app:app` target still works identically
    (it accesses the attribute once), but something that only imports
    build_mock_app itself - e.g. a unit test exercising this module from inside the
    same process as the rest of the suite - no longer triggers
    _patch_gateway_construction()'s permanent, process-wide monkeypatching just by
    virtue of importing this module at all."""
    if name == "app":
        return build_mock_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
