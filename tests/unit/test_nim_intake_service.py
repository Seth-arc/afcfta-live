"""Unit tests for IntakeService.parse_user_input().

Tests cover:
- Valid NIM JSON response is parsed and validated as NimAssessmentDraft.
- Disabled NIM (returns None) yields an empty draft.
- Invalid JSON from NIM yields an empty draft (no crash).
- NimClientError yields an empty draft (no crash).
- The system prompt and user input are passed to NimClient.generate_json.
- Context hints fill gaps the model left as None.
- Context hints do not override values the model already extracted.
- Context hint lines appear in the system prompt sent to NIM.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.nim.intake import (
    AssessmentContext,
    HS6Candidate,
    NimAssessmentDraft,
    NimConfidence,
    TradeFlow,
)
from app.services.nim.client import NimClientError
from app.services.nim.intake_service import (
    IntakeService,
    NIM_MAX_INPUT_CHARS,
    NIM_REJECTION_REASON_INPUT_TOO_LONG,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(return_value: str | None = None, raises: Exception | None = None) -> MagicMock:
    """Build a mock NimClient.generate_json()."""
    client = MagicMock()
    if raises is not None:
        client.generate_json = AsyncMock(side_effect=raises)
    else:
        client.generate_json = AsyncMock(return_value=return_value)
    return client


def _nim_json(
    hs6_code: str | None = "110311",
    exporter: str | None = "GHA",
    importer: str | None = "NGA",
    year: int | None = 2025,
    persona_mode: str | None = "exporter",
    overall: float = 0.9,
) -> str:
    """Build a valid NimAssessmentDraft JSON string for mock responses."""
    return json.dumps({
        "product": {
            "hs6_code": hs6_code,
            "hs_version": "HS2017",
            "product_description_parsed": None,
        },
        "trade_flow": {
            "exporter": exporter,
            "importer": importer,
            "year": year,
        },
        "context": {"persona_mode": persona_mode},
        "production_facts": {"material_inputs": []},
        "existing_documents": [],
        "nim_confidence": {
            "overall": overall,
            "hs6_confidence": 0.9,
            "corridor_confidence": 0.85,
            "facts_confidence": 0.0,
        },
        "nim_assumptions": [],
    })


def _context(
    persona_mode: str | None = None,
    exporter: str | None = None,
    importer: str | None = None,
    year: int | None = None,
) -> object:
    """Build a minimal AssistantContext-like object for context hint tests."""
    from app.schemas.nim.assistant import AssistantContext
    return AssistantContext(
        persona_mode=persona_mode,
        exporter=exporter,
        importer=importer,
        year=year,
    )


# ---------------------------------------------------------------------------
# Basic response handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_returns_draft_from_valid_nim_json() -> None:
    """Valid NIM JSON is parsed into a populated NimAssessmentDraft."""
    client = _mock_client(_nim_json())
    draft = await IntakeService(client).parse_user_input("export wheat from Ghana to Nigeria")

    assert isinstance(draft, NimAssessmentDraft)
    assert draft.product is not None
    assert draft.product.hs6_code == "110311"
    assert draft.trade_flow is not None
    assert draft.trade_flow.exporter == "GHA"
    assert draft.trade_flow.importer == "NGA"
    assert draft.trade_flow.year == 2025
    assert draft.context is not None
    assert draft.context.persona_mode.value == "exporter"


@pytest.mark.asyncio
async def test_parse_returns_empty_draft_when_nim_disabled() -> None:
    """When NIM returns None (disabled), an empty NimAssessmentDraft is returned."""
    client = _mock_client(return_value=None)
    draft = await IntakeService(client).parse_user_input("export wheat")

    assert isinstance(draft, NimAssessmentDraft)
    assert draft.product is None
    assert draft.trade_flow is None
    assert draft.context is None


@pytest.mark.asyncio
async def test_parse_returns_empty_draft_on_invalid_json() -> None:
    """If NIM returns malformed JSON, an empty draft is returned without raising."""
    client = _mock_client(return_value="not valid json {{{{")
    draft = await IntakeService(client).parse_user_input("export wheat")

    assert isinstance(draft, NimAssessmentDraft)
    assert draft.product is None


@pytest.mark.asyncio
async def test_parse_returns_empty_draft_on_schema_validation_error() -> None:
    """If NIM returns JSON that fails NimAssessmentDraft validation, empty draft is returned."""
    bad_json = json.dumps({"product": {"hs6_code": "1103"}, "extra_field": "oops"})
    client = _mock_client(return_value=bad_json)
    draft = await IntakeService(client).parse_user_input("export wheat")

    assert isinstance(draft, NimAssessmentDraft)
    assert draft.product is None


@pytest.mark.asyncio
async def test_parse_returns_empty_draft_on_nim_client_error() -> None:
    """NimClientError from the client yields an empty draft without raising."""
    client = _mock_client(
        raises=NimClientError("timeout", status_code=None, reason="timeout")
    )
    draft = await IntakeService(client).parse_user_input("export wheat")

    assert isinstance(draft, NimAssessmentDraft)
    assert draft.product is None


# ---------------------------------------------------------------------------
# generate_json call arguments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_passes_user_input_to_generate_json() -> None:
    """parse_user_input passes the user_input string as the second argument."""
    client = _mock_client(_nim_json())
    await IntakeService(client).parse_user_input("export wheat from Ghana to Nigeria")

    _, call_args, _ = client.generate_json.mock_calls[0]
    assert call_args[1] == "export wheat from Ghana to Nigeria"


@pytest.mark.asyncio
async def test_parse_sends_input_exactly_at_2000_char_boundary_to_nim() -> None:
    """Input at the AGENTS.md boundary is still sent to NIM unchanged."""
    user_input = "x" * NIM_MAX_INPUT_CHARS
    client = _mock_client(_nim_json())

    await IntakeService(client).parse_user_input(user_input)

    client.generate_json.assert_awaited_once()
    _, call_args, _ = client.generate_json.mock_calls[0]
    assert call_args[1] == user_input


@pytest.mark.asyncio
async def test_parse_rejects_input_one_char_over_boundary_without_calling_nim(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Input above the AGENTS.md boundary returns an empty draft for clarification."""
    user_input = "x" * (NIM_MAX_INPUT_CHARS + 1)
    client = _mock_client(_nim_json())

    with caplog.at_level(logging.WARNING):
        draft = await IntakeService(client).parse_user_input(user_input)

    client.generate_json.assert_not_called()
    assert draft == NimAssessmentDraft(
        nim_rejection_reason=NIM_REJECTION_REASON_INPUT_TOO_LONG
    )
    assert draft.nim_rejection_reason == NIM_REJECTION_REASON_INPUT_TOO_LONG
    assert "user_input_char_count=2001" in caplog.text


