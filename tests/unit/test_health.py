"""Tests for the health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health(async_client) -> None:
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.1.0"
