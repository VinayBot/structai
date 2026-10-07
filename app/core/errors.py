from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx


class AppError(Exception):
    code = "internal_error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: int | None = None,
        *,
        retry_after_seconds: float | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds
        self.suggestion = suggestion
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class UnauthorizedError(AppError):
    code = "unauthorized"
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AppError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class GenerationError(AppError):
    code = "generation_failed"
    status_code = status.HTTP_502_BAD_GATEWAY


class GuardrailError(AppError):
    code = "guardrail_blocked"
    status_code = status.HTTP_400_BAD_REQUEST


class OutputGuardrailError(AppError):
    code = "output_guardrail_blocked"
    status_code = status.HTTP_502_BAD_GATEWAY


class PiiDetectedError(AppError):
    code = "pii_detected"
    status_code = status.HTTP_400_BAD_REQUEST


class OutputPiiDetectedError(AppError):
    code = "output_pii_blocked"
    status_code = status.HTTP_502_BAD_GATEWAY


class InvalidEmailDomainError(AppError):
    code = "invalid_email_domain"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class EmailDomainUnreachableError(AppError):
    code = "email_domain_unreachable"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class RateLimitError(AppError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class PayloadTooLargeError(AppError):
    code = "payload_too_large"
    status_code = status.HTTP_413_CONTENT_TOO_LARGE


def _error_body(
    code: str,
    message: str,
    retry_after_seconds: float | None = None,
    suggestion: str | None = None,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_ctx.get(),
            "retry_after_seconds": retry_after_seconds,
            "suggestion": suggestion,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = None
        if exc.retry_after_seconds is not None:
            headers = {"Retry-After": str(max(1, round(exc.retry_after_seconds)))}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.retry_after_seconds, exc.suggestion),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body("validation_error", str(exc.errors())),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred"),
        )
