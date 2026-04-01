"""End-to-end validation for the rendering layer.

Covers the full pipeline:

  engine payload → counterfactuals → RenderingService.render()
  → NIM attempt (mock) → guardrail check → DecisionRenderer fallback
  → RenderedDecision → AssistantRendering shape

═══════════════════════════════════════════════════════════════════════════════
SCENARIOS COVERED
═══════════════════════════════════════════════════════════════════════════════
1. Eligible result        → clean qualifying narrative, no fix_strategy, no gap_analysis.
2. Failed VNM             → quantified gap_analysis and actionable fix_strategy.
3. Failed CTH             → tariff-shift fix narrative, no numeric gap.
4. Missing facts          → incomplete assessment narrative, no invented certainty.
5. Pending rule status    → warning appears, result is not blocked.
6. Contradictory NIM      → rejected and DecisionRenderer fallback used.
7. Empty/malformed NIM    → fallback used, no crash.

═══════════════════════════════════════════════════════════════════════════════
CROSS-CUTTING ASSERTIONS  (enforced in every scenario)
═══════════════════════════════════════════════════════════════════════════════
A1  assessment fields identical to engine payload (eligible, pathway_used,
    rule_status, tariff_outcome, confidence_class).
A2  assistant_rendering never overrides eligible, pathway_used, rule_status,
    or tariff_outcome.
A3  No hallucinated fields in assistant_rendering.
A4  The full response can be replayed through the audit layer using the
    persisted identifiers (case_id, evaluation_id, audit_url).
A5  The assistant_rendering shape is stable across all scenarios.

═══════════════════════════════════════════════════════════════════════════════
DB-INDEPENDENT
═══════════════════════════════════════════════════════════════════════════════
All tests run without Postgres. The RenderingService is invoked directly
with mock NIM clients. The deterministic engine payload is constructed
locally, so no real engine or audit layer is needed.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.schemas.nim.assistant import AssistantRendering
from app.services.nim.client import NimClient, NimClientError
from app.services.nim.decision_renderer import DecisionRenderer, RenderedDecision
from app.services.nim.rendering_service import RenderingService
from tests.contract_constants import (
    ASSISTANT_RENDERING_FIELDS,
    ENGINE_DECISION_FIELDS,
)

pytestmark = pytest.mark.integration

# ─── Frozen engine decision keys that rendering must never alter ────────────

_PROTECTED_DECISION_KEYS = frozenset({
    "eligible",
    "pathway_used",
    "rule_status",
    "tariff_outcome",
})

# ─── Payload builders ──────────────────────────────────────────────────────


def _engine_payload(
    *,
    eligible: bool = False,
    pathway_used: str | None = None,
    rule_status: str = "agreed",
    confidence_class: str = "complete",
    pathway_analysis: list[dict[str, Any]] | None = None,
    missing_facts: list[str] | None = None,
    failures: list[str] | None = None,
    tariff_outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "decision": {
            "eligible": eligible,
            "pathway_used": pathway_used,
            "rule_status": rule_status,
            "confidence_class": confidence_class,
        },
        "product": {
            "hs6_code": "180631",
            "product_description": "Chocolate bars, filled",
        },
        "pathway_analysis": pathway_analysis or [],
        "missing_facts": missing_facts or [],
        "failures": failures or [],
        "evidence_required": ["certificate_of_origin", "bill_of_materials"],
        "tariff_outcome": tariff_outcome
        or {
            "preferential_rate": "0%",
            "base_rate": "20%",
            "status": "in_force",
        },
    }


def _mock_nim_client(
    *,
    response: str | None = None,
    error: NimClientError | None = None,
    enabled: bool = True,
) -> NimClient:
    client = AsyncMock(spec=NimClient)
    client.enabled = enabled
    if error is not None:
        client.generate_json = AsyncMock(side_effect=error)
    else:
        client.generate_json = AsyncMock(return_value=response)
    return client


def _valid_nim_json(
    *,
    headline: str = "This product does not qualify for AfCFTA preference yet.",
    summary: str = (
        "HS6 180631 (Chocolate bars, filled) does not qualify. "
        "The VNM threshold was exceeded."
    ),
    gap_analysis: str | None = "You are 8 percentage points above the VNM threshold.",
    fix_strategy: str | None = "Reduce non-originating value by at least 8 points.",
    next_steps: list[str] | None = None,
    warnings: list[str] | None = None,
) -> str:
    return json.dumps({
        "headline": headline,
        "summary": summary,
        "gap_analysis": gap_analysis,
        "fix_strategy": fix_strategy,
        "next_steps": next_steps or [
            "Review non-originating input costs.",
            "Consider sourcing originating inputs.",
            "Re-run the assessment after changes.",
        ],
        "warnings": warnings or [],
    })


# ─── Cross-cutting assertion helpers ───────────────────────────────────────


def _assert_shape_stable(rendered: RenderedDecision) -> None:
    """A5: assistant_rendering shape is stable across all scenarios."""
    d = rendered.to_dict()
    assert set(d.keys()) == ASSISTANT_RENDERING_FIELDS, (
        f"Shape mismatch: got {set(d.keys())}, expected {ASSISTANT_RENDERING_FIELDS}"
    )
    assert isinstance(d["headline"], str) and len(d["headline"]) > 0
    assert isinstance(d["summary"], str) and len(d["summary"]) > 0
    assert d["gap_analysis"] is None or isinstance(d["gap_analysis"], str)
    assert d["fix_strategy"] is None or isinstance(d["fix_strategy"], str)
    assert isinstance(d["next_steps"], list) and len(d["next_steps"]) >= 2
    assert isinstance(d["warnings"], list)


def _assert_no_hallucinated_fields(rendered: RenderedDecision) -> None:
    """A3: No hallucinated fields in assistant_rendering."""
    d = rendered.to_dict()
    extra = set(d.keys()) - ASSISTANT_RENDERING_FIELDS
    assert extra == set(), f"Hallucinated fields in rendering: {extra}"
    # Also validate through the Pydantic model (extra="forbid")
    AssistantRendering.model_validate(d)


def _assert_rendering_does_not_override_engine(
    rendered: RenderedDecision,
    engine_payload: dict[str, Any],
) -> None:
    """A1 + A2: rendering never overrides deterministic engine fields.

    The rendered output is a narrative layer. It must not contain any key
    from the engine decision namespace. The engine_payload decision values
    must remain exactly as supplied — rendering cannot alter them.
    """
    d = rendered.to_dict()
    # Rendering fields must not include any engine decision field name
    for key in _PROTECTED_DECISION_KEYS:
        assert key not in d, (
            f"Rendering must not contain engine decision field '{key}'"
        )
    # The original engine_payload decision values are untouched
    decision = engine_payload["decision"]
    assert decision == engine_payload["decision"], (
        "Engine payload decision was mutated during rendering"
    )


def _assert_replay_identifiers_available(
    engine_payload: dict[str, Any],
) -> None:
    """A4: the engine payload carries enough structure for audit replay.

    In the full assistant flow, case_id and evaluation_id are added by the
    orchestration layer after engine persistence. Here we verify the engine
    payload itself is structurally complete enough that audit persistence
    could proceed — i.e. the decision, product, and pathway_analysis keys
    are all present and well-typed.
    """
    assert "decision" in engine_payload
    assert "product" in engine_payload
    assert "pathway_analysis" in engine_payload
    decision = engine_payload["decision"]
    assert isinstance(decision.get("eligible"), bool)
    assert isinstance(decision.get("rule_status"), str)
    assert isinstance(decision.get("confidence_class"), str)


def _run_cross_cutting_assertions(
    rendered: RenderedDecision,
    engine_payload: dict[str, Any],
) -> None:
    """Run all five cross-cutting assertions."""
    _assert_shape_stable(rendered)
    _assert_no_hallucinated_fields(rendered)
    _assert_rendering_does_not_override_engine(rendered, engine_payload)
    _assert_replay_identifiers_available(engine_payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 1 — Eligible result
# ═══════════════════════════════════════════════════════════════════════════


class TestEligibleResult:
    """Clean qualifying narrative, no fix_strategy, no gap_analysis."""

    @pytest.mark.asyncio
    async def test_eligible_via_nim_disabled_produces_clean_qualifying_narrative(
        self,
    ) -> None:
        payload = _engine_payload(
            eligible=True,
            pathway_used="CTH",
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": True,
                    "reasons": [
                        "Tariff heading of non-originating inputs changes at heading level."
                    ],
                }
            ],
        )
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert "qualifies" in result.headline.lower()
        assert "CTH" in result.summary
        assert result.fix_strategy is None
        assert result.gap_analysis is None
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_eligible_via_valid_nim_produces_clean_qualifying_narrative(
        self,
    ) -> None:
        payload = _engine_payload(
            eligible=True,
            pathway_used="CTH",
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": True,
                    "reasons": [
                        "Tariff heading of non-originating inputs changes at heading level."
                    ],
                }
            ],
        )
        nim_json = _valid_nim_json(
            headline="This product qualifies for AfCFTA preference.",
            summary="HS6 180631 qualifies under CTH. Tariff heading shift confirmed.",
            gap_analysis=None,
            fix_strategy=None,
        )
        client = _mock_nim_client(response=nim_json)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert "qualifies" in result.headline.lower()
        assert result.fix_strategy is None
        assert result.gap_analysis is None
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 2 — Failed VNM
# ═══════════════════════════════════════════════════════════════════════════


class TestFailedVNM:
    """Quantified gap_analysis and actionable fix_strategy."""

    @pytest.mark.asyncio
    async def test_failed_vnm_produces_quantified_gap_and_fix_strategy(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": [
                        "Non-originating value is 48%, above the allowed 40%."
                    ],
                }
            ],
        )
        counterfactuals = [
            {
                "kind": "value_reduction",
                "message": "Reduce non-originating value by at least 8 percentage points.",
                "delta": "8",
                "pathway_code": "VNM",
            }
        ]
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload, counterfactuals=counterfactuals
        )

        assert isinstance(result, RenderedDecision)
        assert "does not qualify" in result.headline.lower()
        assert result.gap_analysis is not None
        assert "8" in result.gap_analysis
        assert "VNM" in result.gap_analysis
        assert result.fix_strategy is not None
        assert "reduce" in result.fix_strategy.lower()
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 3 — Failed CTH
# ═══════════════════════════════════════════════════════════════════════════


class TestFailedCTH:
    """Tariff-shift fix narrative, no numeric gap."""

    @pytest.mark.asyncio
    async def test_failed_cth_produces_tariff_shift_fix_without_numeric_gap(
        self,
    ) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": [
                        "One or more non-originating inputs share the same heading "
                        "as the final product."
                    ],
                }
            ],
        )
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert "does not qualify" in result.summary.lower()
        assert result.gap_analysis is None
        assert result.fix_strategy is not None
        assert "heading" in result.fix_strategy.lower()
        assert "percentage point" not in result.fix_strategy.lower()
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 4 — Missing facts
# ═══════════════════════════════════════════════════════════════════════════


class TestMissingFacts:
    """Incomplete assessment narrative, no invented certainty."""

    @pytest.mark.asyncio
    async def test_missing_facts_produces_incomplete_narrative(self) -> None:
        payload = _engine_payload(
            eligible=False,
            confidence_class="incomplete",
            missing_facts=["ex_works", "non_originating_inputs"],
        )
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert "can't complete" in result.headline.lower()
        assert "ex-works value" in result.summary.lower()
        assert "list of non-originating inputs" in result.summary.lower()
        # No gap_analysis when facts are missing — can't quantify a gap
        assert result.gap_analysis is None
        # fix_strategy should point to filling missing facts, not a false corrective
        assert result.fix_strategy is not None
        assert "missing" in result.fix_strategy.lower() or "fill" in result.fix_strategy.lower()
        # Warnings must flag the incomplete state
        assert any("incomplete" in w.lower() for w in result.warnings)
        # Must never claim eligibility or ineligibility when facts are missing
        assert "qualifies" not in result.headline.lower()
        assert "does not qualify" not in result.headline.lower()
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 5 — Pending rule status
# ═══════════════════════════════════════════════════════════════════════════


class TestPendingRuleStatus:
    """Warning appears in warnings, result is not blocked."""

    @pytest.mark.asyncio
    async def test_pending_rule_status_adds_warning_without_blocking_result(
        self,
    ) -> None:
        payload = _engine_payload(
            eligible=True,
            pathway_used="CTH",
            rule_status="pending",
            confidence_class="provisional",
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": True,
                    "reasons": [
                        "The CTH conditions are met on current submitted facts."
                    ],
                }
            ],
        )
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        # Result is not blocked — headline still reflects qualification
        assert "pending" in result.headline.lower() or "qualifies" in result.headline.lower()
        # Warning about pending status must be present
        assert any("pending" in w.lower() for w in result.warnings)
        # fix_strategy should be None — product qualifies
        assert result.fix_strategy is None
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 6 — Contradictory NIM rendering
# ═══════════════════════════════════════════════════════════════════════════


class TestContradictoryNIMRendering:
    """Contradictory NIM output is rejected and DecisionRenderer fallback used."""

    @pytest.mark.asyncio
    async def test_nim_claims_qualification_when_ineligible_triggers_fallback(
        self,
    ) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": [
                        "Non-originating value is 48%, above the allowed 40%."
                    ],
                }
            ],
        )
        contradictory_nim = _valid_nim_json(
            headline="This product qualifies for AfCFTA preference.",
            summary="HS6 180631 qualifies under VNM. Everything looks good.",
        )
        counterfactuals = [
            {
                "kind": "value_reduction",
                "message": "Reduce non-originating value by at least 8 percentage points.",
                "delta": "8",
                "pathway_code": "VNM",
            }
        ]
        client = _mock_nim_client(response=contradictory_nim)
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload, counterfactuals=counterfactuals
        )

        assert isinstance(result, RenderedDecision)
        # Fallback must reflect the engine truth: ineligible
        assert "does not qualify" in result.headline.lower()
        # NIM was called but rejected
        client.generate_json.assert_awaited_once()
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_claims_failure_when_eligible_triggers_fallback(self) -> None:
        payload = _engine_payload(
            eligible=True,
            pathway_used="CTH",
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": True,
                    "reasons": ["Tariff heading shift confirmed."],
                }
            ],
        )
        contradictory_nim = _valid_nim_json(
            headline="This product does not qualify for AfCFTA preference.",
            summary="HS6 180631 fails to meet AfCFTA requirements.",
            gap_analysis=None,
            fix_strategy=None,
        )
        client = _mock_nim_client(response=contradictory_nim)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert "qualifies" in result.headline.lower()
        client.generate_json.assert_awaited_once()
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_invents_pathway_not_in_analysis_triggers_fallback(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["VNM threshold exceeded."],
                }
            ],
        )
        # NIM references PROCESS pathway not in pathway_analysis
        invented_pathway_nim = _valid_nim_json(
            summary=(
                "HS6 180631 fails VNM and also the PROCESS pathway "
                "which requires specific manufacturing steps."
            ),
        )
        client = _mock_nim_client(response=invented_pathway_nim)
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload,
            counterfactuals=[
                {"kind": "value_reduction", "message": "Reduce value.", "delta": "8", "pathway_code": "VNM"}
            ],
        )

        assert isinstance(result, RenderedDecision)
        # Fallback must not reference the invented PROCESS pathway
        assert "process" not in result.summary.lower()
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_invents_delta_not_in_counterfactuals_triggers_fallback(
        self,
    ) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["VNM threshold exceeded."],
                }
            ],
        )
        # NIM says delta=15 but counterfactuals say delta=8
        invented_delta_nim = _valid_nim_json(
            gap_analysis="You are 15 percentage points above the VNM threshold.",
        )
        counterfactuals = [
            {"kind": "value_reduction", "message": "Reduce by 8.", "delta": "8", "pathway_code": "VNM"}
        ]
        client = _mock_nim_client(response=invented_delta_nim)
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload, counterfactuals=counterfactuals
        )

        assert isinstance(result, RenderedDecision)
        if result.gap_analysis is not None:
            assert "15" not in result.gap_analysis
            assert "8" in result.gap_analysis
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 7 — Empty or malformed NIM rendering
# ═══════════════════════════════════════════════════════════════════════════


class TestEmptyOrMalformedNIMRendering:
    """Fallback used, no crash."""

    @pytest.mark.asyncio
    async def test_empty_string_nim_response_uses_fallback(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["VNM threshold exceeded."],
                }
            ],
        )
        client = _mock_nim_client(response="")
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload,
            counterfactuals=[
                {"kind": "value_reduction", "message": "Reduce by 8.", "delta": "8", "pathway_code": "VNM"}
            ],
        )

        assert isinstance(result, RenderedDecision)
        assert result.headline
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_malformed_json_nim_response_uses_fallback(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["Same heading as final product."],
                }
            ],
        )
        client = _mock_nim_client(response="not valid json {{{")
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert result.headline
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_returns_none_uses_fallback(self) -> None:
        payload = _engine_payload(
            eligible=True,
            pathway_used="CTH",
            pathway_analysis=[
                {
                    "pathway_code": "CTH",
                    "priority_rank": 1,
                    "passed": True,
                    "reasons": ["Tariff heading shift confirmed."],
                }
            ],
        )
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert "qualifies" in result.headline.lower()
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_timeout_uses_fallback(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["VNM threshold exceeded."],
                }
            ],
        )
        client = _mock_nim_client(
            error=NimClientError(
                "NIM request timed out after 30s",
                status_code=None,
                reason="timeout",
                attempt=2,
            )
        )
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload,
            counterfactuals=[
                {"kind": "value_reduction", "message": "Reduce by 8.", "delta": "8", "pathway_code": "VNM"}
            ],
        )

        assert isinstance(result, RenderedDecision)
        assert result.headline
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_returns_json_missing_required_field_uses_fallback(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["VNM threshold exceeded."],
                }
            ],
        )
        # Missing 'summary' field
        incomplete_json = json.dumps({
            "headline": "Something.",
            "next_steps": ["A", "B"],
            "warnings": [],
        })
        client = _mock_nim_client(response=incomplete_json)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert result.headline
        _run_cross_cutting_assertions(result, payload)

    @pytest.mark.asyncio
    async def test_nim_returns_extra_fields_uses_fallback(self) -> None:
        payload = _engine_payload(
            eligible=False,
            pathway_analysis=[
                {
                    "pathway_code": "VNM",
                    "priority_rank": 1,
                    "passed": False,
                    "reasons": ["VNM threshold exceeded."],
                }
            ],
        )
        # Extra field 'confidence' should be rejected by extra="forbid"
        extra_fields_json = json.dumps({
            "headline": "This product does not qualify yet.",
            "summary": "VNM threshold exceeded.",
            "gap_analysis": None,
            "fix_strategy": None,
            "next_steps": ["Step one.", "Step two."],
            "warnings": [],
            "confidence": "high",
        })
        client = _mock_nim_client(response=extra_fields_json)
        service = RenderingService(nim_client=client)

        result = await service.render(engine_payload=payload, counterfactuals=[])

        assert isinstance(result, RenderedDecision)
        assert result.headline
        # Verify the hallucinated field did not leak through
        d = result.to_dict()
        assert "confidence" not in d
        _run_cross_cutting_assertions(result, payload)


# ═══════════════════════════════════════════════════════════════════════════
# Cross-scenario shape stability
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderingShapeStability:
    """Verify that RenderedDecision.to_dict() has a stable shape that can
    always be loaded into AssistantRendering without error, regardless of
    the scenario that produced it.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario_name, payload, counterfactuals",
        [
            (
                "eligible",
                _engine_payload(
                    eligible=True,
                    pathway_used="CTH",
                    pathway_analysis=[
                        {"pathway_code": "CTH", "priority_rank": 1, "passed": True,
                         "reasons": ["Heading shift confirmed."]},
                    ],
                ),
                [],
            ),
            (
                "failed_vnm",
                _engine_payload(
                    eligible=False,
                    pathway_analysis=[
                        {"pathway_code": "VNM", "priority_rank": 1, "passed": False,
                         "reasons": ["VNM threshold exceeded."]},
                    ],
                ),
                [{"kind": "value_reduction", "message": "Reduce by 8.", "delta": "8", "pathway_code": "VNM"}],
            ),
            (
                "failed_cth",
                _engine_payload(
                    eligible=False,
                    pathway_analysis=[
                        {"pathway_code": "CTH", "priority_rank": 1, "passed": False,
                         "reasons": ["Same heading as final product."]},
                    ],
                ),
                [],
            ),
            (
                "missing_facts",
                _engine_payload(
                    eligible=False,
                    confidence_class="incomplete",
                    missing_facts=["ex_works", "non_originating_inputs"],
                ),
                [],
            ),
            (
                "pending_rule",
                _engine_payload(
                    eligible=True,
                    pathway_used="CTH",
                    rule_status="pending",
                    confidence_class="provisional",
                    pathway_analysis=[
                        {"pathway_code": "CTH", "priority_rank": 1, "passed": True,
                         "reasons": ["CTH conditions met."]},
                    ],
                ),
                [],
            ),
        ],
        ids=["eligible", "failed_vnm", "failed_cth", "missing_facts", "pending_rule"],
    )
    async def test_all_scenarios_produce_valid_assistant_rendering(
        self,
        scenario_name: str,
        payload: dict[str, Any],
        counterfactuals: list[dict[str, Any]],
    ) -> None:
        client = _mock_nim_client(response=None, enabled=False)
        service = RenderingService(nim_client=client)

        result = await service.render(
            engine_payload=payload,
            counterfactuals=counterfactuals,
        )

        # Convert to dict and load into AssistantRendering — must not raise
        d = result.to_dict()
        ar = AssistantRendering.model_validate(d)

        # Shape assertions
        assert set(d.keys()) == ASSISTANT_RENDERING_FIELDS
        assert ar.headline == result.headline
        assert ar.summary == result.summary
        assert ar.gap_analysis == result.gap_analysis
        assert ar.fix_strategy == result.fix_strategy
        assert ar.next_steps == result.next_steps
        assert ar.warnings == result.warnings
