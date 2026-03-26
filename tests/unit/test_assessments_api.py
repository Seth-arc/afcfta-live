"""Unit tests for assessment routes with mocked eligibility services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.exceptions import EvaluationPersistenceError
from app.core.enums import RuleStatusEnum
from app.schemas.assessments import (
    EligibilityAssessmentResponse,
    EligibilityRequest,
    TariffOutcomeResponse,
)


def _assessment_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "hs6_code": "110311",
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
    payload.update(overrides)
    return payload


def _assessment_response() -> EligibilityAssessmentResponse:
    return EligibilityAssessmentResponse(
        hs6_code="110311",
        eligible=True,
        pathway_used="CTH",
        rule_status=RuleStatusEnum.AGREED,
        tariff_outcome=TariffOutcomeResponse(
            preferential_rate="0.0000",
            base_rate="15.0000",
            status="in_force",
        ),
        failures=[],
        missing_facts=[],
        evidence_required=["certificate_of_origin"],
        missing_evidence=[],
        readiness_score=1.0,
        completeness_ratio=1.0,
        confidence_class="complete",
        audit_persisted=True,
    )


@pytest.mark.asyncio
async def test_assessments_route_calls_interface_request_and_sets_replay_headers(
    app: FastAPI,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())
    captured_payloads: list[object] = []
    lifecycle: list[str] = []

    class FakeEligibilityService:
        async def assess_interface_request(self, payload) -> object:
            lifecycle.append("service_called")
            captured_payloads.append(payload)
            return SimpleNamespace(
                case_id=case_id,
                evaluation_id=evaluation_id,
                response=_assessment_response(),
            )

    @asynccontextmanager
    async def fake_context():
        lifecycle.append("context_enter")
        try:
            yield FakeEligibilityService()
        finally:
            lifecycle.append("context_exit")

    monkeypatch.setattr("app.api.v1.assessments.assessment_eligibility_service_context", fake_context)

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(hs6_code="11031100"),
    )

    assert response.status_code == 200, response.text
    assert captured_payloads[0].hs6_code == "110311"
    assert lifecycle == ["context_enter", "service_called", "context_exit"]
    assert response.headers["X-AIS-Case-Id"] == case_id
    assert response.headers["X-AIS-Evaluation-Id"] == evaluation_id
    assert response.headers["X-AIS-Audit-URL"] == f"/api/v1/audit/evaluations/{evaluation_id}"
    assert response.json()["audit_persisted"] is True


def test_eligibility_request_accepts_year_2025() -> None:
    payload = EligibilityRequest.model_validate(_assessment_payload(year=2025))

    assert payload.year == 2025


@pytest.mark.asyncio
async def test_assessments_route_rejects_year_2019_with_422(
    async_client: AsyncClient,
) -> None:
    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(year=2019),
    )

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], list)
    assert any(
        error["loc"][-1] == "year"
        and error["msg"] == f"Value error, year must be between 2020 and {date.today().year + 1}; got 2019"
        for error in body["detail"]
    )


@pytest.mark.asyncio
async def test_assessments_route_rejects_year_beyond_next_calendar_year_with_422(
    async_client: AsyncClient,
) -> None:
    future_year = date.today().year + 2

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(year=future_year),
    )

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], list)
    assert any(
        error["loc"][-1] == "year"
        and error["msg"] == (
            f"Value error, year must be between 2020 and {date.today().year + 1}; got {future_year}"
        )
        for error in body["detail"]
    )


@pytest.mark.asyncio
async def test_assessments_case_alias_calls_interface_case_and_sets_headers(
    app: FastAPI,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())
    lifecycle: list[str] = []

    class FakeEligibilityService:
        async def assess_interface_case(self, requested_case_id: str, payload) -> object:
            lifecycle.append("service_called")
            assert requested_case_id == case_id
            assert payload.year == 2025
            assert payload.existing_documents == ["certificate_of_origin"]
            return SimpleNamespace(
                case_id=case_id,
                evaluation_id=evaluation_id,
                response=_assessment_response(),
            )

    @asynccontextmanager
    async def fake_context():
        lifecycle.append("context_enter")
        try:
            yield FakeEligibilityService()
        finally:
            lifecycle.append("context_exit")

    monkeypatch.setattr("app.api.v1.assessments.assessment_eligibility_service_context", fake_context)

    response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025, "submitted_documents": ["certificate_of_origin"]},
    )

    assert response.status_code == 200, response.text
    assert lifecycle == ["context_enter", "service_called", "context_exit"]
    assert response.headers["X-AIS-Case-Id"] == case_id
    assert response.headers["X-AIS-Evaluation-Id"] == evaluation_id
    assert response.json()["pathway_used"] == "CTH"


@pytest.mark.asyncio
async def test_assessments_route_returns_structured_persistence_error_when_context_close_fails(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle: list[str] = []

    class FakeEligibilityService:
        async def assess_interface_request(self, payload) -> object:
            lifecycle.append("service_called")
            return SimpleNamespace(
                case_id=str(uuid4()),
                evaluation_id=str(uuid4()),
                response=_assessment_response(),
            )

    @asynccontextmanager
    async def failing_context():
        lifecycle.append("context_enter")
        try:
            yield FakeEligibilityService()
        finally:
            lifecycle.append("context_exit")
            raise EvaluationPersistenceError(
                "Assessment transaction failed while closing the replayable snapshot",
                detail={"reason": "assessment_transaction_close_failed"},
            )

    monkeypatch.setattr("app.api.v1.assessments.assessment_eligibility_service_context", failing_context)

    response = await async_client.post(
        "/api/v1/assessments",
        json=_assessment_payload(),
    )

    assert lifecycle == ["context_enter", "service_called", "context_exit"]
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "EVALUATION_PERSISTENCE_ERROR"
    assert response.json()["error"]["details"] == {
        "reason": "assessment_transaction_close_failed",
    }
