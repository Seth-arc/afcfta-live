"""Integration tests for API-key authentication enforcement on versioned routes."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


def _valid_case_payload() -> dict[str, object]:
    """Return a minimally valid case-creation payload."""

    return {
        "case_external_ref": f"AUTH-CASE-{uuid4()}",
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


def _valid_assessment_payload() -> dict[str, object]:
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


def _valid_case_assessment_payload() -> dict[str, object]:
    """Return a minimally valid case-backed assessment payload."""

    return {"year": 2025}


def _valid_evidence_payload() -> dict[str, object]:
    """Return a minimally valid evidence-readiness payload."""

    return {
        "entity_type": "pathway",
        "entity_key": "PATHWAY:00000000-0000-0000-0000-000000000001",
        "persona_mode": "exporter",
        "existing_documents": [],
    }


@pytest.mark.asyncio
async def test_health_endpoint_remains_unauthenticated(
    unauthenticated_async_client: AsyncClient,
) -> None:
    """GET /health should stay publicly accessible without credentials."""

    response = await unauthenticated_async_client.get("/api/v1/health")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/api/v1/cases", {"json": _valid_case_payload()}),
        ("get", f"/api/v1/cases/{uuid4()}", {}),
        ("post", f"/api/v1/cases/{uuid4()}/assess", {"json": _valid_case_assessment_payload()}),
        ("get", f"/api/v1/cases/{uuid4()}/latest", {}),
        ("post", "/api/v1/assessments", {"json": _valid_assessment_payload()}),
        ("post", "/api/v1/assistant/assess", {"json": {"user_input": "Can I export HS 110311?"}}),
        (
            "post",
            f"/api/v1/assessments/cases/{uuid4()}",
            {"json": _valid_case_assessment_payload()},
        ),
        ("get", f"/api/v1/audit/evaluations/{uuid4()}", {}),
        ("get", f"/api/v1/audit/cases/{uuid4()}/evaluations", {}),
        ("get", f"/api/v1/audit/cases/{uuid4()}/latest", {}),
        ("post", "/api/v1/evidence/readiness", {"json": _valid_evidence_payload()}),
        ("get", "/api/v1/rules/110311", {"params": {"hs_version": "HS2017"}}),
        ("get", "/api/v1/sources", {"params": {"limit": 1}}),
        ("get", "/api/v1/provisions", {"params": {"limit": 1}}),
        (
            "get",
            "/api/v1/tariffs",
            {
                "params": {
                    "exporter": "GHA",
                    "importer": "NGA",
                    "hs6": "110311",
                    "year": 2025,
                }
            },
        ),
        ("get", "/api/v1/intelligence/corridors/GHA/NGA", {}),
        ("get", "/api/v1/intelligence/alerts", {"params": {"limit": 1}}),
    ],
)
async def test_protected_routes_require_api_key_and_return_structured_401(
    unauthenticated_async_client: AsyncClient,
    method: str,
    path: str,
    kwargs: dict[str, object],
) -> None:
    """All non-health routes should reject missing credentials with the shared error envelope."""

    response = await getattr(unauthenticated_async_client, method)(path, **kwargs)

    assert response.status_code == 401, response.text
    body = response.json()
    assert set(body) == {"error", "meta"}
    assert body["error"]["code"] == "AUTHENTICATION_ERROR"
    assert body["error"]["details"] == {
        "auth_scheme": "api_key",
        "header_name": "X-API-Key",
        "reason": "missing_api_key",
    }
    assert body["meta"]["request_id"]
    assert response.headers["X-Request-ID"] == body["meta"]["request_id"]


@pytest.mark.asyncio
async def test_protected_route_rejects_invalid_api_key_with_structured_401(
    unauthenticated_async_client: AsyncClient,
) -> None:
    """Protected routes should reject wrong API keys with the shared error envelope."""

    response = await unauthenticated_async_client.get(
        "/api/v1/sources",
        params={"limit": 1},
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 401, response.text
    body = response.json()
    assert body["error"]["code"] == "AUTHENTICATION_ERROR"
    assert body["error"]["details"] == {
        "auth_scheme": "api_key",
        "header_name": "X-API-Key",
        "reason": "invalid_api_key",
    }


@pytest.mark.asyncio
async def test_authenticated_client_can_reach_protected_route(
    async_client: AsyncClient,
) -> None:
    """Authenticated requests should pass the router guard and reach protected handlers."""

    response = await async_client.get("/api/v1/sources", params={"limit": 1})

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
