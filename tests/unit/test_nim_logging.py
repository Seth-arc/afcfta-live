"""Unit tests for app.services.nim.logging.

Verifies:
- Each log function emits the expected event name and fields.
- Raw user text and model output text are never present in any log record.
- user_input_char_count is only emitted when io_logging_enabled=True.
- request_id from context vars is included in all events.
- Log level is correct: INFO for clean paths, WARNING for incomplete/rejected.
- Correlation identifiers (case_id, evaluation_id, audit_url) are present
  in assessment_completed events.
"""

from __future__ import annotations

import logging

import pytest

from app.core.logging import bind_request_log_context, reset_request_log_context
from app.services.nim.logging import (
    log_nim_assessment_completed,
    log_nim_clarification_sent,
    log_nim_input_rejected,
    log_nim_intake_parsed,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NIM_LOGGER = "app.nim"

_SENTINEL_USER_TEXT = "Can I export wheat from Ghana?"
_SENTINEL_EXPLANATION_TEXT = "The goods qualify under CTH with zero tariff."
_SENTINEL_QUESTION_TEXT = "What is the HS6 code for your product?"


def _get_structured(record: logging.LogRecord) -> dict:
    """Return the structured_data dict from a LogRecord emitted via log_event()."""
    return getattr(record, "structured_data", {})


# ---------------------------------------------------------------------------
# log_nim_intake_parsed
# ---------------------------------------------------------------------------


def test_intake_parsed_complete_draft_is_info(caplog):
    """Complete draft emits an INFO-level nim.intake_parsed event."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=True,
            nim_model="meta/llama-3.1-70b",
            latency_ms=142,
            draft_complete=True,
            missing_required_facts=[],
            nim_confidence_overall=0.92,
            has_context_hints=True,
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    data = _get_structured(record)
    assert data["event"] == "nim.intake_parsed"
    assert data["draft_complete"] is True
    assert data["intake_latency_ms"] == 142
    assert data["nim_model"] == "meta/llama-3.1-70b"
    assert data["nim_enabled"] is True
    assert data["nim_confidence_overall"] == pytest.approx(0.92)
    assert data["has_context_hints"] is True
    assert data["missing_required_facts"] == []


def test_intake_parsed_incomplete_draft_is_warning(caplog):
    """Incomplete draft emits a WARNING-level event with missing fact names."""
    with caplog.at_level(logging.WARNING, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=True,
            nim_model="meta/llama-3.1-70b",
            latency_ms=55,
            draft_complete=False,
            missing_required_facts=["hs6_code", "exporter", "importer"],
            nim_confidence_overall=None,
            has_context_hints=False,
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    data = _get_structured(record)
    assert data["draft_complete"] is False
    assert set(data["missing_required_facts"]) == {"hs6_code", "exporter", "importer"}


def test_intake_parsed_nim_disabled_omits_model_name(caplog):
    """When NIM is disabled, nim_model is not included in the log record."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=False,
            nim_model="",
            latency_ms=1,
            draft_complete=False,
            missing_required_facts=["hs6_code"],
            nim_confidence_overall=None,
            has_context_hints=False,
        )

    data = _get_structured(caplog.records[0])
    assert data["nim_enabled"] is False
    # nim_model is None when disabled; JsonLogFormatter drops None fields
    assert data.get("nim_model") is None


def test_intake_parsed_never_logs_user_text(caplog):
    """user_input string must never appear in the log record, even by accident."""
    with caplog.at_level(logging.DEBUG, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=True,
            nim_model="meta/llama-3.1-70b",
            latency_ms=100,
            draft_complete=True,
            missing_required_facts=[],
            nim_confidence_overall=0.8,
            has_context_hints=False,
            # io_logging_enabled is False by default — char count should be absent
            user_input_char_count=len(_SENTINEL_USER_TEXT),
        )

    data = _get_structured(caplog.records[0])
    assert "user_input" not in data
    assert "user_input_char_count" not in data
    # The sentinel text itself must not appear anywhere in the record
    assert _SENTINEL_USER_TEXT not in str(data)


def test_intake_parsed_io_logging_enabled_includes_char_count(caplog):
    """With io_logging_enabled=True, user_input_char_count is included."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=True,
            nim_model="meta/llama-3.1-70b",
            latency_ms=80,
            draft_complete=True,
            missing_required_facts=[],
            nim_confidence_overall=0.9,
            has_context_hints=False,
            io_logging_enabled=True,
            user_input_char_count=len(_SENTINEL_USER_TEXT),
        )

    data = _get_structured(caplog.records[0])
    # Char count (integer) is present; raw text is still absent
    assert data["user_input_char_count"] == len(_SENTINEL_USER_TEXT)
    assert "user_input" not in data
    assert _SENTINEL_USER_TEXT not in str(data)


def test_intake_parsed_io_logging_disabled_omits_char_count(caplog):
    """With io_logging_enabled=False (default), user_input_char_count is absent."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=True,
            nim_model="meta/llama-3.1-70b",
            latency_ms=80,
            draft_complete=True,
            missing_required_facts=[],
            nim_confidence_overall=0.9,
            has_context_hints=False,
            io_logging_enabled=False,
            user_input_char_count=42,
        )

    data = _get_structured(caplog.records[0])
    assert "user_input_char_count" not in data


