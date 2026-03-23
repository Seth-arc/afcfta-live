"""Unit tests for the safe text and JSON expression evaluator."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from app.core.exceptions import ExpressionEvaluationError
from app.services.expression_evaluator import ExpressionEvaluator


def test_vnm_passes_when_threshold_is_met() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate("vnom_percent <= 60", {"vnom_percent": 55})

    assert result.result is True
    assert result.missing_variables == []
    assert result.checks[0].passed is True


def test_vnm_fails_when_threshold_is_exceeded() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate("vnom_percent <= 60", {"vnom_percent": 65})

    assert result.result is False
    assert result.checks[0].passed is False


def test_cth_passes_when_headings_differ() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(
        "tariff_heading_input != tariff_heading_output",
        {"tariff_heading_input": "1103", "tariff_heading_output": "1201"},
    )

    assert result.result is True
    assert result.checks[0].passed is True


def test_cth_fails_when_headings_match() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(
        "tariff_heading_input != tariff_heading_output",
        {"tariff_heading_input": "1103", "tariff_heading_output": "1103"},
    )

    assert result.result is False
    assert result.checks[0].passed is False


def test_wo_passes_when_wholly_obtained_is_true() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate("wholly_obtained == true", {"wholly_obtained": True})

    assert result.result is True
    assert result.checks[0].passed is True


def test_wo_fails_when_wholly_obtained_is_false() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate("wholly_obtained == true", {"wholly_obtained": False})

    assert result.result is False
    assert result.checks[0].passed is False


def test_missing_variable_returns_none_and_tracks_variable_name() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate("wholly_obtained == true", {})

    assert result.result is None
    assert result.missing_variables == ["wholly_obtained"]
    assert result.checks[0].passed is None


def test_compound_and_passes_when_both_checks_pass() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(
        "vnom_percent <= 60 AND specific_process_performed == true",
        {"vnom_percent": 55, "specific_process_performed": True},
    )

    assert result.result is True
    assert len(result.checks) == 2
    assert all(check.passed is True for check in result.checks)


def test_compound_and_fails_when_one_check_fails() -> None:
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(
        "vnom_percent <= 60 AND specific_process_performed == true",
        {"vnom_percent": 55, "specific_process_performed": False},
    )

    assert result.result is False
    assert [check.passed for check in result.checks] == [True, False]


def test_json_all_combinator_passes_when_all_children_pass() -> None:
    evaluator = ExpressionEvaluator()
    expression = {
        "op": "all",
        "args": [
            {"op": "formula_lte", "formula": "vnom_percent", "value": 60},
            {"op": "fact_eq", "fact": "specific_process_performed", "value": True},
        ],
    }

    result = evaluator.evaluate(
        expression,
        {"vnom_percent": 55, "specific_process_performed": True},
    )

    assert result.result is True
    assert len(result.checks) == 2


def test_json_any_combinator_passes_when_one_child_passes() -> None:
    evaluator = ExpressionEvaluator()
    expression = {
        "op": "any",
        "args": [
            {"op": "fact_eq", "fact": "wholly_obtained", "value": True},
            {"op": "formula_lte", "formula": "vnom_percent", "value": 60},
        ],
    }

    result = evaluator.evaluate(
        expression,
        {"wholly_obtained": False, "vnom_percent": 55},
    )

    assert result.result is True
    assert [check.passed for check in result.checks] == [False, True]


def test_json_fact_ne_supports_ref_fact() -> None:
    evaluator = ExpressionEvaluator()
    expression = {
        "op": "fact_ne",
        "fact": "tariff_heading_input",
        "ref_fact": "tariff_heading_output",
    }

    result = evaluator.evaluate(
        expression,
        {"tariff_heading_input": "1103", "tariff_heading_output": "1201"},
    )

    assert result.result is True
    assert result.checks[0].passed is True


def test_every_non_originating_input_passes_when_all_inputs_differ_from_output() -> None:
    evaluator = ExpressionEvaluator()
    expression = {
        "op": "every_non_originating_input",
        "test": {"op": "heading_ne_output"},
    }

    result = evaluator.evaluate(
        expression,
        {
            "non_originating_inputs": [{"hs4_code": "1001", "hs6_code": "100190"}],
            "output_hs6_code": "110311",
        },
    )

    assert result.result is True
    assert result.missing_variables == []
    assert result.checks[0].check_code == "HEADING_NE_OUTPUT"
    assert result.checks[0].passed is True


def test_every_non_originating_input_tracks_missing_registered_special_facts() -> None:
    evaluator = ExpressionEvaluator()
    expression = {
        "op": "every_non_originating_input",
        "test": {"op": "subheading_ne_output"},
    }

    result = evaluator.evaluate(expression, {})

    assert result.result is None
    assert result.missing_variables == ["non_originating_inputs", "output_hs6_code"]
    assert result.checks[0].passed is None
    assert result.checks[0].check_code == "SUBHEADING_NE_OUTPUT"


def test_expression_too_long_raises_error() -> None:
    evaluator = ExpressionEvaluator()
    expression = "vnom_percent <= 60 " * 30

    with pytest.raises(ExpressionEvaluationError) as exc_info:
        evaluator.evaluate(expression, {"vnom_percent": 55})

    assert "maximum length" in exc_info.value.message


def test_unknown_json_op_raises_error() -> None:
    evaluator = ExpressionEvaluator()

    with pytest.raises(ExpressionEvaluationError) as exc_info:
        evaluator.evaluate({"op": "unknown_op"}, {})

    assert "Unsupported expression_json op" in exc_info.value.message


def test_source_file_does_not_use_dynamic_execution() -> None:
    source_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "expression_evaluator.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert re.search(r"\beval\s*\(", source) is None
    assert re.search(r"\bexec\s*\(", source) is None
    assert re.search(r"(?<!re\.)\bcompile\s*\(", source) is None
def test_source_file_does_not_use_dynamic_execution() -> None:
    """Ensure the evaluator source never uses eval/exec/standalone compile."""

    import re
    from pathlib import Path

    source = Path("app/services/expression_evaluator.py").read_text(encoding="utf-8")

    assert re.search(r"\beval\s*\(", source) is None
    assert re.search(r"\bexec\s*\(", source) is None
    assert not re.search(r"(?<!re\.)compile\s*\(", source)
