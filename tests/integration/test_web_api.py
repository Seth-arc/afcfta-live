"""Integration tests for the browser-safe /web/api route family."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_intake_service
from app.core.enums import PersonaModeEnum
from app.schemas.nim.intake import (
    AssessmentContext,
    HS6Candidate,
    NimAssessmentDraft,
    TradeFlow,
)
from app.services.nim.intake_service import IntakeService

pytestmark = pytest.mark.integration

WEB_ASSISTANT_URL = "/web/api/assistant/assess"


def _request_with_context() -> dict[str, object]:
    return {
        "user_input": "Can I export wheat groats from Ghana to Nigeria in 2025?",
        "context": {
            "persona_mode": "exporter",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
        },
    }


def _complete_gha_nga_draft() -> NimAssessmentDraft:
    return NimAssessmentDraft(
        product=HS6Candidate(hs6_code="110311"),
        trade_flow=TradeFlow(exporter="GHA", importer="NGA", year=2025),
        context=AssessmentContext(persona_mode=PersonaModeEnum.EXPORTER),
    )


def _override_intake_with_complete_draft(app: FastAPI) -> None:
    draft = _complete_gha_nga_draft()
    real_service = IntakeService(MagicMock())

    mock_service = MagicMock(spec=IntakeService)
    mock_service.parse_user_input = AsyncMock(return_value=draft)
    mock_service.to_eligibility_request = real_service.to_eligibility_request
    mock_service.nim_client = MagicMock(enabled=False, model="")

    app.dependency_overrides[get_intake_service] = lambda: mock_service


def _remove_intake_override(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_intake_service, None)


@pytest.mark.asyncio
async def test_web_assistant_assess_works_without_machine_api_key_and_keeps_replay_headers(
    app: FastAPI,
    unauthenticated_async_client: AsyncClient,
) -> None:
    """The browser BFF must assess through /web/api without exposing machine auth."""

    request_id = f"browser-request-{uuid4()}"
    _override_intake_with_complete_draft(app)
    try:
        response = await unauthenticated_async_client.post(
            WEB_ASSISTANT_URL,
            headers={"X-Request-ID": request_id},
            json=_request_with_context(),
        )
    finally:
        _remove_intake_override(app)

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["response_type"] == "assessment"
    assert body["case_id"] is not None
    assert body["evaluation_id"] is not None
    assert body["audit_url"] == f"/web/api/audit/evaluations/{body['evaluation_id']}"

    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-ais-case-id"] == body["case_id"]
    assert response.headers["x-ais-evaluation-id"] == body["evaluation_id"]
    assert response.headers["x-ais-audit-url"] == body["audit_url"]

    header_names = {header.lower() for header in response.headers.keys()}
    assert "x-api-key" not in header_names
    assert "authorization" not in header_names
    assert "proxy-authorization" not in header_names


@pytest.mark.asyncio
async def test_web_audit_replay_route_returns_snapshot_without_machine_api_key(
    app: FastAPI,
    unauthenticated_async_client: AsyncClient,
) -> None:
    """Browser replay should work through /web/api without machine-client auth."""

    _override_intake_with_complete_draft(app)
    try:
        assessment_response = await unauthenticated_async_client.post(
            WEB_ASSISTANT_URL,
            json=_request_with_context(),
        )
    finally:
        _remove_intake_override(app)

    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    assert assessment_body["response_type"] == "assessment"

    replay_request_id = f"browser-replay-{uuid4()}"
    audit_response = await unauthenticated_async_client.get(
        assessment_body["audit_url"],
        headers={"X-Request-ID": replay_request_id},
    )

    assert audit_response.status_code == 200, audit_response.text
    assert audit_response.headers["x-request-id"] == replay_request_id
    assert "x-api-key" not in {header.lower() for header in audit_response.headers.keys()}

    trail = audit_response.json()
    assert trail["replay_mode"] == "snapshot_frozen"
    assert trail["evaluation"]["evaluation_id"] == assessment_body["evaluation_id"]
    assert trail["evaluation"]["case_id"] == assessment_body["case_id"]
