from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


ROOT_DIR = Path(__file__).resolve().parents[2]
PDF_PATH = (
    ROOT_DIR
    / "docs"
    / "corpus"
    / "02_rules_of_origin"
    / "EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf"
)
OUTPUT_PATH = ROOT_DIR / "data" / "staged" / "extracted_tables" / "appendix_iv_raw.csv"

# ---------------------------------------------------------------------------
# Column boundaries (x-coordinates) derived from character position analysis.
# The PDF is landscape 842 x 595.  Three logical columns:
#   Col 1 (HS code):      x  70 – 180
#   Col 2 (Description):  x 180 – 455
#   Col 3 (Rule text):    x 455 – 790
# ---------------------------------------------------------------------------
COL1_X0 = 70
COL1_X1 = 180
COL2_X0 = 180
COL2_X1 = 455
COL3_X0 = 455
COL3_X1 = 790

# Vertical margins to skip page headers/footers
Y_TOP = 55
Y_BOTTOM = 570

# Tolerance for grouping words into the same text line (points)
Y_LINE_TOLERANCE = 3

# First N pages are introductory notes, not rule tables
INTRO_PAGES_END = 15

HEADER_PREFIXES = (
    "section ",
    "chapter ",
    "ex-chapter ",
)

# --- Encoding fixes for common PDF garble ---
ENCODING_FIXES = {
    "Â°T4H": "th",
    "Â°": "°",
    "\u00c2\u00b0": "°",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "â\u0080\u009c": '"',
    "â\u0080\u009d": '"',
    "â\u0080\u0099": "'",
    "â\u0080\u0098": "'",
    "â€œ": '"',
    "â€\x9d": '"',
    "â€": '"',
    "â€™": "'",
    "â€˜": "'",
    "Ã©": "é",
    "Ã¨": "è",
    "Ã¢": "â",
    "Ã´": "ô",
    "Ã¯": "ï",
    "Ã ": "à",
    "Ã§": "ç",
    "Chapteter": "Chapter",
    "Chapt eter": "Chapter",
    "mateter": "mater",
    "Mateter": "Mater",
    "filalam": "filam",
    "filmlm": "film",
    "maltlt": "malt",
    "yoghurtrt": "yoghurt",
    "buttermililk": "buttermilk",
    "isomeririsation": "isomerisation",
    "polymeririsation": "polymerisation",
    "desulphuririsation": "desulphurisation",
    "specifific": "specific",
    "componentnsts": "components",
    "fitteted": "fitted",
    "medicicinal": "medicinal",
    "chemicical": "chemical",
    "modidfified": "modified",
    "modifified": "modified",
    "examplele": "example",
    "combininat": "combinat",
    "decololorisation": "decolorisation",
    "especicaially": "especially",
    "mesislin": "meslin",
    "procesing": "processing",
    "caried": "carried",
    "pneumatitic": "pneumatic",
    "stripipped": "stripped",
    "Materirials": "Materials",
    "materirials": "materials",
}

# Junk patterns for lines that are page headers / column headers
JUNK_LINE_PATTERNS = [
    re.compile(r"(?i)african\s+continental\s+free\s+trade"),
    re.compile(r"(?i)as\s+approved\s+by\s+the"),
    re.compile(r"(?i)^\s*(?:dec\s*ember|january|february|march|april|may|june|july|august|september|october|november)\s+\d{4}\s*$"),
    re.compile(r"(?i)working\s+or\s+process"),
    re.compile(r"(?i)materials?,?\s+which\s+confers\s+originating"),
    re.compile(r"(?i)^\s*description\s+of\s+product"),
    re.compile(r"(?i)^hs\s+chapt"),
    re.compile(r"(?i)^heading\s+or\s+sub"),
    re.compile(r"(?i)^heading\s*$"),
    re.compile(r"^\s*\d\s*$"),  # lone digit
]


@dataclass(slots=True)
class ExtractedRow:
    page_num: int
    row_index: int
    raw_hs_code: str
    raw_description: str
    raw_rule_text: str
    row_type: str


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def deduplicate_glyphs(text: str) -> str:
    """Collapse doubled glyphs from overlapping PDF rendering."""
    if not text:
        return text
    return re.sub(r'(.)\1', r'\1', text)