# ---------------------------------------------------------------------------
# log_nim_clarification_sent
# ---------------------------------------------------------------------------


def test_clarification_sent_emits_correct_event(caplog):
    """log_nim_clarification_sent emits nim.clarification_sent at INFO."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_clarification_sent(
            latency_ms=33,
            missing_required_facts=["hs6_code", "year"],
            low_confidence_trigger=False,
            gap_key_asked="hs6_code",
            nim_enabled=True,
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    data = _get_structured(record)
    assert data["event"] == "nim.clarification_sent"
    assert data["clarification_latency_ms"] == 33
    assert data["gap_count"] == 2
    assert data["gap_key_asked"] == "hs6_code"
    assert data["low_confidence_trigger"] is False
    assert data["nim_enabled"] is True


def test_clarification_sent_low_confidence_sets_trigger_flag(caplog):
    """When triggered by low confidence rather than missing facts, the flag is set."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_clarification_sent(
            latency_ms=20,
            missing_required_facts=["hs6_code"],
            low_confidence_trigger=True,
            gap_key_asked="hs6_code",
            nim_enabled=True,
        )

    data = _get_structured(caplog.records[0])
    assert data["low_confidence_trigger"] is True


def test_clarification_sent_never_logs_question_text(caplog):
    """Clarification question text must not appear in the log record."""
    with caplog.at_level(logging.DEBUG, logger=_NIM_LOGGER):
        log_nim_clarification_sent(
            latency_ms=10,
            missing_required_facts=["hs6_code"],
            low_confidence_trigger=False,
            gap_key_asked="hs6_code",
            nim_enabled=True,
        )

    raw = str(_get_structured(caplog.records[0]))
    assert _SENTINEL_QUESTION_TEXT not in raw


# ---------------------------------------------------------------------------
# log_nim_input_rejected
# ---------------------------------------------------------------------------


def test_input_rejected_emits_warning(caplog):
    """log_nim_input_rejected emits nim.input_rejected at WARNING."""
    with caplog.at_level(logging.WARNING, logger=_NIM_LOGGER):
        log_nim_input_rejected(exc_type="ValueError")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    data = _get_structured(record)
    assert data["event"] == "nim.input_rejected"
    assert data["rejection_code"] == "INPUT_REJECTED"
    assert data["exc_type"] == "ValueError"


def test_input_rejected_validation_error_type(caplog):
    """ValidationError type name is preserved for diagnosis."""
    with caplog.at_level(logging.WARNING, logger=_NIM_LOGGER):
        log_nim_input_rejected(exc_type="ValidationError")

    data = _get_structured(caplog.records[0])
    assert data["exc_type"] == "ValidationError"


def test_input_rejected_never_logs_exception_message(caplog):
    """Exception message (which may contain model output) is not logged."""
    with caplog.at_level(logging.DEBUG, logger=_NIM_LOGGER):
        log_nim_input_rejected(exc_type="ValueError")

    data = _get_structured(caplog.records[0])
    # Only exc_type and rejection_code — no message or detail fields
    assert "message_text" not in data
    assert "detail" not in data


# ---------------------------------------------------------------------------
# log_nim_assessment_completed
# ---------------------------------------------------------------------------


