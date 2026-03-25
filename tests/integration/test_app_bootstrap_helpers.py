"""Integration tests for app bootstrap, middleware, and startup helpers."""

from __future__ import annotations

import importlib
import sys
import types

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from app.api.deps import InMemoryRateLimiter, RedisRateLimiter
from app.config import Settings, get_settings
from app.core.exceptions import CaseNotFoundError


pytestmark = pytest.mark.integration


def _reload_main_module():
    import app.main as main_module

    return importlib.reload(main_module)


def _request(path: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "state": {},
        }
    )


def test_request_id_reuses_existing_state_value(test_settings: Settings) -> None:
    main_module = _reload_main_module()
    request = _request("/existing-id")
    request.state.request_id = "req-existing"

    assert main_module._request_id(request) == "req-existing"


def test_request_id_uses_header_when_state_is_empty(test_settings: Settings) -> None:
    main_module = _reload_main_module()
    request = _request("/header-id", headers=[(b"x-request-id", b"req-header")])

    assert main_module._request_id(request) == "req-header"
    assert request.state.request_id == "req-header"


def test_route_path_falls_back_to_url_path_without_matched_route(test_settings: Settings) -> None:
    main_module = _reload_main_module()
    request = _request("/unmatched/path")

    assert main_module._route_path(request) == "/unmatched/path"


def test_configure_error_tracker_supports_none_backend(test_settings: Settings) -> None:
    main_module = _reload_main_module()
    tracker = main_module._configure_error_tracker(
        test_settings.model_copy(update={"ERROR_TRACKING_BACKEND": "none"})
    )

    tracker.capture_exception(RuntimeError("ignored"))
    assert isinstance(tracker, main_module.ErrorTracker)


def test_configure_error_tracker_handles_unsupported_backend(test_settings: Settings) -> None:
    main_module = _reload_main_module()
    tracker = main_module._configure_error_tracker(
        test_settings.model_copy(update={"ERROR_TRACKING_BACKEND": "rollbar"})
    )

    assert isinstance(tracker, main_module.ErrorTracker)


def test_configure_error_tracker_handles_missing_sentry_dsn(test_settings: Settings) -> None:
    main_module = _reload_main_module()
    tracker = main_module._configure_error_tracker(
        test_settings.model_copy(
            update={
                "ERROR_TRACKING_BACKEND": "sentry",
                "SENTRY_DSN": None,
            }
        )
    )

    assert isinstance(tracker, main_module.ErrorTracker)


def test_configure_error_tracker_handles_missing_sentry_sdk(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    main_module = _reload_main_module()

    def _raise_import_error(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr(main_module.importlib, "import_module", _raise_import_error)
    tracker = main_module._configure_error_tracker(
        test_settings.model_copy(
            update={
                "ERROR_TRACKING_BACKEND": "sentry",
                "SENTRY_DSN": "https://public@example.invalid/1",
            }
        )
    )

    assert isinstance(tracker, main_module.ErrorTracker)


def test_configure_error_tracker_initializes_sentry_when_available(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    main_module = _reload_main_module()
    init_calls: list[dict[str, object]] = []
    captured: list[str] = []

    fake_sentry_sdk = types.SimpleNamespace(
        init=lambda **kwargs: init_calls.append(kwargs),
        capture_exception=lambda exc: captured.append(str(exc)),
    )
    monkeypatch.setattr(main_module.importlib, "import_module", lambda name: fake_sentry_sdk)

    tracker = main_module._configure_error_tracker(
        test_settings.model_copy(
            update={
                "ERROR_TRACKING_BACKEND": "sentry",
                "SENTRY_DSN": "https://public@example.invalid/1",
                "ENV": "staging",
                "APP_VERSION": "9.9.9",
                "SENTRY_TRACES_SAMPLE_RATE": 0.25,
            }
        )
    )

    tracker.capture_exception(RuntimeError("boom"))

    assert init_calls == [
        {
            "dsn": "https://public@example.invalid/1",
            "environment": "staging",
            "release": "9.9.9",
            "traces_sample_rate": 0.25,
        }
    ]
    assert captured == ["boom"]


@pytest.mark.asyncio
async def test_domain_exception_route_returns_structured_error_envelope(
    test_settings: Settings,
) -> None:
    main_module = _reload_main_module()
    app = main_module.create_app()

    @app.get("/missing")
    async def _missing() -> dict[str, str]:
        raise CaseNotFoundError("Case was not found", detail={"case_id": "case-123"})

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/missing")

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["error"]["code"] == "CASE_NOT_FOUND"
    assert body["error"]["details"] == {"case_id": "case-123"}
    assert body["meta"]["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_unhandled_exception_route_returns_structured_500_and_tracks_error(
    test_settings: Settings,
) -> None:
    main_module = _reload_main_module()
    app = main_module.create_app()
    captured: list[str] = []
    app.state.error_tracker = main_module.ErrorTracker(
        capture_exception=lambda exc: captured.append(type(exc).__name__)
    )

    @app.get("/boom")
    async def _boom() -> dict[str, str]:
        raise ValueError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/boom", headers={"X-Request-ID": "req-500"})

    assert response.status_code == 500, response.text
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "An unexpected error occurred"
    assert body["meta"]["request_id"] == "req-500"
    assert response.headers["X-Request-ID"] == "req-500"
    assert captured == ["ValueError"]


@pytest.mark.asyncio
async def test_create_app_adds_cors_middleware_when_origins_are_configured(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "https://portal.example, https://ops.example",
    )
    get_settings.cache_clear()
    main_module = _reload_main_module()
    app = main_module.create_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://portal.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://portal.example"
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_lifespan_rejects_multiple_workers_without_redis(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv("UVICORN_WORKERS", "2")
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    main_module = _reload_main_module()
    app = main_module.create_app()

    with pytest.raises(RuntimeError, match="requires REDIS_URL"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_switches_to_redis_rate_limiter_when_redis_is_available(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://cache.example:6379/0")
    get_settings.cache_clear()
    main_module = _reload_main_module()
    ping_calls: list[str] = []
    close_calls: list[str] = []

    class FakeRedisClient:
        async def ping(self) -> None:
            ping_calls.append("ping")

        async def aclose(self) -> None:
            close_calls.append("close")

    fake_client = FakeRedisClient()
    redis_asyncio = types.ModuleType("redis.asyncio")
    redis_asyncio.from_url = lambda url, decode_responses=False: fake_client
    redis_package = types.ModuleType("redis")
    redis_package.asyncio = redis_asyncio
    monkeypatch.setitem(sys.modules, "redis", redis_package)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)

    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        assert isinstance(app.state.rate_limiter, RedisRateLimiter)

    assert ping_calls == ["ping"]
    assert close_calls == ["close"]


@pytest.mark.asyncio
async def test_lifespan_falls_back_to_in_memory_when_redis_ping_fails(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://cache.example:6379/0")
    get_settings.cache_clear()
    main_module = _reload_main_module()
    close_calls: list[str] = []

    class FakeRedisClient:
        async def ping(self) -> None:
            raise RuntimeError("redis unavailable")

        async def aclose(self) -> None:
            close_calls.append("close")

    fake_client = FakeRedisClient()
    redis_asyncio = types.ModuleType("redis.asyncio")
    redis_asyncio.from_url = lambda url, decode_responses=False: fake_client
    redis_package = types.ModuleType("redis")
    redis_package.asyncio = redis_asyncio
    monkeypatch.setitem(sys.modules, "redis", redis_package)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)

    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        assert isinstance(app.state.rate_limiter, InMemoryRateLimiter)

    assert close_calls == ["close"]