@pytest.mark.asyncio
async def test_parse_passes_system_prompt_as_first_arg() -> None:
    """parse_user_input passes a non-empty system prompt as the first argument."""
    client = _mock_client(_nim_json())
    await IntakeService(client).parse_user_input("export wheat")

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert isinstance(prompt, str)
    assert len(prompt) > 50
    assert "hs6_code" in prompt


# ---------------------------------------------------------------------------
# Context hints — filling gaps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_exporter_fills_missing_model_value() -> None:
    """Context exporter is applied when the model left exporter as None."""
    raw = _nim_json(exporter=None)
    client = _mock_client(raw)
    ctx = _context(exporter="GHA")
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.trade_flow is not None
    assert draft.trade_flow.exporter == "GHA"


@pytest.mark.asyncio
async def test_context_importer_fills_missing_model_value() -> None:
    """Context importer is applied when the model left importer as None."""
    raw = _nim_json(importer=None)
    client = _mock_client(raw)
    ctx = _context(importer="NGA")
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.trade_flow.importer == "NGA"


@pytest.mark.asyncio
async def test_context_year_fills_missing_model_value() -> None:
    """Context year is applied when the model left year as None."""
    raw = _nim_json(year=None)
    client = _mock_client(raw)
    ctx = _context(year=2025)
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.trade_flow.year == 2025


@pytest.mark.asyncio
async def test_context_persona_mode_fills_missing_model_value() -> None:
    """Context persona_mode is applied when the model left persona_mode as None."""
    raw = _nim_json(persona_mode=None)
    client = _mock_client(raw)
    ctx = _context(persona_mode="officer")
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.context is not None
    assert draft.context.persona_mode.value == "officer"


