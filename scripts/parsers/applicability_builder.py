from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
RULES_INPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_pathways.csv"
HS6_INPUT_PATH = ROOT_DIR / "data" / "staged" / "hs6_product.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "processed" / "rules" / "appendix_iv_applicability.csv"

OUTPUT_FIELDNAMES = [
    "hs6_code",
    "hs6_id",
    "psr_hs_code",
    "applicability_type",
    "priority_rank",
]


@dataclass(slots=True)
class RuleRecord:
    hs_code: str
    hs_level: str
    page_ref: str
    legal_rule_text_verbatim: str
    hs_code_start: str = ""
    hs_code_end: str = ""


@dataclass(slots=True)
class ApplicabilityRow:
    hs6_code: str
    hs6_id: str
    psr_hs_code: str
    applicability_type: str
    priority_rank: int


def read_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_rows(rows: list[ApplicabilityRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "hs6_code": row.hs6_code,
                    "hs6_id": row.hs6_id,
                    "psr_hs_code": row.psr_hs_code,
                    "applicability_type": row.applicability_type,
                    "priority_rank": row.priority_rank,
                }
            )


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def rule_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("hs_code", ""),
        row.get("hs_level", ""),
        row.get("page_ref", ""),
        row.get("legal_rule_text_verbatim", ""),
    )


def build_rule_records(pathway_rows: list[dict[str, str]]) -> list[RuleRecord]:
    seen: set[tuple[str, str, str, str]] = set()
    rules: list[RuleRecord] = []
    for row in pathway_rows:
        key = rule_key(row)
        if key in seen:
            continue
        seen.add(key)
        rules.append(
            RuleRecord(
                hs_code=normalize_text(row.get("hs_code")),
                hs_level=normalize_text(row.get("hs_level")),
                page_ref=normalize_text(row.get("page_ref")),
                legal_rule_text_verbatim=normalize_text(row.get("legal_rule_text_verbatim")),
            )
        )
    return rules


def index_rules(rules: list[RuleRecord]) -> tuple[dict[str, RuleRecord], dict[str, RuleRecord], dict[str, RuleRecord], list[RuleRecord]]:
    subheading_rules: dict[str, RuleRecord] = {}
    heading_rules: dict[str, RuleRecord] = {}
    chapter_rules: dict[str, RuleRecord] = {}
    range_rules: list[RuleRecord] = []

    for rule in rules:
        if rule.hs_level == "subheading" and rule.hs_code and rule.hs_code not in subheading_rules:
            subheading_rules[rule.hs_code] = rule
        elif rule.hs_level == "heading" and rule.hs_code and rule.hs_code not in heading_rules:
            heading_rules[rule.hs_code] = rule
        elif rule.hs_level == "chapter" and rule.hs_code and rule.hs_code not in chapter_rules:
            chapter_rules[rule.hs_code] = rule

        if rule.hs_code_start and rule.hs_code_end:
            range_rules.append(rule)

    return subheading_rules, heading_rules, chapter_rules, range_rules


def build_applicability_rows(pathway_rows: list[dict[str, str]], hs6_rows: list[dict[str, str]]) -> tuple[list[ApplicabilityRow], dict[str, int]]:
    rules = build_rule_records(pathway_rows)
    subheading_rules, heading_rules, chapter_rules, range_rules = index_rules(rules)

    applicability_rows: list[ApplicabilityRow] = []
    no_coverage = 0
    duplicates_collapsed = 0

    for product in hs6_rows:
        hs6_code = normalize_text(product.get("hs6_code"))
        hs6_id = normalize_text(product.get("hs6_id"))
        heading = hs6_code[:4]
        chapter = hs6_code[:2]

        matched_rule: RuleRecord | None = None
        applicability_type = ""
        priority_rank = 0

        if hs6_code in subheading_rules:
            matched_rule = subheading_rules[hs6_code]
            applicability_type = "direct"
            priority_rank = 1
        else:
            for rule in range_rules:
                if rule.hs_code_start <= hs6_code <= rule.hs_code_end:
                    matched_rule = rule
                    applicability_type = "range"
                    priority_rank = 1
                    break

        if matched_rule is None and heading in heading_rules:
            matched_rule = heading_rules[heading]
            applicability_type = "inherited_heading"
            priority_rank = 2

        if matched_rule is None and chapter in chapter_rules:
            matched_rule = chapter_rules[chapter]
            applicability_type = "inherited_chapter"
            priority_rank = 3

        if matched_rule is None:
            no_coverage += 1
            continue

        row = ApplicabilityRow(
            hs6_code=hs6_code,
            hs6_id=hs6_id,
            psr_hs_code=matched_rule.hs_code,
            applicability_type=applicability_type,
            priority_rank=priority_rank,
        )
        applicability_rows.append(row)

    deduped_rows: list[ApplicabilityRow] = []
    seen_output_keys: set[tuple[str, str, str, str, int]] = set()
    for row in applicability_rows:
        key = (row.hs6_code, row.hs6_id, row.psr_hs_code, row.applicability_type, row.priority_rank)
        if key in seen_output_keys:
            duplicates_collapsed += 1
            continue
        seen_output_keys.add(key)
        deduped_rows.append(row)

    stats = {
        "total_rules": len(rules),
        "range_rules": len(range_rules),
        "no_coverage": no_coverage,
        "duplicates_collapsed": duplicates_collapsed,
    }
    return deduped_rows, stats


