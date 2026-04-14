"""Integration tests for API rate-limiting behavior on protected routes."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.local_db import (
    DEFAULT_LOCAL_DB_HOST,
    DEFAULT_LOCAL_DB_NAME,
    DEFAULT_LOCAL_DB_PASSWORD,
    DEFAULT_LOCAL_DB_PORT,
    DEFAULT_LOCAL_DB_USER,
    build_local_database_urls,
)


pytestmark = pytest.mark.integration


def _assessment_payload() -> dict[str, object]:
    """Return a minimally valid direct assessment payload."""

    return {
        "hs6_code": "110311",
        "hs_version": "HS2017",
        "exporter": "GHA",
        "importer": "NGA",
        "year": 2025,
        "persona_mode": "exporter",
        "production_facts": [
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            }
        ],
    }


def _case_payload(*, assess: bool = False) -> dict[str, object]:
    """Return a minimally valid persisted-case payload for case-backed assessment tests."""

    payload: dict[str, object] = {
        "case_external_ref": f"RL-CASE-{uuid4()}",
        "persona_mode": "exporter",
        "exporter_state": "GHA",
        "importer_state": "NGA",
        "hs6_code": "110311",
        "hs_version": "HS2017",
        "declared_origin": "GHA",
        "production_facts": [
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            }
        ],
    }
    if assess:
        payload["assess"] = True
        payload["assessment"] = {"year": 2025}
    return payload


@pytest.fixture
def low_rate_limit_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Override settings for deterministic throttling assertions."""

    local_db_env = {
        "LOCAL_DB_HOST": DEFAULT_LOCAL_DB_HOST,
        "LOCAL_DB_PORT": str(DEFAULT_LOCAL_DB_PORT),
        "LOCAL_DB_NAME": DEFAULT_LOCAL_DB_NAME,
        "LOCAL_DB_USER": DEFAULT_LOCAL_DB_USER,
        "LOCAL_DB_PASSWORD": DEFAULT_LOCAL_DB_PASSWORD,
    }
    for key, value in local_db_env.items():
        monkeypatch.setenv(key, value)
    async_url, sync_url = build_local_database_urls(local_db_env)
    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("DATABASE_URL_SYNC", sync_url)
    monkeypatch.setenv("API_AUTH_KEY", "pytest-api-key")
    monkeypatch.setenv("API_AUTH_PRINCIPAL", "pytest-suite")
    monkeypatch.setenv("API_AUTH_HEADER_NAME", "X-API-Key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_MAX_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS", "1")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def low_rate_limit_app(low_rate_limit_settings: Settings) -> FastAPI:
    """Create a test app with intentionally low throttling limits."""

    import app.main as main_module

    importlib.reload(main_module)
    return main_module.create_app()


