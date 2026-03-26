"""Unit tests for the NIM clarification schema and service.

Tests cover:
- ClarificationContext: empty-context rejection, valid single-group contexts,
  highest_priority_gap() ordering, has_any_gap().
- ClarificationService.generate_clarification():
  - NIM phrased question returned when valid JSON received.
  - Deterministic fallback on NIM disabled, invalid JSON, NimClientError.
  - Deterministic fallback when NIM output implies eligibility outcome.
  - Deterministic fallback on empty question from NIM.
  - missing_facts in response combines draft + engine missing facts.
  - missing_evidence in response mirrors context.
  - Priority: draft gaps trigger a question before engine facts.
  - Priority: engine facts trigger a question before evidence.
  - Deterministic templates are specific per gap type.
  - System prompt instructs NIM not to infer eligibility.
  - User input passed to NIM includes the gap key.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.schemas.nim.clarification import ClarificationContext
from app.services.nim.clarification_service import (
    ClarificationService,
    _INPUT_TOO_LONG_QUESTION,
    _deterministic_question,
    _question_implies_outcome,
    _NIM_PHRASING_SYSTEM_PROMPT,
)
from app.services.nim.client import NimClientError
from app.services.nim.intake_service import NIM_REJECTION_REASON_INPUT_TOO_LONG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(
    return_value: str | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    if raises is not None:
        client.generate_json = AsyncMock(side_effect=raises)
    else:
        client.generate_json = AsyncMock(return_value=return_value)
    return client


def _nim_question_json(question: str) -> str:
    return json.dumps({"question": question})


def _service(return_value: str | None = None, raises: Exception | None = None) -> ClarificationService:
    return ClarificationService(_mock_client(return_value, raises))


# ---------------------------------------------------------------------------
# ClarificationContext — validation
# ---------------------------------------------------------------------------


class TestClarificationContextValidation:
    def test_all_empty_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError, match="at least one gap"):
            ClarificationContext()

    def test_explicitly_empty_lists_raises(self) -> None:
        with pytest.raises(ValidationError):
            ClarificationContext(
                missing_draft_facts=[],
                missing_engine_facts=[],
                missing_evidence=[],
            )

    def test_missing_draft_facts_alone_is_valid(self) -> None:
        ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
        assert ctx.missing_draft_facts == ["hs6_code"]

    def test_missing_engine_facts_alone_is_valid(self) -> None:
        ctx = ClarificationContext(missing_engine_facts=["ex_works"])
        assert ctx.missing_engine_facts == ["ex_works"]

    def test_missing_evidence_alone_is_valid(self) -> None:
        ctx = ClarificationContext(missing_evidence=["certificate_of_origin"])
        assert ctx.missing_evidence == ["certificate_of_origin"]

    def test_nim_rejection_reason_alone_is_valid(self) -> None:
        ctx = ClarificationContext(
            nim_rejection_reason=NIM_REJECTION_REASON_INPUT_TOO_LONG
        )
        assert ctx.nim_rejection_reason == NIM_REJECTION_REASON_INPUT_TOO_LONG

    def test_failure_codes_only_still_raises(self) -> None:
        """failure_codes alone does not count as a gap."""
        with pytest.raises(ValidationError):
            ClarificationContext(failure_codes=["MISSING_CORE_FACTS"])

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClarificationContext(
                missing_draft_facts=["hs6_code"],
                invented_field="bad",
            )


# ---------------------------------------------------------------------------
# ClarificationContext — highest_priority_gap and has_any_gap
# ---------------------------------------------------------------------------


class TestClarificationContextHelpers:
    def test_highest_priority_returns_first_draft_fact(self) -> None:
        ctx = ClarificationContext(
            missing_draft_facts=["hs6_code", "exporter"],
            missing_engine_facts=["ex_works"],
            missing_evidence=["certificate_of_origin"],
        )
        assert ctx.highest_priority_gap() == "hs6_code"

    def test_highest_priority_skips_to_engine_facts_when_no_draft_gaps(self) -> None:
        ctx = ClarificationContext(
            missing_engine_facts=["ex_works", "non_originating"],
            missing_evidence=["certificate_of_origin"],
        )
        assert ctx.highest_priority_gap() == "ex_works"

    def test_highest_priority_falls_back_to_evidence_when_only_evidence_missing(self) -> None:
        ctx = ClarificationContext(missing_evidence=["invoice"])
        assert ctx.highest_priority_gap() == "invoice"

    def test_draft_facts_take_priority_over_engine_facts(self) -> None:
        ctx = ClarificationContext(
            missing_draft_facts=["year"],
            missing_engine_facts=["ex_works"],
        )
        assert ctx.highest_priority_gap() == "year"

    def test_engine_facts_take_priority_over_evidence(self) -> None:
        ctx = ClarificationContext(
            missing_engine_facts=["ex_works"],
            missing_evidence=["invoice"],
        )
        assert ctx.highest_priority_gap() == "ex_works"

    def test_has_any_gap_true_with_draft_facts(self) -> None:
        ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
        assert ctx.has_any_gap() is True

    def test_has_any_gap_true_with_engine_facts(self) -> None:
        ctx = ClarificationContext(missing_engine_facts=["ex_works"])
        assert ctx.has_any_gap() is True

    def test_has_any_gap_true_with_evidence(self) -> None:
        ctx = ClarificationContext(missing_evidence=["invoice"])
        assert ctx.has_any_gap() is True


# ---------------------------------------------------------------------------
# Outcome-implication guard (unit tests for the helper)
# ---------------------------------------------------------------------------


class TestQuestionImpliesOutcome:
    @pytest.mark.parametrize("phrase", [
        "This product will qualify under the AfCFTA rules.",
        "Your goods are eligible for preferential treatment.",
        "This will not qualify.",
        "It is unlikely to qualify.",
        "The shipment will pass inspection.",
        "This is compliant with the rules.",
        "Your application will be approved.",
    ])
    def test_outcome_phrases_detected(self, phrase: str) -> None:
        assert _question_implies_outcome(phrase) is True

    @pytest.mark.parametrize("phrase", [
        "What is the HS6 code for your goods?",
        "Which country is exporting the goods?",
        "Do you have a certificate of origin?",
        "Please provide the ex-works value.",
        "What year is this assessment for?",
    ])
    def test_neutral_questions_not_flagged(self, phrase: str) -> None:
        assert _question_implies_outcome(phrase) is False


# ---------------------------------------------------------------------------
# Deterministic question templates (unit tests for the helper)
# ---------------------------------------------------------------------------


class TestDeterministicQuestion:
    def test_hs6_code_question_is_specific(self) -> None:
        q = _deterministic_question("hs6_code")
        assert "HS6" in q or "product code" in q.lower()

    def test_exporter_question_mentions_iso_code(self) -> None:
        q = _deterministic_question("exporter")
        assert "ISO" in q or "3-letter" in q.lower() or "country" in q.lower()

    def test_importer_question_mentions_iso_code(self) -> None:
        q = _deterministic_question("importer")
        assert "ISO" in q or "3-letter" in q.lower() or "country" in q.lower()

    def test_year_question_is_specific(self) -> None:
        q = _deterministic_question("year")
        assert "year" in q.lower()

    def test_persona_mode_question_lists_roles(self) -> None:
        q = _deterministic_question("persona_mode")
        assert any(role in q.lower() for role in ("exporter", "officer", "analyst"))

    def test_known_engine_fact_question_contains_fact_name(self) -> None:
        q = _deterministic_question("ex_works")
        assert "ex works" in q.lower()

    def test_known_engine_fact_question_contains_direct_transport(self) -> None:
        q = _deterministic_question("direct_transport")
        assert "direct transport" in q.lower()

    def test_unknown_key_returns_generic_evidence_question(self) -> None:
        q = _deterministic_question("bill_of_lading")
        assert "bill of lading" in q.lower()


# ---------------------------------------------------------------------------
# ClarificationService — NIM phrasing path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_nim_phrased_question_when_valid_json_received() -> None:
    nim_q = "What is the HS6 product code for the goods you are trading?"
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    svc = _service(_nim_question_json(nim_q))

    result = await svc.generate_clarification(ctx)

    assert result.question == nim_q


@pytest.mark.asyncio
async def test_returns_shorter_input_clarification_for_oversized_input() -> None:
    ctx = ClarificationContext(
        nim_rejection_reason=NIM_REJECTION_REASON_INPUT_TOO_LONG
    )
    client = _mock_client(_nim_question_json("unused"))
    svc = ClarificationService(client)

    result = await svc.generate_clarification(ctx)

    client.generate_json.assert_not_called()
    assert result.question == _INPUT_TOO_LONG_QUESTION
    assert result.missing_facts == []
    assert result.missing_evidence == []


@pytest.mark.asyncio
async def test_nim_question_string_is_stripped_of_whitespace() -> None:
    raw = json.dumps({"question": "  What is the HS6 code?  "})
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    svc = _service(raw)

    result = await svc.generate_clarification(ctx)

    assert result.question == "What is the HS6 code?"


# ---------------------------------------------------------------------------
# ClarificationService — fallback paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_when_nim_disabled() -> None:
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    svc = _service(return_value=None)

    result = await svc.generate_clarification(ctx)

    assert "HS6" in result.question or "product code" in result.question.lower()


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_on_nim_client_error() -> None:
    ctx = ClarificationContext(missing_draft_facts=["exporter"])
    svc = _service(raises=NimClientError("timeout", reason="timeout"))

    result = await svc.generate_clarification(ctx)

    assert "country" in result.question.lower() or "exporting" in result.question.lower()


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_on_invalid_json() -> None:
    ctx = ClarificationContext(missing_draft_facts=["year"])
    svc = _service(return_value="not valid json {{{")

    result = await svc.generate_clarification(ctx)

    assert "year" in result.question.lower()


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_when_question_key_missing_in_json() -> None:
    ctx = ClarificationContext(missing_draft_facts=["importer"])
    svc = _service(return_value=json.dumps({"answer": "something else"}))

    result = await svc.generate_clarification(ctx)

    assert "country" in result.question.lower() or "importing" in result.question.lower()


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_on_empty_question_from_nim() -> None:
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    svc = _service(return_value=json.dumps({"question": ""}))

    result = await svc.generate_clarification(ctx)

    assert "HS6" in result.question or "product code" in result.question.lower()


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_when_nim_implies_eligible_outcome() -> None:
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    svc = _service(
        return_value=_nim_question_json(
            "What is your HS code? This product will qualify for preferential treatment."
        )
    )

    result = await svc.generate_clarification(ctx)

    # Should use fallback, not the outcome-implying question
    assert "will qualify" not in result.question.lower()


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_when_nim_says_eligible() -> None:
    ctx = ClarificationContext(missing_engine_facts=["ex_works"])
    svc = _service(
        return_value=_nim_question_json(
            "Your goods are eligible — please confirm the ex-works value."
        )
    )

    result = await svc.generate_clarification(ctx)

    assert "eligible" not in result.question.lower()


# ---------------------------------------------------------------------------
# ClarificationService — response field assembly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_facts_combines_draft_and_engine_facts() -> None:
    ctx = ClarificationContext(
        missing_draft_facts=["hs6_code", "exporter"],
        missing_engine_facts=["ex_works"],
    )
    svc = _service(_nim_question_json("What is the HS6 code?"))

    result = await svc.generate_clarification(ctx)

    assert "hs6_code" in result.missing_facts
    assert "exporter" in result.missing_facts
    assert "ex_works" in result.missing_facts


@pytest.mark.asyncio
async def test_missing_facts_ordering_preserves_draft_before_engine() -> None:
    ctx = ClarificationContext(
        missing_draft_facts=["hs6_code"],
        missing_engine_facts=["ex_works"],
    )
    svc = _service(_nim_question_json("What is the HS6 code?"))

    result = await svc.generate_clarification(ctx)

    draft_idx = result.missing_facts.index("hs6_code")
    engine_idx = result.missing_facts.index("ex_works")
    assert draft_idx < engine_idx


@pytest.mark.asyncio
async def test_missing_evidence_mirrors_context() -> None:
    ctx = ClarificationContext(
        missing_evidence=["certificate_of_origin", "invoice"],
        missing_draft_facts=["hs6_code"],
    )
    svc = _service(_nim_question_json("What is the HS6 code?"))

    result = await svc.generate_clarification(ctx)

    assert result.missing_evidence == ["certificate_of_origin", "invoice"]


@pytest.mark.asyncio
async def test_missing_evidence_empty_when_none_missing() -> None:
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    svc = _service(_nim_question_json("What is the HS6 code?"))

    result = await svc.generate_clarification(ctx)

    assert result.missing_evidence == []


# ---------------------------------------------------------------------------
# ClarificationService — gap priority drives which question is asked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_fact_gap_asked_before_engine_fact() -> None:
    """When both draft and engine gaps exist, draft gap drives the NIM question."""
    ctx = ClarificationContext(
        missing_draft_facts=["year"],
        missing_engine_facts=["ex_works"],
    )
    svc = _service(return_value=None)  # NIM disabled → deterministic fallback

    result = await svc.generate_clarification(ctx)

    assert "year" in result.question.lower()


@pytest.mark.asyncio
async def test_engine_fact_gap_asked_before_evidence() -> None:
    """When both engine and evidence gaps exist, engine fact drives the question."""
    ctx = ClarificationContext(
        missing_engine_facts=["ex_works"],
        missing_evidence=["invoice"],
    )
    svc = _service(return_value=None)  # NIM disabled → deterministic fallback

    result = await svc.generate_clarification(ctx)

    assert "ex works" in result.question.lower()


@pytest.mark.asyncio
async def test_evidence_question_asked_when_only_evidence_missing() -> None:
    ctx = ClarificationContext(missing_evidence=["certificate_of_origin"])
    svc = _service(return_value=None)

    result = await svc.generate_clarification(ctx)

    assert "certificate of origin" in result.question.lower()


# ---------------------------------------------------------------------------
# ClarificationService — NIM call arguments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_instructs_nim_not_to_infer_eligibility() -> None:
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    client = _mock_client(_nim_question_json("What is the HS6 code?"))
    svc = ClarificationService(client)

    await svc.generate_clarification(ctx)

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "NOT" in prompt or "not" in prompt
    assert "eligible" in prompt.lower() or "outcome" in prompt.lower()


@pytest.mark.asyncio
async def test_user_input_includes_gap_key() -> None:
    ctx = ClarificationContext(missing_draft_facts=["exporter"])
    client = _mock_client(_nim_question_json("Which country is exporting?"))
    svc = ClarificationService(client)

    await svc.generate_clarification(ctx)

    _, call_args, _ = client.generate_json.mock_calls[0]
    user_input = call_args[1]
    assert "exporter" in user_input


@pytest.mark.asyncio
async def test_user_input_describes_gap_type_for_draft_fact() -> None:
    ctx = ClarificationContext(missing_draft_facts=["hs6_code"])
    client = _mock_client(_nim_question_json("What is the HS6 code?"))
    svc = ClarificationService(client)

    await svc.generate_clarification(ctx)

    _, call_args, _ = client.generate_json.mock_calls[0]
    user_input = call_args[1]
    assert "intake" in user_input.lower() or "required" in user_input.lower()


@pytest.mark.asyncio
async def test_user_input_describes_gap_type_for_engine_fact() -> None:
    ctx = ClarificationContext(missing_engine_facts=["ex_works"])
    client = _mock_client(_nim_question_json("Please provide the ex-works value."))
    svc = ClarificationService(client)

    await svc.generate_clarification(ctx)

    _, call_args, _ = client.generate_json.mock_calls[0]
    user_input = call_args[1]
    assert "production" in user_input.lower() or "engine" in user_input.lower()


@pytest.mark.asyncio
async def test_user_input_describes_gap_type_for_evidence() -> None:
    ctx = ClarificationContext(missing_evidence=["invoice"])
    client = _mock_client(_nim_question_json("Do you have an invoice?"))
    svc = ClarificationService(client)

    await svc.generate_clarification(ctx)

    _, call_args, _ = client.generate_json.mock_calls[0]
    user_input = call_args[1]
    assert "document" in user_input.lower() or "supporting" in user_input.lower()


# ---------------------------------------------------------------------------
# System prompt constant — static contract tests
# ---------------------------------------------------------------------------


def test_nim_phrasing_system_prompt_prohibits_outcome_inference() -> None:
    assert "NOT" in _NIM_PHRASING_SYSTEM_PROMPT or "not" in _NIM_PHRASING_SYSTEM_PROMPT
    assert "eligible" in _NIM_PHRASING_SYSTEM_PROMPT.lower()


def test_nim_phrasing_system_prompt_requests_json_object() -> None:
    assert "question" in _NIM_PHRASING_SYSTEM_PROMPT
    assert "JSON" in _NIM_PHRASING_SYSTEM_PROMPT
