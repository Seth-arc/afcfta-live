"""Unit tests for deterministic decision narrative rendering."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.nim.decision_renderer import (
    DecisionRenderer,
    DecisionRendererError,
    RenderedDecision,
)


def _engine_payload(
    *,
    eligible: bool = False,
    pathway_used: str | None = None,
    rule_status: str = "agreed",
    confidence_class: str = "complete",
    pathway_analysis: list[dict[str, Any]] | None = None,
    missing_facts: list[str] | None = None,
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
        "failures": [],
        "evidence_required": ["certificate_of_origin", "bill_of_materials"],
        "tariff_outcome": tariff_outcome
        or {
            "preferential_rate": "0%",
            "base_rate": "20%",
            "status": "in_force",
        },
    }


def _renderer() -> DecisionRenderer:
    return DecisionRenderer()


def test_eligible_result_renders_clean_qualifying_narrative_with_pathway_reason() -> None:
    payload = _engine_payload(
        eligible=True,
        pathway_used="CTH",
        pathway_analysis=[
            {
                "pathway_code": "CTH",
                "priority_rank": 1,
                "passed": True,
                "reasons": ["Tariff heading of non-originating inputs changes at heading level."],
            }
        ],
    )

    result = _renderer().render(engine_payload=payload)

    assert isinstance(result, RenderedDecision)
    assert "qualifies" in result.headline.lower()
    assert "CTH" in result.summary
    assert "Tariff heading of non-originating inputs changes at heading level." in result.summary
    assert result.fix_strategy is None
    assert result.gap_analysis is None


def test_failed_vnm_renders_quantified_gap_when_counterfactual_delta_present() -> None:
    payload = _engine_payload(
        eligible=False,
        pathway_analysis=[
            {
                "pathway_code": "VNM",
                "priority_rank": 1,
                "passed": False,
                "reasons": ["Non-originating value is 48%, above the allowed 40%."],
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

    result = _renderer().render(engine_payload=payload, counterfactuals=counterfactuals)

    assert "does not qualify" in result.headline.lower()
    assert result.gap_analysis == "You are 8 percentage points above the VNM threshold."
    assert result.fix_strategy is not None
    assert "Reduce non-originating value by at least 8 percentage points." in result.fix_strategy


def test_failed_cth_renders_tariff_shift_narrative_without_inventing_gap() -> None:
    payload = _engine_payload(
        eligible=False,
        pathway_analysis=[
            {
                "pathway_code": "CTH",
                "priority_rank": 1,
                "passed": False,
                "reasons": [
                    (
                        "One or more non-originating inputs share the same heading "
                        "as the final product."
                    )
                ],
            }
        ],
    )

    result = _renderer().render(engine_payload=payload, counterfactuals=[])

    assert "does not qualify" in result.summary.lower()
    assert "same heading" in result.summary.lower()
    assert result.gap_analysis is None
    assert result.fix_strategy is not None
    assert "heading" in result.fix_strategy.lower()
    assert "percentage point" not in result.fix_strategy.lower()


def test_missing_facts_renders_incomplete_narrative_without_fake_certainty() -> None:
    payload = _engine_payload(
        eligible=False,
        confidence_class="incomplete",
        missing_facts=["ex_works", "non_originating_inputs"],
    )

    result = _renderer().render(engine_payload=payload)

    assert "can't complete" in result.headline.lower()
    assert "ex-works value" in result.summary.lower()
    assert "list of non-originating inputs" in result.summary.lower()
    assert result.gap_analysis is None
    assert any("incomplete" in warning.lower() for warning in result.warnings)


def test_pending_rule_status_adds_warning() -> None:
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
                "reasons": ["The CTH conditions are met on current submitted facts."],
            }
        ],
    )

    result = _renderer().render(engine_payload=payload)

    assert any("pending" in warning.lower() for warning in result.warnings)


def test_malformed_payload_raises_decision_renderer_error() -> None:
    malformed_payload = {
        "decision": {"eligible": True, "rule_status": "agreed"},
        "product": {"hs6_code": "180631"},
        "pathway_analysis": [],
        "missing_facts": [],
        "failures": [],
        "evidence_required": [],
    }

    with pytest.raises(DecisionRendererError):
        _renderer().render(engine_payload=malformed_payload)
