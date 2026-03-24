"""Unit tests for the safe text and JSON expression evaluator."""

from __future__ import annotations

from pathlib import Path
import re

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.exceptions import ExpressionEvaluationError
from app.services.expression_evaluator import ExpressionEvaluator

# ---------------------------------------------------------------------------
# Bounded generators for property tests
# ---------------------------------------------------------------------------

# Monetary values: positive integers large enough to produce fractional
# percentages but small enough for fast Decimal arithmetic.
_POS_MONETARY = st.integers(min_value=1, max_value=1_000_000)
_NON_NEG_MONETARY = st.integers(min_value=0, max_value=1_000_000)

# VNM/VA threshold expressed as a whole-number percentage (0-100).
_THRESHOLD_PCT = st.integers(min_value=0, max_value=100)

# HS-4 tariff headings as zero-padded 4-digit strings ("1000"-"9999").
_HEADING = st.integers(min_value=1000, max_value=9999).map(str)


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


# ---------------------------------------------------------------------------
# Property-based tests — derived-variable math
# ---------------------------------------------------------------------------


@given(ex_works=_POS_MONETARY, non_originating=_NON_NEG_MONETARY, threshold=_THRESHOLD_PCT)
@settings(max_examples=300)
def test_vnom_and_va_are_complements_at_every_threshold(
    ex_works: int, non_originating: int, threshold: int
) -> None:
    """vnom_percent + va_percent == 100, so vnom <= T iff va >= (100 - T).

    Invariant: the two formulas are strict mathematical complements.
    A bug in either formula (swapped numerator/denominator, wrong sign,
    wrong divisor) breaks this equivalence for some input triple.
    """
    facts = {"ex_works": ex_works, "non_originating": non_originating}
    evaluator = ExpressionEvaluator()

    vnom_result = evaluator.evaluate(
        {"op": "formula_lte", "formula": "vnom_percent", "value": threshold}, facts
    )
    va_result = evaluator.evaluate(
        {"op": "formula_gte", "formula": "va_percent", "value": 100 - threshold}, facts
    )

    assert vnom_result.result == va_result.result


@given(ex_works=_POS_MONETARY, non_originating=_NON_NEG_MONETARY)
@settings(max_examples=200)
def test_vnom_is_at_most_100_when_non_originating_does_not_exceed_ex_works(
    ex_works: int, non_originating: int
) -> None:
    """vnom_percent ∈ [0, 100] whenever non_originating ≤ ex_works.

    Catches: wrong divisor (non_originating instead of ex_works),
    or multiplication factor other than 100.
    """
    assume(non_originating <= ex_works)
    facts = {"ex_works": ex_works, "non_originating": non_originating}
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(
        {"op": "formula_lte", "formula": "vnom_percent", "value": 100}, facts
    )

    assert result.result is True
    assert result.missing_variables == []


@given(ex_works=_POS_MONETARY, excess=_POS_MONETARY)
@settings(max_examples=200)
def test_vnom_exceeds_100_when_non_originating_exceeds_ex_works(
    ex_works: int, excess: int
) -> None:
    """vnom_percent > 100 when non_originating > ex_works.

    Catches: a cap or clamp applied to vnom before threshold comparison,
    which would silently allow economically impossible inputs to pass.
    """
    non_originating = ex_works + excess
    facts = {"ex_works": ex_works, "non_originating": non_originating}
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(
        {"op": "formula_lte", "formula": "vnom_percent", "value": 100}, facts
    )

    assert result.result is False


@given(non_originating=_NON_NEG_MONETARY)
@settings(max_examples=100)
def test_zero_ex_works_always_raises_for_any_non_originating(non_originating: int) -> None:
    """ex_works == 0 must raise ExpressionEvaluationError, never silently default.

    Catches: a guard that only fires for non_originating == 0, or a silent
    fallback of 0 / 0 → 0 that would incorrectly report zero VNM content.
    """
    facts = {"ex_works": 0, "non_originating": non_originating}
    evaluator = ExpressionEvaluator()

    with pytest.raises(ExpressionEvaluationError, match="Division by zero"):
        evaluator.evaluate(
            {"op": "formula_lte", "formula": "vnom_percent", "value": 60}, facts
        )


# ---------------------------------------------------------------------------
# Property-based tests — text vs JSON format equivalence
# ---------------------------------------------------------------------------


