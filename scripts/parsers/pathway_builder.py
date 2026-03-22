from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


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