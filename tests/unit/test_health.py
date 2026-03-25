"""Tests for public liveness and readiness health endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.base import classify_pool_pressure


# ---------------------------------------------------------------------------
# classify_pool_pressure — pure function, no mocking needed
# ---------------------------------------------------------------------------


def test_pool_pressure_ok_when_utilisation_is_low() -> None:
    assert classify_pool_pressure(checked_out=0, pool_size=5) == "ok"
    assert classify_pool_pressure(checked_out=1, pool_size=5) == "ok"
    assert classify_pool_pressure(checked_out=3, pool_size=5) == "ok"


def test_pool_pressure_elevated_at_75_percent() -> None:
    # 4 / 5 = 80 % >= 75 % threshold
    assert classify_pool_pressure(checked_out=4, pool_size=5) == "elevated"


def test_pool_pressure_saturated_at_95_percent() -> None:
    # 5 / 5 = 100 % >= 95 % threshold
    assert classify_pool_pressure(checked_out=5, pool_size=5) == "saturated"


def test_pool_pressure_ok_when_pool_size_is_zero() -> None:
    assert classify_pool_pressure(checked_out=0, pool_size=0) == "ok"


def test_pool_pressure_boundary_just_below_elevated() -> None:
    # 3 / 4 = 75 % — exactly at the elevated threshold
    assert classify_pool_pressure(checked_out=3, pool_size=4) == "elevated"


def test_pool_pressure_boundary_just_below_saturated() -> None:
    # 18 / 20 = 90 % — above elevated, below saturated
    assert classify_pool_pressure(checked_out=18, pool_size=20) == "elevated"


# ---------------------------------------------------------------------------
# /health liveness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(async_client) -> None:
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# /health/ready — authenticated (pool_stats present)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readiness_returns_dependency_status_when_database_is_available(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v1.health.check_database_readiness", check_mock)

    fake_stats = {
        "checked_out": 1,
        "pool_size": 5,
        "overflow": 0,
        "checked_in": 4,
        "pool_pressure": "ok",
    }
    monkeypatch.setattr("app.api.v1.health.get_pool_stats", MagicMock(return_value=fake_stats))

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["checks"] == {"database": "ok"}
    assert body["timestamp"]
    assert body["pool_stats"] == fake_stats
    check_mock.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_readiness_pool_stats_pressure_field_is_present(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.v1.health.check_database_readiness", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.api.v1.health.get_pool_stats",
        MagicMock(return_value={
            "checked_out": 5,
            "pool_size": 5,
            "overflow": 0,
            "checked_in": 0,
            "pool_pressure": "saturated",
        }),
    )

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["pool_stats"]["pool_pressure"] == "saturated"


# ---------------------------------------------------------------------------
# /health/ready — unauthenticated (pool_stats absent)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readiness_pool_stats_absent_for_unauthenticated_caller(
    unauthenticated_async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.v1.health.check_database_readiness", AsyncMock(return_value=None))

    response = await unauthenticated_async_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "pool_stats" not in body


# ---------------------------------------------------------------------------
# /health/ready — database unavailable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readiness_returns_structured_503_when_database_is_unavailable(
    async_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_mock = AsyncMock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr("app.api.v1.health.check_database_readiness", check_mock)
    monkeypatch.setattr(
        "app.api.v1.health.get_pool_stats",
        MagicMock(return_value={"checked_out": 0, "pool_size": 5, "overflow": 0,
                                "checked_in": 5, "pool_pressure": "ok"}),
    )

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
