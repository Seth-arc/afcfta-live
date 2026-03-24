"""FastAPI application factory and top-level exception handling."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.deps import InMemoryRateLimiter
from app.config import get_settings
from app.core.exceptions import (
    AISBaseException,
    AuthenticationError,
    AuditTrailNotFoundError,
    CaseNotFoundError,
    ClassificationError,
    CorridorNotSupportedError,
    EvaluationPersistenceError,
    ExpressionEvaluationError,
    InsufficientFactsError,
    RateLimitExceededError,
    RuleNotFoundError,
    StatusUnknownError,
    TariffNotFoundError,
)
from app.schemas.common import ErrorDetail, ErrorResponse, Meta

logger = logging.getLogger(__name__)


DOMAIN_STATUS_CODES: dict[type[AISBaseException], int] = {
    AuthenticationError: 401,
    RateLimitExceededError: 429,
    ClassificationError: 404,
    RuleNotFoundError: 404,
    TariffNotFoundError: 404,
    StatusUnknownError: 404,
    AuditTrailNotFoundError: 404,
    CaseNotFoundError: 404,
    CorridorNotSupportedError: 422,
    InsufficientFactsError: 422,
    ExpressionEvaluationError: 500,
    EvaluationPersistenceError: 500,
}


def _request_id(request: Request) -> str:
    """Return the current request id, generating one if needed."""

    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    return request_id


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    """Build a structured error payload aligned to `ErrorResponse`."""

    request_id = _request_id(request)
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details),
        meta=Meta(
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"X-Request-ID": request_id},
    )


async def _domain_exception_handler(request: Request, exc: AISBaseException) -> JSONResponse:
    """Render domain exceptions as structured JSON without leaking internals."""

    status_code = DOMAIN_STATUS_CODES.get(type(exc), 400)
    return _error_response(
        request,
        status_code=status_code,
        code=exc.code,
        message=exc.message,
        details=exc.detail,
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic 500 response for unexpected errors."""

    logger.exception("Unhandled exception while processing request %s", _request_id(request))
    return _error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run application startup and shutdown hooks using FastAPI lifespan."""

    settings = app.state.settings
    logger.info("%s v%s starting", settings.APP_TITLE, settings.APP_VERSION)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request.state.request_id)
        return response

    app.add_exception_handler(AISBaseException, _domain_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
