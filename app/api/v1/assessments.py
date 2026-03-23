"""Thin route handlers for running deterministic eligibility assessments."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_assessment_eligibility_service
from app.schemas.assessments import EligibilityAssessmentResponse, EligibilityRequest
from app.services.eligibility_service import EligibilityService

router = APIRouter()


@router.post("/assessments", response_model=EligibilityAssessmentResponse)
async def assess_case(
    payload: EligibilityRequest,
    eligibility_service: EligibilityService = Depends(get_assessment_eligibility_service),
) -> EligibilityAssessmentResponse:
    """Run the full eligibility orchestrator for the provided payload."""

    return await eligibility_service.assess(payload)
