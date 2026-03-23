"""Fixture-driven unit tests for Appendix IV rule decomposition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.parsers.rule_decomposer import RuleComponent, build_output_rows, decompose_rule_text


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "appendix_iv_decomposer_cases.json"


def _component_summary(components: list[RuleComponent]) -> list[dict[str, Any]]:
    return [
        {
            "component_type": component.component_type,
            "operator_type": component.operator_type,
            "threshold_percent": component.threshold_percent,
            "threshold_basis": component.threshold_basis,
            "tariff_shift_level": component.tariff_shift_level,
            "specific_process_text": component.specific_process_text,
            "normalized_expression": component.normalized_expression,
            "confidence_score": component.confidence_score,
            "component_order": component.component_order,
        }
        for component in components
    ]


def _load_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


@pytest.mark.parametrize(
    ("case_id", "input_text", "expected"),
    [
        (case["case_id"], case["input"], case["expected"])
        for case in _load_cases()
    ],
    ids=[case["case_id"] for case in _load_cases()],
)
def test_decompose_rule_text_matches_expected_fixture_cases(
    case_id: str,
    input_text: str,
    expected: list[dict[str, Any]],
) -> None:
    """The decomposer should emit stable component summaries for fixed Appendix IV patterns."""

    actual = _component_summary(decompose_rule_text(input_text))

    assert actual == expected, case_id


def test_build_output_rows_flattens_multi_component_rules_with_original_columns() -> None:
    """CSV row building should duplicate source columns once per decomposed component."""

    input_rows = [
        {
            "psr_code": "PSR-001",
            "raw_rule_text": "CTH and MaxNOM 50% (EXW)",
            "rule_status": "agreed",
        }
    ]

    output_rows = build_output_rows(input_rows)

    assert len(output_rows) == 2
    assert [row["component_order"] for row in output_rows] == [1, 2]
    assert [row["component_type"] for row in output_rows] == ["CTH", "VNM"]
    assert [row["operator_type"] for row in output_rows] == ["standalone", "and"]
    assert all(row["psr_code"] == "PSR-001" for row in output_rows)
    assert all(row["rule_status"] == "agreed" for row in output_rows)
    assert output_rows[0]["threshold_percent"] == ""
    assert output_rows[1]["threshold_percent"] == 50.0
    assert output_rows[1]["threshold_basis"] == "ex_works"
    assert output_rows[0]["normalized_expression"] == "heading_ne_output"
    assert output_rows[1]["normalized_expression"] == "vnom_percent <= 50"