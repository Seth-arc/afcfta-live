"""Unit tests for the NIM rendering service and schema.

Tests cover:
- NimRendering schema: valid construction, field constraints, extra-field rejection.
- RenderingService.render():
  - Valid NIM response → returned as RenderedDecision from NIM output.
  - Contradictory headline (eligible=false but claims qualification) → rejected, fallback.
  - Invented pathway in summary → rejected, fallback.
  - Invented delta in gap_analysis → rejected, fallback.
  - NIM timeout → fallback returned without crash.
  - Invalid JSON from NIM → fallback returned without crash.
  - NIM disabled → fallback returned immediately.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.schemas.nim.rendering import NimRendering
from app.services.nim.client import NimClient, NimClientError
from app.services.nim.decision_renderer import DecisionRenderer, RenderedDecision
from app.services.nim.rendering_service import (
    RenderingService,
    _check_headline_contradiction,
    _check_summary_invented_pathways,
    _check_gap_analysis_invented_delta,
    _check_fix_strategy_invented_pathways,
    _check_warnings_valid,
)


# ---------------------------------------------------------------------------
# Fixtures: engine payload and NIM response builders
# ---------------------------------------------------------------------------


def _engine_payload(
    *,
    eligible: bool = False,
    pathway_used: str | None = None,
    rule_status: str = "agreed",
    confidence_class: str = "complete",
    hs6_code: str = "180631",
    product_description: str = "Chocolate bars, filled",
    pathway_analysis: list | None = None,
    missing_facts: list | None = None,
    evidence_required: list | None = None,
    failures: list | None = None,
    tariff_outcome: dict | None = None,
) -> dict:
    """Build a minimal engine payload for testing."""
    if pathway_analysis is None:
        pathway_analysis = [
            {
                "pathway_code": "VNM",
                "priority_rank": 1,
                "passed": False,
                "reasons": [
                    "Non-originating value is 48%, above the allowed 40%."
                ],
            },
            {
                "pathway_code": "CTH",
                "priority_rank": 2,
                "passed": False,
                "reasons": [
                    "One or more non-originating inputs share the same heading."
                ],
            },
        ]
    return {
        "decision": {
            "eligible": eligible,
            "pathway_used": pathway_used,
            "rule_status": rule_status,
            "confidence_class": confidence_class,
        },
        "product": {
            "hs6_code": hs6_code,
            "product_description": product_description,
        },
        "pathway_analysis": pathway_analysis,
        "missing_facts": missing_facts or [],
        "failures": failures or [],
        "evidence_required": evidence_required or [],
        "tariff_outcome": tariff_outcome or {},
    }


def _valid_nim_response(
    *,
    eligible: bool = False,
    headline: str | None = None,
    summary: str | None = None,
    gap_analysis: str | None = "You are 8 percentage points above the VNM threshold.",
    fix_strategy: str | None = "Reduce non-originating value by at least 8 percentage points.",
    next_steps: list[str] | None = None,
    warnings: list[str] | None = None,
) -> str:
    """Build a valid JSON string mimicking NIM output."""
    if headline is None:
        headline = (
            "This product does not qualify for AfCFTA preference yet."
            if not eligible
            else "This product qualifies for AfCFTA preference."
        )
    if summary is None:
        summary = (
            "HS6 180631 (Chocolate bars, filled) does not qualify yet. "
            "The main issue is that non-originating value is 48%, above the allowed 40%."
        )
    if next_steps is None:
        next_steps = [
            "Review non-originating input costs.",
            "Consider sourcing originating inputs.",
            "Re-run the assessment after changes.",
        ]
    if warnings is None:
        warnings = []

    return json.dumps({
        "headline": headline,
        "summary": summary,
        "gap_analysis": gap_analysis,
        "fix_strategy": fix_strategy,
        "next_steps": next_steps,
        "warnings": warnings,
    })


def _counterfactuals(
    *,
    delta: str = "8",
    pathway_code: str = "VNM",
) -> list[dict]:
    return [
        {
            "kind": "value_reduction",
            "message": (
                f"Reduce non-originating value by at least {delta} percentage "
                f"points to meet the {pathway_code} threshold."
            ),
            "delta": delta,
            "pathway_code": pathway_code,
        }
    ]


def _mock_nim_client(
    *,
    response: str | None = None,
    error: NimClientError | None = None,
    enabled: bool = True,
) -> NimClient:
    """Create a mock NimClient with controlled behaviour."""
    client = AsyncMock(spec=NimClient)
    client.enabled = enabled

    if error is not None:
        client.generate_json = AsyncMock(side_effect=error)
    else:
        client.generate_json = AsyncMock(return_value=response)

    return client


# ---------------------------------------------------------------------------
# NimRendering schema tests
# ---------------------------------------------------------------------------


class TestNimRenderingSchema:
    """Test the NimRendering Pydantic model."""

    def test_valid_construction(self) -> None:
        r = NimRendering(
            headline="Product qualifies.",
            summary="It qualifies under VNM.",
            gap_analysis=None,
            fix_strategy=None,
            next_steps=["Step 1.", "Step 2."],
            warnings=[],
        )
        assert r.headline == "Product qualifies."
        assert len(r.next_steps) == 2

    def test_next_steps_min_items(self) -> None:
        with pytest.raises(ValidationError):
            NimRendering(
                headline="H",
                summary="S",
                next_steps=["Only one"],
                warnings=[],
            )

    def test_next_steps_max_items(self) -> None:
        with pytest.raises(ValidationError):
            NimRendering(
                headline="H",
                summary="S",
                next_steps=["A", "B", "C", "D", "E"],
                warnings=[],
            )

    def test_warnings_max_items(self) -> None:
        with pytest.raises(ValidationError):
            NimRendering(
                headline="H",
                summary="S",
                next_steps=["A", "B"],
                warnings=["W1", "W2", "W3", "W4"],
            )

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            NimRendering(
                headline="H",
                summary="S",
                next_steps=["A", "B"],
                warnings=[],
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# Guardrail unit tests
# ---------------------------------------------------------------------------


class TestContradictionGuardrails:
    """Test individual guardrail functions in isolation."""

    def test_headline_claims_qualification_when_ineligible(self) -> None:
        result = _check_headline_contradiction(
            "This product qualifies for preference.", eligible=False
        )
        assert result is not None
        assert "qualifies" in result

    def test_headline_claims_failure_when_eligible(self) -> None:
        result = _check_headline_contradiction(
            "This product does not qualify.", eligible=True
        )
        assert result is not None
        assert "does not qualify" in result

    def test_headline_consistent_passes(self) -> None:
        assert _check_headline_contradiction(
            "This product does not qualify yet.", eligible=False
        ) is None
        assert _check_headline_contradiction(
            "This product qualifies for AfCFTA preference.", eligible=True
        ) is None

    def test_summary_invented_pathway(self) -> None:
        result = _check_summary_invented_pathways(
            "The product fails the PROCESS pathway.",
            valid_codes={"VNM", "CTH"},
        )
        assert result is not None
        assert "PROCESS" in result

    def test_summary_valid_pathway(self) -> None:
        assert _check_summary_invented_pathways(
            "The VNM pathway threshold was exceeded.",
            valid_codes={"VNM", "CTH"},
        ) is None

    def test_gap_analysis_invented_delta(self) -> None:
        result = _check_gap_analysis_invented_delta(
            "You are 15 percentage points above the threshold.",
            valid_deltas={"8"},
        )
        assert result is not None
        assert "15" in result

    def test_gap_analysis_valid_delta(self) -> None:
        assert _check_gap_analysis_invented_delta(
            "You are 8 percentage points above the threshold.",
            valid_deltas={"8"},
        ) is None

    def test_gap_analysis_none_passes(self) -> None:
        assert _check_gap_analysis_invented_delta(None, valid_deltas={"8"}) is None

    def test_fix_strategy_invented_pathway(self) -> None:
        result = _check_fix_strategy_invented_pathways(
            "Switch to the WO pathway for compliance.",
            valid_codes={"VNM", "CTH"},
        )
        assert result is not None
        assert "WO" in result

    def test_fix_strategy_valid_pathway(self) -> None:
        assert _check_fix_strategy_invented_pathways(
            "Reduce non-originating value to meet the VNM threshold.",
            valid_codes={"VNM", "CTH"},
        ) is None

    def test_warnings_valid_pending_status(self) -> None:
        decision = {"rule_status": "pending", "confidence_class": "provisional"}
        assert _check_warnings_valid(
            ["The rule status is pending, so results may change."],
            decision,
            missing_facts=[],
        ) is None

    def test_warnings_mentions_status_when_agreed(self) -> None:
        decision = {"rule_status": "agreed", "confidence_class": "complete"}
        result = _check_warnings_valid(
            ["The rule is still pending approval."],
            decision,
            missing_facts=[],
        )
        assert result is not None


# ---------------------------------------------------------------------------
# RenderingService integration tests
# ---------------------------------------------------------------------------


class TestRenderingServiceValidResponse:
    """Valid NIM response is returned as RenderedDecision."""

    @pytest.mark.asyncio
    async def test_valid_nim_response_returned(self) -> None:
        nim_json = _valid_nim_response()
        client = _mock_nim_client(response=nim_json)
        service = RenderingService(nim_client=client)

        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        assert isinstance(result, RenderedDecision)
        assert "does not qualify" in result.headline.lower()
        assert len(result.next_steps) == 3
        # Verify NIM was actually called
        client.generate_json.assert_awaited_once()


class TestRenderingServiceHeadlineContradiction:
    """Contradictory headline → rejected, fallback returned."""

    @pytest.mark.asyncio
    async def test_headline_claims_qualification_when_ineligible(self) -> None:
        nim_json = _valid_nim_response(
            headline="This product qualifies for AfCFTA preference."
        )
        client = _mock_nim_client(response=nim_json)
        service = RenderingService(nim_client=client)

        payload = _engine_payload(eligible=False)
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        # Should be the deterministic fallback
        assert isinstance(result, RenderedDecision)
        assert "does not qualify" in result.headline.lower()

    @pytest.mark.asyncio
    async def test_headline_claims_failure_when_eligible(self) -> None:
        nim_json = _valid_nim_response(
            eligible=True,
            headline="This product does not qualify for AfCFTA preference.",
        )
        client = _mock_nim_client(response=nim_json)
        service = RenderingService(nim_client=client)

        payload = _engine_payload(
            eligible=True,
            pathway_used="VNM",
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": True,
                    "reasons": ["Value content threshold met."],
                }
            ],
        )
        result = await service.render(
            engine_payload=payload,
            counterfactuals=[],
        )

        # Deterministic fallback should say it qualifies
        assert isinstance(result, RenderedDecision)
        assert "qualifies" in result.headline.lower()


class TestRenderingServiceInventedPathway:
    """Invented pathway in summary → rejected, fallback returned."""

    @pytest.mark.asyncio
    async def test_summary_references_absent_pathway(self) -> None:
        nim_json = _valid_nim_response(
            summary=(
                "HS6 180631 fails VNM, CTH, and also the PROCESS pathway "
                "which requires specific manufacturing steps."
            )
        )
        client = _mock_nim_client(response=nim_json)
        service = RenderingService(nim_client=client)

        # pathway_analysis only has VNM and CTH, not PROCESS
        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        # Should fall back to deterministic
        assert isinstance(result, RenderedDecision)
        assert "process" not in result.summary.lower()


class TestRenderingServiceInventedDelta:
    """Invented delta in gap_analysis → rejected, fallback returned."""

    @pytest.mark.asyncio
    async def test_gap_analysis_invents_delta(self) -> None:
        nim_json = _valid_nim_response(
            gap_analysis="You are 15 percentage points above the VNM threshold."
        )
        client = _mock_nim_client(response=nim_json)
        service = RenderingService(nim_client=client)

        # Counterfactuals have delta=8, not 15
        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(delta="8"),
        )

        # Should fall back to deterministic
        assert isinstance(result, RenderedDecision)
        # The deterministic gap_analysis uses the real delta
        if result.gap_analysis is not None:
            assert "15" not in result.gap_analysis


class TestRenderingServiceNimTimeout:
    """NIM timeout → fallback returned without crash."""

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback(self) -> None:
        client = _mock_nim_client(
            error=NimClientError(
                "NIM request timed out after 30s",
                status_code=None,
                reason="timeout",
                attempt=2,
            )
        )
        service = RenderingService(nim_client=client)

        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        assert isinstance(result, RenderedDecision)
        assert result.headline  # Non-empty deterministic headline


class TestRenderingServiceInvalidJson:
    """Invalid JSON from NIM → fallback returned without crash."""

    @pytest.mark.asyncio
    async def test_malformed_json_returns_fallback(self) -> None:
        client = _mock_nim_client(response="not valid json {{{")
        service = RenderingService(nim_client=client)

        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        assert isinstance(result, RenderedDecision)
        assert result.headline


class TestRenderingServiceNimDisabled:
    """NIM disabled → fallback returned immediately."""

    @pytest.mark.asyncio
    async def test_disabled_returns_fallback(self) -> None:
        # When NIM is disabled, generate_json returns None
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        assert isinstance(result, RenderedDecision)
        assert result.headline
        # The headline should be from the deterministic renderer
        assert "does not qualify" in result.headline.lower()


class TestRenderingServiceSchemaViolation:
    """NIM returns JSON that violates NimRendering schema constraints."""

    @pytest.mark.asyncio
    async def test_missing_required_field_returns_fallback(self) -> None:
        # JSON missing the 'summary' field
        bad_json = json.dumps({
            "headline": "Something.",
            "next_steps": ["A", "B"],
            "warnings": [],
        })
        client = _mock_nim_client(response=bad_json)
        service = RenderingService(nim_client=client)

        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        assert isinstance(result, RenderedDecision)
        assert result.headline  # Deterministic fallback

    @pytest.mark.asyncio
    async def test_too_few_next_steps_returns_fallback(self) -> None:
        bad_json = json.dumps({
            "headline": "This product does not qualify yet.",
            "summary": "Some summary.",
            "gap_analysis": None,
            "fix_strategy": None,
            "next_steps": ["Only one step."],
            "warnings": [],
        })
        client = _mock_nim_client(response=bad_json)
        service = RenderingService(nim_client=client)

        payload = _engine_payload()
        result = await service.render(
            engine_payload=payload,
            counterfactuals=_counterfactuals(),
        )

        assert isinstance(result, RenderedDecision)
        # Deterministic renderer always provides >=2 next_steps for failed products
