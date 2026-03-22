from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_hs_normalized.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_decomposed.csv"

WO_RE = re.compile(r"(?i)^(WO|wholly\s+obtained)\b")
WHOLE_OBTAINED_RE = re.compile(r"(?i)\bwholly\s+obtained\b")
CTH_RE = re.compile(r"(?i)^CTH(?:\b|\s)")
CTSH_RE = re.compile(r"(?i)^CTSH(?:\b|\s)")
CC_RE = re.compile(r"(?i)^CC(?:\b|\s)")
CTH_TEXT_RE = re.compile(
    r"(?i)(?:materials?\s+)?(?:classified\s+in\s+a\s+|of\s+any\s+|from\s+any\s+|any\s+other\s+)?heading"
    r"(?:s)?(?:\s+other\s+than\s+that\s+of\s+the\s+product|\s+other\s+that\s+of\s+the\s+product|"
    r"\s*,?\s*except\s+that\s+of\s+the\s+product|\s+except\s+that\s+of\s+the\s+product)"
)
CTSH_TEXT_RE = re.compile(
    r"(?i)(?:materials?\s+)?(?:classified\s+in\s+a\s+|of\s+any\s+|from\s+any\s+|any\s+other\s+)?sub[\s-]?heading"
    r"(?:s)?(?:\s+other\s+than\s+that\s+of\s+the\s+product|\s+other\s+that\s+of\s+the\s+product|"
    r"\s*,?\s*except\s+that\s+of\s+the\s+product|\s+except\s+that\s+of\s+the\s+product)"
)
CC_TEXT_RE = re.compile(
    r"(?i)(?:materials?\s+)?(?:classified\s+in\s+a\s+|of\s+any\s+|from\s+any\s+|any\s+other\s+)?chapter"
    r"(?:s)?(?:\s+other\s+than\s+that\s+of\s+the\s+product|\s+other\s+that\s+of\s+the\s+product|"
    r"\s*,?\s*except\s+that\s+of\s+the\s+product|\s+except\s+that\s+of\s+the\s+product)"
)
EXCEPTION_RE = re.compile(r"(?i)(except\s+from\s+.*)$")
VNM_RE = re.compile(
    r"(?i)(?:maxnom|vnm|max(?:imum)?\s+non[\s-]?originating(?:\s+materials?)?(?:\s+content)?)\s*"
    r"(\d+(?:\.\d+)?)\s*%"
    r"(?:\s*\(?\s*(EXW|FOB|CIF)\s*\)?)?"
)
VNM_TEXT_RE = re.compile(
    r"(?i)value\s+of\s+(?:(?:all\s+the|the)\s+)?(?:non[\s-]?originating\s+)?materials?\s+used\s+d\s*o(?:e)?s\s+not\s+exceed\s+"
    r"(\d+(?:\.\d+)?)\s*%\s*.*?(ex-works|ex works|ex-work|ex work|EXW|FOB|CIF)"
)
VA_RE = re.compile(
    r"(?i)(?:RVC|MinLVC|VA|min(?:imum)?\s+(?:local|regional|value[\s-]?added)(?:\s+content)?)\s*"
    r"(\d+(?:\.\d+)?)\s*%"
    r"(?:\s*\(?\s*(EXW|FOB)\s*\)?)?"
)
VA_TEXT_RE = re.compile(
    r"(?i)(?:minimum\s+.*?value\s+added|regional\s+value\s+content).*?(\d+(?:\.\d+)?)\s*%.*?(ex-works|ex works|EXW|FOB)?"
)
PROCESS_RE = re.compile(r"(?i)^(manufacture|processing|production)\s+from\s+")
PROCESS_TEXT_RE = re.compile(
    r"(?i)^(operations?\s+of\s+refining|retreading\b|printing\s+accompanied\s+by|carding\s+or\s+combing|spinning\b|manufacture\s+by\b)"
)
PENDING_RE = re.compile(r"(?i)yet\s+to\s+be\s+agreed")
RULE_START_RE = re.compile(
    r"(?i)^\s*(?:CTH|CTSH|CC|WO|MaxNOM|VNM|RVC|MinLVC|VA|"
    r"Manufacture\s+(?:from|in\s+which)|Processing\s+from|Production\s+from|"
    r"Wholly\s+obtained|minimum\s+.*?value\s+added|value\s+of\s+.*?non[\s-]?originating)"
)