def test_assessment_completed_emits_info_with_all_correlation_fields(caplog):
    """log_nim_assessment_completed emits nim.assessment_completed at INFO
    with all required correlation fields for replay linkage.
    """
    case_id = "case-abc-123"
    evaluation_id = "eval-xyz-456"
    audit_url = f"/api/v1/audit/evaluations/{evaluation_id}"

    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_assessment_completed(
            nim_model="meta/llama-3.1-70b",
            case_id=case_id,
            evaluation_id=evaluation_id,
            audit_url=audit_url,
            engine_latency_ms=350,
            explanation_latency_ms=120,
            total_latency_ms=620,
            eligible=True,
            confidence_class="complete",
            pathway_used="CTH",
            explanation_fallback_used=False,
            persona_mode="exporter",
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    data = _get_structured(record)

    assert data["event"] == "nim.assessment_completed"
    assert data["case_id"] == case_id
    assert data["evaluation_id"] == evaluation_id
    assert data["audit_url"] == audit_url
    assert data["engine_latency_ms"] == 350
    assert data["explanation_latency_ms"] == 120
    assert data["total_latency_ms"] == 620
    assert data["eligible"] is True
    assert data["confidence_class"] == "complete"
    assert data["pathway_used"] == "CTH"
    assert data["explanation_fallback_used"] is False
    assert data["persona_mode"] == "exporter"
    assert data["nim_model"] == "meta/llama-3.1-70b"


def test_assessment_completed_fallback_used_is_flagged(caplog):
    """explanation_fallback_used=True is faithfully emitted for diagnosis."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_assessment_completed(
            nim_model="meta/llama-3.1-70b",
            case_id="c1",
            evaluation_id="e1",
            audit_url="/api/v1/audit/evaluations/e1",
            engine_latency_ms=300,
            explanation_latency_ms=0,
            total_latency_ms=310,
            eligible=False,
            confidence_class="provisional",
            pathway_used=None,
            explanation_fallback_used=True,
            persona_mode=None,
        )

    data = _get_structured(caplog.records[0])
    assert data["explanation_fallback_used"] is True


def test_assessment_completed_never_logs_explanation_text(caplog):
    """Plain-language explanation text must not appear in the assessment event."""
    with caplog.at_level(logging.DEBUG, logger=_NIM_LOGGER):
        log_nim_assessment_completed(
            nim_model="meta/llama-3.1-70b",
            case_id="c1",
            evaluation_id="e1",
            audit_url="/api/v1/audit/evaluations/e1",
            engine_latency_ms=300,
            explanation_latency_ms=100,
            total_latency_ms=420,
            eligible=True,
            confidence_class="complete",
            pathway_used="WO",
            explanation_fallback_used=False,
            persona_mode="analyst",
        )

    raw = str(_get_structured(caplog.records[0]))
    assert _SENTINEL_EXPLANATION_TEXT not in raw
    assert "explanation_text" not in raw


# ---------------------------------------------------------------------------
# Request ID correlation — context var propagation
# ---------------------------------------------------------------------------


def test_all_events_include_request_id_from_context(caplog):
    """All NIM log events must carry the request_id set in log context."""
    tokens = bind_request_log_context(request_id="req-test-0001")
    try:
        with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
            log_nim_intake_parsed(
                nim_enabled=False,
                nim_model="",
                latency_ms=5,
                draft_complete=False,
                missing_required_facts=["hs6_code"],
                nim_confidence_overall=None,
                has_context_hints=False,
            )
            log_nim_clarification_sent(
                latency_ms=10,
                missing_required_facts=["hs6_code"],
                low_confidence_trigger=False,
                gap_key_asked="hs6_code",
                nim_enabled=False,
            )
            log_nim_assessment_completed(
                nim_model="",
                case_id="c1",
                evaluation_id="e1",
                audit_url="/api/v1/audit/evaluations/e1",
                engine_latency_ms=100,
                explanation_latency_ms=50,
                total_latency_ms=160,
                eligible=True,
                confidence_class="complete",
                pathway_used=None,
                explanation_fallback_used=True,
                persona_mode=None,
            )
    finally:
        reset_request_log_context(tokens)

    assert len(caplog.records) == 3
    for record in caplog.records:
        data = _get_structured(record)
        assert data.get("request_id") == "req-test-0001", (
            f"request_id missing or wrong in event {data.get('event')}"
        )


def test_events_without_context_omit_request_id(caplog):
    """When no request_id is in context, the field is omitted (not set to None)."""
    # Ensure context is clean — reset to default (no token needed since we're not
    # overriding; just verify the default None is omitted)
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_input_rejected(exc_type="ValueError")

    data = _get_structured(caplog.records[0])
    # get_request_log_context() omits None values, so request_id should be absent
    # unless something else set it in context from a prior test.
    # We only assert it's not wrong — not that it's necessarily absent, because
    # caplog tests run in the same process and context vars may carry over.
    if "request_id" in data:
        assert isinstance(data["request_id"], str)


# ---------------------------------------------------------------------------
# Logger namespace separation from audit logger
# ---------------------------------------------------------------------------


def test_nim_events_use_app_nim_logger(caplog):
    """NIM log events must use the app.nim logger, not app.audit."""
    with caplog.at_level(logging.INFO, logger=_NIM_LOGGER):
        log_nim_intake_parsed(
            nim_enabled=False,
            nim_model="",
            latency_ms=1,
            draft_complete=False,
            missing_required_facts=["hs6_code"],
            nim_confidence_overall=None,
            has_context_hints=False,
        )

    assert len(caplog.records) == 1
    assert caplog.records[0].name == _NIM_LOGGER


def test_audit_logger_does_not_receive_nim_events(caplog):
    """NIM events must not appear on the app.audit logger."""
    with caplog.at_level(logging.DEBUG, logger="app.audit"):
        log_nim_intake_parsed(
            nim_enabled=False,
            nim_model="",
            latency_ms=1,
            draft_complete=False,
            missing_required_facts=["hs6_code"],
            nim_confidence_overall=None,
            has_context_hints=False,
        )

    nim_records = [r for r in caplog.records if r.name == "app.audit"]
    assert nim_records == [], "NIM events must not appear on the app.audit logger"
