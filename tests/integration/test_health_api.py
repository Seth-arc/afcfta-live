"""Integration tests for public liveness and readiness endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_readiness_endpoint_is_public_and_reports_database_health(
    unauthenticated_async_client: AsyncClient,
) -> None:
    """GET /health/ready should be publicly reachable and report readiness details."""

    response = await unauthenticated_async_client.get("/api/v1/health/ready")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok"}
    assert body["timestamp"]