@pytest.mark.asyncio
async def test_context_fills_all_gaps_on_empty_draft() -> None:
    """All context hints are applied when the model returns an empty draft."""
    client = _mock_client(return_value=None)  # NIM disabled
    ctx = _context(exporter="GHA", importer="NGA", year=2025, persona_mode="exporter")
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.trade_flow is not None
    assert draft.trade_flow.exporter == "GHA"
    assert draft.trade_flow.importer == "NGA"
    assert draft.trade_flow.year == 2025
    assert draft.context is not None
    assert draft.context.persona_mode.value == "exporter"


# ---------------------------------------------------------------------------
# Context hints — do not override model values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_exporter_does_not_override_model_value() -> None:
    """Context exporter hint is ignored when the model already extracted an exporter."""
    raw = _nim_json(exporter="GHA")
    client = _mock_client(raw)
    ctx = _context(exporter="CMR")  # different from what model extracted
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.trade_flow.exporter == "GHA"  # model value preserved


@pytest.mark.asyncio
async def test_context_persona_mode_does_not_override_model_value() -> None:
    """Context persona_mode hint is ignored when the model already set one."""
    raw = _nim_json(persona_mode="exporter")
    client = _mock_client(raw)
    ctx = _context(persona_mode="officer")
    draft = await IntakeService(client).parse_user_input("export wheat", context=ctx)

    assert draft.context.persona_mode.value == "exporter"  # model value preserved


# ---------------------------------------------------------------------------
# Context hints appear in system prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_hints_appear_in_system_prompt() -> None:
    """Context hint values are included in the system prompt sent to NIM."""
    client = _mock_client(_nim_json())
    ctx = _context(exporter="GHA", importer="NGA", year=2025, persona_mode="officer")
    await IntakeService(client).parse_user_input("export wheat", context=ctx)

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "GHA" in prompt
    assert "NGA" in prompt
    assert "2025" in prompt
    assert "officer" in prompt


@pytest.mark.asyncio
async def test_no_context_hints_block_when_context_is_none() -> None:
    """When context is None, no hint block is appended to the system prompt."""
    client = _mock_client(_nim_json())
    await IntakeService(client).parse_user_input("export wheat", context=None)

    _, call_args, _ = client.generate_json.mock_calls[0]
    prompt = call_args[0]
    assert "Context hints" not in prompt


# ---------------------------------------------------------------------------
# nim_confidence and nim_assumptions preserved on draft
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nim_confidence_preserved_on_draft() -> None:
    """NIM confidence scores are present on the returned draft for the intake service."""
    client = _mock_client(_nim_json(overall=0.87))
    draft = await IntakeService(client).parse_user_input("export wheat")

    assert draft.nim_confidence is not None
    assert draft.nim_confidence.overall == pytest.approx(0.87)


def test_to_eligibility_request_model_dump_excludes_nim_confidence_and_assumptions() -> None:
    """EligibilityRequest must never expose NIM-only metadata keys."""
    draft = NimAssessmentDraft(
        product=HS6Candidate(hs6_code="110311"),
        trade_flow=TradeFlow(exporter="GHA", importer="NGA", year=2025),
        context=AssessmentContext(persona_mode="exporter"),
        nim_confidence=NimConfidence(overall=0.95),
        nim_assumptions=["assumed corridor from phrasing"],
    )

    request_payload = IntakeService(_mock_client()).to_eligibility_request(draft).model_dump()

    assert "nim_confidence" not in request_payload
    assert "nim_assumptions" not in request_payload


def test_to_eligibility_request_strips_nim_metadata_without_model_call() -> None:
    """Manual draft mapping must drop all NIM-only metadata to catch contract drift."""
    draft = NimAssessmentDraft(
        product=HS6Candidate(
            hs6_code="110311",
            product_description_parsed="wheat groats",
        ),
        trade_flow=TradeFlow(exporter="GHA", importer="NGA", year=2025),
        context=AssessmentContext(persona_mode="exporter"),
        nim_confidence=NimConfidence(overall=0.88),
        nim_assumptions=["used trade context"],
        nim_rejection_reason=NIM_REJECTION_REASON_INPUT_TOO_LONG,
    )

    request_payload = IntakeService(_mock_client()).to_eligibility_request(draft).model_dump()

    assert "nim_confidence" not in request_payload
    assert "nim_assumptions" not in request_payload
    assert "nim_rejection_reason" not in request_payload
    assert "product_description_parsed" not in request_payload
