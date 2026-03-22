from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT_DIR / "data" / "staged" / "extracted_tables" / "appendix_iv_raw.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "staged" / "raw_csv" / "appendix_iv_classified.csv"

SECTION_HEADER_RE = re.compile(r"(?i)^\s*section\s+[ivxlcdm0-9]+\b")
CHAPTER_HEADER_RE = re.compile(r"(?i)^\s*(?:ex[\s-]*)?chapter\s+\d{1,2}\b")
FOOTNOTE_RE = re.compile(r"^\s*\(?\d{1,3}\)?[.)\-:]?\s+\S")
PENDING_PATTERNS = (
    re.compile(r"(?i)\byet\s+to\s+be\s+agreed\b"),
    re.compile(r"(?i)\bto\s+be\s+agreed\b"),
    re.compile(r"(?i)\bnot\s+yet\s+agreed\b"),
    re.compile(r"(?i)\bpending\b"),
)
TRANSITION_PATTERNS = (
    re.compile(r"(?i)\bfor\s+\d+\s+years?\b"),
    re.compile(r"(?i)\bfor\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+years?\b"),
    re.compile(r"(?i)\bafter\s+which\b"),
    re.compile(r"(?i)\bsubject\s+to\s+(?:an\s+objective\s+)?review\b"),
    re.compile(r"(?i)\breview\s+after\s+\w+\s+years?\b"),
)


@dataclass(slots=True)
class ClassifiedRow:
    page_num: str
    source_row_index: str
    raw_hs_code: str
    raw_description: str
    raw_rule_text: str
    row_type: str
    pending_flag: bool
    transition_flag: bool
    parent_row_index: str


def normalize_text(value: str | None) -> str:
    text = str(value or "")
    text = text.replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def collapse_text(*parts: str) -> str:
    return " ".join(part for part in (normalize_text(part) for part in parts) if part).strip()


def has_hs_reference(raw_hs_code: str) -> bool:
    text = normalize_text(raw_hs_code)
    if not text:
        return False

    if SECTION_HEADER_RE.match(text) or CHAPTER_HEADER_RE.match(text):
        return True

    cleaned = re.sub(r"(?i)^ex[\s-]*", "", text)
    cleaned = re.sub(r"(?i)^chapter\s+", "", cleaned)
    cleaned = re.sub(r"[.\s\-–]", "", cleaned)
    return cleaned.isdigit() and len(cleaned) in {2, 4, 6, 8, 12}


def is_note_row(raw_hs_code: str, raw_description: str, raw_rule_text: str) -> bool:
    hs_text = normalize_text(raw_hs_code)
    combined = collapse_text(raw_hs_code, raw_description, raw_rule_text)
    if hs_text:
        return False
    return bool(FOOTNOTE_RE.match(combined)) or combined.lower().startswith(("note", "notes", "n.b.", "nb"))


def detect_pending_flag(rule_text: str) -> bool:
    text = normalize_text(rule_text)
    return any(pattern.search(text) for pattern in PENDING_PATTERNS)


def detect_transition_flag(rule_text: str) -> bool:
    text = normalize_text(rule_text)
    return any(pattern.search(text) for pattern in TRANSITION_PATTERNS)


