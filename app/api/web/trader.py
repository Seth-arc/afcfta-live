"""Same-origin browser routes for the trader UI.

These routes expose only the narrow trader-safe operations the browser needs.
They do not require the browser to know the machine-client API key.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.api.deps import (
    get_audit_service,
    get_clarification_service,
    get_explanation_service,
    get_intake_service,
    get_rendering_service,
    require_assessment_rate_limit,
    require_default_rate_limit,
    rewrite_browser_audit_url,
)
from app.api.v1.assessments import assess_case as machine_assess_case
from app.api.v1.assistant import assistant_assess as machine_assistant_assess
from app.api.v1.audit import get_evaluation_audit_trail as machine_get_evaluation_audit_trail
from app.config import Settings, get_settings
from app.schemas.assessments import EligibilityAssessmentResponse, EligibilityRequest
from app.schemas.audit import AuditTrail
from app.schemas.nim.assistant import AssistantRequest, AssistantResponseEnvelope
from app.services.audit_service import AuditService
from app.services.nim.clarification_service import ClarificationService
from app.services.nim.explanation_service import ExplanationService
from app.services.nim.intake_service import IntakeService
from app.services.nim.rendering_service import RenderingService

router = APIRouter()


def _rewrite_replay_headers_for_browser(response: Response) -> None:
    """Rewrite machine audit URLs to the browser-safe BFF path family."""

    browser_audit_url = rewrite_browser_audit_url(
        response.headers.get("X-AIS-Audit-URL")
    )
    if browser_audit_url is not None:
        response.headers["X-AIS-Audit-URL"] = browser_audit_url


@router.post(
    "/assessments",
    response_model=EligibilityAssessmentResponse,
    dependencies=[Depends(require_assessment_rate_limit)],
)
async def browser_assess_case(
    payload: EligibilityRequest,
    response: Response,
    background_tasks: BackgroundTasks,
) -> EligibilityAssessmentResponse:
    """Run one deterministic assessment for the same-origin trader UI."""

    assessment = await machine_assess_case(
        payload=payload,
        response=response,
        background_tasks=background_tasks,
    )
    _rewrite_replay_headers_for_browser(response)
    return assessment


@router.post(
    "/assistant/assess",
    response_model=AssistantResponseEnvelope,
    dependencies=[Depends(require_assessment_rate_limit)],
)
async def browser_assistant_assess(
    payload: AssistantRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    intake_service: IntakeService = Depends(get_intake_service),
    clarification_service: ClarificationService = Depends(get_clarification_service),
    explanation_service: ExplanationService = Depends(get_explanation_service),
    rendering_service: RenderingService = Depends(get_rendering_service),
    settings: Settings = Depends(get_settings),
) -> AssistantResponseEnvelope:
    """Proxy the trader UI assistant flow without exposing machine auth."""

    envelope = await machine_assistant_assess(
        payload=payload,
        response=response,
        background_tasks=background_tasks,
        intake_service=intake_service,
        clarification_service=clarification_service,
        explanation_service=explanation_service,
        rendering_service=rendering_service,
        settings=settings,
    )

    browser_audit_url = rewrite_browser_audit_url(
        response.headers.get("X-AIS-Audit-URL") or envelope.audit_url
    )
    if browser_audit_url is None:
        return envelope

    response.headers["X-AIS-Audit-URL"] = browser_audit_url
    return envelope.model_copy(update={"audit_url": browser_audit_url})


@router.get(
    "/audit/evaluations/{evaluation_id}",
    response_model=AuditTrail,
    dependencies=[Depends(require_default_rate_limit)],
)
async def browser_get_evaluation_audit_trail(
    evaluation_id: str,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditTrail:
    """Return one persisted decision trace through the browser-safe path family."""

    return await machine_get_evaluation_audit_trail(
        evaluation_id=evaluation_id,
        audit_service=audit_service,
    )
