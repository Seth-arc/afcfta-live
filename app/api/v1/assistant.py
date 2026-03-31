"""NIM-assisted eligibility assessment endpoint.

Orchestration boundary:
- NIM parses and explains. It never decides eligibility.
- The deterministic engine (EligibilityService) is the sole source of
  truth for all legal decision fields.
- The DB connection for the engine is opened lazily: only when the draft
  passes all completeness and confidence checks and the engine call is
  actually needed. Clarification responses and schema-level 422s are served
  without any DB access.
- assess_interface_request() guarantees a replayable audit trail before
  returning. Persistence failure propagates as 500 — no unreplayable
  decision is ever returned to the caller.
- Explanation is additive only and never alters assessment fields.
- Rate limiting matches the /assessments route (assessment_rate_limit).

Early-exit conditions (no DB connection, no engine call):
1. FastAPI rejects `user_input` longer than 2000 characters with HTTP 422.
2. Required draft facts missing (hs6_code, exporter, importer, year, persona_mode).
3. NIM confidence below _MIN_NIM_CONFIDENCE (0.7) when present.
4. to_eligibility_request() raises ValueError or ValidationError (malformed draft).
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from pydantic import ValidationError

from app.api.deps import (
    get_clarification_service,
    get_explanation_service,
    get_intake_service,
    require_assessment_rate_limit,
    run_replayable_interface_assessment,
    schedule_advisory_alert_dispatch,
)
from app.config import Settings, get_settings
from app.schemas.nim.assistant import (
    AssistantError,
    AssistantRequest,
    AssistantResponseEnvelope,
)
from app.schemas.nim.clarification import ClarificationContext
from app.services.nim.clarification_service import ClarificationService
from app.services.nim.explanation_service import ExplanationService
from app.services.nim.intake_service import IntakeService
from app.services.nim.logging import (
    log_nim_assessment_completed,
    log_nim_clarification_sent,
    log_nim_input_rejected,
    log_nim_intake_parsed,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_assessment_rate_limit)])

# Minimum NIM confidence required to proceed to the engine without clarification.
_MIN_NIM_CONFIDENCE: float = 0.7


@router.post("/assistant/assess", response_model=AssistantResponseEnvelope)
async def assistant_assess(
    payload: AssistantRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    intake_service: IntakeService = Depends(get_intake_service),
    clarification_service: ClarificationService = Depends(get_clarification_service),
    explanation_service: ExplanationService = Depends(get_explanation_service),
    settings: Settings = Depends(get_settings),
) -> AssistantResponseEnvelope:
    """NIM-assisted eligibility assessment.

    The DB connection is opened lazily: only on the assessment path, after
    all completeness checks pass. Clarification responses and schema-level 422s are served
    without any DB access.

    Orchestration flow:
    1. Parse natural-language input — IntakeService calls NIM and validates JSON.
       Falls back to an empty draft when NIM is disabled or fails.
    2. Clarification gate — if intake rejects the raw text, required facts are
       absent, or NIM confidence is below threshold, return a
       ClarificationResponse. No DB connection made.
    3. Map draft to EligibilityRequest, stripping all NIM-only metadata. Return
       an error envelope if the mapping itself is rejected. No DB connection made.
    4. Open a REPEATABLE READ DB session, run the deterministic engine, close the
       read snapshot, then persist the replay header on a detached write session.
       Set replay headers.
    5. Generate plain-language explanation via ExplanationService (deterministic
       fallback always fires; explanation never alters assessment fields).
    6. Return combined AssistantResponseEnvelope.
    """
    t_start = time.monotonic()

    # -------------------------------------------------------------------------
    # Step 1: Parse natural-language input into a structured draft
    # -------------------------------------------------------------------------
    t_intake = time.monotonic()
    draft = await intake_service.parse_user_input(payload.user_input, payload.context)
    intake_latency_ms = int((time.monotonic() - t_intake) * 1000)

    missing_facts = draft.missing_required_facts()

    log_nim_intake_parsed(
        nim_enabled=intake_service.nim_client.enabled,
        nim_model=intake_service.nim_client.model,
        latency_ms=intake_latency_ms,
        draft_complete=len(missing_facts) == 0,
        missing_required_facts=missing_facts,
        nim_confidence_overall=(
            draft.nim_confidence.overall if draft.nim_confidence is not None else None
        ),
        has_context_hints=payload.context is not None,
        io_logging_enabled=settings.NIM_LOG_IO,
        user_input_char_count=len(payload.user_input) if settings.NIM_LOG_IO else None,
    )

    # -------------------------------------------------------------------------
    # Step 2: Completeness and confidence gate → clarification (no DB)
    # -------------------------------------------------------------------------
    low_confidence = (
        draft.nim_confidence is not None
        and draft.nim_confidence.overall < _MIN_NIM_CONFIDENCE
    )

    if draft.nim_rejection_reason is not None:
        t_clr = time.monotonic()
        clarification = await clarification_service.generate_clarification(
            ClarificationContext(nim_rejection_reason=draft.nim_rejection_reason)
        )
        clr_latency_ms = int((time.monotonic() - t_clr) * 1000)

        log_nim_clarification_sent(
            latency_ms=clr_latency_ms,
            missing_required_facts=[],
            low_confidence_trigger=False,
            gap_key_asked="nim_input_retry_shorter",
            nim_enabled=clarification_service.nim_client.enabled,
        )

        return AssistantResponseEnvelope(
            response_type="clarification",
            audit_persisted=False,
            clarification=clarification,
        )

    if missing_facts or low_confidence:
        # When only confidence is insufficient (all required facts present),
        # ask about hs6_code — the highest-value fact to re-confirm.
        clarification_missing = missing_facts if missing_facts else ["hs6_code"]
        clarification_context = ClarificationContext(
            missing_draft_facts=clarification_missing
        )

        t_clr = time.monotonic()
        clarification = await clarification_service.generate_clarification(
            clarification_context
        )
        clr_latency_ms = int((time.monotonic() - t_clr) * 1000)

        log_nim_clarification_sent(
            latency_ms=clr_latency_ms,
            missing_required_facts=clarification_missing,
            low_confidence_trigger=low_confidence and not missing_facts,
            gap_key_asked=clarification_missing[0],
            nim_enabled=clarification_service.nim_client.enabled,
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
        log_nim_input_rejected(exc_type=type(exc).__name__)
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
    t_engine = time.monotonic()
    result = await run_replayable_interface_assessment(eligibility_request)
    engine_latency_ms = int((time.monotonic() - t_engine) * 1000)
    schedule_advisory_alert_dispatch(
        background_tasks,
        getattr(result, "pending_alert_specs", None),
    )

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

    t_expl = time.monotonic()
    explanation_result = await explanation_service.generate_explanation(
        assessment=result.response,
        persona_mode=persona_mode_str,
        hs6_code=eligibility_request.hs6_code,
        exporter=eligibility_request.exporter,
        importer=eligibility_request.importer,
    )
    expl_latency_ms = int((time.monotonic() - t_expl) * 1000)

    total_latency_ms = int((time.monotonic() - t_start) * 1000)

    log_nim_assessment_completed(
        nim_model=explanation_service.nim_client.model,
        case_id=result.case_id,
        evaluation_id=result.evaluation_id,
        audit_url=audit_url,
        engine_latency_ms=engine_latency_ms,
        explanation_latency_ms=expl_latency_ms,
        total_latency_ms=total_latency_ms,
        eligible=result.response.eligible,
        confidence_class=result.response.confidence_class,
        pathway_used=result.response.pathway_used,
        explanation_fallback_used=explanation_result.fallback_used,
        persona_mode=persona_mode_str,
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
        explanation_fallback_used=explanation_result.fallback_used,
    )