def classify_extracted_row(row: dict[str, str]) -> ClassifiedRow:
    page_num = str(row.get("page_num", "")).strip()
    source_row_index = str(row.get("row_index", "")).strip()
    raw_hs_code = normalize_text(row.get("raw_hs_code"))
    raw_description = normalize_text(row.get("raw_description"))
    raw_rule_text = normalize_text(row.get("raw_rule_text"))
    extracted_row_type = normalize_text(row.get("row_type")).lower()
    combined_text = collapse_text(raw_hs_code, raw_description, raw_rule_text)

    if not combined_text:
        row_type = "skip"
    elif extracted_row_type == "note" or is_note_row(raw_hs_code, raw_description, raw_rule_text):
        row_type = "note"
    elif SECTION_HEADER_RE.match(raw_hs_code) or SECTION_HEADER_RE.match(raw_description):
        row_type = "section_header"
    elif extracted_row_type == "header" or CHAPTER_HEADER_RE.match(raw_hs_code) or CHAPTER_HEADER_RE.match(raw_description):
        row_type = "chapter_header"
    elif not raw_hs_code and collapse_text(raw_description, raw_rule_text):
        row_type = "continuation"
    elif has_hs_reference(raw_hs_code) and raw_rule_text:
        row_type = "rule_row"
    else:
        row_type = "skip"

    rule_text_for_flags = raw_rule_text
    if row_type == "continuation" and not rule_text_for_flags:
        rule_text_for_flags = raw_description

    pending_flag = row_type in {"rule_row", "continuation"} and detect_pending_flag(rule_text_for_flags)
    transition_flag = row_type in {"rule_row", "continuation"} and detect_transition_flag(rule_text_for_flags)

    return ClassifiedRow(
        page_num=page_num,
        source_row_index=source_row_index,
        raw_hs_code=raw_hs_code,
        raw_description=raw_description,
        raw_rule_text=raw_rule_text,
        row_type=row_type,
        pending_flag=pending_flag,
        transition_flag=transition_flag,
        parent_row_index="",
    )


def merge_continuations(rows: list[ClassifiedRow]) -> int:
    last_rule_row: ClassifiedRow | None = None
    continuations_merged = 0

    for row in rows:
        if row.row_type == "rule_row":
            last_rule_row = row
            continue

        if row.row_type != "continuation":
            continue

        if last_rule_row is None:
            row.row_type = "skip"
            row.pending_flag = False
            row.transition_flag = False
            continue

        continuation_text = collapse_text(row.raw_rule_text, row.raw_description)
        if continuation_text:
            last_rule_row.raw_rule_text = collapse_text(last_rule_row.raw_rule_text, continuation_text)

        last_rule_row.pending_flag = last_rule_row.pending_flag or row.pending_flag
        last_rule_row.transition_flag = last_rule_row.transition_flag or row.transition_flag
        row.parent_row_index = last_rule_row.source_row_index
        continuations_merged += 1

    return continuations_merged


def write_output(rows: list[ClassifiedRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "page_num",
                "raw_hs_code",
                "raw_description",
                "raw_rule_text",
                "row_type",
                "pending_flag",
                "transition_flag",
                "parent_row_index",
            ],
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "page_num": row.page_num,
                    "raw_hs_code": row.raw_hs_code,
                    "raw_description": row.raw_description,
                    "raw_rule_text": row.raw_rule_text,
                    "row_type": row.row_type,
                    "pending_flag": row.pending_flag,
                    "transition_flag": row.transition_flag,
                    "parent_row_index": row.parent_row_index,
                }
            )


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Raw extractor output not found: {INPUT_PATH}")

    with INPUT_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        input_rows = list(csv.DictReader(csv_file))

    classified_rows = [classify_extracted_row(row) for row in input_rows]
    continuations_merged = merge_continuations(classified_rows)
    write_output(classified_rows, OUTPUT_PATH)

    rule_rows = sum(1 for row in classified_rows if row.row_type == "rule_row")
    pending_rules = sum(1 for row in classified_rows if row.row_type == "rule_row" and row.pending_flag)
    transition_rules = sum(
        1 for row in classified_rows if row.row_type == "rule_row" and row.transition_flag
    )
    skipped_rows = sum(1 for row in classified_rows if row.row_type == "skip")

    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Total rows processed: {len(classified_rows)}")
    print(f"Rule rows: {rule_rows}")
    print(f"Continuations merged: {continuations_merged}")
    print(f"Pending rules: {pending_rules}")
    print(f"Transition rules: {transition_rules}")
    print(f"Skipped rows: {skipped_rows}")


if __name__ == "__main__":
    main()