def applicability_summary(rows: list[ApplicabilityRow]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.applicability_type] += 1
    return dict(counts)


def validate_test_vector_8() -> bool:
    pathway_rows = [
        {
            "hs_code": "01",
            "hs_level": "chapter",
            "page_ref": "1",
            "legal_rule_text_verbatim": "WO",
        },
        {
            "hs_code": "0301",
            "hs_level": "heading",
            "page_ref": "2",
            "legal_rule_text_verbatim": "CTH",
        },
        {
            "hs_code": "030111",
            "hs_level": "subheading",
            "page_ref": "3",
            "legal_rule_text_verbatim": "CTSH",
        },
    ]
    hs6_rows = [
        {"hs6_id": "1", "hs6_code": "010111"},
        {"hs6_id": "2", "hs6_code": "010121"},
        {"hs6_id": "3", "hs6_code": "030111"},
        {"hs6_id": "4", "hs6_code": "030119"},
        {"hs6_id": "5", "hs6_code": "030211"},
    ]
    actual_rows, _ = build_applicability_rows(pathway_rows, hs6_rows)
    actual = [
        {
            "hs6_code": row.hs6_code,
            "psr_hs_code": row.psr_hs_code,
            "applicability_type": row.applicability_type,
            "priority_rank": row.priority_rank,
        }
        for row in actual_rows
    ]
    expected = [
        {"hs6_code": "010111", "psr_hs_code": "01", "applicability_type": "inherited_chapter", "priority_rank": 3},
        {"hs6_code": "010121", "psr_hs_code": "01", "applicability_type": "inherited_chapter", "priority_rank": 3},
        {"hs6_code": "030111", "psr_hs_code": "030111", "applicability_type": "direct", "priority_rank": 1},
        {"hs6_code": "030119", "psr_hs_code": "0301", "applicability_type": "inherited_heading", "priority_rank": 2},
    ]
    return actual == expected and all(row["hs6_code"] != "030211" for row in actual)


def main() -> None:
    if not RULES_INPUT_PATH.exists():
        raise FileNotFoundError(f"Pathways CSV not found: {RULES_INPUT_PATH}")
    if not HS6_INPUT_PATH.exists():
        raise FileNotFoundError(f"HS6 backbone CSV not found: {HS6_INPUT_PATH}")

    pathway_rows = read_rows(RULES_INPUT_PATH)
    hs6_rows = read_rows(HS6_INPUT_PATH)
    applicability_rows, builder_stats = build_applicability_rows(pathway_rows, hs6_rows)
    write_rows(applicability_rows, OUTPUT_PATH)

    coverage_counts = applicability_summary(applicability_rows)
    total_hs6 = len(hs6_rows)
    covered_hs6 = len(applicability_rows)
    uncovered_hs6 = total_hs6 - covered_hs6
    coverage_percent = (covered_hs6 / total_hs6 * 100) if total_hs6 else 0.0

    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Total HS6 codes in backbone: {total_hs6}")
    print(f"HS6 codes with PSR coverage: {covered_hs6}")
    print(f"HS6 codes with NO coverage: {uncovered_hs6}")
    for applicability_type in sorted(coverage_counts):
        print(f"{applicability_type}: {coverage_counts[applicability_type]}")
    print(f"Coverage percentage: {coverage_percent:.2f}%")
    print(f"Range rules detected: {builder_stats['range_rules']}")
    if builder_stats["duplicates_collapsed"]:
        print(f"Duplicate applicability rows collapsed: {builder_stats['duplicates_collapsed']}")
    print(f"Test Vector 8: {'PASS' if validate_test_vector_8() else 'FAIL'}")


if __name__ == "__main__":
    main()