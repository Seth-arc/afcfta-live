"""Tests for public liveness and readiness health endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_health(async_client) -> None:
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_readiness_returns_dependency_status_when_database_is_available(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v1.health.check_database_readiness", check_mock)

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["checks"] == {"database": "ok"}
    assert body["timestamp"]
    check_mock.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_readiness_returns_structured_503_when_database_is_unavailable(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_mock = AsyncMock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr("app.api.v1.health.check_database_readiness", check_mock)

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert set(body) == {"error", "meta"}
    assert body["error"]["code"] == "READINESS_CHECK_FAILED"
    assert body["error"]["message"] == "Service dependencies are not ready"
    assert body["error"]["details"] == {
        "status": "degraded",
        "checks": {"database": "unavailable"},
    }
    assert body["meta"]["request_id"]
    check_mock.assert_awaited_once_with()