@pytest_asyncio.fixture
async def low_rate_limit_client(low_rate_limit_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Create an authenticated client bound to the low-rate-limit test app."""

    transport = ASGITransport(app=low_rate_limit_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-API-Key": "pytest-api-key"},
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_assessment_routes_throttle_before_default_routes_under_low_limits(
    low_rate_limit_client: AsyncClient,
) -> None:
    """High-cost assessment routes should exhaust their smaller budget before default protected reads."""

    first_source = await low_rate_limit_client.get("/api/v1/sources", params={"limit": 1})
    second_source = await low_rate_limit_client.get("/api/v1/sources", params={"limit": 1})

    assert first_source.status_code == 200, first_source.text
    assert second_source.status_code == 200, second_source.text

    first_assessment = await low_rate_limit_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(),
    )
    throttled_assessment = await low_rate_limit_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(),
    )

    assert first_assessment.status_code == 200, first_assessment.text
    assert throttled_assessment.status_code == 429, throttled_assessment.text

    body = throttled_assessment.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert body["error"]["details"]["policy_name"] == "assessments"
    assert body["error"]["details"]["max_requests"] == 1
    assert body["error"]["details"]["window_seconds"] == 60
    assert body["error"]["details"]["principal_id"] == "pytest-suite"
    assert body["error"]["details"]["retry_after_seconds"] >= 1


@pytest.mark.asyncio
async def test_case_assessment_route_uses_assessment_rate_limit_policy(
    low_rate_limit_client: AsyncClient,
) -> None:
    """The canonical case-owned assessment route must use the assessment policy, not default."""

    create_case = await low_rate_limit_client.post("/api/v1/cases", json=_case_payload())
    assert create_case.status_code == 201, create_case.text
    case_id = create_case.json()["case_id"]

    first_assessment = await low_rate_limit_client.post(
        f"/api/v1/cases/{case_id}/assess",
        json={"year": 2025},
    )
    throttled_assessment = await low_rate_limit_client.post(
        f"/api/v1/cases/{case_id}/assess",
        json={"year": 2025},
    )

    assert first_assessment.status_code == 200, first_assessment.text
    assert throttled_assessment.status_code == 429, throttled_assessment.text

    body = throttled_assessment.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert body["error"]["details"]["policy_name"] == "assessments"
    assert body["error"]["details"]["max_requests"] == 1


@pytest.mark.asyncio
async def test_case_create_with_assess_true_uses_assessment_rate_limit_policy(
    low_rate_limit_client: AsyncClient,
) -> None:
    """POST /cases with assess=true must consume the assessment-policy budget."""

    first = await low_rate_limit_client.post("/api/v1/cases", json=_case_payload(assess=True))
    throttled = await low_rate_limit_client.post("/api/v1/cases", json=_case_payload(assess=True))

    assert first.status_code == 201, first.text
    assert throttled.status_code == 429, throttled.text

    body = throttled.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert body["error"]["details"]["policy_name"] == "assessments"
    assert body["error"]["details"]["max_requests"] == 1


@pytest.mark.asyncio
async def test_rate_limit_is_enforced_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """RATE_LIMIT_ENABLED=true with max=2 must return 429 + Retry-After on the third request.

    Does not require a live database: the assessment handler is stubbed so that
    only the rate-limit dependency (which runs first) is exercised for r1/r2,
    and r3 is blocked before the handler is reached at all.

    # TEST-ONLY: RATE_LIMIT_ENABLED is set explicitly in this test fixture.
    # This override must NOT be copied to production config (.env.prod).
    # Production must independently maintain RATE_LIMIT_ENABLED=true.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://localhost/fake")
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://localhost/fake")
    monkeypatch.setenv("API_AUTH_KEY", "pytest-api-key")
    monkeypatch.setenv("API_AUTH_PRINCIPAL", "pytest-suite")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS", "2")
    get_settings.cache_clear()

    import app.main as main_module

    importlib.reload(main_module)
    test_app = main_module.create_app()

    @asynccontextmanager
    async def _stub_ctx():
        svc = AsyncMock()
        svc.assess_interface_request.side_effect = HTTPException(
                status_code=503, detail="stub: no db in rate-limit test"
            )
        yield svc

    transport = ASGITransport(app=test_app)
    try:
        with patch(
            "app.api.v1.assessments.assessment_eligibility_service_context",
            side_effect=_stub_ctx,
        ):
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers={"X-API-Key": "pytest-api-key"},
            ) as client:
                await client.post("/api/v1/assessments", json=_assessment_payload())
                await client.post("/api/v1/assessments", json=_assessment_payload())
                r3 = await client.post("/api/v1/assessments", json=_assessment_payload())

        # r1 and r2 pass the rate-limit check (counter incremented) then fail in the
        # stubbed handler — that is expected and their status codes are not asserted.
        # r3 is blocked by the rate limiter before any handler logic runs.
        assert r3.status_code == 429, r3.text
        assert "Retry-After" in r3.headers
    finally:
        get_settings.cache_clear()
