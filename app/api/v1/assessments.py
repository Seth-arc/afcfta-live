"""Thin route handlers for running deterministic eligibility assessments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import require_assessment_rate_limit
from app.api.deps import get_assessment_eligibility_service
from app.schemas.assessments import (
    CaseAssessmentRequest,
    EligibilityAssessmentResponse,
    EligibilityRequest,
)
from app.services.eligibility_service import EligibilityService

router = APIRouter(dependencies=[Depends(require_assessment_rate_limit)])


@router.post("/assessments", response_model=EligibilityAssessmentResponse)
async def assess_case(
    payload: EligibilityRequest,
    response: Response,
    eligibility_service: EligibilityService = Depends(get_assessment_eligibility_service),
) -> EligibilityAssessmentResponse:
    """Run the full eligibility orchestrator for the provided payload."""

    assessment = await eligibility_service.assess_interface_request(payload)
    response.headers["X-AIS-Case-Id"] = assessment.case_id
    response.headers["X-AIS-Evaluation-Id"] = assessment.evaluation_id
    response.headers["X-AIS-Audit-URL"] = f"/api/v1/audit/evaluations/{assessment.evaluation_id}"
    return assessment.response


@router.post("/assessments/cases/{case_id}", response_model=EligibilityAssessmentResponse)
async def assess_stored_case(
    case_id: str,
    payload: CaseAssessmentRequest,
    response: Response,
    eligibility_service: EligibilityService = Depends(get_assessment_eligibility_service),
) -> EligibilityAssessmentResponse:
    """Run the full eligibility orchestrator using facts already stored on a case."""

    assessment = await eligibility_service.assess_interface_case(case_id, payload)
    response.headers["X-AIS-Case-Id"] = assessment.case_id
    response.headers["X-AIS-Evaluation-Id"] = assessment.evaluation_id
    response.headers["X-AIS-Audit-URL"] = f"/api/v1/audit/evaluations/{assessment.evaluation_id}"
    return assessment.response