def fix_encoding(text: str) -> str:
    """Fix common PDF encoding garble."""
    if not text:
        return text
    for bad, good in ENCODING_FIXES.items():
        text = text.replace(bad, good)
    return text


def clean_pipes(text: str) -> str:
    """Remove stray pipe characters from PDF column boundaries."""
    if not text:
        return text
    text = re.sub(r'\s*\|\s*', ' ', text)
    text = re.sub(r'^\|+\s*', '', text)
    text = re.sub(r'\s*\|+$', '', text)
    return text.strip()


def deduplicate_phrases(text: str) -> str:
    """Remove phrases that appear twice in a row (PDF overlap artifact)."""
    if not text or len(text) < 10:
        return text
    match = re.match(r'^(.{8,}?)\s+\1', text)
    if match:
        return text[match.start(1):match.end(1)] + text[match.end():]
    return text


def clean_text(text: str) -> str:
    """Full cleaning pipeline for extracted text."""
    if not text:
        return ""
    text = deduplicate_glyphs(text)
    text = fix_encoding(text)
    text = clean_pipes(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = deduplicate_phrases(text)
    return text.strip()


def clean_hs_code(raw_code: str) -> str:
    """Strip footnote digits/symbols baked into HS codes and normalize format.

    HS code formats in the PDF:
        Headings:     XX.XX      (e.g. 04.01)  → output: 04.01
        Subheadings:  XXXX.XX    (e.g. 1103.11) → output: 11.03.11
        Chapters:     Chapter N                  → output: Chapter N

    Footnote superscripts get baked in as trailing digits (e.g. 15.046 → 15.04).
    """
    if not raw_code:
        return raw_code

    text = raw_code.strip()

    # Remove exclamation marks, quotes, backticks that are noise
    text = re.sub(r'[!`"\']+', '', text)

    # Handle "Ex-Chapter N" or "Ex Chapter" prefix
    text = re.sub(r'(?i)^ex[\s-]*chapter', 'Ex-Chapter', text)

    # Handle "Ex" prefix on codes: "Ex0305.69" → "Ex 03.05"
    text = re.sub(r'(?i)^ex[\s-]*(\d)', r'Ex \1', text)

    # Remove doubled HS codes: "15.18 15.18" → "15.18"
    dup_match = re.match(r'^([\dEx.\-\s]+?)\s+\1\s*$', text, re.IGNORECASE)
    if dup_match:
        text = dup_match.group(1).strip()

    # If it's a chapter reference, just clean and return
    if re.match(r'(?i)^(ex[\s-]*)?chapter\s+\d{1,2}', text):
        chapter_match = re.match(r'(?i)^((?:ex[\s-]*)?chapter\s+\d{1,2})', text)
        if chapter_match:
            return chapter_match.group(1)

    # Separate any "Ex " prefix before numeric processing
    ex_prefix = ""
    code_text = text
    ex_match = re.match(r'(?i)^(ex\s+)(.*)', text)
    if ex_match:
        ex_prefix = "Ex "
        code_text = ex_match.group(2).strip()

    # --- Pattern 1: Subheading format XXXX.XX (e.g. 1103.11, 0910.91) ---
    # This is a 4-digit heading concatenated with a 2-digit subheading
    sub_match = re.match(r'^(\d{4})[.](\d{2})', code_text)
    if sub_match:
        four = sub_match.group(1)   # e.g. "1103"
        two = sub_match.group(2)    # e.g. "11"
        ch = four[:2]               # "11"
        hd = four[2:]               # "03"
        return f"{ex_prefix}{ch}.{hd}.{two}"

    # --- Pattern 2: Already formatted XX.XX.XX (subheading with dots) ---
    sub_dot_match = re.match(r'^(\d{2})[.](\d{2})[.](\d{2})', code_text)
    if sub_dot_match:
        ch = sub_dot_match.group(1)
        hd = sub_dot_match.group(2)
        sh = sub_dot_match.group(3)
        return f"{ex_prefix}{ch}.{hd}.{sh}"

    # --- Pattern 3: Heading format XX.XX (e.g. 04.01, 15.18) ---
    # Must be exactly 2 digits, dot, 2 digits — ignore trailing footnote digits
    hd_match = re.match(r'^(\d{2})[.](\d{2})', code_text)
    if hd_match:
        ch = hd_match.group(1)
        hd = hd_match.group(2)
        return f"{ex_prefix}{ch}.{hd}"

    # --- Pattern 4: Short heading with missing leading zero (e.g. 4.01) ---
    short_match = re.match(r'^(\d{1})[.](\d{2})', code_text)
    if short_match:
        ch = short_match.group(1).zfill(2)
        hd = short_match.group(2)
        return f"{ex_prefix}{ch}.{hd}"

    return text


def is_junk_line(text: str) -> bool:
    """Check if a text line is a repeating page/column header."""
    if not text or not text.strip():
        return True
    for pattern in JUNK_LINE_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Position-based extraction
# ---------------------------------------------------------------------------

def assign_column(x0: float) -> int:
    """Assign a word to column 1, 2, or 3 based on its x-position."""
    if x0 < COL2_X0:
        return 1
    elif x0 < COL3_X0:
        return 2
    else:
        return 3


def extract_page_rows(page: pdfplumber.page.Page) -> list[dict]:
    """Extract structured rows from a single page using word positions.

    Returns a list of dicts with keys: col1, col2, col3 (text strings).
    """
    # Get all words with position data
    words = page.extract_words(
        x_tolerance=3,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=False,
    )

    if not words:
        return []

    # Filter to content area (skip page headers/footers)
    words = [w for w in words if Y_TOP <= w["top"] <= Y_BOTTOM and COL1_X0 <= w["x0"] <= COL3_X1]

    if not words:
        return []

    # Group words into text lines by y-position (top coordinate)
    words.sort(key=lambda w: (w["top"], w["x0"]))

    lines: list[list[dict]] = []
    current_line: list[dict] = []
    current_y = -999

    for w in words:
        if abs(w["top"] - current_y) > Y_LINE_TOLERANCE:
            if current_line:
                lines.append(current_line)
            current_line = [w]
            current_y = w["top"]
        else:
            current_line.append(w)

    if current_line:
        lines.append(current_line)

    # For each text line, assemble column text
    text_lines: list[dict] = []
    for line_words in lines:
        cols = {1: [], 2: [], 3: []}
        for w in sorted(line_words, key=lambda w: w["x0"]):
            col = assign_column(w["x0"])
            cols[col].append(w["text"])

        col1 = " ".join(cols[1]).strip()
        col2 = " ".join(cols[2]).strip()
        col3 = " ".join(cols[3]).strip()

        # Skip completely empty lines
        if not col1 and not col2 and not col3:
            continue

        text_lines.append({"col1": col1, "col2": col2, "col3": col3})

    return text_lines


def merge_into_logical_rows(text_lines: list[dict]) -> list[dict]:
    """Merge text lines into logical rows.

    A new logical row starts when col1 has an HS code or chapter reference.
    Continuation lines (empty col1) are appended to the previous row.
    """
    logical_rows: list[dict] = []
    current: dict | None = None

    for tl in text_lines:
        col1_clean = clean_text(tl["col1"])
        col2_clean = clean_text(tl["col2"])
        col3_clean = clean_text(tl["col3"])

        # Check if this is a junk line (combine all columns for checking)
        combined = f"{col1_clean} {col2_clean} {col3_clean}".strip()
        if is_junk_line(combined):
            continue

        # Does col1 contain an HS code or chapter reference? → new row
        has_hs = bool(re.search(r'\d{2}[.\s]\d{2}', col1_clean))
        has_chapter = bool(re.match(r'(?i)(ex[\s-]*)?chapter\s+\d', col1_clean))
        has_section = bool(re.match(r'(?i)section\s+', col1_clean))

        if has_hs or has_chapter or has_section:
            # Save previous row
            if current:
                logical_rows.append(current)
            current = {"col1": col1_clean, "col2": col2_clean, "col3": col3_clean}
        elif current is not None:
            # Continuation — append to current row
            if col1_clean:
                current["col1"] += " " + col1_clean
            if col2_clean:
                current["col2"] += " " + col2_clean
            if col3_clean:
                current["col3"] += " " + col3_clean
        else:
            # Orphan line before any HS code on this page — skip
            continue

    if current:
        logical_rows.append(current)

    return logical_rows


def classify_row(hs_code: str, description: str, rule_text: str) -> str:
    """Classify a logical row as header, data, or note."""
    hs_lower = hs_code.lower()

    # Chapter/section rows are headers
    if re.match(r'(?i)(ex[\s-]*)?chapter\s+\d', hs_code):
        return "header"
    if re.match(r'(?i)section\s+', hs_code):
        return "header"

    # Note rows
    if hs_lower.startswith(("note", "notes")):
        return "note"

    return "data"


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract_rows(pdf_path: Path) -> tuple[list[ExtractedRow], dict[str, int]]:
    extracted_rows: list[ExtractedRow] = []
    stats = {
        "total_pages_scanned": 0,
        "intro_pages_skipped": 0,
        "data_rows": 0,
        "header_rows": 0,
        "note_rows": 0,
        "junk_lines_skipped": 0,
    }

    with pdfplumber.open(pdf_path) as pdf:
        stats["total_pages_scanned"] = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, start=1):
            if page_num <= INTRO_PAGES_END:
                stats["intro_pages_skipped"] += 1
                continue

            # Step 1: Extract text lines with column positions
            text_lines = extract_page_rows(page)
            if not text_lines:
                continue

            # Step 2: Merge into logical rows
            logical_rows = merge_into_logical_rows(text_lines)

            # Step 3: Clean and classify each logical row
            for row_idx, lr in enumerate(logical_rows):
                hs_code = clean_hs_code(lr["col1"])
                description = lr["col2"].strip()
                rule_text = lr["col3"].strip()

                # Final cleanup pass
                description = re.sub(r"\s+", " ", description).strip()
                rule_text = re.sub(r"\s+", " ", rule_text).strip()

                # Remove leading "M " artifact from rule text
                rule_text = re.sub(r"^M\s+(?=Manufacture)", "Manufacture"[0:0], rule_text)
                if rule_text.startswith("M Manufacture"):
                    rule_text = rule_text[2:]

                row_type = classify_row(hs_code, description, rule_text)

                extracted_rows.append(
                    ExtractedRow(
                        page_num=page_num,
                        row_index=row_idx,
                        raw_hs_code=hs_code,
                        raw_description=description,
                        raw_rule_text=rule_text,
                        row_type=row_type,
                    )
                )

                if row_type == "data":
                    stats["data_rows"] += 1
                elif row_type == "header":
                    stats["header_rows"] += 1
                elif row_type == "note":
                    stats["note_rows"] += 1

    return extracted_rows, stats


