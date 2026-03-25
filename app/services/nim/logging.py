"""NIM-layer operational logging.

Emits structured log events for each stage of the assistant orchestration path.
All events use the ``app.nim`` logger, distinct from the ``app.audit`` logger
used by the deterministic eligibility engine.

Separation from the legal audit trail
--------------------------------------
- These events are Python log records, not database writes.
- They carry NIM-specific operational metadata: latency, model config, fallback
  signals, and correlation identifiers.
- They do NOT write to the evaluations or cases tables.
- They do NOT duplicate eligibility-engine outcome logging (AuditService).
- The persisted audit trail (evaluations, check rows) is the legal record;
  these logs are the operational layer that connects assistant traffic to it.

What IS logged (always)
-----------------------
- ``request_id``        — from context vars; threads all events for one request.
- ``event``             — stable dotted name (``nim.intake_parsed`` etc.).
- ``nim_model``         — model identifier from NimClient config (not model output).
- ``nim_enabled``       — whether the model was active or bypassed entirely.
- ``latency_ms``        — wall-clock time for each NIM call and for the full request.
- ``draft_complete``    — whether all required engine facts were present.
- ``missing_required_facts`` — list of fact-key names (hs6_code, exporter, …), never values.
- ``nim_confidence_overall`` — NIM's own parsing confidence score, when present.
- ``fallback_used``     — True when the deterministic fallback replaced NIM output.
- Outcome fields from the deterministic engine (``eligible``, ``confidence_class``,
  ``pathway_used``) — these are engine outputs, not NIM output.
- Correlation keys: ``case_id``, ``evaluation_id``, ``audit_url`` when available.

What is intentionally NOT logged (ever)
----------------------------------------
- ``user_input``        — freeform text; PII/privacy risk by default.
- NIM model output text — explanation, clarification question, nim_assumptions.
- Production-fact values — may carry commercially sensitive numbers.
- Full EligibilityRequest or NimAssessmentDraft serialisations.

What is conditionally logged (NIM_LOG_IO=true only)
----------------------------------------------------
- ``user_input_char_count``  — integer length of user_input; no content.

Correlation path
----------------
Every event carries ``request_id`` (from context vars) so all stages of one
HTTP request are grouped. Assessment events additionally carry ``case_id``,
``evaluation_id``, and ``audit_url``, linking each NIM assistant session to
the specific persisted evaluation that can be replayed via
``GET /api/v1/audit/evaluations/{evaluation_id}``.
"""

from __future__ import annotations

import logging

from app.core.logging import log_event

logger = logging.getLogger("app.nim")


def log_nim_intake_parsed(
    *,
    nim_enabled: bool,
    nim_model: str,
    latency_ms: int,
    draft_complete: bool,
    missing_required_facts: list[str],
    nim_confidence_overall: float | None,
    has_context_hints: bool,
    io_logging_enabled: bool = False,
    user_input_char_count: int | None = None,
) -> None:
    """Emit an operational event after NIM parses the user's natural-language input.

    Level is WARNING when required facts are missing (clarification will follow);
    INFO when the draft is complete and the engine path is available.

    The ``user_input_char_count`` field is only included when ``io_logging_enabled``
    is True (NIM_LOG_IO setting). The raw user_input string is never logged.
    """
    fields: dict[str, object] = {
        "nim_enabled": nim_enabled,
        "nim_model": nim_model if nim_enabled else None,
        "intake_latency_ms": latency_ms,
        "draft_complete": draft_complete,
        "missing_required_facts": missing_required_facts,
        "nim_confidence_overall": nim_confidence_overall,
        "has_context_hints": has_context_hints,
    }
    if io_logging_enabled and user_input_char_count is not None:
        fields["user_input_char_count"] = user_input_char_count

    level = logging.INFO if draft_complete else logging.WARNING
    log_event(
        logger,
        level,
        event="nim.intake_parsed",
        message="NIM intake parsing complete",
        **fields,
    )


def log_nim_clarification_sent(
    *,
    latency_ms: int,
    missing_required_facts: list[str],
    low_confidence_trigger: bool,
    gap_key_asked: str,
    nim_enabled: bool,
) -> None:
    """Emit an event when a clarification response is returned to the caller.

    Logged at INFO. The question text is never included — only the gap key
    selected by the deterministic priority algorithm.
    """
    log_event(
        logger,
        logging.INFO,
        event="nim.clarification_sent",
        message="NIM assistant returning clarification response",
        clarification_latency_ms=latency_ms,
        missing_required_facts=missing_required_facts,
        gap_count=len(missing_required_facts),
        low_confidence_trigger=low_confidence_trigger,
        gap_key_asked=gap_key_asked,
        nim_enabled=nim_enabled,
    )


def log_nim_input_rejected(
    *,
    exc_type: str,
) -> None:
    """Emit a WARNING when the NIM draft cannot be mapped to an EligibilityRequest.

    Only the exception class name is logged. The exception message is not included
    because it may contain model-derived content.

    This event fires only at Step 3 (mapping), after the completeness gate has
    already passed. It signals a structural incompatibility, not missing facts.
    """
    log_event(
        logger,
        logging.WARNING,
        event="nim.input_rejected",
        message="NIM draft mapping rejected — returning error envelope",
        rejection_code="INPUT_REJECTED",
        exc_type=exc_type,
    )


def log_nim_assessment_completed(
    *,
    nim_model: str,
    case_id: str,
    evaluation_id: str,
    audit_url: str,
    engine_latency_ms: int,
    explanation_latency_ms: int,
    total_latency_ms: int,
    eligible: bool,
    confidence_class: str,
    pathway_used: str | None,
    explanation_fallback_used: bool,
    persona_mode: str | None,
) -> None:
    """Emit an event after the full assessment path completes successfully.

    Carries all correlation identifiers needed to link this assistant session
    to the persisted evaluation. The ``audit_url`` is the canonical path for
    replaying the deterministic decision.

    Engine outcome fields (``eligible``, ``confidence_class``, ``pathway_used``)
    are included here for quick operational diagnosis. They are always sourced
    from the deterministic engine output, never from NIM.

    Explanation text is never included; ``explanation_fallback_used`` signals
    whether the deterministic summary substituted for a NIM-generated text.
    """
    log_event(
        logger,
        logging.INFO,
        event="nim.assessment_completed",
        message="NIM assistant assessment completed",
        nim_model=nim_model,
        case_id=case_id,
        evaluation_id=evaluation_id,
        audit_url=audit_url,
        engine_latency_ms=engine_latency_ms,
        explanation_latency_ms=explanation_latency_ms,
        total_latency_ms=total_latency_ms,
        eligible=eligible,
        confidence_class=confidence_class,
        pathway_used=pathway_used,
        explanation_fallback_used=explanation_fallback_used,
        persona_mode=persona_mode,
    )
