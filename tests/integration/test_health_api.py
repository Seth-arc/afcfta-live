"""Integration tests for public liveness and readiness endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_readiness_endpoint_is_reachable_without_auth(
    unauthenticated_async_client: AsyncClient,
) -> None:
    """GET /health/ready must be reachable by unauthenticated container probes."""

    response = await unauthenticated_async_client.get("/api/v1/health/ready")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok"}
    assert body["timestamp"]
    assert "pool_stats" not in body


@pytest.mark.asyncio
async def test_readiness_endpoint_returns_pool_stats_for_authenticated_caller(
    async_client: AsyncClient,
) -> None:
    """GET /health/ready must include a structurally valid pool_stats block when authenticated."""

    response = await async_client.get("/api/v1/health/ready")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok"}
    assert body["timestamp"]

    assert "pool_stats" in body, "pool_stats block missing from authenticated response"
    stats = body["pool_stats"]

    assert isinstance(stats["checked_out"], int)
    assert isinstance(stats["pool_size"], int)
    assert isinstance(stats["overflow"], int)
    assert isinstance(stats["checked_in"], int)
    assert stats["pool_pressure"] in {"ok", "elevated", "saturated"}

    assert stats["checked_out"] >= 0
    assert stats["pool_size"] >= 0
    assert stats["overflow"] >= 0
    assert stats["checked_in"] >= 0


@pytest.mark.asyncio
async def test_readiness_endpoint_remains_stable_across_repeated_authenticated_probes(
    async_client: AsyncClient,
) -> None:
    """Repeated authenticated probes must keep returning pool stats and DB-ok status."""

    first = await async_client.get("/api/v1/health/ready")
    second = await async_client.get("/api/v1/health/ready")

    for response in (first, second):
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"] == {"database": "ok"}
        assert body["timestamp"]
        assert "pool_stats" in body
