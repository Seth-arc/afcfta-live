"""Thin route handlers for running deterministic eligibility assessments."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.api.deps import require_assessment_rate_limit
from app.api.deps import assessment_eligibility_service_context
from app.api.deps import schedule_advisory_alert_dispatch
from app.schemas.assessments import (
    CaseAssessmentRequest,
    EligibilityAssessmentResponse,
    EligibilityRequest,
)

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
    background_tasks: BackgroundTasks,
) -> EligibilityAssessmentResponse:
    """Run one assessment and return only after the replayable transaction has closed."""

    async with assessment_eligibility_service_context() as eligibility_service:
        assessment = await eligibility_service.assess_interface_request(payload)
    schedule_advisory_alert_dispatch(
        background_tasks,
        getattr(assessment, "pending_alert_specs", None),
    )
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
    background_tasks: BackgroundTasks,
) -> EligibilityAssessmentResponse:
    """Compatibility alias that closes the assessment transaction before responding."""

    async with assessment_eligibility_service_context() as eligibility_service:
        assessment = await eligibility_service.assess_interface_case(case_id, payload)
    schedule_advisory_alert_dispatch(
        background_tasks,
        getattr(assessment, "pending_alert_specs", None),
    )
    _set_replay_headers(
        response,
        case_id=assessment.case_id,
        evaluation_id=assessment.evaluation_id,
    )
    return assessment.response