@given(ex_works=_POS_MONETARY, non_originating=_NON_NEG_MONETARY, threshold=_THRESHOLD_PCT)
@settings(max_examples=200)
def test_text_and_json_vnom_expressions_produce_identical_results(
    ex_works: int, non_originating: int, threshold: int
) -> None:
    """Text expression "vnom_percent <= T" and JSON formula_lte must agree on every input.

    Catches: separate parsing paths that apply different numeric coercion
    or rounding, causing one format to pass and the other to fail at the
    same boundary.
    """
    facts = {"ex_works": ex_works, "non_originating": non_originating}
    evaluator = ExpressionEvaluator()

    text_result = evaluator.evaluate(f"vnom_percent <= {threshold}", facts)
    json_result = evaluator.evaluate(
        {"op": "formula_lte", "formula": "vnom_percent", "value": threshold}, facts
    )

    assert text_result.result == json_result.result


# ---------------------------------------------------------------------------
# Property-based tests — AND / OR combinator semantics
# ---------------------------------------------------------------------------


@given(
    vnom_value=st.integers(min_value=1, max_value=99),
    thresholds=st.lists(_THRESHOLD_PCT, min_size=1, max_size=6),
)
@settings(max_examples=200)
def test_json_all_combinator_matches_python_all_for_any_threshold_set(
    vnom_value: int, thresholds: list[int]
) -> None:
    """JSON "all" combinator over formula_lte nodes is semantically identical to Python all().

    Catches: an OR/AND swap, a combinator that short-circuits to True on an
    empty sub-result, or a result-merging bug that ignores some children.
    """
    facts = {"ex_works": 100, "non_originating": vnom_value}
    expression = {
        "op": "all",
        "args": [
            {"op": "formula_lte", "formula": "vnom_percent", "value": t} for t in thresholds
        ],
    }
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(expression, facts)

    expected = all(vnom_value <= t for t in thresholds)
    assert result.result == expected


@given(
    vnom_value=st.integers(min_value=1, max_value=99),
    thresholds=st.lists(_THRESHOLD_PCT, min_size=1, max_size=6),
)
@settings(max_examples=200)
def test_json_any_combinator_matches_python_any_for_any_threshold_set(
    vnom_value: int, thresholds: list[int]
) -> None:
    """JSON "any" combinator over formula_lte nodes is semantically identical to Python any().

    Catches: an AND/OR swap, or a combinator that stops evaluating after the
    first False child instead of continuing to find a passing branch.
    """
    facts = {"ex_works": 100, "non_originating": vnom_value}
    expression = {
        "op": "any",
        "args": [
            {"op": "formula_lte", "formula": "vnom_percent", "value": t} for t in thresholds
        ],
    }
    evaluator = ExpressionEvaluator()

    result = evaluator.evaluate(expression, facts)

    expected = any(vnom_value <= t for t in thresholds)
    assert result.result == expected


# ---------------------------------------------------------------------------
# Property-based tests — CTH heading-shift check
# ---------------------------------------------------------------------------


@given(
    output_heading=_HEADING,
    input_headings=st.lists(_HEADING, min_size=1, max_size=5),
)
@settings(max_examples=200)
def test_cth_passes_when_all_input_headings_differ_from_output(
    output_heading: str, input_headings: list[str]
) -> None:
    """every_non_originating_input passes iff every input heading ≠ the output heading.

    Catches: using any() instead of all() in the heading loop, or an
    off-by-one on the HS4 slice (output_code[:4] vs output_code[:6]).
    """
    assume(all(h != output_heading for h in input_headings))
    evaluator = ExpressionEvaluator()
    expression = {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}}
    facts = {
        "non_originating_inputs": [{"hs4_code": h} for h in input_headings],
        "output_hs6_code": output_heading + "00",
    }

    result = evaluator.evaluate(expression, facts)

    assert result.result is True
    assert result.missing_variables == []


@given(
    output_heading=_HEADING,
    other_inputs=st.lists(_HEADING, min_size=0, max_size=4),
)
@settings(max_examples=200)
def test_cth_fails_as_soon_as_one_input_heading_matches_output(
    output_heading: str, other_inputs: list[str]
) -> None:
    """A single matching input heading is sufficient to fail the CTH check.

    Catches: an any()-based implementation that only fails when all inputs
    match, or a slice error that compares the wrong number of digits.
    """
    # Append the matching heading so at least one input always matches.
    inputs = other_inputs + [output_heading]
    evaluator = ExpressionEvaluator()
    expression = {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}}
    facts = {
        "non_originating_inputs": [{"hs4_code": h} for h in inputs],
        "output_hs6_code": output_heading + "00",
    }

    result = evaluator.evaluate(expression, facts)

    assert result.result is False
