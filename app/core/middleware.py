import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import new_request_id, request_id_ctx
from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
from app.core.metrics_buffer import RequestRecord, get_request_buffer

RequestResponseCallNext = Callable[[Request], Awaitable[Response]]


async def request_id_middleware(request: Request, call_next: RequestResponseCallNext) -> Response:
    incoming = request.headers.get("x-request-id")
    rid = incoming or new_request_id()
    token = request_id_ctx.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["x-request-id"] = rid
    return response


async def metrics_middleware(request: Request, call_next: RequestResponseCallNext) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    route = request.scope.get("route")
    path = route.path if route is not None else request.url.path

    HTTP_REQUESTS_TOTAL.labels(
        method=request.method, path=path, status_code=response.status_code
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)
    get_request_buffer().record(
        RequestRecord(
            ts=time.time(),
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration * 1000,
        )
    )
    return response
