"""NIM-assisted eligibility assessment endpoint.

Orchestration boundary:
- NIM parses and explains. It never decides eligibility.
- The deterministic engine (EligibilityService) is the sole source of
  truth for all legal decision fields.
- The DB connection for the engine is opened lazily: only when the draft
  passes all completeness and confidence checks and the engine call is
  actually needed. Clarification and 422 responses are served without
  any DB access.
- assess_interface_request() guarantees a replayable audit trail before
  returning. Persistence failure propagates as 500 — no unreplayable
  decision is ever returned to the caller.
- Explanation is additive only and never alters assessment fields.
- Rate limiting matches the /assessments route (assessment_rate_limit).

Early-exit conditions (no DB connection, no engine call):
1. Required draft facts missing (hs6_code, exporter, importer, year, persona_mode).
2. NIM confidence below _MIN_NIM_CONFIDENCE (0.7) when present.
3. to_eligibility_request() raises ValueError or ValidationError (malformed draft).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError

from app.api.deps import (
    assessment_eligibility_service_context,
    get_clarification_service,
    get_explanation_service,
    get_intake_service,
    require_assessment_rate_limit,
)
from app.schemas.nim.assistant import (
    AssistantError,
    AssistantRequest,
    AssistantResponseEnvelope,
)
from app.schemas.nim.clarification import ClarificationContext
from app.services.nim.clarification_service import ClarificationService
from app.services.nim.explanation_service import ExplanationService
from app.services.nim.intake_service import IntakeService

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_assessment_rate_limit)])

# Minimum NIM confidence required to proceed to the engine without clarification.
_MIN_NIM_CONFIDENCE: float = 0.7


@router.post("/assistant/assess", response_model=AssistantResponseEnvelope)
async def assistant_assess(
    payload: AssistantRequest,
    response: Response,
    intake_service: IntakeService = Depends(get_intake_service),
    clarification_service: ClarificationService = Depends(get_clarification_service),
    explanation_service: ExplanationService = Depends(get_explanation_service),
) -> AssistantResponseEnvelope:
    """NIM-assisted eligibility assessment.

    The DB connection is opened lazily: only on the assessment path, after
    all completeness checks pass. Clarification and 422 responses are served
    without any DB access.

    Orchestration flow:
    1. Parse natural-language input — IntakeService calls NIM and validates JSON.
       Falls back to an empty draft when NIM is disabled or fails.
    2. Completeness gate — if required facts are absent or NIM confidence is
       below threshold, return a ClarificationResponse. No DB connection made.
    3. Map draft to EligibilityRequest, stripping all NIM-only metadata. Return
       an error envelope if the mapping itself is rejected. No DB connection made.
    4. Open a REPEATABLE READ DB session and call assess_interface_request() for
       a guaranteed replayable audit trail. Set replay headers.
    5. Generate plain-language explanation via ExplanationService (deterministic
       fallback always fires; explanation never alters assessment fields).
    6. Return combined AssistantResponseEnvelope.
    """
    # -------------------------------------------------------------------------
    # Step 1: Parse natural-language input into a structured draft
    # -------------------------------------------------------------------------
    draft = await intake_service.parse_user_input(payload.user_input, payload.context)

    # -------------------------------------------------------------------------
    # Step 2: Completeness and confidence gate → clarification (no DB)
    # -------------------------------------------------------------------------
    missing_facts = draft.missing_required_facts()
    low_confidence = (
        draft.nim_confidence is not None
        and draft.nim_confidence.overall < _MIN_NIM_CONFIDENCE
    )

    if missing_facts or low_confidence:
        # When only confidence is insufficient (all required facts present),
        # ask about hs6_code — the highest-value fact to re-confirm.
        clarification_missing = missing_facts if missing_facts else ["hs6_code"]
        clarification_context = ClarificationContext(
            missing_draft_facts=clarification_missing
        )
        clarification = await clarification_service.generate_clarification(
            clarification_context
        )
        return AssistantResponseEnvelope(
            response_type="clarification",
            audit_persisted=False,
            clarification=clarification,
        )

    # -------------------------------------------------------------------------
    # Step 3: Map to live EligibilityRequest — reject malformed drafts (no DB)
    # -------------------------------------------------------------------------
    try:
        eligibility_request = intake_service.to_eligibility_request(draft)
    except (ValueError, ValidationError) as exc:
        logger.warning("NIM draft mapping rejected: %s", exc)
        return AssistantResponseEnvelope(
            response_type="error",
            audit_persisted=False,
            error=AssistantError(
                code="INPUT_REJECTED",
                message=str(exc),
            ),
        )

    # -------------------------------------------------------------------------
    # Step 4: Lazy DB open → guaranteed replayable engine run
    # The REPEATABLE READ session is opened here, only on the assessment path.
    # assess_interface_request() ensures an evaluation row exists before
    # returning. Persistence failure raises EvaluationPersistenceError → 500.
    # -------------------------------------------------------------------------
    async with assessment_eligibility_service_context() as eligibility_service:
        result = await eligibility_service.assess_interface_request(eligibility_request)

    audit_url = f"/api/v1/audit/evaluations/{result.evaluation_id}"
    response.headers["X-AIS-Case-Id"] = result.case_id
    response.headers["X-AIS-Evaluation-Id"] = result.evaluation_id
    response.headers["X-AIS-Audit-URL"] = audit_url

    # -------------------------------------------------------------------------
    # Step 5: Plain-language explanation — deterministic fallback always present
    # Persona mode: prefer caller-supplied context; fall back to NIM-parsed value.
    # -------------------------------------------------------------------------
    persona_mode_str: str | None = None
    if payload.context is not None and payload.context.persona_mode is not None:
        persona_mode_str = payload.context.persona_mode.value
    elif draft.context is not None and draft.context.persona_mode is not None:
        persona_mode_str = draft.context.persona_mode.value

    explanation_result = await explanation_service.generate_explanation(
        result.response, persona_mode_str
    )

    # -------------------------------------------------------------------------
    # Step 6: Return combined envelope
    # -------------------------------------------------------------------------
    return AssistantResponseEnvelope(
        response_type="assessment",
        case_id=result.case_id,
        evaluation_id=result.evaluation_id,
        audit_url=audit_url,
        audit_persisted=result.response.audit_persisted,
        assessment=result.response,
        explanation=explanation_result.text,
    )
