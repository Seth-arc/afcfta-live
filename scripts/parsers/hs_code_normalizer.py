from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_classified.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_hs_normalized.csv"

CHAPTER_RE = re.compile(r"(?i)^\s*(?:ex[\s-]*)?chapter\s+(\d{1,2})\b")
RANGE_RE = re.compile(
    r"(?i)^\s*(?:ex[\s-]*)?(\d{1,2}(?:\.\d{2}){1,2})\s*[-–]\s*(\d{1,2}(?:\.\d{2}){1,2})\s*$"
)
EX_PREFIX_RE = re.compile(r"(?i)^\s*ex[\s-]*")


@dataclass(slots=True)
class NormalizedRow:
    source: dict[str, str]
    hs_code: str
    hs_level: str
    hs_code_start: str
    hs_code_end: str
    hs_display: str
    ex_prefix_flag: bool
    confidence_score: float


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def format_hs_display(code: str) -> str:
    if len(code) == 6:
        return f"{code[:4]}.{code[4:]}"
    if len(code) == 4:
        return f"{code[:2]}.{code[2:]}"
    return code


def normalize_hs_code(raw_hs_code: str) -> tuple[str, str, str, str, str, bool, float]:
    raw = normalize_text(raw_hs_code)
    ex_prefix_flag = bool(EX_PREFIX_RE.match(raw))
    code_text = EX_PREFIX_RE.sub("", raw).strip()

    chapter_match = CHAPTER_RE.match(raw)
    if chapter_match:
        hs_code = chapter_match.group(1).zfill(2)
        return hs_code, "chapter", "", "", hs_code, ex_prefix_flag, 1.0

    range_match = RANGE_RE.match(raw)
    if range_match:
        start_digits = digits_only(range_match.group(1))
        end_digits = digits_only(range_match.group(2))
        confidence = 1.0 if len(start_digits) in {4, 6} and len(end_digits) == len(start_digits) else 0.0
        hs_level = "heading" if len(start_digits) == 4 else "subheading" if len(start_digits) == 6 else ""
        hs_display = format_hs_display(start_digits) if confidence else ""
        return start_digits, hs_level, start_digits, end_digits, hs_display, ex_prefix_flag, confidence

    clean = digits_only(code_text)
    if len(clean) == 2:
        return clean, "chapter", "", "", clean, ex_prefix_flag, 1.0
    if len(clean) == 4:
        return clean, "heading", "", "", format_hs_display(clean), ex_prefix_flag, 1.0
    if len(clean) == 6:
        return clean, "subheading", "", "", format_hs_display(clean), ex_prefix_flag, 1.0

    return clean, "", "", "", "", ex_prefix_flag, 0.0


def read_rule_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        return [row for row in reader if normalize_text(row.get("row_type")) == "rule_row"]


def build_normalized_rows(rows: list[dict[str, str]]) -> list[NormalizedRow]:
    normalized_rows: list[NormalizedRow] = []
    for row in rows:
        hs_code, hs_level, hs_code_start, hs_code_end, hs_display, ex_prefix_flag, confidence = normalize_hs_code(
            row.get("raw_hs_code", "")
        )
        normalized_rows.append(
            NormalizedRow(
                source=row,
                hs_code=hs_code,
                hs_level=hs_level,
                hs_code_start=hs_code_start,
                hs_code_end=hs_code_end,
                hs_display=hs_display,
                ex_prefix_flag=ex_prefix_flag,
                confidence_score=confidence,
            )
        )
    return normalized_rows


def write_output(rows: list[NormalizedRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "page_num",
        "raw_hs_code",
        "raw_description",
        "raw_rule_text",
        "row_type",
        "pending_flag",
        "transition_flag",
        "parent_row_index",
        "hs_code",
        "hs_level",
        "hs_code_start",
        "hs_code_end",
        "hs_display",
        "ex_prefix_flag",
        "confidence_score",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = dict(row.source)
            payload.update(
                {
                    "hs_code": row.hs_code,
                    "hs_level": row.hs_level,
                    "hs_code_start": row.hs_code_start,
                    "hs_code_end": row.hs_code_end,
                    "hs_display": row.hs_display,
                    "ex_prefix_flag": row.ex_prefix_flag,
                    "confidence_score": row.confidence_score,
                }
            )
            writer.writerow(payload)


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Classified Appendix IV CSV not found: {INPUT_PATH}")

    input_rows = read_rule_rows(INPUT_PATH)
    normalized_rows = build_normalized_rows(input_rows)
    write_output(normalized_rows, OUTPUT_PATH)

    level_counts = {"chapter": 0, "heading": 0, "subheading": 0}
    ranges_found = 0
    ex_prefixed = 0
    failed = 0

    for row in normalized_rows:
        if row.hs_level in level_counts:
            level_counts[row.hs_level] += 1
        if row.hs_code_start and row.hs_code_end:
            ranges_found += 1
        if row.ex_prefix_flag:
            ex_prefixed += 1
        if row.confidence_score == 0.0:
            failed += 1

    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Total rules: {len(normalized_rows)}")
    print(f"Chapter rules: {level_counts['chapter']}")
    print(f"Heading rules: {level_counts['heading']}")
    print(f"Subheading rules: {level_counts['subheading']}")
    print(f"Ranges found: {ranges_found}")
    print(f"Ex-prefixed: {ex_prefixed}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()