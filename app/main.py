"""FastAPI application factory and top-level exception handling."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import importlib
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.deps import InMemoryRateLimiter, RedisRateLimiter
from app.config import get_settings
from app.core.exceptions import AISBaseException, RateLimitExceededError
from app.core.http_status import DOMAIN_STATUS_CODES
from app.core.logging import (
    bind_request_log_context,
    configure_logging,
    log_event,
    reset_request_log_context,
)
from app.schemas.common import ErrorDetail, ErrorResponse, Meta

logger = logging.getLogger(__name__)
request_logger = logging.getLogger("app.request")


class ErrorTracker:
    """Minimal optional external error-tracking seam."""

    def __init__(self, capture_exception: callable | None = None) -> None:
        self._capture_exception = capture_exception

    def capture_exception(self, exc: Exception) -> None:
        if self._capture_exception is None:
            return
        self._capture_exception(exc)


def _configure_error_tracker(settings) -> ErrorTracker:
    """Initialize an optional external error tracker without making it mandatory."""

    backend = settings.ERROR_TRACKING_BACKEND.strip().lower()
    if backend in {"", "none"}:
        return ErrorTracker()

    if backend != "sentry":
        logger.warning("Unsupported error tracking backend '%s'; continuing without external tracking", backend)
        return ErrorTracker()

    if not settings.SENTRY_DSN:
        logger.warning("Sentry backend configured without SENTRY_DSN; continuing without external tracking")
        return ErrorTracker()

    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
    except ImportError:
        logger.warning("Sentry backend configured but sentry_sdk is not installed; continuing without external tracking")
        return ErrorTracker()

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        release=settings.APP_VERSION,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )
    logger.info("External error tracking initialized with backend %s", backend)
    return ErrorTracker(capture_exception=sentry_sdk.capture_exception)


def _configure_metrics(app: FastAPI, settings) -> None:
    """Register Prometheus scraping only when metrics are explicitly enabled."""

    if not settings.METRICS_ENABLED:
        return

    try:
        from prometheus_fastapi_instrumentator import Instrumentator, metrics
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "METRICS_ENABLED=true requires prometheus-fastapi-instrumentator to be installed."
        ) from exc

    instrumentator = Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics"],
    )
    instrumentator.add(
        metrics.latency(
            metric_name="http_request_duration_seconds",
            should_include_handler=True,
            should_include_method=False,
            should_include_status=True,
        )
    )
    instrumentator.add(
        metrics.requests(
            metric_name="http_requests_total",
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )
    instrumentator.instrument(app).expose(
        app,
        include_in_schema=False,
        should_gzip=True,
    )


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


def _route_path(request: Request) -> str:
    """Return the matched route template when available."""

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path


def _request_log_level(status_code: int) -> int:
    """Map HTTP response classes onto pragmatic request log levels."""

    if status_code >= 500:
        return logging.ERROR
    if status_code >= 400:
        return logging.WARNING
    return logging.INFO


def _log_http_request(request: Request, *, status_code: int, started_at: float) -> None:
    """Emit one structured request log with latency and caller context."""

    log_event(
        request_logger,
        _request_log_level(status_code),
        event="http_request",
        message="Request completed",
        method=request.method,
        path=request.url.path,
        route=_route_path(request),
        status_code=status_code,
        latency_ms=int((perf_counter() - started_at) * 1000),
        authenticated_principal=getattr(request.state, "authenticated_principal", None),
        auth_scheme=getattr(request.state, "authenticated_auth_scheme", None),
    )


async def _domain_exception_handler(request: Request, exc: AISBaseException) -> JSONResponse:
    """Render domain exceptions as structured JSON without leaking internals."""

    status_code = DOMAIN_STATUS_CODES.get(type(exc), 400)
    response = _error_response(
        request,
        status_code=status_code,
        code=exc.code,
        message=exc.message,
        details=exc.detail,
    )
    if isinstance(exc, RateLimitExceededError) and exc.detail:
        retry_after = exc.detail.get("retry_after_seconds")
        if retry_after is not None:
            response.headers["Retry-After"] = str(int(retry_after))
    return response


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic 500 response for unexpected errors."""

    request.app.state.error_tracker.capture_exception(exc)
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

    if settings.UVICORN_WORKERS > 1 and not settings.REDIS_URL:
        raise RuntimeError(
            f"UVICORN_WORKERS={settings.UVICORN_WORKERS} requires REDIS_URL to be set. "
            "InMemoryRateLimiter is per-process: each worker maintains independent buckets, "
            "making the effective rate limit UVICORN_WORKERS × the configured max. "
            "Set REDIS_URL to a live Redis instance or keep UVICORN_WORKERS=1."
        )

    redis_client = None
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]

            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
            await redis_client.ping()
            app.state.rate_limiter = RedisRateLimiter(redis_client)
            logger.info("Redis-backed sliding-window rate limiter active at %s", settings.REDIS_URL)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s); falling back to in-process rate limiter — "
                "keep UVICORN_WORKERS=1 until Redis is reachable",
                exc,
            )
            if redis_client is not None:
                await redis_client.aclose()
                redis_client = None

    yield

    if redis_client is not None:
        await redis_client.aclose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.error_tracker = _configure_error_tracker(settings)
    # Register root-level operational endpoints before versioned routers so they
    # remain outside the API-key protected router dependencies.
    _configure_metrics(app, settings)

    if settings.CORS_ALLOW_ORIGINS:
        origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", settings.API_AUTH_HEADER_NAME, "X-Request-ID"],
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        started_at = perf_counter()
        context_tokens = bind_request_log_context(request_id=request.state.request_id)

        try:
            response = await call_next(request)
        except Exception:
            if settings.LOG_REQUESTS_ENABLED:
                _log_http_request(request, status_code=500, started_at=started_at)
            reset_request_log_context(context_tokens)
            raise

        response.headers.setdefault("X-Request-ID", request.state.request_id)
        if settings.LOG_REQUESTS_ENABLED:
            _log_http_request(request, status_code=response.status_code, started_at=started_at)
        reset_request_log_context(context_tokens)
        return response

    app.add_exception_handler(AISBaseException, _domain_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