@dataclass(slots=True)
class RuleComponent:
    component_type: str
    operator_type: str
    threshold_percent: float | None = None
    threshold_basis: str | None = None
    tariff_shift_level: str | None = None
    specific_process_text: str | None = None
    normalized_expression: str | None = None
    confidence_score: float = 0.0
    component_order: int = 1


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def map_basis(raw_basis: str | None) -> str | None:
    if not raw_basis:
        return "ex_works"
    basis = raw_basis.upper().replace("-", " ").strip()
    return {
        "EXW": "ex_works",
        "EX WORKS": "ex_works",
        "FOB": "fob",
        "CIF": "customs_value",
    }.get(basis, "ex_works")


def looks_like_rule_fragment(text: str) -> bool:
    return bool(RULE_START_RE.match(normalize_text(text)))


def split_by_connector(text: str, connector_pattern: re.Pattern[str]) -> list[str]:
    matches = list(connector_pattern.finditer(text))
    if not matches:
        return [text.strip()]

    parts: list[str] = []
    last_index = 0
    for match in matches:
        left = text[last_index:match.start()].strip()
        right = text[match.end():].strip()
        if not left or not right or not looks_like_rule_fragment(right):
            continue
        parts.append(left)
        last_index = match.end()

    if parts:
        tail = text[last_index:].strip()
        if tail:
            parts.append(tail)
        return parts

    return [text.strip()]


def split_on_or(text: str) -> list[str]:
    except_match = re.search(r"(?i)except\s+from", text)
    if except_match:
        before_except = text[:except_match.start()]
        if re.search(r"\s+or\s+", before_except, flags=re.IGNORECASE):
            return [text.strip()]

    parts = split_by_connector(text, re.compile(r";\s*or\s+", re.IGNORECASE))
    if len(parts) > 1:
        return parts

    parts = split_by_connector(text, re.compile(r"\s+or\s+", re.IGNORECASE))
    if len(parts) > 1:
        return parts

    return split_by_connector(text, re.compile(r";"))


def split_on_and(text: str) -> list[str]:
    return split_by_connector(text, re.compile(r"\s+and\s+", re.IGNORECASE))


def parse_single_rule(text: str) -> RuleComponent:
    rule_text = normalize_text(text)
    rule_text = re.sub(r"(?i)^;+\s*", "", rule_text)
    rule_text = re.sub(r"(?i)^m\s+manufacture", "Manufacture", rule_text)
    rule_text = re.sub(r"(?i)\bd\s+oes\b", "does", rule_text)
    rule_text = re.sub(r"(?i)\bd\s+does\b", "does", rule_text)
    rule_text = re.sub(r"(?i)\bex[-\s]?work\b", "ex-works", rule_text)

    if PENDING_RE.search(rule_text):
        return RuleComponent(
            component_type="NOTE",
            operator_type="standalone",
            specific_process_text=rule_text,
            normalized_expression=None,
            confidence_score=0.0,
        )

    if WO_RE.match(rule_text):
        return RuleComponent(
            component_type="WO",
            operator_type="standalone",
            normalized_expression="wholly_obtained == true",
            confidence_score=1.0,
        )

    if CTH_RE.match(rule_text) or CTH_TEXT_RE.search(rule_text):
        exception_match = EXCEPTION_RE.search(rule_text)
        exception_text = exception_match.group(1).strip() if exception_match else None
        normalized_expression = "heading_ne_output"
        if exception_text:
            normalized_expression = f"heading_ne_output except {exception_text}"
        return RuleComponent(
            component_type="CTH",
            operator_type="standalone",
            tariff_shift_level="heading",
            specific_process_text=exception_text,
            normalized_expression=normalized_expression,
            confidence_score=1.0,
        )

    if CTSH_RE.match(rule_text) or CTSH_TEXT_RE.search(rule_text):
        return RuleComponent(
            component_type="CTSH",
            operator_type="standalone",
            tariff_shift_level="subheading",
            normalized_expression="subheading_ne_output",
            confidence_score=1.0,
        )

    if CC_RE.match(rule_text) or CC_TEXT_RE.search(rule_text):
        return RuleComponent(
            component_type="CC",
            operator_type="standalone",
            tariff_shift_level="chapter",
            normalized_expression="chapter_ne_output",
            confidence_score=1.0,
        )

    vnm_match = VNM_RE.search(rule_text)
    if not vnm_match:
        vnm_match = VNM_TEXT_RE.search(rule_text)
    if vnm_match:
        threshold = float(vnm_match.group(1))
        basis = map_basis(vnm_match.group(2) if len(vnm_match.groups()) > 1 else None)
        return RuleComponent(
            component_type="VNM",
            operator_type="standalone",
            threshold_percent=threshold,
            threshold_basis=basis,
            normalized_expression=f"vnom_percent <= {threshold:g}",
            confidence_score=1.0,
        )

    va_match = VA_RE.search(rule_text)
    if not va_match:
        va_match = VA_TEXT_RE.search(rule_text)
    if va_match:
        threshold = float(va_match.group(1))
        basis = map_basis(va_match.group(2) if len(va_match.groups()) > 1 else None)
        return RuleComponent(
            component_type="VA",
            operator_type="standalone",
            threshold_percent=threshold,
            threshold_basis=basis,
            normalized_expression=f"va_percent >= {threshold:g}",
            confidence_score=1.0,
        )

    if WHOLE_OBTAINED_RE.search(rule_text):
        return RuleComponent(
            component_type="WO",
            operator_type="standalone",
            normalized_expression="wholly_obtained == true",
            confidence_score=1.0,
        )

    if PROCESS_RE.match(rule_text) or PROCESS_TEXT_RE.match(rule_text):
        return RuleComponent(
            component_type="PROCESS",
            operator_type="standalone",
            specific_process_text=rule_text,
            normalized_expression=None,
            confidence_score=0.5,
        )

    return RuleComponent(
        component_type="NOTE",
        operator_type="standalone",
        specific_process_text=rule_text,
        normalized_expression=None,
        confidence_score=0.0,
    )


