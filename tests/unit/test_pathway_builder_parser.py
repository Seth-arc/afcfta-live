"""Fixture-driven unit tests for Appendix IV pathway generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.parsers.pathway_builder import build_output_rows, pathway_summary


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "appendix_iv_pathway_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


@pytest.mark.parametrize(
    ("case_id", "component_rows", "expected"),
    [
        (case["case_id"], case["component_rows"], case["expected"])
        for case in _load_cases()
    ],
    ids=[case["case_id"] for case in _load_cases()],
)
def test_build_output_rows_matches_expected_pathway_fixtures(
    case_id: str,
    component_rows: list[dict[str, str]],
    expected: list[dict[str, Any]],
) -> None:
    """The pathway builder should emit stable pathway summaries for fixed component groups."""

    actual = pathway_summary(build_output_rows(component_rows))

    assert actual == expected, case_id


def test_build_output_rows_preserves_pending_status_and_non_executable_note_wrapper() -> None:
    """Pending NOTE pathways should remain visible with null expressions and pending status."""

    component_rows = [
        {
            "page_num": "7",
            "raw_description": "Review product",
            "raw_rule_text": "Yet to be agreed",
            "pending_flag": "True",
            "hs_code": "9999",
            "hs_level": "heading",
            "hs_display": "99.99",
            "component_type": "NOTE",
            "operator_type": "standalone",
            "component_order": "1",
            "threshold_percent": "",
            "threshold_basis": "",
            "tariff_shift_level": "",
            "specific_process_text": "Yet to be agreed",
            "confidence_score": "0.0",
        }
    ]

    output_rows = build_output_rows(component_rows)

    assert len(output_rows) == 1
    assert output_rows[0].rule_status == "pending"
    assert output_rows[0].pathway_code == "NOTE"
    assert output_rows[0].pathway_label == "Manual Review Required"
    assert json.loads(output_rows[0].expression_json)["expression"] is None
    assert output_rows[0].confidence_score == "0"


def test_build_output_rows_sets_priority_ranks_across_or_alternatives() -> None:
    """OR-separated alternatives should become separate pathways with increasing priority rank."""

    component_rows = [
        {
            "page_num": "2",
            "raw_description": "Example product",
            "raw_rule_text": "CTH; or MaxNOM 55% (EXW); or VA 40% (FOB)",
            "pending_flag": "False",
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "component_type": "CTH",
            "operator_type": "standalone",
            "component_order": "1",
            "threshold_percent": "",
            "threshold_basis": "",
            "tariff_shift_level": "heading",
            "specific_process_text": "",
            "confidence_score": "1.0",
        },
        {
            "page_num": "2",
            "raw_description": "Example product",
            "raw_rule_text": "CTH; or MaxNOM 55% (EXW); or VA 40% (FOB)",
            "pending_flag": "False",
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "component_type": "VNM",
            "operator_type": "or",
            "component_order": "2",
            "threshold_percent": "55",
            "threshold_basis": "ex_works",
            "tariff_shift_level": "",
            "specific_process_text": "",
            "confidence_score": "1.0",
        },
        {
            "page_num": "2",
            "raw_description": "Example product",
            "raw_rule_text": "CTH; or MaxNOM 55% (EXW); or VA 40% (FOB)",
            "pending_flag": "False",
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "component_type": "VA",
            "operator_type": "or",
            "component_order": "3",
            "threshold_percent": "40",
            "threshold_basis": "fob",
            "tariff_shift_level": "",
            "specific_process_text": "",
            "confidence_score": "1.0",
        },
    ]

    output_rows = build_output_rows(component_rows)

    assert [row.pathway_code for row in output_rows] == ["CTH", "VNM", "VA"]
    assert [row.priority_rank for row in output_rows] == [1, 2, 3]