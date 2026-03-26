"""Unit tests for assessment routes with mocked eligibility services."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_assessment_eligibility_service
from app.core.enums import RuleStatusEnum
from app.schemas.assessments import EligibilityAssessmentResponse, TariffOutcomeResponse


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
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())
    captured_payloads: list[object] = []

    class FakeEligibilityService:
        async def assess_interface_request(self, payload) -> object:
            captured_payloads.append(payload)
            return SimpleNamespace(
                case_id=case_id,
                evaluation_id=evaluation_id,
                response=_assessment_response(),
            )

    async def override_service() -> FakeEligibilityService:
        return FakeEligibilityService()

    app.dependency_overrides[get_assessment_eligibility_service] = override_service

    try:
        response = await async_client.post(
            "/api/v1/assessments",
            json={
                "hs6_code": "11031100",
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
            },
        )
    finally:
        app.dependency_overrides.pop(get_assessment_eligibility_service, None)

    assert response.status_code == 200, response.text
    assert captured_payloads[0].hs6_code == "110311"
    assert response.headers["X-AIS-Case-Id"] == case_id
    assert response.headers["X-AIS-Evaluation-Id"] == evaluation_id
    assert response.headers["X-AIS-Audit-URL"] == f"/api/v1/audit/evaluations/{evaluation_id}"
    assert response.json()["audit_persisted"] is True


@pytest.mark.asyncio
async def test_assessments_case_alias_calls_interface_case_and_sets_headers(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())

    class FakeEligibilityService:
        async def assess_interface_case(self, requested_case_id: str, payload) -> object:
            assert requested_case_id == case_id
            assert payload.year == 2025
            assert payload.existing_documents == ["certificate_of_origin"]
            return SimpleNamespace(
                case_id=case_id,
                evaluation_id=evaluation_id,
                response=_assessment_response(),
            )

    async def override_service() -> FakeEligibilityService:
        return FakeEligibilityService()

    app.dependency_overrides[get_assessment_eligibility_service] = override_service

    try:
        response = await async_client.post(
            f"/api/v1/assessments/cases/{case_id}",
            json={"year": 2025, "submitted_documents": ["certificate_of_origin"]},
        )
    finally:
        app.dependency_overrides.pop(get_assessment_eligibility_service, None)

    assert response.status_code == 200, response.text
    assert response.headers["X-AIS-Case-Id"] == case_id
    assert response.headers["X-AIS-Evaluation-Id"] == evaluation_id
    assert response.json()["pathway_used"] == "CTH"
