"""Unit tests for the deterministic counterfactual engine."""

from __future__ import annotations

from typing import Any

from app.services.nim.counterfactual_engine import (
    CounterfactualEngine,
    CounterfactualResult,
)


def _engine() -> CounterfactualEngine:
    return CounterfactualEngine()


def _vnm_pathway(
    *,
    passed: bool | None = False,
    threshold_percent: Any = "40",
) -> dict[str, Any]:
    return {
        "pathway_code": "VNM",
        "priority_rank": 1,
        "passed": passed,
        "threshold_percent": threshold_percent,
        "reasons": ["Non-originating value exceeds threshold."],
    }


def _va_pathway(
    *,
    passed: bool | None = False,
    threshold_percent: Any = "35",
) -> dict[str, Any]:
    return {
        "pathway_code": "VA",
        "priority_rank": 2,
        "passed": passed,
        "threshold_percent": threshold_percent,
        "reasons": ["Value added is below threshold."],
    }


def _cth_pathway(*, passed: bool | None = False) -> dict[str, Any]:
    return {
        "pathway_code": "CTH",
        "priority_rank": 1,
        "passed": passed,
        "reasons": ["Non-originating inputs share the same heading as the final product."],
    }


# --- VNM failure with known actual and threshold ---


def test_vnm_failure_with_known_actual_and_threshold_emits_correct_delta() -> None:
    results = _engine().generate(
        normalized_facts={"vnom_percent": "48"},
        pathway_analysis=[_vnm_pathway(passed=False, threshold_percent="40")],
    )

    assert len(results) == 1
    r = results[0]
    assert r.kind == "value_reduction"
    assert r.delta == "8"
    assert r.pathway_code == "VNM"
    assert r.fact_key == "non_originating"
    assert "8 percentage points" in r.message
    assert "40%" in r.message


# --- VA failure with known actual and threshold ---


def test_va_failure_with_known_actual_and_threshold_emits_correct_delta() -> None:
    results = _engine().generate(
        normalized_facts={"va_percent": "28"},
        pathway_analysis=[_va_pathway(passed=False, threshold_percent="35")],
    )

    assert len(results) == 1
    r = results[0]
    assert r.kind == "value_add_increase"
    assert r.delta == "7"
    assert r.pathway_code == "VA"
    assert r.fact_key == "ex_works"
    assert "7 percentage points" in r.message
    assert "35%" in r.message


# --- CTH failure emits fix message with no delta ---


def test_cth_failure_emits_fix_message_without_delta() -> None:
    results = _engine().generate(
        normalized_facts={},
        pathway_analysis=[_cth_pathway(passed=False)],
    )

    assert len(results) == 1
    r = results[0]
    assert r.kind == "tariff_shift_fix"
    assert r.delta is None
    assert r.pathway_code == "CTH"
    assert "heading" in r.message.lower()
    assert "originating" in r.message.lower()


# --- Passed pathways are not included ---


def test_passed_pathways_not_included_in_results() -> None:
    results = _engine().generate(
        normalized_facts={"vnom_percent": "48"},
        pathway_analysis=[
            _vnm_pathway(passed=True, threshold_percent="40"),
            _cth_pathway(passed=True),
        ],
    )

    assert results == []


def test_none_passed_pathways_not_included_in_results() -> None:
    """Pathways where passed is None (untested) should also be skipped."""
    results = _engine().generate(
        normalized_facts={"vnom_percent": "48"},
        pathway_analysis=[_vnm_pathway(passed=None, threshold_percent="40")],
    )

    assert results == []


# --- Missing threshold value → no quantified result, no crash ---


def test_vnm_missing_threshold_emits_no_result() -> None:
    results = _engine().generate(
        normalized_facts={"vnom_percent": "48"},
        pathway_analysis=[_vnm_pathway(passed=False, threshold_percent=None)],
    )

    assert results == []


def test_va_missing_actual_emits_no_result() -> None:
    results = _engine().generate(
        normalized_facts={},
        pathway_analysis=[_va_pathway(passed=False, threshold_percent="35")],
    )

    assert results == []


def test_vnm_garbage_threshold_emits_no_result() -> None:
    results = _engine().generate(
        normalized_facts={"vnom_percent": "48"},
        pathway_analysis=[_vnm_pathway(passed=False, threshold_percent="not_a_number")],
    )

    assert results == []


# --- Deduplication across repeated pathway codes ---


def test_deduplication_across_repeated_pathway_codes() -> None:
    results = _engine().generate(
        normalized_facts={},
        pathway_analysis=[
            _cth_pathway(passed=False),
            _cth_pathway(passed=False),
        ],
    )

    assert len(results) == 1
    assert results[0].pathway_code == "CTH"


# --- Additional pathway coverage ---


def test_ctsh_failure_emits_subheading_fix() -> None:
    results = _engine().generate(
        normalized_facts={},
        pathway_analysis=[
            {
                "pathway_code": "CTSH",
                "priority_rank": 1,
                "passed": False,
                "reasons": ["Subheading not shifted."],
            }
        ],
    )

    assert len(results) == 1
    r = results[0]
    assert r.kind == "tariff_shift_fix"
    assert r.pathway_code == "CTSH"
    assert "subheading" in r.message.lower()


def test_wo_failure_emits_origin_fix() -> None:
    results = _engine().generate(
        normalized_facts={},
        pathway_analysis=[
            {
                "pathway_code": "WO",
                "priority_rank": 1,
                "passed": False,
                "reasons": ["Product is not wholly obtained."],
            }
        ],
    )

    assert len(results) == 1
    r = results[0]
    assert r.kind == "origin_fix"
    assert r.pathway_code == "WO"
    assert "wholly obtained" in r.message.lower()


def test_process_failure_emits_process_fix() -> None:
    results = _engine().generate(
        normalized_facts={},
        pathway_analysis=[
            {
                "pathway_code": "PROCESS",
                "priority_rank": 1,
                "passed": False,
                "reasons": ["Required process not performed."],
            }
        ],
    )

    assert len(results) == 1
    r = results[0]
    assert r.kind == "process_fix"
    assert r.pathway_code == "PROCESS"
    assert "manufacturing process" in r.message.lower()


def test_to_dict_returns_all_fields() -> None:
    r = CounterfactualResult(
        kind="value_reduction",
        message="Reduce by 8pp.",
        delta="8",
        pathway_code="VNM",
        fact_key="non_originating",
    )
    d = r.to_dict()

    assert d == {
        "kind": "value_reduction",
        "message": "Reduce by 8pp.",
        "delta": "8",
        "pathway_code": "VNM",
        "fact_key": "non_originating",
    }
