"""Thin route handlers for running deterministic eligibility assessments."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.api.deps import (
    _persist_prepared_interface_assessment,
    assessment_eligibility_service_context,
    require_assessment_rate_limit,
    schedule_advisory_alert_dispatch,
)
from app.schemas.assessments import (
    CaseAssessmentRequest,
    EligibilityAssessmentResponse,
    EligibilityRequest,
)
from app.services.eligibility_service import PreparedInterfaceAssessment

router = APIRouter(dependencies=[Depends(require_assessment_rate_limit)])


def _set_replay_headers(response: Response, *, case_id: str, evaluation_id: str) -> None:
    """Attach deterministic replay identifiers to one assessment response."""

    response.headers["X-AIS-Case-Id"] = case_id
    response.headers["X-AIS-Evaluation-Id"] = evaluation_id
    response.headers["X-AIS-Audit-URL"] = f"/api/v1/audit/evaluations/{evaluation_id}"


async def run_replayable_interface_assessment(payload: EligibilityRequest):
    """Run assessment in a repeatable-read scope, then persist replay state separately."""

    async with assessment_eligibility_service_context() as eligibility_service:
        prepared = await eligibility_service.prepare_interface_request_assessment(payload)
        if not isinstance(prepared, PreparedInterfaceAssessment):
            return await eligibility_service.assess_interface_request(payload)
    return await _persist_prepared_interface_assessment(prepared)


async def run_replayable_case_assessment(
    case_id: str,
    payload: CaseAssessmentRequest,
):
    """Run case-backed assessment in repeatable-read, then persist replay state separately."""

    async with assessment_eligibility_service_context() as eligibility_service:
        prepared = await eligibility_service.prepare_interface_case_assessment(case_id, payload)
        if not isinstance(prepared, PreparedInterfaceAssessment):
            return await eligibility_service.assess_interface_case(case_id, payload)
    return await _persist_prepared_interface_assessment(prepared)


@router.post("/assessments", response_model=EligibilityAssessmentResponse)
async def assess_case(
    payload: EligibilityRequest,
    response: Response,
    background_tasks: BackgroundTasks,
) -> EligibilityAssessmentResponse:
    """Run one assessment and return only after replay persistence succeeds."""

    assessment = await run_replayable_interface_assessment(payload)
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
    """Compatibility alias that persists replay state after the read snapshot closes."""

    assessment = await run_replayable_case_assessment(case_id, payload)
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
