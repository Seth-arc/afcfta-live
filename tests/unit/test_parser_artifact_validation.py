from __future__ import annotations

from dataclasses import asdict

import pytest

from scripts.parsers.applicability_builder import validate_output_rows as validate_applicability_output_rows
from scripts.parsers.pathway_builder import build_output_rows as build_pathway_output_rows
from scripts.parsers.pathway_builder import validate_output_rows as validate_pathway_output_rows
from scripts.parsers.rule_decomposer import validate_output_rows as validate_decomposed_output_rows
from scripts.parsers.validation_runner import (
    enforce_parser_artifact_contracts,
    run_parser_artifact_checks,
    validate_parser_confidence_rows,
)


def test_validate_decomposed_rows_reports_missing_vnm_threshold_basis() -> None:
    rows = [
        {
            "page_num": "1",
            "raw_description": "Example product",
            "raw_rule_text": "MaxNOM 55% (EXW)",
            "pending_flag": "False",
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "component_type": "VNM",
            "operator_type": "standalone",
            "component_order": "1",
            "threshold_percent": "55",
            "threshold_basis": "",
            "tariff_shift_level": "",
            "specific_process_text": "",
            "normalized_expression": "vnom_percent <= 55",
            "confidence_score": "1.0",
        }
    ]

    result = validate_decomposed_output_rows(rows)

    assert result.passed is False
    assert any(issue.field == "threshold_basis" for issue in result.issues)
    assert any("runtime-supported threshold_basis" in issue.message for issue in result.issues)


def test_validate_pathway_rows_flags_cc_runtime_mismatch() -> None:
    component_rows = [
        {
            "page_num": "1",
            "raw_description": "Example product",
            "raw_rule_text": "CC",
            "pending_flag": "False",
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "component_type": "CC",
            "operator_type": "standalone",
            "component_order": "1",
            "threshold_percent": "",
            "threshold_basis": "",
            "tariff_shift_level": "chapter",
            "specific_process_text": "",
            "confidence_score": "1.0",
        }
    ]

    pathway_rows = [asdict(row) for row in build_pathway_output_rows(component_rows)]
    result = validate_pathway_output_rows(pathway_rows)

    assert result.passed is False
    assert any(issue.field == "expression_json.expression.test.op" for issue in result.issues)
    assert any("runtime because the grammar only supports heading/subheading" in issue.message for issue in result.issues)


def test_validate_applicability_rows_requires_priority_to_match_precedence() -> None:
    rows = [
        {
            "hs6_code": "010110",
            "hs6_id": "1",
            "psr_hs_code": "0101",
            "applicability_type": "inherited_heading",
            "priority_rank": "1",
        }
    ]

    result = validate_applicability_output_rows(rows)

    assert result.passed is False
    assert any(issue.field == "priority_rank" for issue in result.issues)
    assert any("match applicability_type precedence" in issue.message for issue in result.issues)


def test_validate_parser_confidence_rows_rejects_low_confidence_executable_component() -> None:
    rows = [
        {
            "hs_code": "0101",
            "component_type": "CTH",
            "raw_rule_text": "A change to heading 01.01 from any other heading.",
            "confidence_score": "0.5",
        }
    ]

    result = validate_parser_confidence_rows(rows)

    assert result.passed is False
    assert any(issue.field == "confidence_score" for issue in result.issues)
    assert any("sub-1.0 confidence is only allowed for PROCESS/NOTE" in issue.message for issue in result.issues)


def test_run_parser_artifact_checks_allows_isolated_process_manual_review_rows() -> None:
    decomposed_rows = [
        {
            "page_num": "1",
            "raw_description": "Example chemical product",
            "raw_rule_text": "Manufacture from chemical materials of any heading",
            "pending_flag": "False",
            "hs_code": "2801",
            "hs_level": "heading",
            "hs_display": "28.01",
            "component_type": "PROCESS",
            "operator_type": "standalone",
            "component_order": "1",
            "threshold_percent": "",
            "threshold_basis": "",
            "tariff_shift_level": "",
            "specific_process_text": "Manufacture from chemical materials of any heading",
            "normalized_expression": "",
            "confidence_score": "0.5",
        }
    ]
    pathway_rows = [asdict(row) for row in build_pathway_output_rows(decomposed_rows)]
    applicability_rows = [
        {
            "hs6_code": "280110",
            "hs6_id": "1",
            "psr_hs_code": "2801",
            "applicability_type": "inherited_heading",
            "priority_rank": "2",
        }
    ]

    results = run_parser_artifact_checks(
        decomposed_rows=decomposed_rows,
        pathway_rows=pathway_rows,
        applicability_rows=applicability_rows,
    )
    confidence_result = next(
        result for result in results if result.artifact_type == "parser confidence gate"
    )

    assert confidence_result.passed is True


def test_enforce_parser_artifact_contracts_raises_actionable_error() -> None:
    decomposed_rows = [
        {
            "page_num": "1",
            "raw_description": "Example product",
            "raw_rule_text": "MaxNOM 55% (EXW)",
            "pending_flag": "False",
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "component_type": "VNM",
            "operator_type": "standalone",
            "component_order": "1",
            "threshold_percent": "55",
            "threshold_basis": "",
            "tariff_shift_level": "",
            "specific_process_text": "",
            "normalized_expression": "vnom_percent <= 55",
            "confidence_score": "1.0",
        }
    ]
    pathway_rows = [
        {
            "hs_code": "0101",
            "hs_level": "heading",
            "hs_display": "01.01",
            "product_description": "Example product",
            "legal_rule_text_verbatim": "CC",
            "rule_status": "agreed",
            "pathway_code": "CC",
            "pathway_label": "Change of Chapter",
            "pathway_type": "specific",
            "expression_json": '{"pathway_code":"CC","variables":[],"expression":{"op":"every_non_originating_input","test":{"op":"chapter_ne_output"}}}',
            "threshold_percent": "",
            "threshold_basis": "",
            "tariff_shift_level": "chapter",
            "allows_cumulation": "True",
            "allows_tolerance": "True",
            "priority_rank": "1",
            "confidence_score": "1.0",
            "page_ref": "1",
        }
    ]
    applicability_rows = [
        {
            "hs6_code": "010110",
            "hs6_id": "1",
            "psr_hs_code": "0101",
            "applicability_type": "inherited_heading",
            "priority_rank": "1",
        }
    ]

    with pytest.raises(RuntimeError) as exc_info:
        enforce_parser_artifact_contracts(
            decomposed_rows=decomposed_rows,
            pathway_rows=pathway_rows,
            applicability_rows=applicability_rows,
        )

    message = str(exc_info.value)
    assert "Promotion aborted" in message
    assert "decomposed row 1" in message
    assert "pathways row 1" in message
    assert "applicability row 1" in message
