"""Unit tests for optional Prometheus metrics exposure."""

from __future__ import annotations

import builtins
import importlib
import sys
import types

import pytest
from fastapi import Response
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings


def _reload_main_module():
    import app.main as main_module

    return importlib.reload(main_module)


def _install_fake_instrumentator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a lightweight instrumentator stub so unit tests do not need the wheel installed."""

    class FakeInstrumentator:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.instrumentations: list[object] = []

        def add(self, instrumentation: object) -> "FakeInstrumentator":
            self.instrumentations.append(instrumentation)
            return self

        def instrument(self, app) -> "FakeInstrumentator":
            self.app = app
            return self

        def expose(
            self,
            app,
            endpoint: str = "/metrics",
            include_in_schema: bool = True,
            **kwargs,
        ) -> "FakeInstrumentator":
            @app.get(endpoint, include_in_schema=include_in_schema)
            async def _metrics() -> Response:
                payload = "\n".join(
                    [
                        "# HELP http_request_duration_seconds fake latency histogram",
                        "# TYPE http_request_duration_seconds histogram",
                        'http_request_duration_seconds_bucket{handler="/api/v1/health",status="200",le="+Inf"} 1',
                        "# HELP http_requests_total fake request counter",
                        "# TYPE http_requests_total counter",
                        'http_requests_total{method="GET",handler="/api/v1/health",status="200"} 1',
                    ]
                )
                return Response(
                    content=payload,
                    media_type="text/plain; version=0.0.4; charset=utf-8",
                )

            return self

    fake_metrics = types.SimpleNamespace(
        latency=lambda **kwargs: ("latency", kwargs),
        requests=lambda **kwargs: ("requests", kwargs),
    )
    fake_module = types.ModuleType("prometheus_fastapi_instrumentator")
    fake_module.Instrumentator = FakeInstrumentator
    fake_module.metrics = fake_metrics
    monkeypatch.setitem(sys.modules, "prometheus_fastapi_instrumentator", fake_module)


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_404_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    get_settings.cache_clear()
    main_module = _reload_main_module()

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_plaintext_metrics_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "true")
    _install_fake_instrumentator(monkeypatch)
    get_settings.cache_clear()
    main_module = _reload_main_module()

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_request_duration_seconds" in response.text
    assert "http_requests_total" in response.text


def test_create_app_fails_fast_when_metrics_enabled_but_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.delitem(sys.modules, "prometheus_fastapi_instrumentator", raising=False)

    original_import = builtins.__import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "prometheus_fastapi_instrumentator":
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    get_settings.cache_clear()

    with pytest.raises(
        RuntimeError,
        match="METRICS_ENABLED=true requires prometheus-fastapi-instrumentator to be installed.",
    ):
        _reload_main_module()
