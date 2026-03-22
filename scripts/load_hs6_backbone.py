"""Load HS2017 HS6 backbone rows from WCO HS nomenclature CSV.

Input:
- docs/corpus/06_reference_data/hs2017/hscodes.csv

Output:
- data/staged/hs6_product.csv
"""

import csv
import re
import sys
import uuid
from pathlib import Path

INPUT_CSV = Path("docs/corpus/06_reference_data/hs2017/hscodes.csv")
OUTPUT_CSV = Path("data/staged/hs6_product.csv")
HS_VERSION = "HS2017"

OUTPUT_COLUMNS = [
    "hs6_id",
    "hs_version",
    "hs6_code",
    "hs6_display",
    "chapter",
    "heading",
    "description",
]

TRAILING_ANGLE_REF_RE = re.compile(r"(?:\s*<[^<>]*>\s*)+$")
LEADING_ASTERISK_RE = re.compile(r"^\*+")


def clean_description(raw_description: str) -> str:
    """Return the cleaned terminal description segment for a HS line."""
    text = (raw_description or "").strip()

    if ":" in text:
        text = text.rsplit(":", 1)[-1].strip()

    text = LEADING_ASTERISK_RE.sub("", text).strip()
    text = TRAILING_ANGLE_REF_RE.sub("", text).strip()

    return text


def chapter_is_valid(chapter: str) -> bool:
    """Validate chapter is numeric and inside the HS goods range 01-97."""
    if not chapter.isdigit() or len(chapter) != 2:
        return False

    chapter_num = int(chapter)
    return 1 <= chapter_num <= 97


def load_hs6_rows(input_csv_path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Read source CSV and return first-seen unique HS6 rows and counters."""
    seen_hs6_codes: set[str] = set()
    rows_by_hs6: dict[str, dict[str, str]] = {}

    total_rows = 0
    duplicate_rows = 0
    invalid_source_rows = 0

    with input_csv_path.open("r", newline="", encoding="utf-8-sig") as src:
        reader = csv.DictReader(src)

        if not reader.fieldnames:
            raise ValueError("Input CSV has no header row")

        headers = {name.strip() for name in reader.fieldnames if name}
        required_headers = {"hscode", "description"}
        if not required_headers.issubset(headers):
            raise ValueError(
                "Input CSV must contain 'hscode' and 'description' columns"
            )

        for record in reader:
            total_rows += 1

            hscode_raw = (record.get("hscode") or "").strip()
            if len(hscode_raw) < 6:
                invalid_source_rows += 1
                continue

            hs6_code = hscode_raw[:6]
            if len(hs6_code) != 6 or not hs6_code.isdigit():
                invalid_source_rows += 1
                continue

            if hs6_code in seen_hs6_codes:
                duplicate_rows += 1
                continue

            description = clean_description(record.get("description") or "")
            chapter = hs6_code[:2]
            heading = hs6_code[:4]

            rows_by_hs6[hs6_code] = {
                "hs6_id": str(uuid.uuid4()),
                "hs_version": HS_VERSION,
                "hs6_code": hs6_code,
                "hs6_display": f"{heading}.{hs6_code[4:]}",
                "chapter": chapter,
                "heading": heading,
                "description": description,
            }
            seen_hs6_codes.add(hs6_code)

    rows = sorted(rows_by_hs6.values(), key=lambda row: row["hs6_code"])

    counters = {
        "total_rows": total_rows,
        "unique_hs6": len(rows),
        "duplicate_rows": duplicate_rows,
        "invalid_source_rows": invalid_source_rows,
    }
    return rows, counters


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    """Validate generated rows and return a list of validation errors."""
    errors: list[str] = []

    seen_codes: set[str] = set()
    for idx, row in enumerate(rows, start=1):
        hs6_code = row.get("hs6_code", "")
        chapter = row.get("chapter", "")

        if len(hs6_code) != 6 or not hs6_code.isdigit():
            errors.append(
                f"Row {idx}: hs6_code '{hs6_code}' must be exactly 6 numeric digits"
            )

        if hs6_code in seen_codes:
            errors.append(f"Row {idx}: duplicate hs6_code '{hs6_code}'")
        seen_codes.add(hs6_code)

        if not chapter_is_valid(chapter):
            errors.append(
                f"Row {idx}: chapter '{chapter}' must be between 01 and 97"
            )

    return errors


def write_output(rows: list[dict[str, str]], output_csv_path: Path) -> None:
    """Write generated HS6 rows to staged CSV."""
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    with output_csv_path.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found at {INPUT_CSV}")
        return 1

    try:
        rows, counters = load_hs6_rows(INPUT_CSV)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    validation_errors = validate_rows(rows)
    if validation_errors:
        print("ERROR: Validation failed.")
        for err in validation_errors[:20]:
            print(f"- {err}")
        if len(validation_errors) > 20:
            print(f"... and {len(validation_errors) - 20} more errors")
        return 1

    write_output(rows, OUTPUT_CSV)

    print("HS6 backbone load summary")
    print(f"- Input rows read: {counters['total_rows']}")
    print(f"- Invalid source rows skipped: {counters['invalid_source_rows']}")
    print(f"- Duplicate HS6 rows skipped: {counters['duplicate_rows']}")
    print(f"- Unique HS6 rows written: {counters['unique_hs6']}")
    print(f"- Output file: {OUTPUT_CSV}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
