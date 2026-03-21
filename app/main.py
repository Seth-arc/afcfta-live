"""FastAPI application entrypoint for the AfCFTA Intelligence API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.core.exceptions import (
    AISBaseException,
    ClassificationError,
    CorridorNotSupportedError,
    ExpressionEvaluationError,
    InsufficientFactsError,
    RuleNotFoundError,
    StatusUnknownError,
    TariffNotFoundError,
)
from app.schemas.common import ErrorDetail, ErrorResponse, Meta

logger = logging.getLogger(__name__)


def _build_error_response(
    request: Request,
    exc: AISBaseException,
    status_code: int,
) -> JSONResponse:
    meta = Meta(
        request_id=request.headers.get("x-request-id", str(uuid4())),
        timestamp=datetime.now(timezone.utc),
    )
    payload = ErrorResponse(
        error=ErrorDetail(
            code=exc.__class__.__name__,
            message=str(exc),
            details=exc.detail,
        ),
        meta=meta,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def _not_found_handler(request: Request, exc: AISBaseException) -> JSONResponse:
    return _build_error_response(request, exc, status.HTTP_404_NOT_FOUND)


async def _unprocessable_handler(request: Request, exc: AISBaseException) -> JSONResponse:
    return _build_error_response(request, exc, status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _bad_request_handler(request: Request, exc: AISBaseException) -> JSONResponse:
    return _build_error_response(request, exc, status.HTTP_400_BAD_REQUEST)


async def _server_error_handler(request: Request, exc: AISBaseException) -> JSONResponse:
    return _build_error_response(request, exc, status.HTTP_500_INTERNAL_SERVER_ERROR)


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    settings = get_settings()
    app = FastAPI(title=settings.APP_TITLE, version=settings.APP_VERSION)
    app.include_router(api_router, prefix="/api/v1")

    for exception_class in (
        ClassificationError,
        RuleNotFoundError,
        TariffNotFoundError,
        StatusUnknownError,
    ):
        app.add_exception_handler(exception_class, _not_found_handler)

    app.add_exception_handler(InsufficientFactsError, _unprocessable_handler)
    app.add_exception_handler(CorridorNotSupportedError, _bad_request_handler)
    app.add_exception_handler(ExpressionEvaluationError, _server_error_handler)
    app.add_exception_handler(AISBaseException, _bad_request_handler)

    @app.on_event("startup")
    async def log_startup() -> None:
        logger.info("%s v%s starting", settings.APP_TITLE, settings.APP_VERSION)

    return app


app = create_app()
