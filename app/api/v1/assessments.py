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


def _set_replay_headers(response: Response, *, case_id: str, evaluation_id: str) -> None:
    """Attach deterministic replay identifiers to one assessment response."""

    response.headers["X-AIS-Case-Id"] = case_id
    response.headers["X-AIS-Evaluation-Id"] = evaluation_id
    response.headers["X-AIS-Audit-URL"] = f"/api/v1/audit/evaluations/{evaluation_id}"


@router.post("/assessments", response_model=EligibilityAssessmentResponse)
async def assess_case(
    payload: EligibilityRequest,
    response: Response,
    eligibility_service: EligibilityService = Depends(get_assessment_eligibility_service),
) -> EligibilityAssessmentResponse:
    """Run the full eligibility orchestrator for the provided payload."""

    assessment = await eligibility_service.assess_interface_request(payload)
    _set_replay_headers(
        response,
        case_id=assessment.case_id,
        evaluation_id=assessment.evaluation_id,
    )
    return assessment.response


@router.post("/assessments/cases/{case_id}", response_model=EligibilityAssessmentResponse)
async def assess_stored_case(
    case_id: str,
    payload: CaseAssessmentRequest,
    response: Response,
    eligibility_service: EligibilityService = Depends(get_assessment_eligibility_service),
) -> EligibilityAssessmentResponse:
    """Compatibility alias for POST /api/v1/cases/{case_id}/assess."""

    assessment = await eligibility_service.assess_interface_case(case_id, payload)
    _set_replay_headers(
        response,
        case_id=assessment.case_id,
        evaluation_id=assessment.evaluation_id,
    )
    return assessment.response
