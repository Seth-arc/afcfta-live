from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.enums import HsLevelEnum, RuleStatusEnum, ThresholdBasisEnum
from scripts.parsers.artifact_contracts import (
    ArtifactValidationIssue,
    ArtifactValidationResult,
    normalize_text as normalize_contract_text,
    parse_bool_string,
    parse_float,
    parse_int,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv"
HS_VERSION = "HS2017"

OUTPUT_FIELDNAMES = [
    "hs_code",
    "hs_level",
    "hs_display",
    "product_description",
    "legal_rule_text_verbatim",
    "rule_status",
    "pathway_code",
    "pathway_label",
    "pathway_type",
    "expression_json",
    "threshold_percent",
    "threshold_basis",
    "tariff_shift_level",
    "allows_cumulation",
    "allows_tolerance",
    "priority_rank",
    "confidence_score",
    "page_ref",
]

VARIABLE_DEFS = {
    "vnom_percent": {
        "name": "vnom_percent",
        "formula": "non_originating / ex_works * 100",
    },
    "va_percent": {
        "name": "va_percent",
        "formula": "(ex_works - non_originating) / ex_works * 100",
    },
}

LEAF_LABELS = {
    "WO": "Wholly Obtained",
    "CTH": "Change of Tariff Heading",
    "CTSH": "Change of Tariff Subheading",
    "CC": "Change of Chapter",
    "PROCESS": "Specific Process",
    "NOTE": "Manual Review Required",
}

VALID_RULE_STATUSES = {member.value for member in RuleStatusEnum}
VALID_HS_LEVELS = {member.value for member in HsLevelEnum}
VALID_THRESHOLD_BASES = {member.value for member in ThresholdBasisEnum}
VALID_PATHWAY_COMPONENT_CODES = {"WO", "CTH", "CTSH", "CC", "VNM", "VA", "PROCESS", "NOTE"}
NULL_EXPRESSION_CODES = {"PROCESS", "NOTE"}
VARIABLE_NAME_TO_FORMULA = {
    definition["name"]: definition["formula"]
    for definition in VARIABLE_DEFS.values()
}


@dataclass(slots=True)
class PathwayRecord:
    hs_code: str
    hs_level: str
    hs_display: str
    product_description: str
    legal_rule_text_verbatim: str
    rule_status: str
    pathway_code: str
    pathway_label: str
    pathway_type: str
    expression_json: str
    threshold_percent: str
    threshold_basis: str
    tariff_shift_level: str
    allows_cumulation: str
    allows_tolerance: str
    priority_rank: int
    confidence_score: str
    page_ref: str


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def read_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[PathwayRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def rule_group_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("page_num", ""),
        row.get("hs_code", ""),
        row.get("raw_description", ""),
        row.get("raw_rule_text", ""),
    )


def sort_component_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("page_num") or 0),
            row.get("hs_code", ""),
            int(float(row.get("component_order") or 0)),
        ),
    )


