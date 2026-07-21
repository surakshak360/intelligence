"""
Custom exceptions + handlers.

Implements GROUND_RULES.md section 2.3 "Standard Error Codes" and the
error envelope from section 2.2:

    {
      "success": false,
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "...",
        "details": {...},
        "request_id": "req_abc123"
      }
    }

"Fail Fast, Fail Loud" (section 1) — every failure path here returns an
explicit code; nothing fails silently.
"""
from typing import Any, Optional

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)

# Maps error code -> HTTP status, per GROUND_RULES 2.3
ERROR_HTTP_STATUS = {
    "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
    "UNAUTHORIZED": status.HTTP_401_UNAUTHORIZED,
    "FORBIDDEN": status.HTTP_403_FORBIDDEN,
    "NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "CONFLICT": status.HTTP_409_CONFLICT,
    "RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
    "UPSTREAM_ERROR": status.HTTP_502_BAD_GATEWAY,
    "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class ServiceError(Exception):
    """Base error carrying a GROUND_RULES-standard error code."""

    def __init__(self, code: str, message: str, details: Optional[dict[str, Any]] = None):
        assert code in ERROR_HTTP_STATUS, f"Unknown error code: {code}"
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(ServiceError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__("NOT_FOUND", message, details)


class ValidationErrorX(ServiceError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__("VALIDATION_ERROR", message, details)


class ConflictError(ServiceError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__("CONFLICT", message, details)


def _error_body(code: str, message: str, details: dict) -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id_ctx.get(),
        },
    }


def register_exception_handlers(app) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        logger.warning(
            "service_error",
            extra={"extra_fields": {"code": exc.code, "path": request.url.path}},
        )
        return JSONResponse(
            status_code=ERROR_HTTP_STATUS[exc.code],
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body(
                "VALIDATION_ERROR",
                "Request failed validation.",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            exc_info=exc,
            extra={"extra_fields": {"path": request.url.path}},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred.", {}),
        )