def decompose_rule_text(rule_text: str) -> list[RuleComponent]:
    text = normalize_text(rule_text)
    if not text:
        return [
            RuleComponent(
                component_type="NOTE",
                operator_type="standalone",
                specific_process_text="",
                normalized_expression=None,
                confidence_score=0.0,
                component_order=1,
            )
        ]

    components: list[RuleComponent] = []
    or_parts = split_on_or(text)

    for or_index, or_part in enumerate(or_parts):
        and_parts = split_on_and(or_part)
        for and_index, and_part in enumerate(and_parts):
            component = parse_single_rule(and_part)
            if or_index > 0 and and_index == 0:
                component.operator_type = "or"
            elif and_index > 0:
                component.operator_type = "and"
            else:
                component.operator_type = "standalone"
            component.component_order = len(components) + 1
            components.append(component)

    return components


def read_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_output(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_output_rows(input_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    for row in input_rows:
        components = decompose_rule_text(row.get("raw_rule_text", ""))
        for component in components:
            output_row = dict(row)
            output_row.update(
                {
                    "component_order": component.component_order,
                    "component_type": component.component_type,
                    "operator_type": component.operator_type,
                    "threshold_percent": "" if component.threshold_percent is None else component.threshold_percent,
                    "threshold_basis": "" if component.threshold_basis is None else component.threshold_basis,
                    "tariff_shift_level": "" if component.tariff_shift_level is None else component.tariff_shift_level,
                    "specific_process_text": "" if component.specific_process_text is None else component.specific_process_text,
                    "normalized_expression": "" if component.normalized_expression is None else component.normalized_expression,
                    "confidence_score": component.confidence_score,
                }
            )
            output_rows.append(output_row)
    return output_rows


def _component_summary(components: list[RuleComponent]) -> list[dict[str, object]]:
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


def validate_test_vectors() -> list[tuple[str, bool]]:
    tests: list[tuple[str, str, list[dict[str, object]]]] = [
        (
            "Test Vector 1",
            "WO",
            [
                {
                    "component_type": "WO",
                    "operator_type": "standalone",
                    "threshold_percent": None,
                    "threshold_basis": None,
                    "tariff_shift_level": None,
                    "specific_process_text": None,
                    "normalized_expression": "wholly_obtained == true",
                    "confidence_score": 1.0,
                    "component_order": 1,
                }
            ],
        ),
        (
            "Test Vector 2",
            "CTH",
            [
                {
                    "component_type": "CTH",
                    "operator_type": "standalone",
                    "threshold_percent": None,
                    "threshold_basis": None,
                    "tariff_shift_level": "heading",
                    "specific_process_text": None,
                    "normalized_expression": "heading_ne_output",
                    "confidence_score": 1.0,
                    "component_order": 1,
                }
            ],
        ),
        (
            "Test Vector 3",
            "MaxNOM 55% (EXW)",
            [
                {
                    "component_type": "VNM",
                    "operator_type": "standalone",
                    "threshold_percent": 55.0,
                    "threshold_basis": "ex_works",
                    "tariff_shift_level": None,
                    "specific_process_text": None,
                    "normalized_expression": "vnom_percent <= 55",
                    "confidence_score": 1.0,
                    "component_order": 1,
                }
            ],
        ),
        (
            "Test Vector 4",
            "CTH; or MaxNOM 55% (EXW)",
            [
                {
                    "component_type": "CTH",
                    "operator_type": "standalone",
                    "threshold_percent": None,
                    "threshold_basis": None,
                    "tariff_shift_level": "heading",
                    "specific_process_text": None,
                    "normalized_expression": "heading_ne_output",
                    "confidence_score": 1.0,
                    "component_order": 1,
                },
                {
                    "component_type": "VNM",
                    "operator_type": "or",
                    "threshold_percent": 55.0,
                    "threshold_basis": "ex_works",
                    "tariff_shift_level": None,
                    "specific_process_text": None,
                    "normalized_expression": "vnom_percent <= 55",
                    "confidence_score": 1.0,
                    "component_order": 2,
                },
            ],
        ),
        (
            "Test Vector 5",
            "CTH and MaxNOM 50% (EXW)",
            [
                {
                    "component_type": "CTH",
                    "operator_type": "standalone",
                    "threshold_percent": None,
                    "threshold_basis": None,
                    "tariff_shift_level": "heading",
                    "specific_process_text": None,
                    "normalized_expression": "heading_ne_output",
                    "confidence_score": 1.0,
                    "component_order": 1,
                },
                {
                    "component_type": "VNM",
                    "operator_type": "and",
                    "threshold_percent": 50.0,
                    "threshold_basis": "ex_works",
                    "tariff_shift_level": None,
                    "specific_process_text": None,
                    "normalized_expression": "vnom_percent <= 50",
                    "confidence_score": 1.0,
                    "component_order": 2,
                },
            ],
        ),
        (
            "Test Vector 6",
            "CTH except from heading 10.06",
            [
                {
                    "component_type": "CTH",
                    "operator_type": "standalone",
                    "threshold_percent": None,
                    "threshold_basis": None,
                    "tariff_shift_level": "heading",
                    "specific_process_text": "except from heading 10.06",
                    "normalized_expression": "heading_ne_output except except from heading 10.06",
                    "confidence_score": 1.0,
                    "component_order": 1,
                }
            ],
        ),
        (
            "Test Vector 7",
            "Manufacture from chemical materials of any heading",
            [
                {
                    "component_type": "PROCESS",
                    "operator_type": "standalone",
                    "threshold_percent": None,
                    "threshold_basis": None,
                    "tariff_shift_level": None,
                    "specific_process_text": "Manufacture from chemical materials of any heading",
                    "normalized_expression": None,
                    "confidence_score": 0.5,
                    "component_order": 1,
                }
            ],
        ),
    ]

    results: list[tuple[str, bool]] = []
    for test_name, input_text, expected in tests:
        actual = _component_summary(decompose_rule_text(input_text))
        results.append((test_name, actual == expected))
    return results


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Normalized Appendix IV CSV not found: {INPUT_PATH}")

    input_rows = read_rows(INPUT_PATH)
    output_rows = build_output_rows(input_rows)
    write_output(output_rows, OUTPUT_PATH)

    total_rules_processed = len(input_rows)
    component_type_counts: dict[str, int] = {}
    or_alternatives = 0
    and_combinations = 0
    low_confidence = 0
    zero_confidence = 0

    for row in output_rows:
        component_type = row["component_type"]
        component_type_counts[component_type] = component_type_counts.get(component_type, 0) + 1
        if row["operator_type"] == "or":
            or_alternatives += 1
        if row["operator_type"] == "and":
            and_combinations += 1
        confidence = float(row["confidence_score"])
        if confidence < 1.0:
            low_confidence += 1
        if confidence == 0.0:
            zero_confidence += 1

    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Total rules processed: {total_rules_processed}")
    for component_type in sorted(component_type_counts):
        print(f"{component_type}: {component_type_counts[component_type]}")
    print(f"OR alternatives: {or_alternatives}")
    print(f"AND combinations: {and_combinations}")
    print(f"Low confidence (< 1.0): {low_confidence}")
    print(f"Zero confidence: {zero_confidence}")

    for test_name, passed in validate_test_vectors():
        print(f"{test_name}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()