def split_component_groups(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    groups: list[list[dict[str, str]]] = []
    current_group: list[dict[str, str]] = []

    for row in sort_component_rows(rows):
        operator_type = (row.get("operator_type") or "standalone").strip().lower()
        if not current_group:
            current_group = [row]
            continue

        if operator_type == "and":
            current_group.append(row)
            continue

        groups.append(current_group)
        current_group = [row]

    if current_group:
        groups.append(current_group)

    return groups


def parse_threshold(row: dict[str, str]) -> float | None:
    raw_value = normalize_text(row.get("threshold_percent"))
    if not raw_value:
        return None
    return float(raw_value)


def format_threshold(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:g}"


def format_basis_label(basis: str | None) -> str:
    if not basis:
        return "EXW"
    return {
        "ex_works": "EXW",
        "fob": "FOB",
        "customs_value": "CUSTOMS_VALUE",
    }.get(basis, basis.upper())


def component_label(row: dict[str, str]) -> str:
    component_type = row.get("component_type", "")
    threshold = parse_threshold(row)
    threshold_basis = normalize_text(row.get("threshold_basis"))
    if component_type == "VNM":
        return f"Maximum Non-Originating Materials {format_threshold(threshold)}% ({format_basis_label(threshold_basis)})"
    if component_type == "VA":
        return f"Minimum Value Added {format_threshold(threshold)}% ({format_basis_label(threshold_basis)})"
    return LEAF_LABELS.get(component_type, component_type)


def build_leaf_expression(row: dict[str, str]) -> dict | None:
    component_type = row.get("component_type", "")
    threshold = parse_threshold(row)
    specific_process_text = normalize_text(row.get("specific_process_text"))

    if component_type == "WO":
        return {"op": "fact_eq", "fact": "wholly_obtained", "value": True}
    if component_type == "CTH":
        expression = {
            "op": "every_non_originating_input",
            "test": {"op": "heading_ne_output"},
        }
        if specific_process_text:
            expression["exceptions"] = specific_process_text
        return expression
    if component_type == "CTSH":
        return {
            "op": "every_non_originating_input",
            "test": {"op": "subheading_ne_output"},
        }
    if component_type == "CC":
        return {
            "op": "every_non_originating_input",
            "test": {"op": "chapter_ne_output"},
        }
    if component_type == "VNM" and threshold is not None:
        return {"op": "formula_lte", "formula": "vnom_percent", "value": int(threshold) if threshold.is_integer() else threshold}
    if component_type == "VA" and threshold is not None:
        return {"op": "formula_gte", "formula": "va_percent", "value": int(threshold) if threshold.is_integer() else threshold}
    return None


def build_variables(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    variables: list[dict[str, str]] = []
    for row in rows:
        component_type = row.get("component_type", "")
        variable_name = None
        if component_type == "VNM":
            variable_name = "vnom_percent"
        elif component_type == "VA":
            variable_name = "va_percent"
        if variable_name and variable_name not in seen:
            variables.append(VARIABLE_DEFS[variable_name])
            seen.add(variable_name)
    return variables


def pathway_code(rows: list[dict[str, str]]) -> str:
    component_types = [row.get("component_type", "") for row in rows]
    return "+".join(component_types)


def pathway_label(rows: list[dict[str, str]]) -> str:
    labels = [component_label(row) for row in rows]
    return " + ".join(labels)


def pathway_expression_payload(rows: list[dict[str, str]]) -> dict:
    code = pathway_code(rows)
    variables = build_variables(rows)
    leaf_expressions = [build_leaf_expression(row) for row in rows]
    if any(expression is None for expression in leaf_expressions):
        expression = None
    elif len(leaf_expressions) == 1:
        expression = leaf_expressions[0]
    else:
        expression = {"op": "all", "args": leaf_expressions}
    return {
        "pathway_code": code,
        "variables": variables,
        "expression": expression,
    }


def derive_rule_status(rule_rows: list[dict[str, str]]) -> str:
    return "pending" if any((row.get("pending_flag") or "").strip().lower() == "true" for row in rule_rows) else "agreed"


def derive_threshold_percent(rows: list[dict[str, str]]) -> str:
    for row in rows:
        threshold = normalize_text(row.get("threshold_percent"))
        if threshold:
            return threshold
    return ""


def derive_threshold_basis(rows: list[dict[str, str]]) -> str:
    for row in rows:
        threshold_basis = normalize_text(row.get("threshold_basis"))
        if threshold_basis:
            return threshold_basis
    return ""


def derive_tariff_shift_level(rows: list[dict[str, str]]) -> str:
    for row in rows:
        tariff_shift_level = normalize_text(row.get("tariff_shift_level"))
        if tariff_shift_level:
            return tariff_shift_level
    return ""


def pathway_allows_wo_exceptions(rows: list[dict[str, str]]) -> tuple[str, str]:
    if any(row.get("component_type") == "WO" for row in rows):
        return "False", "False"
    return "True", "True"


def pathway_confidence(rows: list[dict[str, str]]) -> str:
    confidence_values = [float(row.get("confidence_score") or 0.0) for row in rows]
    return f"{min(confidence_values):g}"


def build_pathway_record(rule_rows: list[dict[str, str]], component_rows: list[dict[str, str]], priority_rank: int) -> PathwayRecord:
    base_row = component_rows[0]
    expression_payload = pathway_expression_payload(component_rows)
    allows_cumulation, allows_tolerance = pathway_allows_wo_exceptions(component_rows)
    return PathwayRecord(
        hs_code=base_row.get("hs_code", ""),
        hs_level=base_row.get("hs_level", ""),
        hs_display=base_row.get("hs_display", ""),
        product_description=base_row.get("raw_description", ""),
        legal_rule_text_verbatim=base_row.get("raw_rule_text", ""),
        rule_status=derive_rule_status(rule_rows),
        pathway_code=expression_payload["pathway_code"],
        pathway_label=pathway_label(component_rows),
        pathway_type="specific",
        expression_json=json.dumps(expression_payload, ensure_ascii=True, separators=(",", ":")),
        threshold_percent=derive_threshold_percent(component_rows),
        threshold_basis=derive_threshold_basis(component_rows),
        tariff_shift_level=derive_tariff_shift_level(component_rows),
        allows_cumulation=allows_cumulation,
        allows_tolerance=allows_tolerance,
        priority_rank=priority_rank,
        confidence_score=pathway_confidence(component_rows),
        page_ref=base_row.get("page_num", ""),
    )


def build_output_rows(input_rows: list[dict[str, str]]) -> list[PathwayRecord]:
    grouped_rows: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        grouped_rows[rule_group_key(row)].append(row)

    output_rows: list[PathwayRecord] = []
    for _, rule_rows in sorted(grouped_rows.items(), key=lambda item: sort_component_rows(item[1])[0].get("hs_code", "")):
        component_groups = split_component_groups(rule_rows)
        for priority_rank, component_group in enumerate(component_groups, start=1):
            output_rows.append(build_pathway_record(rule_rows, component_group, priority_rank))
    return output_rows


def pathway_summary(pathway_rows: list[PathwayRecord]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for row in pathway_rows:
        summaries.append(
            {
                "pathway_code": row.pathway_code,
                "pathway_label": row.pathway_label,
                "priority_rank": row.priority_rank,
                "expression_json": json.loads(row.expression_json),
            }
        )
    return summaries


def _row_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            normalize_contract_text(row.get("hs_code")),
            normalize_contract_text(row.get("page_ref")),
            normalize_contract_text(row.get("pathway_code")),
        ]
    )


def _issue(row_number: int, field: str, message: str, row: dict[str, str], value: object | None = None) -> ArtifactValidationIssue:
    return ArtifactValidationIssue(
        artifact_type="pathways",
        row_number=row_number,
        field=field,
        message=message,
        row_key=_row_key(row),
        value=normalize_contract_text(value),
    )


def _validate_expression_node(
    node: object,
    row_number: int,
    row: dict[str, str],
    field_prefix: str,
) -> list[ArtifactValidationIssue]:
    issues: list[ArtifactValidationIssue] = []
    if not isinstance(node, dict):
        return [_issue(row_number, field_prefix, "expression nodes must be JSON objects", row, node)]

    op = node.get("op")
    if not isinstance(op, str):
        return [_issue(row_number, field_prefix, "expression nodes must include string op", row, op)]

    if op in {"all", "any"}:
        args = node.get("args")
        if not isinstance(args, list) or not args:
            issues.append(_issue(row_number, f"{field_prefix}.args", f"{op} requires a non-empty args list", row, args))
            return issues
        for index, child in enumerate(args):
            issues.extend(_validate_expression_node(child, row_number, row, f"{field_prefix}.args[{index}]"))
        return issues

    if op == "formula_lte":
        if node.get("formula") != "vnom_percent":
            issues.append(_issue(row_number, f"{field_prefix}.formula", "formula_lte must target vnom_percent", row, node.get("formula")))
        if not isinstance(node.get("value"), (int, float)):
            issues.append(_issue(row_number, f"{field_prefix}.value", "formula_lte requires numeric value", row, node.get("value")))
        return issues

    if op == "formula_gte":
        if node.get("formula") != "va_percent":
            issues.append(_issue(row_number, f"{field_prefix}.formula", "formula_gte must target va_percent", row, node.get("formula")))
        if not isinstance(node.get("value"), (int, float)):
            issues.append(_issue(row_number, f"{field_prefix}.value", "formula_gte requires numeric value", row, node.get("value")))
        return issues

    if op == "fact_eq":
        if not isinstance(node.get("fact"), str):
            issues.append(_issue(row_number, f"{field_prefix}.fact", "fact_eq requires a fact name", row, node.get("fact")))
        if "value" not in node:
            issues.append(_issue(row_number, f"{field_prefix}.value", "fact_eq requires value", row))
        return issues

    if op == "fact_ne":
        if not isinstance(node.get("fact"), str):
            issues.append(_issue(row_number, f"{field_prefix}.fact", "fact_ne requires a fact name", row, node.get("fact")))
        if "value" not in node and not isinstance(node.get("ref_fact"), str):
            issues.append(
                _issue(row_number, f"{field_prefix}.ref_fact", "fact_ne requires value or ref_fact", row, node.get("ref_fact"))
            )
        return issues

    if op == "every_non_originating_input":
        test = node.get("test")
        if not isinstance(test, dict):
            issues.append(_issue(row_number, f"{field_prefix}.test", "every_non_originating_input requires test object", row, test))
            return issues
        test_op = test.get("op")
        if test_op not in {"heading_ne_output", "subheading_ne_output"}:
            issues.append(
                _issue(
                    row_number,
                    f"{field_prefix}.test.op",
                    "every_non_originating_input test op must be runtime-supported",
                    row,
                    test_op,
                )
            )
        exceptions = node.get("exceptions")
        if exceptions is not None and not isinstance(exceptions, str):
            issues.append(
                _issue(row_number, f"{field_prefix}.exceptions", "exceptions must preserve verbatim text as a string", row, exceptions)
            )
        return issues

    issues.append(_issue(row_number, field_prefix, "Unsupported expression op for the runtime contract", row, op))
    return issues


def validate_output_rows(rows: list[dict[str, str]]) -> ArtifactValidationResult:
    issues: list[ArtifactValidationIssue] = []
    priorities_by_rule: dict[tuple[str, str, str, str], list[tuple[int, int]]] = defaultdict(list)

    for row_number, row in enumerate(rows, start=1):
        hs_code = normalize_contract_text(row.get("hs_code"))
        hs_level = normalize_contract_text(row.get("hs_level"))
        legal_rule_text = normalize_contract_text(row.get("legal_rule_text_verbatim"))
        rule_status = normalize_contract_text(row.get("rule_status"))
        pathway_code = normalize_contract_text(row.get("pathway_code"))
        pathway_label = normalize_contract_text(row.get("pathway_label"))
        pathway_type = normalize_contract_text(row.get("pathway_type"))
        threshold_percent = parse_float(row.get("threshold_percent"))
        threshold_basis = normalize_contract_text(row.get("threshold_basis"))
        tariff_shift_level = normalize_contract_text(row.get("tariff_shift_level"))
        allows_cumulation = parse_bool_string(row.get("allows_cumulation"))
        allows_tolerance = parse_bool_string(row.get("allows_tolerance"))
        priority_rank = parse_int(row.get("priority_rank"))
        confidence_score = parse_float(row.get("confidence_score"))
        page_ref = parse_int(row.get("page_ref"))
        expression_json = normalize_contract_text(row.get("expression_json"))

        if not hs_code:
            issues.append(_issue(row_number, "hs_code", "hs_code is required", row))
        if hs_level not in VALID_HS_LEVELS:
            issues.append(_issue(row_number, "hs_level", "hs_level must match the runtime enum", row, hs_level))
        if not legal_rule_text:
            issues.append(_issue(row_number, "legal_rule_text_verbatim", "Verbatim legal text is required", row))
        if rule_status not in VALID_RULE_STATUSES:
            issues.append(_issue(row_number, "rule_status", "rule_status must match the runtime enum", row, rule_status))
        if not pathway_label:
            issues.append(_issue(row_number, "pathway_label", "pathway_label is required", row))
        if pathway_type != "specific":
            issues.append(_issue(row_number, "pathway_type", "Only specific pathways are supported in v0.1 parser artifacts", row, pathway_type))
        if allows_cumulation is None:
            issues.append(_issue(row_number, "allows_cumulation", "allows_cumulation must be True or False", row, row.get("allows_cumulation")))
        if allows_tolerance is None:
            issues.append(_issue(row_number, "allows_tolerance", "allows_tolerance must be True or False", row, row.get("allows_tolerance")))
        if priority_rank is None or priority_rank < 1:
            issues.append(_issue(row_number, "priority_rank", "priority_rank must be a positive integer", row, row.get("priority_rank")))
        if confidence_score is None or not 0.0 <= confidence_score <= 1.0:
            issues.append(_issue(row_number, "confidence_score", "confidence_score must be between 0.0 and 1.0", row, row.get("confidence_score")))
        if page_ref is None or page_ref < 1:
            issues.append(_issue(row_number, "page_ref", "page_ref must be a positive integer", row, row.get("page_ref")))

        pathway_codes = pathway_code.split("+") if pathway_code else []
        if not pathway_codes:
            issues.append(_issue(row_number, "pathway_code", "pathway_code is required", row))
        for code in pathway_codes:
            if code not in VALID_PATHWAY_COMPONENT_CODES:
                issues.append(_issue(row_number, "pathway_code", "pathway_code contains unsupported component code", row, code))

        if any(code == "WO" for code in pathway_codes):
            if allows_cumulation is not False or allows_tolerance is not False:
                issues.append(_issue(row_number, "allows_cumulation", "WO pathways must disable cumulation and tolerance", row))

        if any(code in {"VNM", "VA"} for code in pathway_codes):
            if threshold_percent is None:
                issues.append(_issue(row_number, "threshold_percent", "Threshold pathways require threshold_percent", row))
            if threshold_basis not in VALID_THRESHOLD_BASES:
                issues.append(_issue(row_number, "threshold_basis", "Threshold pathways require runtime-supported threshold_basis", row, threshold_basis))
        elif threshold_percent is not None or threshold_basis:
            issues.append(_issue(row_number, "threshold_percent", "Non-threshold pathways must not declare threshold fields", row))

        if any(code in {"CTH", "CTSH", "CC"} for code in pathway_codes) and not tariff_shift_level:
            issues.append(_issue(row_number, "tariff_shift_level", "Tariff-shift pathways require tariff_shift_level", row))

        try:
            payload = json.loads(expression_json)
        except json.JSONDecodeError as exc:
            issues.append(_issue(row_number, "expression_json", f"expression_json must be valid JSON: {exc.msg}", row))
            payload = None

        if isinstance(payload, dict):
            if payload.get("pathway_code") != pathway_code:
                issues.append(
                    _issue(row_number, "expression_json.pathway_code", "Wrapped payload pathway_code must match row pathway_code", row, payload.get("pathway_code"))
                )

            variables = payload.get("variables")
            if not isinstance(variables, list):
                issues.append(_issue(row_number, "expression_json.variables", "variables must be a list", row, variables))
                variables = []

            seen_variable_names: set[str] = set()
            for index, variable in enumerate(variables):
                if not isinstance(variable, dict):
                    issues.append(_issue(row_number, f"expression_json.variables[{index}]", "Each variable must be an object", row, variable))
                    continue
                variable_name = variable.get("name")
                variable_formula = variable.get("formula")
                if variable_name not in VARIABLE_NAME_TO_FORMULA:
                    issues.append(
                        _issue(row_number, f"expression_json.variables[{index}].name", "Unsupported derived variable", row, variable_name)
                    )
                    continue
                if VARIABLE_NAME_TO_FORMULA[variable_name] != variable_formula:
                    issues.append(
                        _issue(row_number, f"expression_json.variables[{index}].formula", "Derived variable formula must match the runtime contract", row, variable_formula)
                    )
                if variable_name in seen_variable_names:
                    issues.append(
                        _issue(row_number, f"expression_json.variables[{index}].name", "Derived variables must not be duplicated", row, variable_name)
                    )
                seen_variable_names.add(variable_name)

            required_variables = set()
            if "VNM" in pathway_codes:
                required_variables.add("vnom_percent")
            if "VA" in pathway_codes:
                required_variables.add("va_percent")
            if seen_variable_names != required_variables:
                issues.append(
                    _issue(
                        row_number,
                        "expression_json.variables",
                        "Derived variables must exactly match the threshold components in the pathway",
                        row,
                        sorted(seen_variable_names),
                    )
                )

            expression = payload.get("expression")
            if expression is None:
                if not pathway_codes or not all(code in NULL_EXPRESSION_CODES for code in pathway_codes):
                    issues.append(
                        _issue(row_number, "expression_json.expression", "Null expressions are only allowed for NOTE/PROCESS manual-review pathways", row)
                    )
            else:
                issues.extend(_validate_expression_node(expression, row_number, row, "expression_json.expression"))
                if "CC" in pathway_codes:
                    issues.append(
                        _issue(
                            row_number,
                            "expression_json.expression",
                            "CC pathways are not executable in the v0.1 runtime because the grammar only supports heading/subheading tariff-shift tests",
                            row,
                            pathway_code,
                        )
                    )

        rule_key = (
            hs_code,
            hs_level,
            normalize_contract_text(row.get("product_description")),
            legal_rule_text,
        )
        priorities_by_rule[rule_key].append((row_number, priority_rank or 0))

    for entries in priorities_by_rule.values():
        ordered = sorted(entries, key=lambda item: item[1])
        expected = list(range(1, len(ordered) + 1))
        actual = [priority for _, priority in ordered]
        if actual != expected:
            row_number = ordered[0][0]
            row = rows[row_number - 1]
            issues.append(
                _issue(
                    row_number,
                    "priority_rank",
                    "priority_rank values must be contiguous within each rule's OR alternatives",
                    row,
                    actual,
                )
            )

    return ArtifactValidationResult(
        artifact_type="pathways",
        total_rows=len(rows),
        issues=tuple(issues),
    )


def component_row(component_type: str, operator_type: str, component_order: int, **kwargs: object) -> dict[str, str]:
    row = {
        "page_num": "1",
        "raw_description": "Example product",
        "raw_rule_text": "Example rule",
        "pending_flag": "False",
        "hs_code": "0101",
        "hs_level": "heading",
        "hs_display": "01.01",
        "component_type": component_type,
        "operator_type": operator_type,
        "component_order": str(component_order),
        "threshold_percent": "",
        "threshold_basis": "",
        "tariff_shift_level": "",
        "specific_process_text": "",
        "confidence_score": "1.0",
    }
    for key, value in kwargs.items():
        row[key] = "" if value is None else str(value)
    return row


def validate_test_vectors() -> list[tuple[str, bool]]:
    tests: list[tuple[str, list[dict[str, str]], list[dict[str, object]]]] = [
        (
            "Test Vector 1",
            [component_row("WO", "standalone", 1)],
            [
                {
                    "pathway_code": "WO",
                    "pathway_label": "Wholly Obtained",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "WO",
                        "variables": [],
                        "expression": {"op": "fact_eq", "fact": "wholly_obtained", "value": True},
                    },
                }
            ],
        ),
        (
            "Test Vector 2",
            [component_row("CTH", "standalone", 1, tariff_shift_level="heading")],
            [
                {
                    "pathway_code": "CTH",
                    "pathway_label": "Change of Tariff Heading",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "CTH",
                        "variables": [],
                        "expression": {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}},
                    },
                }
            ],
        ),
        (
            "Test Vector 3",
            [component_row("VNM", "standalone", 1, threshold_percent="55", threshold_basis="ex_works")],
            [
                {
                    "pathway_code": "VNM",
                    "pathway_label": "Maximum Non-Originating Materials 55% (EXW)",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "VNM",
                        "variables": [{"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}],
                        "expression": {"op": "formula_lte", "formula": "vnom_percent", "value": 55},
                    },
                }
            ],
        ),
        (
            "Test Vector 4",
            [
                component_row("CTH", "standalone", 1, tariff_shift_level="heading"),
                component_row("VNM", "or", 2, threshold_percent="55", threshold_basis="ex_works"),
            ],
            [
                {
                    "pathway_code": "CTH",
                    "pathway_label": "Change of Tariff Heading",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "CTH",
                        "variables": [],
                        "expression": {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}},
                    },
                },
                {
                    "pathway_code": "VNM",
                    "pathway_label": "Maximum Non-Originating Materials 55% (EXW)",
                    "priority_rank": 2,
                    "expression_json": {
                        "pathway_code": "VNM",
                        "variables": [{"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}],
                        "expression": {"op": "formula_lte", "formula": "vnom_percent", "value": 55},
                    },
                },
            ],
        ),
        (
            "Test Vector 5",
            [
                component_row("CTH", "standalone", 1, tariff_shift_level="heading"),
                component_row("VNM", "and", 2, threshold_percent="50", threshold_basis="ex_works"),
            ],
            [
                {
                    "pathway_code": "CTH+VNM",
                    "pathway_label": "Change of Tariff Heading + Maximum Non-Originating Materials 50% (EXW)",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "CTH+VNM",
                        "variables": [{"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}],
                        "expression": {
                            "op": "all",
                            "args": [
                                {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}},
                                {"op": "formula_lte", "formula": "vnom_percent", "value": 50},
                            ],
                        },
                    },
                }
            ],
        ),
        (
            "Test Vector 6",
            [component_row("CTH", "standalone", 1, tariff_shift_level="heading", specific_process_text="except from heading 10.06")],
            [
                {
                    "pathway_code": "CTH",
                    "pathway_label": "Change of Tariff Heading",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "CTH",
                        "variables": [],
                        "expression": {
                            "op": "every_non_originating_input",
                            "test": {"op": "heading_ne_output"},
                            "exceptions": "except from heading 10.06",
                        },
                    },
                }
            ],
        ),
        (
            "Test Vector 7",
            [component_row("PROCESS", "standalone", 1, specific_process_text="Manufacture from chemical materials of any heading", confidence_score="0.5")],
            [
                {
                    "pathway_code": "PROCESS",
                    "pathway_label": "Specific Process",
                    "priority_rank": 1,
                    "expression_json": {
                        "pathway_code": "PROCESS",
                        "variables": [],
                        "expression": None,
                    },
                }
            ],
        ),
    ]

    results: list[tuple[str, bool]] = []
    for test_name, component_rows, expected in tests:
        actual = pathway_summary(build_output_rows(component_rows))
        results.append((test_name, actual == expected))
    return results


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Decomposed Appendix IV CSV not found: {INPUT_PATH}")

    input_rows = read_rows(INPUT_PATH)
    output_rows = build_output_rows(input_rows)
    write_rows(output_rows, OUTPUT_PATH)

    pathway_code_counts: dict[str, int] = {}
    expression_count = 0
    null_expression_count = 0
    for row in output_rows:
        pathway_code_counts[row.pathway_code] = pathway_code_counts.get(row.pathway_code, 0) + 1
        payload = json.loads(row.expression_json)
        if payload.get("expression") is None:
            null_expression_count += 1
        else:
            expression_count += 1

    unique_rules = {rule_group_key(row) for row in input_rows}
    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Total rules: {len(unique_rules)}")
    print(f"Total pathways: {len(output_rows)}")
    for pathway_code in sorted(pathway_code_counts):
        print(f"{pathway_code}: {pathway_code_counts[pathway_code]}")
    print(f"With expression: {expression_count}")
    print(f"Null expression: {null_expression_count}")

    for test_name, passed in validate_test_vectors():
        print(f"{test_name}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()