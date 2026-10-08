import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.http_client import aclose_http_client, get_http_client
from app.core.logging import configure_logging
from app.core.middleware import metrics_middleware, request_id_middleware
from app.core.otel import init_otel
from app.db import get_session_maker
from app.routes.admin import router as admin_router
from app.routes.arch import router as arch_router
from app.routes.auth import router as auth_router
from app.routes.chats import router as chats_router
from app.routes.eval import router as eval_router
from app.routes.files import router as files_router
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.projects import router as projects_router
from app.routes.schemas import router as schemas_router
from app.routes.search import router as search_router
from app.routes.structured import router as structured_router
from app.routes.traces import router as traces_router
from app.routes.usage import router as usage_router
from app.services.eval_import import import_existing_reports

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Warms the shared connection pool every provider call uses before the app starts
    # serving traffic, rather than paying its setup cost on whichever request happens
    # to need a provider first.
    get_http_client()
    init_otel(get_settings())
    try:
        imported = await import_existing_reports(get_session_maker())
        if imported:
            logger.info("imported %d historical eval report(s) on startup", imported)
    except Exception:
        logger.warning("skipping eval report import: DB not ready", exc_info=True)
    yield
    await aclose_http_client()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title="StructAI", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(metrics_middleware)
    app.middleware("http")(request_id_middleware)

    register_exception_handlers(app)

    # /health and /metrics stay unversioned: infra probes and Prometheus scrape
    # targets are conventionally outside API versioning, consumed by tooling
    # that doesn't track the API's own version lifecycle.
    app.include_router(health_router)
    app.include_router(metrics_router)

    api_v1 = "/api/v1"
    app.include_router(auth_router, prefix=api_v1)
    app.include_router(schemas_router, prefix=api_v1)
    app.include_router(structured_router, prefix=api_v1)
    app.include_router(projects_router, prefix=api_v1)
    app.include_router(chats_router, prefix=api_v1)
    app.include_router(files_router, prefix=api_v1)
    app.include_router(usage_router, prefix=api_v1)
    app.include_router(search_router, prefix=api_v1)
    app.include_router(traces_router, prefix=api_v1)
    app.include_router(eval_router, prefix=api_v1)
    app.include_router(arch_router, prefix=api_v1)
    app.include_router(admin_router, prefix=api_v1)

    return app


app = create_app()