def write_csv(rows: list[ExtractedRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "page_num",
                "row_index",
                "raw_hs_code",
                "raw_description",
                "raw_rule_text",
                "row_type",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "page_num": row.page_num,
                    "row_index": row.row_index,
                    "raw_hs_code": row.raw_hs_code,
                    "raw_description": row.raw_description,
                    "raw_rule_text": row.raw_rule_text,
                    "row_type": row.row_type,
                }
            )


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Appendix IV PDF not found: {PDF_PATH}")

    rows, stats = extract_rows(PDF_PATH)
    write_csv(rows, OUTPUT_PATH)

    print(f"Output CSV: {OUTPUT_PATH}")
    print(f"Total pages scanned: {stats['total_pages_scanned']}")
    print(f"Intro pages skipped: {stats['intro_pages_skipped']}")
    print(f"Data rows extracted: {stats['data_rows']}")
    print(f"Header rows: {stats['header_rows']}")
    print(f"Note rows: {stats['note_rows']}")

    # Quick quality check
    total_data = stats["data_rows"] + stats["header_rows"]
    rules_present = sum(1 for r in rows if r.raw_rule_text.strip() and r.row_type in ("data", "header"))
    if total_data > 0:
        print(f"Rule text coverage: {rules_present}/{total_data} ({rules_present/total_data*100:.0f}%)")


if __name__ == "__main__":
    main()