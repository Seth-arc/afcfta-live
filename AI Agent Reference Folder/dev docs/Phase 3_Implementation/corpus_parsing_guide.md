# AfCFTA Corpus Parsing Guide — From Raw PDF to Database Rows

**Purpose:** Step-by-step operational guide for someone who has never done document parsing before.  
**Scope:** Covers all six document types, with deepest detail on Appendix IV (PSR rules) and tariff schedules — the two hardest and most critical parsing jobs.

---

## How to Read This Guide

The parsing pipeline has a strict dependency order. You cannot build the rules layer without the backbone, and you cannot build the eligibility pathways without the rules layer. Work through this guide top to bottom.

The order is:

1. **L1 — HS6 Backbone** (easiest, do first)
2. **L3 — Tariff Schedules** (medium, semi-structured input)
3. **L2 — Appendix IV PSR Rules** (hardest, core IP)
4. **L4 — Status Assertions** (narrative extraction)
5. **L5 — Evidence Requirements** (pattern-based)
6. **Source Registry** (runs in parallel with everything)

---

# PART 1: SOURCE REGISTRY (Do This First For Everything)

Before parsing any document, you register it. Every row in every table traces back to a `source_id`. This is your audit trail.

## What the source_registry row looks like

```
source_id:              (auto-generated UUID)
title:                  "Appendix IV to Annex 2 — Product Specific Rules"
short_title:            "Appendix IV PSR"
source_group:           "02_rules_of_origin"
source_type:            "appendix"
authority_tier:         "binding"
issuing_body:           "African Union / AfCFTA Secretariat"
jurisdiction_scope:     "continental"
country_code:           NULL  (continental doc, not country-specific)
publication_date:       2021-01-01  (or actual date)
effective_date:         2021-01-01
version_label:          "2021 consolidated"
status:                 "current"
language:               "en"
hs_version:             "HS2017"
file_path:              "/sources/02_rules_of_origin/appendix_iv_psr_2021.pdf"
mime_type:              "application/pdf"
checksum_sha256:        (compute with: shasum -a 256 filename.pdf)
```

## Practical steps

1. Create a folder structure matching the six ingest folders from your Canonical Corpus doc
2. Place each source document in the right folder
3. Compute SHA256 checksums for every file
4. Insert one `source_registry` row per file
5. Record the returned `source_id` — you'll use it in every downstream table

**Tool:** You can do this with a simple Python script that walks the folder tree, computes checksums, and inserts rows. This is not a parsing problem — it's just file registration.

---

# PART 2: L1 — HS6 BACKBONE (Easiest — Start Here)

## What you're building

The `hs6_product` table. Every other table joins to this. It contains one row per 6-digit HS code.

## Where the data comes from

The World Customs Organization publishes the Harmonized System nomenclature. For AfCFTA, the relevant version is **HS2017** (some schedules may reference HS2022). The data is available as:

- Structured CSV/Excel from WCO or UN COMTRADE
- The HS nomenclature tables included in AfCFTA e-Tariff Book exports
- WCO reference files

This is NOT a PDF parsing problem. You're loading structured reference data.

## What a row looks like

```
hs6_id:         (auto-generated UUID)
hs_version:     "HS2017"
hs6_code:       "110311"
hs6_display:    "1103.11"
chapter:        "11"
heading:        "1103"
description:    "Groats and meal of wheat"
section:        "II"
section_name:   "Vegetable products"
```

## Step-by-step process

### Step 1: Obtain the HS nomenclature file

Download from UN COMTRADE, WCO, or extract from the e-Tariff Book. You want a file that has at minimum: HS code (6 digits), description, chapter, heading.

### Step 2: Clean the raw data

```python
import pandas as pd

# Load the raw file
df = pd.read_csv("hs2017_nomenclature.csv")

# Standardize the HS code column
# Remove dots, spaces, dashes. Pad to 6 digits.
df["hs6_code"] = (
    df["hs_code"]
    .astype(str)
    .str.replace(r"[.\-\s]", "", regex=True)
    .str.zfill(6)
)

# Only keep 6-digit codes (filter out 2-digit chapters and 4-digit headings)
df = df[df["hs6_code"].str.len() == 6].copy()

# Derive chapter and heading
df["chapter"] = df["hs6_code"].str[:2]
df["heading"] = df["hs6_code"].str[:4]

# Create display format: "1103.11"
df["hs6_display"] = df["hs6_code"].str[:4] + "." + df["hs6_code"].str[4:]

# Add HS version
df["hs_version"] = "HS2017"

# Deduplicate
df = df.drop_duplicates(subset=["hs_version", "hs6_code"])
```

### Step 3: Validate

```python
# Every code must be exactly 6 digits, all numeric
assert df["hs6_code"].str.match(r"^\d{6}$").all(), "Invalid HS6 codes found"

# No duplicates
assert df.duplicated(subset=["hs_version", "hs6_code"]).sum() == 0

# Chapters should be 01-97 (98/99 are national use)
chapters = df["chapter"].astype(int)
assert chapters.between(1, 97).all(), "Unexpected chapter numbers"

# Should have ~5,000+ rows for HS2017
print(f"Total HS6 codes: {len(df)}")  # expect ~5,387 for HS2017
```

### Step 4: Load into PostgreSQL

```python
import uuid
from sqlalchemy import text

for _, row in df.iterrows():
    db.execute(text("""
        INSERT INTO hs6_product (hs6_id, hs_version, hs6_code, hs6_display,
                                  chapter, heading, description)
        VALUES (:id, :ver, :code, :display, :ch, :hd, :desc)
        ON CONFLICT (hs_version, hs6_code) DO NOTHING
    """), {
        "id": str(uuid.uuid4()),
        "ver": row["hs_version"],
        "code": row["hs6_code"],
        "display": row["hs6_display"],
        "ch": row["chapter"],
        "hd": row["heading"],
        "desc": row["description"],
    })
```

**Time estimate:** Half a day including validation.

---

# PART 3: L3 — TARIFF SCHEDULES (Medium Difficulty)

## What you're building

Three tables: `tariff_schedule_header`, `tariff_schedule_line`, `tariff_schedule_rate_by_year`.

## Where the data comes from

- **e-Tariff Book exports** (the AfCFTA Secretariat publishes these — they're the primary source)
- **State Party submitted schedules** (PDFs or spreadsheets)
- **Gazetted national tariff schedules**

The e-Tariff Book data is typically available as **Excel/CSV exports**, which is much easier than PDF parsing. The State Party schedules sometimes come as PDFs with tables, which requires table extraction.

## What the data looks like raw

A typical tariff schedule row (from an Excel export) looks something like:

```
HS Code | Description | Category | Base Rate | Year 1 | Year 2 | Year 3 | ... | Year 10
110311  | Groats...   | B        | 20%       | 18%    | 16%    | 14%    |     | 0%
```

The header tells you: importing state, exporting scope (which countries does this apply to), HS version, status.

## Step-by-step process

### Step 1: Identify what you have

For each of your five v0.1 countries (Nigeria, Ghana, Côte d'Ivoire, Senegal, Cameroon), find:

- Their submitted tariff schedule (the "offer")
- The e-Tariff Book export for their corridors
- Whether the schedule is official, provisional, or gazetted

List out what you actually have. For v0.1, you may only have partial schedules — that's fine, you'll tag them with the appropriate status.

### Step 2: Parse the schedule header

For each schedule file, create one `tariff_schedule_header` row:

```
schedule_id:        (auto UUID)
source_id:          (from source_registry — which file did this come from?)
importing_state:    "NGA"
exporting_scope:    "AfCFTA"  (or "GHA" if it's a bilateral schedule)
schedule_status:    "provisional"  (or "official", "gazetted", etc.)
publication_date:   2023-06-15
effective_date:     2024-01-01
hs_version:         "HS2017"
category_system:    "A/B/C/D/E"
notes:              "Guided Trade Initiative provisional schedule"
```

### Step 3: Parse the schedule lines

This is the row-by-row work. For each line in the spreadsheet:

```python
import pandas as pd

# Load the tariff schedule spreadsheet
df = pd.read_excel("nigeria_tariff_schedule.xlsx", sheet_name="Schedule")

# Common issues you'll encounter:
# 1. Header row might not be row 0 — look for the row with "HS Code" in it
# 2. HS codes might be formatted as numbers (110311) or text (1103.11)
# 3. Rate columns might say "20%" or "20" or "Free" or "Excluded"
# 4. Merged cells for section headers (Chapter 01, Chapter 02, etc.)
# 5. Footnotes and annotations mixed into data rows

# Find the actual header row
for i, row in df.iterrows():
    if any("HS" in str(cell).upper() for cell in row if pd.notna(cell)):
        header_row = i
        break

# Re-read with correct header
df = pd.read_excel("nigeria_tariff_schedule.xlsx", 
                    sheet_name="Schedule", header=header_row)
```

### Step 4: Clean HS codes

```python
def clean_hs_code(raw):
    """Normalize any HS code format to 6-digit string."""
    if pd.isna(raw):
        return None
    s = str(raw).strip()
    # Remove dots, spaces, dashes
    s = s.replace(".", "").replace("-", "").replace(" ", "")
    # Remove trailing decimals from Excel number formatting (110311.0 -> 110311)
    if "." in s:
        s = s.split(".")[0]
    # Pad to 6 digits
    s = s.zfill(6)
    # Validate: must be 4 or 6 digits after cleaning
    if len(s) == 6 and s.isdigit():
        return s
    return None  # flag for manual review

df["hs6_code"] = df["hs_code_column"].apply(clean_hs_code)

# Log rows where cleaning failed
bad_rows = df[df["hs6_code"].isna()]
if len(bad_rows) > 0:
    bad_rows.to_csv("tariff_parse_errors.csv", index=True)
    print(f"WARNING: {len(bad_rows)} rows could not be parsed. Review tariff_parse_errors.csv")
```

### Step 5: Clean rate values

This is trickier than it sounds. Rates come in many formats:

```python
def clean_rate(raw):
    """
    Normalize rate values. Returns a numeric value or None.
    
    Handles:
    - "20%"     -> 20.0
    - "20"      -> 20.0
    - "Free"    -> 0.0
    - "Excl"    -> None (excluded product, handle separately)
    - "N/A"     -> None
    - "5% + $2" -> None (compound rates, flag for manual review)
    - ""        -> None
    """
    if pd.isna(raw):
        return None
    s = str(raw).strip().lower()
    
    if s in ("free", "0", "0%", "0.0", "0.0%", "duty free"):
        return 0.0
    if s in ("excl", "excluded", "excl.", "sensitive", "n/a", ""):
        return None
    
    # Check for compound rates (contain + or "per" or specific duty)
    if "+" in s or "per " in s or "/kg" in s or "/l" in s:
        return None  # flag: compound rate, needs manual review
    
    # Strip % sign and parse
    s = s.replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None  # flag for review

df["mfn_base_rate"] = df["base_rate_column"].apply(clean_rate)
```

### Step 6: Expand year-by-year rates

Each tariff line with a phase-down schedule produces multiple `tariff_schedule_rate_by_year` rows:

```python
# Identify year columns (they might be labeled "Year 1", "2024", "Yr1", etc.)
year_columns = [col for col in df.columns if is_year_column(col)]

def is_year_column(col_name):
    """Detect year/phase columns by name pattern."""
    s = str(col_name).strip().lower()
    # Matches: "year 1", "yr1", "2024", "y1", etc.
    return bool(re.match(r"(year\s*\d+|yr\s*\d+|y\d+|20\d{2})", s))

for _, row in df.iterrows():
    schedule_line_id = insert_schedule_line(row)  # insert the parent line first
    
    for col in year_columns:
        year_number = extract_year_number(col)  # "Year 1" -> 1, "2024" -> 2024
        rate = clean_rate(row[col])
        
        if rate is not None:
            db.execute(text("""
                INSERT INTO tariff_schedule_rate_by_year
                  (rate_id, schedule_line_id, year_offset, calendar_year,
                   applied_rate, rate_status)
                VALUES (:id, :line_id, :offset, :cal_year, :rate, :status)
            """), {
                "id": str(uuid.uuid4()),
                "line_id": schedule_line_id,
                "offset": year_number,
                "cal_year": compute_calendar_year(effective_date, year_number),
                "rate": rate,
                "status": "projected",  # or "in_force" for current/past years
            })
```

### Step 7: Handle the messy cases

Every tariff schedule has these problems. Expect them:

**Problem 1: Merged cells for chapter/section headers**
```
Chapter 11: Products of the milling industry
1103.11  |  Groats and meal of wheat  | B | 20%  | ...
1103.13  |  Groats and meal of maize  | B | 15%  | ...
```
The "Chapter 11" row has no rate data. Skip it during line parsing, but you can use it to validate that HS codes are in the right chapter.

**Problem 2: Ranges instead of individual codes**
```
ex 0901.11-0901.12  |  Coffee, not roasted  | A  | 10%
```
The "ex" prefix means "extract from" — only specific products within that range. Store `hs_code_start` and `hs_code_end` on the schedule line and expand at query time.

**Problem 3: Different countries use different formats**
- Nigeria: might use HS8/10 digit codes (truncate to 6 for your backbone join)
- Ghana: might use a different column layout
- Cameroon: might be in French ("Taux de base" instead of "Base Rate")

**Problem 4: Missing or incomplete schedules**
Some country pairs may not have submitted schedules yet. This is fine — your `tariff_schedule_header.schedule_status` will be `"draft"` or `"not_yet_operational"`, and the status layer will prevent false certainty.

### Step 8: Validate

```python
# Every schedule_line must have a valid hs6_code
assert all(lines_df["hs6_code"].str.match(r"^\d{6}$")), "Invalid HS codes in tariff lines"

# Every schedule_line must reference an existing hs6_product
orphans = db.execute(text("""
    SELECT tsl.hs_code
    FROM tariff_schedule_line tsl
    LEFT JOIN hs6_product hp ON hp.hs6_code = tsl.hs_code AND hp.hs_version = 'HS2017'
    WHERE hp.hs6_id IS NULL
""")).fetchall()
if orphans:
    print(f"WARNING: {len(orphans)} tariff lines have no matching HS6 product")
    # These need manual review — likely HS8/10 codes that need truncation

# Rates should be between 0 and 100 for most products
extreme_rates = db.execute(text("""
    SELECT * FROM tariff_schedule_line WHERE mfn_base_rate > 100
""")).fetchall()
if extreme_rates:
    print(f"WARNING: {len(extreme_rates)} lines have rates > 100%. Review for compound duties.")
```

**Time estimate:** 2-4 days per country, depending on schedule quality.

---

# PART 4: L2 — APPENDIX IV PSR RULES (Hardest — Core Parsing Job)

This is the big one. Appendix IV is a PDF containing a table where each row maps an HS code (or range of codes) to a rule of origin expressed in legal prose. Your job is to turn each row into three related database records: a `psr_rule`, one or more `psr_rule_component` entries, and one or more `eligibility_rule_pathway` entries.

## What Appendix IV looks like physically

It's a table in a PDF. The columns are typically:

```
| HS Code / Heading | Product Description | Qualifying Rule |
|-------------------|---------------------|-----------------|
```

But the structure varies. Some versions have more columns. The key content is always: an HS reference, a product description, and the rule text.

### Example rows (representative, not verbatim)

**Simple row — single rule:**
```
1103.11  |  Groats and meal of wheat  |  CTH
```
This means: to qualify, all non-originating materials must undergo a change of tariff heading (from any heading other than 1103).

**Medium row — threshold rule:**
```
8703.21  |  Vehicles, spark-ignition  |  MaxNOM 55% (EXW)
```
This means: maximum non-originating materials content is 55% of the ex-works price.

**Complex row — alternative pathways (OR):**
```
6204.11  |  Women's suits, of wool  |  CTH; or MaxNOM 55% (EXW)
```
This means: qualify via EITHER a change of tariff heading OR by keeping non-originating content below 55%.

**Complex row — combined requirements (AND):**
```
3901.10  |  Polyethylene, specific gravity < 0.94  |  CTH and MaxNOM 50% (EXW)
```
This means: you need BOTH a tariff heading change AND non-originating content below 50%.

**Chapter-level rule (applies to all codes in chapter):**
```
Chapter 01  |  Live animals  |  WO
```
This means: all products in chapter 01 must be wholly obtained (born and raised in the originating country).

**Heading-level rule with subheading exception:**
```
ex 8501  |  Electric motors  |  CTSH; except from 8501.10 through 8501.40
```

## The pipeline — 10 stages

### STAGE 1: PDF Table Extraction

**Goal:** Get the raw table rows out of the PDF into a structured format (CSV/DataFrame).

**Tools (Python):**
- `camelot-py` — good for well-structured tables with clear borders
- `tabula-py` — Java-based, handles more table varieties
- `pdfplumber` — pure Python, good for complex layouts
- Manual CSV creation for sections that tools can't parse

**Start with pdfplumber (most reliable for legal documents):**

```python
import pdfplumber

def extract_appendix_iv_tables(pdf_path):
    """Extract all tables from Appendix IV PDF."""
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            
            for table in tables:
                for row_idx, row in enumerate(table):
                    # Skip header rows (detect by content)
                    if is_header_row(row):
                        continue
                    
                    all_rows.append({
                        "page": page_num,
                        "row_index": row_idx,
                        "raw_cells": row,  # list of cell strings
                    })
    
    return all_rows

def is_header_row(row):
    """Detect table header rows by content."""
    if row is None:
        return True
    text = " ".join(str(cell or "") for cell in row).lower()
    return any(kw in text for kw in [
        "hs code", "heading", "product description", "qualifying",
        "rule of origin", "subheading"
    ])
```

**What will go wrong (expect this):**

1. **Multi-page tables:** The table continues across pages but the header repeats. You need to detect and skip repeated headers.

2. **Merged cells:** Chapter-level rules span the entire row. The HS code cell might be empty while the description says "Chapter 11" and the rule spans across.

3. **Line breaks within cells:** A single cell might contain multiple lines of text that pdfplumber returns as one string with `\n` characters. Preserve these — the rule text is the verbatim content.

4. **Footnotes and annotations:** Some rows have superscript numbers referencing footnotes. These are important — they often contain exceptions or clarifications.

5. **Column misalignment:** pdfplumber might misassign content to the wrong column on some pages. Always validate.

**Practical advice:** After extraction, immediately dump to CSV and eyeball it against the original PDF. You'll catch alignment issues immediately. This manual review step is NOT optional — it's how you catch the 10% of rows that extract badly.

```python
# Dump raw extraction for manual review
import csv

rows = extract_appendix_iv_tables("appendix_iv.pdf")
with open("raw_extraction_review.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["page", "row_index", "cell_0", "cell_1", "cell_2", "cell_3"])
    for row in rows:
        cells = row["raw_cells"]
        writer.writerow([
            row["page"],
            row["row_index"],
            cells[0] if len(cells) > 0 else "",
            cells[1] if len(cells) > 1 else "",
            cells[2] if len(cells) > 2 else "",
            cells[3] if len(cells) > 3 else "",
        ])
```

### STAGE 2: Row Classification

**Goal:** Classify each extracted row into one of these types:

- `CHAPTER_RULE` — applies to an entire chapter (e.g., "Chapter 01 | Live animals | WO")
- `HEADING_RULE` — applies to a 4-digit heading (e.g., "11.03 | Cereal groats... | CTH")  
- `SUBHEADING_RULE` — applies to a specific 6-digit code (e.g., "1103.11 | ... | CTH")
- `RANGE_RULE` — applies to a range (e.g., "ex 0901.11 - 0901.12 | ... | CTH")
- `SECTION_HEADER` — not a rule, just a section divider (skip)
- `CONTINUATION` — overflow text from the previous row (merge upward)
- `UNPARSEABLE` — flag for manual review

```python
import re

def classify_row(cells):
    """
    Classify a raw table row by its HS code pattern.
    cells is a list of strings from left to right.
    """
    if not cells or all(c is None or str(c).strip() == "" for c in cells):
        return "EMPTY"
    
    hs_cell = str(cells[0] or "").strip()
    
    # Chapter-level rules
    if re.match(r"(?i)^chapter\s+\d{1,2}", hs_cell):
        return "CHAPTER_RULE"
    
    # "ex" prefix means extract/partial coverage
    has_ex = hs_cell.lower().startswith("ex")
    code_part = re.sub(r"(?i)^ex\s*", "", hs_cell).strip()
    
    # Range: "0901.11 - 0901.12" or "0901.11-0901.12"
    if re.search(r"\d{4}\.\d{2}\s*[-–]\s*\d{4}\.\d{2}", code_part):
        return "RANGE_RULE"
    
    # Clean code for length check
    clean = code_part.replace(".", "").replace(" ", "")
    
    if re.match(r"^\d{4}$", clean):
        return "HEADING_RULE"
    elif re.match(r"^\d{6}$", clean):
        return "SUBHEADING_RULE"
    elif re.match(r"^\d{2}$", clean):
        return "CHAPTER_RULE"
    
    # No HS code in first cell — might be a continuation or section header
    if hs_cell == "" and any(str(c or "").strip() for c in cells[1:]):
        return "CONTINUATION"
    
    # Check if it's a section header like "Section II — Vegetable Products"
    if re.match(r"(?i)^section\s+", hs_cell):
        return "SECTION_HEADER"
    
    return "UNPARSEABLE"
```

### STAGE 3: HS Code Normalization

**Goal:** Extract clean HS codes from the messy cell content, determine the HS level, and set up the join keys.

```python
def normalize_hs_from_row(hs_cell, row_type):
    """
    Extract normalized HS code(s) from the raw cell content.
    
    Returns dict with:
    - hs_code: the primary code (cleaned, no dots)
    - hs_code_start: for ranges
    - hs_code_end: for ranges
    - hs_level: 'chapter' | 'heading' | 'subheading'
    - has_ex_prefix: boolean
    - raw_text: original cell content (for provenance)
    """
    raw = str(hs_cell).strip()
    result = {
        "raw_text": raw,
        "has_ex_prefix": raw.lower().startswith("ex"),
        "hs_code_start": None,
        "hs_code_end": None,
    }
    
    # Remove "ex" prefix for code extraction
    code_text = re.sub(r"(?i)^ex\s*", "", raw).strip()
    
    if row_type == "CHAPTER_RULE":
        # "Chapter 11" -> "11"
        match = re.search(r"\d{1,2}", code_text)
        if match:
            result["hs_code"] = match.group().zfill(2)
            result["hs_level"] = "chapter"
            return result
    
    if row_type == "RANGE_RULE":
        # "0901.11 - 0901.12" -> start=090111, end=090112
        parts = re.split(r"\s*[-–]\s*", code_text)
        if len(parts) == 2:
            result["hs_code_start"] = parts[0].replace(".", "").strip().zfill(6)
            result["hs_code_end"] = parts[1].replace(".", "").strip().zfill(6)
            result["hs_code"] = result["hs_code_start"]  # primary = start of range
            result["hs_level"] = "subheading"
            return result
    
    # Standard single code
    clean = code_text.replace(".", "").replace(" ", "").strip()
    
    if len(clean) == 4 and clean.isdigit():
        result["hs_code"] = clean
        result["hs_level"] = "heading"
    elif len(clean) == 6 and clean.isdigit():
        result["hs_code"] = clean
        result["hs_level"] = "subheading"
    elif len(clean) == 2 and clean.isdigit():
        result["hs_code"] = clean
        result["hs_level"] = "chapter"
    else:
        result["hs_code"] = clean
        result["hs_level"] = "subheading"  # default assumption, flag for review
    
    return result
```

### STAGE 4: Rule Text Extraction and Cleaning

**Goal:** Get the verbatim legal rule text from the correct column, clean it without changing its meaning.

```python
def extract_rule_text(cells, column_index=2):
    """
    Extract and clean the rule text from the appropriate column.
    
    Preserves meaning. Does NOT normalize rule types yet —
    that happens in Stage 5.
    """
    raw = str(cells[column_index] or "").strip()
    
    # Fix common PDF extraction artifacts:
    # 1. Broken words from line breaks
    raw = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)  # re-join hyphenated words
    
    # 2. Excessive whitespace
    raw = re.sub(r"\s+", " ", raw).strip()
    
    # 3. Smart quotes to straight quotes
    raw = raw.replace("\u201c", '"').replace("\u201d", '"')
    raw = raw.replace("\u2018", "'").replace("\u2019", "'")
    
    # 4. Common OCR errors in legal text
    raw = raw.replace("l00%", "100%")  # lowercase L mistaken for 1
    raw = raw.replace("O%", "0%")      # letter O mistaken for zero
    
    return raw
```

**Critical rule: the `legal_rule_text_verbatim` field must contain what the PDF actually says.** Do the minimal cleaning above, but do NOT rewrite, paraphrase, or reformat. If the PDF says "MaxNOM 55 % of EXW" and you "normalize" it to "VNM <= 55% (EXW)" — the normalization goes in a different field. The verbatim text is your legal audit trail.

### STAGE 5: Rule Decomposition (The Hard Part)

**Goal:** Break the verbatim rule text into structured components. This is where you go from "CTH; or MaxNOM 55% (EXW)" to machine-executable pieces.

This is the single most important parsing step in the entire system. Get this wrong and the eligibility engine produces wrong answers.

**The rule language is formulaic.** Despite looking complex, AfCFTA PSR rules use a small, repeatable vocabulary:

```
RULE TYPES (your component_type enum):
  WO        = Wholly Obtained (grown, mined, born in country)
  CTH       = Change of Tariff Heading (4-digit level change)
  CTSH      = Change of Tariff Subheading (6-digit level change)
  CC        = Change of Chapter (2-digit level change)
  VNM       = Value of Non-originating Materials (max % threshold)
  VA        = Value Added (min % threshold)
  PROCESS   = Specific manufacturing process required

CONNECTORS:
  "or" / ";"          = alternative pathways (OR logic)
  "and" / ","         = combined requirements (AND logic)
  "except from"       = exception to a tariff shift rule
  "whether or not"    = additional condition that always applies

THRESHOLD PATTERNS:
  "MaxNOM 55% (EXW)"  = VNM, threshold 55, basis ex_works
  "MaxNOM 50% (FOB)"  = VNM, threshold 50, basis fob
  "RVC 40%"           = VA, threshold 40, basis ex_works
  "MinLVC 30%"        = VA, threshold 30, basis ex_works
```

**Build a pattern-matching decomposer:**

```python
import re
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RuleComponent:
    component_type: str          # WO, CTH, CTSH, CC, VNM, VA, PROCESS, EXCEPTION, NOTE
    operator_type: str           # 'and', 'or', 'standalone'
    threshold_percent: Optional[float] = None
    threshold_basis: Optional[str] = None    # 'ex_works', 'fob', etc.
    tariff_shift_level: Optional[str] = None # 'chapter', 'heading', 'subheading'
    specific_process_text: Optional[str] = None
    component_text_verbatim: str = ""
    normalized_expression: Optional[str] = None
    confidence: float = 1.0
    component_order: int = 1

def decompose_rule_text(rule_text: str) -> list[RuleComponent]:
    """
    Decompose verbatim rule text into structured components.
    
    This is the core parsing logic. It handles:
    - Single rules: "CTH"
    - Threshold rules: "MaxNOM 55% (EXW)"
    - Alternatives: "CTH; or MaxNOM 55% (EXW)"
    - Combinations: "CTH and MaxNOM 50% (EXW)"
    - Exceptions: "CTH except from heading 10.06"
    - Wholly obtained: "WO" or "Wholly obtained"
    - Process rules: "Manufacture from [specific process]"
    """
    components = []
    text = rule_text.strip()
    
    # Step 1: Split on top-level "or" / ";" to find alternative pathways
    # Be careful: "or" inside "except from heading 10.06 or 10.07" is NOT a pathway split
    pathways = split_on_or(text)
    
    for pathway_idx, pathway_text in enumerate(pathways):
        # Step 2: Within each pathway, split on "and" / "," for combined requirements
        sub_rules = split_on_and(pathway_text)
        
        for sub_idx, sub_text in enumerate(sub_rules):
            component = parse_single_rule(sub_text.strip())
            
            # Set operator based on position
            if len(pathways) > 1 and pathway_idx > 0 and sub_idx == 0:
                component.operator_type = "or"
            elif len(sub_rules) > 1 and sub_idx > 0:
                component.operator_type = "and"
            else:
                component.operator_type = "standalone"
            
            component.component_order = len(components) + 1
            component.component_text_verbatim = sub_text.strip()
            components.append(component)
    
    return components


def split_on_or(text: str) -> list[str]:
    """
    Split rule text on top-level OR connectors.
    Handles: "; or", " or ", ";" used as OR separator.
    
    Must NOT split inside parentheses or "except from" clauses.
    """
    # Common OR patterns in AfCFTA rules:
    # "CTH; or MaxNOM 55% (EXW)"
    # "CTH or MaxNOM 55% (EXW)"
    # "CTH; MaxNOM 55% (EXW)"  (semicolon alone sometimes means OR)
    
    # Strategy: split on "; or" first (most explicit), then ";" if no other split found
    parts = re.split(r";\s*or\s+", text, flags=re.IGNORECASE)
    if len(parts) > 1:
        return parts
    
    # Try splitting on standalone " or " (but not inside "except from ... or ...")
    # This is a simplification — for production, use a proper tokenizer
    parts = re.split(r"\s+or\s+", text, flags=re.IGNORECASE)
    if len(parts) > 1:
        # Verify this isn't inside an exception clause
        # Heuristic: if "except" appears before "or", don't split
        except_pos = text.lower().find("except")
        or_pos = text.lower().find(" or ")
        if except_pos >= 0 and except_pos < or_pos:
            return [text]  # don't split — the "or" is part of the exception
        return parts
    
    return [text]


def split_on_and(text: str) -> list[str]:
    """
    Split a single pathway on AND connectors.
    Handles: " and ", ", " used as AND between rule types.
    """
    # "CTH and MaxNOM 50% (EXW)"
    parts = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)
    if len(parts) > 1:
        return parts
    
    # Some rules use comma: "CTH, MaxNOM 50% (EXW)"
    # But commas also appear in descriptions. Only split if both parts look like rules.
    if "," in text:
        candidate_parts = text.split(",")
        if all(looks_like_rule(p.strip()) for p in candidate_parts):
            return candidate_parts
    
    return [text]


def looks_like_rule(text: str) -> bool:
    """Quick check if a text fragment looks like a rule component."""
    t = text.strip().upper()
    rule_keywords = ["CTH", "CTSH", "CC", "WO", "VNM", "VA", "MAXNOM", 
                     "RVC", "MINLVC", "PROCESS", "MANUFACTURE", "WHOLLY"]
    return any(kw in t for kw in rule_keywords)


def parse_single_rule(text: str) -> RuleComponent:
    """
    Parse a single rule fragment into a structured component.
    This handles one atomic rule, not combinations.
    """
    t = text.strip()
    upper = t.upper()
    
    # --- Wholly Obtained ---
    if re.match(r"(?i)^(WO|wholly\s+obtained)", t):
        return RuleComponent(
            component_type="WO",
            normalized_expression='{"op": "fact_eq", "fact": "wholly_obtained", "value": true}',
            confidence=1.0,
        )
    
    # --- Change of Tariff Heading ---
    if re.match(r"(?i)^CTH", upper):
        comp = RuleComponent(
            component_type="CTH",
            tariff_shift_level="heading",
        )
        # Check for exceptions: "CTH except from heading 10.06"
        except_match = re.search(r"(?i)except\s+from\s+(.*)", t)
        if except_match:
            comp.specific_process_text = except_match.group(1).strip()
            comp.normalized_expression = (
                '{"op": "every_non_originating_input", '
                '"test": {"op": "heading_ne_output"}, '
                f'"exceptions": "{except_match.group(1).strip()}"'
                '}'
            )
        else:
            comp.normalized_expression = (
                '{"op": "every_non_originating_input", '
                '"test": {"op": "heading_ne_output"}}'
            )
        comp.confidence = 1.0
        return comp
    
    # --- Change of Tariff Subheading ---
    if re.match(r"(?i)^CTSH", upper):
        comp = RuleComponent(
            component_type="CTSH",
            tariff_shift_level="subheading",
        )
        except_match = re.search(r"(?i)except\s+from\s+(.*)", t)
        if except_match:
            comp.specific_process_text = except_match.group(1).strip()
        comp.normalized_expression = (
            '{"op": "every_non_originating_input", '
            '"test": {"op": "subheading_ne_output"}}'
        )
        comp.confidence = 1.0
        return comp
    
    # --- Change of Chapter ---
    if re.match(r"(?i)^CC(\s|$)", upper):
        return RuleComponent(
            component_type="CC",
            tariff_shift_level="chapter",
            normalized_expression=(
                '{"op": "every_non_originating_input", '
                '"test": {"op": "chapter_ne_output"}}'
            ),
            confidence=1.0,
        )
    
    # --- VNM / MaxNOM (Max Non-Originating Materials) ---
    vnm_match = re.match(
        r"(?i)(?:MaxNOM|VNM|max(?:imum)?\s+non[\s-]?originating"
        r"(?:\s+materials?)?(?:\s+content)?)\s*"
        r"(\d+(?:\.\d+)?)\s*%"
        r"(?:\s*\(?\s*(EXW|FOB|CIF)\s*\)?)?",
        t
    )
    if vnm_match:
        threshold = float(vnm_match.group(1))
        basis = vnm_match.group(2)
        basis_mapped = {
            "EXW": "ex_works", "FOB": "fob", "CIF": "customs_value"
        }.get(basis.upper() if basis else "", "ex_works")
        
        return RuleComponent(
            component_type="VNM",
            threshold_percent=threshold,
            threshold_basis=basis_mapped,
            normalized_expression=(
                '{"op": "formula_lte", '
                '"formula": "vnom_percent", '
                f'"value": {threshold}'
                '}'
            ),
            confidence=1.0,
        )
    
    # --- VA / RVC / MinLVC (Value Added) ---
    va_match = re.match(
        r"(?i)(?:RVC|MinLVC|VA|min(?:imum)?\s+(?:local|regional|value[\s-]?added)"
        r"(?:\s+content)?)\s*"
        r"(\d+(?:\.\d+)?)\s*%"
        r"(?:\s*\(?\s*(EXW|FOB)\s*\)?)?",
        t
    )
    if va_match:
        threshold = float(va_match.group(1))
        basis = va_match.group(2)
        basis_mapped = {
            "EXW": "ex_works", "FOB": "fob"
        }.get(basis.upper() if basis else "", "ex_works")
        
        return RuleComponent(
            component_type="VA",
            threshold_percent=threshold,
            threshold_basis=basis_mapped,
            normalized_expression=(
                '{"op": "formula_lte", '
                '"formula": "va_percent", '  # Note: VA is >= threshold, but stored as complement
                f'"value": {100 - threshold}'  # convert to VNM equivalent for engine
                '}'
            ),
            confidence=1.0,
        )
    
    # --- Specific Process ---
    if re.match(r"(?i)^(manufacture|processing|production)\s+from\s+", t):
        return RuleComponent(
            component_type="PROCESS",
            specific_process_text=t,
            normalized_expression=None,  # Process rules need manual expression writing
            confidence=0.5,  # Lower confidence — needs human review
        )
    
    # --- Fallback: unparseable ---
    return RuleComponent(
        component_type="NOTE",
        specific_process_text=t,
        normalized_expression=None,
        confidence=0.0,  # Zero confidence = definitely needs human review
    )
```

### STAGE 6: Pathway Construction

**Goal:** Assemble the components from Stage 5 into executable `eligibility_rule_pathway` records with the `expression_json` structure that the engine expects.

This is where you build the AND/OR tree that the `expression_evaluator` will execute at runtime.

```python
import json

def build_pathways(components: list[RuleComponent], psr_id: str) -> list[dict]:
    """
    Build eligibility_rule_pathway records from decomposed components.
    
    The expression_json structure must match what the ExpressionEvaluator expects:
    {
        "pathway_code": "CTH",
        "variables": [
            {"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}
        ],
        "expression": {
            "op": "all",   // or "any"
            "args": [...]
        }
    }
    """
    pathways = []
    
    # Group components by OR-separation
    # Components with operator_type "or" start a new pathway
    # Components with operator_type "and" or "standalone" belong to the current pathway
    current_pathway_components = []
    pathway_groups = []
    
    for comp in components:
        if comp.operator_type == "or" and current_pathway_components:
            pathway_groups.append(current_pathway_components)
            current_pathway_components = [comp]
        else:
            current_pathway_components.append(comp)
    
    if current_pathway_components:
        pathway_groups.append(current_pathway_components)
    
    for group_idx, group in enumerate(pathway_groups):
        pathway = build_single_pathway(group, psr_id, group_idx + 1)
        if pathway:
            pathways.append(pathway)
    
    return pathways


def build_single_pathway(
    components: list[RuleComponent],
    psr_id: str,
    priority: int
) -> dict:
    """Build one pathway from a group of AND-connected components."""
    
    # Determine pathway code from primary component
    primary = components[0]
    pathway_code = primary.component_type
    if len(components) > 1:
        pathway_code = "+".join(c.component_type for c in components)
    
    # Build variables list
    variables = []
    needs_vnom = any(c.component_type == "VNM" for c in components)
    needs_va = any(c.component_type == "VA" for c in components)
    
    if needs_vnom:
        variables.append({
            "name": "vnom_percent",
            "formula": "non_originating / ex_works * 100"
        })
    if needs_va:
        variables.append({
            "name": "va_percent",
            "formula": "(ex_works - non_originating) / ex_works * 100"
        })
    
    # Build expression tree
    if len(components) == 1:
        # Single component — expression is the component's expression directly
        expr = json.loads(components[0].normalized_expression) if components[0].normalized_expression else None
    else:
        # Multiple AND-connected components
        args = []
        for c in components:
            if c.normalized_expression:
                args.append(json.loads(c.normalized_expression))
        expr = {
            "op": "all",
            "args": args
        }
    
    # Determine threshold (use the first threshold-bearing component)
    threshold = None
    threshold_basis = None
    for c in components:
        if c.threshold_percent is not None:
            threshold = c.threshold_percent
            threshold_basis = c.threshold_basis
            break
    
    return {
        "psr_id": psr_id,
        "pathway_code": pathway_code,
        "pathway_label": " + ".join(c.component_type for c in components),
        "pathway_type": "specific",
        "expression_json": json.dumps({
            "pathway_code": pathway_code,
            "variables": variables,
            "expression": expr,
        }),
        "threshold_percent": threshold,
        "threshold_basis": threshold_basis,
        "tariff_shift_level": next(
            (c.tariff_shift_level for c in components if c.tariff_shift_level), None
        ),
        "allows_cumulation": True,  # default; override per specific rules
        "allows_tolerance": True,   # default de minimis tolerance
        "priority_rank": priority,
    }
```

### STAGE 7: Applicability Resolution (Inheritance)

**Goal:** Build the `hs6_psr_applicability` table that maps every HS6 code to its applicable PSR rule, handling inheritance from chapter and heading level rules.

This is critical because many rules in Appendix IV are written at the chapter or heading level, but your engine queries at the HS6 level.

```python
def build_applicability_table(psr_rules: list[dict], hs6_products: list[dict]):
    """
    For every HS6 product, determine which PSR rule applies.
    
    Resolution order (priority_rank):
    1. Direct subheading match (hs_level = 'subheading', exact hs6 code) — rank 1
    2. Heading match (hs_level = 'heading', hs6[:4] matches) — rank 2
    3. Chapter match (hs_level = 'chapter', hs6[:2] matches) — rank 3
    
    The most specific rule wins. If a product has both a heading-level
    and a subheading-level rule, the subheading rule takes priority.
    """
    applicability_rows = []
    
    # Index rules by level for efficient lookup
    subheading_rules = {}  # hs_code -> psr_rule
    heading_rules = {}     # hs_code (4-digit) -> psr_rule
    chapter_rules = {}     # hs_code (2-digit) -> psr_rule
    range_rules = []       # (start, end, psr_rule) — handled separately
    
    for rule in psr_rules:
        if rule["hs_level"] == "subheading":
            subheading_rules[rule["hs_code"]] = rule
        elif rule["hs_level"] == "heading":
            heading_rules[rule["hs_code"]] = rule
        elif rule["hs_level"] == "chapter":
            chapter_rules[rule["hs_code"]] = rule
        
        if rule.get("hs_code_start") and rule.get("hs_code_end"):
            range_rules.append((rule["hs_code_start"], rule["hs_code_end"], rule))
    
    for product in hs6_products:
        hs6 = product["hs6_code"]
        heading = hs6[:4]
        chapter = hs6[:2]
        
        # Check subheading first (most specific)
        if hs6 in subheading_rules:
            applicability_rows.append({
                "hs6_id": product["hs6_id"],
                "psr_id": subheading_rules[hs6]["psr_id"],
                "applicability_type": "direct",
                "priority_rank": 1,
            })
            continue
        
        # Check ranges
        matched_range = False
        for start, end, rule in range_rules:
            if start <= hs6 <= end:
                applicability_rows.append({
                    "hs6_id": product["hs6_id"],
                    "psr_id": rule["psr_id"],
                    "applicability_type": "range",
                    "priority_rank": 1,
                })
                matched_range = True
                break
        if matched_range:
            continue
        
        # Check heading (inherited)
        if heading in heading_rules:
            applicability_rows.append({
                "hs6_id": product["hs6_id"],
                "psr_id": heading_rules[heading]["psr_id"],
                "applicability_type": "inherited_heading",
                "priority_rank": 2,
            })
            continue
        
        # Check chapter (most general)
        if chapter in chapter_rules:
            applicability_rows.append({
                "hs6_id": product["hs6_id"],
                "psr_id": chapter_rules[chapter]["psr_id"],
                "applicability_type": "inherited_chapter",
                "priority_rank": 3,
            })
            continue
        
        # No rule found — this HS6 has no PSR coverage
        # This is important data: it means the product's RoO are still pending
        print(f"WARNING: No PSR rule found for HS6 {hs6}")
    
    return applicability_rows
```

### STAGE 8: Database Insertion

**Goal:** Insert everything into PostgreSQL in the correct order (foreign key dependencies).

```python
def insert_psr_pipeline(parsed_rows, source_id, hs_version, db):
    """
    Insert all parsed PSR data in correct FK order:
    1. psr_rule
    2. psr_rule_component
    3. eligibility_rule_pathway
    4. hs6_psr_applicability
    """
    all_rules = []
    
    for row in parsed_rows:
        # 1. Insert psr_rule
        psr_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO psr_rule
              (psr_id, source_id, hs_version, hs_code, hs_code_start, hs_code_end,
               hs_level, product_description, legal_rule_text_verbatim,
               legal_rule_text_normalized, rule_status, page_ref, row_ref)
            VALUES
              (:psr_id, :source_id, :hs_version, :hs_code, :hs_code_start, :hs_code_end,
               :hs_level, :description, :verbatim, :normalized, :status, :page, :row_ref)
        """), {
            "psr_id": psr_id,
            "source_id": source_id,
            "hs_version": hs_version,
            "hs_code": row["hs"]["hs_code"],
            "hs_code_start": row["hs"].get("hs_code_start"),
            "hs_code_end": row["hs"].get("hs_code_end"),
            "hs_level": row["hs"]["hs_level"],
            "description": row["product_description"],
            "verbatim": row["rule_text_verbatim"],
            "normalized": row.get("rule_text_normalized"),
            "status": "agreed",  # default; override from status layer
            "page": row["page"],
            "row_ref": row.get("row_ref"),
        })
        
        # 2. Insert components
        for comp in row["components"]:
            db.execute(text("""
                INSERT INTO psr_rule_component
                  (component_id, psr_id, component_type, operator_type,
                   threshold_percent, threshold_basis, tariff_shift_level,
                   specific_process_text, component_text_verbatim,
                   normalized_expression, confidence_score, component_order)
                VALUES
                  (:id, :psr_id, :type, :op, :threshold, :basis, :shift,
                   :process, :verbatim, :expr, :confidence, :order)
            """), {
                "id": str(uuid.uuid4()),
                "psr_id": psr_id,
                "type": comp.component_type,
                "op": comp.operator_type,
                "threshold": comp.threshold_percent,
                "basis": comp.threshold_basis,
                "shift": comp.tariff_shift_level,
                "process": comp.specific_process_text,
                "verbatim": comp.component_text_verbatim,
                "expr": comp.normalized_expression,
                "confidence": comp.confidence,
                "order": comp.component_order,
            })
        
        # 3. Insert pathways
        for pathway in row["pathways"]:
            db.execute(text("""
                INSERT INTO eligibility_rule_pathway
                  (pathway_id, psr_id, pathway_code, pathway_label,
                   pathway_type, expression_json, threshold_percent,
                   threshold_basis, tariff_shift_level,
                   allows_cumulation, allows_tolerance, priority_rank)
                VALUES
                  (:id, :psr_id, :code, :label, :type, :expr_json,
                   :threshold, :basis, :shift, :cumul, :toler, :priority)
            """), {
                "id": str(uuid.uuid4()),
                "psr_id": psr_id,
                "code": pathway["pathway_code"],
                "label": pathway["pathway_label"],
                "type": pathway["pathway_type"],
                "expr_json": pathway["expression_json"],
                "threshold": pathway.get("threshold_percent"),
                "basis": pathway.get("threshold_basis"),
                "shift": pathway.get("tariff_shift_level"),
                "cumul": pathway.get("allows_cumulation", True),
                "toler": pathway.get("allows_tolerance", True),
                "priority": pathway["priority_rank"],
            })
        
        all_rules.append({"psr_id": psr_id, **row["hs"]})
    
    # 4. Build and insert applicability table
    hs6_products = db.execute(text(
        "SELECT hs6_id, hs6_code FROM hs6_product WHERE hs_version = :v"
    ), {"v": hs_version}).fetchall()
    
    applicability = build_applicability_table(all_rules, hs6_products)
    for app in applicability:
        db.execute(text("""
            INSERT INTO hs6_psr_applicability
              (hs6_id, psr_id, applicability_type, priority_rank)
            VALUES (:hs6_id, :psr_id, :type, :rank)
            ON CONFLICT DO NOTHING
        """), app)
    
    db.commit()
```

### STAGE 9: Validation

**Goal:** Verify the parsed data is correct before the engine ever touches it.

```python
def validate_psr_parse(db):
    """Run all validation checks after PSR parsing."""
    errors = []
    
    # CHECK 1: Every psr_rule has at least one component
    orphan_rules = db.execute(text("""
        SELECT pr.psr_id, pr.hs_code
        FROM psr_rule pr
        LEFT JOIN psr_rule_component prc ON prc.psr_id = pr.psr_id
        WHERE prc.component_id IS NULL
    """)).fetchall()
    if orphan_rules:
        errors.append(f"CRITICAL: {len(orphan_rules)} rules have no components")
    
    # CHECK 2: Every psr_rule has at least one pathway
    no_pathway = db.execute(text("""
        SELECT pr.psr_id, pr.hs_code
        FROM psr_rule pr
        LEFT JOIN eligibility_rule_pathway erp ON erp.psr_id = pr.psr_id
        WHERE erp.pathway_id IS NULL
    """)).fetchall()
    if no_pathway:
        errors.append(f"CRITICAL: {len(no_pathway)} rules have no pathways")
    
    # CHECK 3: Low-confidence components need human review
    low_conf = db.execute(text("""
        SELECT prc.component_id, pr.hs_code, prc.component_text_verbatim,
               prc.confidence_score
        FROM psr_rule_component prc
        JOIN psr_rule pr ON pr.psr_id = prc.psr_id
        WHERE prc.confidence_score < 0.8
        ORDER BY prc.confidence_score ASC
    """)).fetchall()
    if low_conf:
        errors.append(
            f"REVIEW NEEDED: {len(low_conf)} components have confidence < 0.8"
        )
        for row in low_conf:
            print(f"  HS {row.hs_code}: '{row.component_text_verbatim}' "
                  f"(confidence: {row.confidence_score})")
    
    # CHECK 4: Pathway expression_json is valid JSON
    bad_json = db.execute(text("""
        SELECT pathway_id, pathway_code, expression_json
        FROM eligibility_rule_pathway
        WHERE expression_json IS NOT NULL
          AND NOT (expression_json::jsonb IS NOT NULL)
    """)).fetchall()
    if bad_json:
        errors.append(f"CRITICAL: {len(bad_json)} pathways have invalid JSON")
    
    # CHECK 5: VNM thresholds are between 0 and 100
    bad_thresholds = db.execute(text("""
        SELECT component_id, threshold_percent
        FROM psr_rule_component
        WHERE threshold_percent IS NOT NULL
          AND (threshold_percent < 0 OR threshold_percent > 100)
    """)).fetchall()
    if bad_thresholds:
        errors.append(f"CRITICAL: {len(bad_thresholds)} components have invalid thresholds")
    
    # CHECK 6: Coverage report
    total_hs6 = db.execute(text(
        "SELECT COUNT(*) FROM hs6_product WHERE hs_version = 'HS2017'"
    )).scalar()
    covered_hs6 = db.execute(text(
        "SELECT COUNT(DISTINCT hs6_id) FROM hs6_psr_applicability"
    )).scalar()
    coverage_pct = (covered_hs6 / total_hs6 * 100) if total_hs6 > 0 else 0
    
    print(f"\n=== PSR PARSE VALIDATION REPORT ===")
    print(f"Total HS6 codes:    {total_hs6}")
    print(f"PSR coverage:       {covered_hs6} ({coverage_pct:.1f}%)")
    print(f"Errors found:       {len(errors)}")
    for e in errors:
        print(f"  - {e}")
    
    return errors
```

### STAGE 10: Human Review Queue

**Goal:** Build a review workflow for rows the parser couldn't handle with full confidence.

The parser assigns a `confidence_score` to every component. Anything below 1.0 needs human eyes.

```python
def generate_review_queue(db):
    """
    Export rows needing human review to a CSV that a domain expert
    can fill in and feed back into the system.
    """
    rows = db.execute(text("""
        SELECT 
            pr.hs_code,
            pr.product_description,
            pr.legal_rule_text_verbatim,
            pr.page_ref,
            prc.component_text_verbatim,
            prc.component_type,
            prc.confidence_score,
            prc.normalized_expression
        FROM psr_rule_component prc
        JOIN psr_rule pr ON pr.psr_id = prc.psr_id
        WHERE prc.confidence_score < 1.0
        ORDER BY prc.confidence_score ASC, pr.hs_code ASC
    """)).fetchall()
    
    # Export as CSV for review
    with open("psr_review_queue.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "hs_code", "product_description", "legal_rule_text",
            "page_ref", "component_text", "parsed_type", "confidence",
            "parsed_expression",
            # Columns for the reviewer to fill in:
            "corrected_type", "corrected_threshold", "corrected_basis",
            "corrected_expression", "reviewer_notes"
        ])
        for row in rows:
            writer.writerow([
                row.hs_code, row.product_description, row.legal_rule_text_verbatim,
                row.page_ref, row.component_text_verbatim, row.component_type,
                row.confidence_score, row.normalized_expression,
                "", "", "", "", ""  # blank columns for reviewer
            ])
    
    print(f"Review queue exported: {len(rows)} components need review")
    print(f"File: psr_review_queue.csv")
```

---

# PART 5: L4 — STATUS ASSERTIONS (Narrative Extraction)

## What you're building

The `status_assertion` table. This tracks whether rules, schedules, and corridors are agreed, pending, provisional, etc.

## Where the data comes from

- Ministerial decisions and communiqués
- Negotiation status reports
- Official AfCFTA implementation updates
- The e-Tariff Book metadata

## Practical approach for v0.1

Status extraction from narrative documents is genuinely hard NLP. For v0.1, take a pragmatic shortcut:

1. **Manual entry for known statuses.** Your five countries' corridor statuses are known from public AfCFTA reporting. Enter these by hand.

2. **Pattern-match on key phrases** in status documents:

```python
STATUS_PATTERNS = [
    (r"(?i)pending\s+(?:agreement|negotiation|finalization)", "pending"),
    (r"(?i)provisionally?\s+(?:applied|in\s+(?:force|effect))", "provisional"),
    (r"(?i)agreed\s+(?:by|at|during)", "agreed"),
    (r"(?i)in\s+force\s+(?:from|since|as\s+of)", "in_force"),
    (r"(?i)subject\s+to\s+(?:review|finalization)", "under_review"),
    (r"(?i)not\s+yet\s+operational", "not_yet_operational"),
    (r"(?i)excluded", "excluded"),
    (r"(?i)sensitive\s+(?:product|list)", "sensitive"),
]
```

3. **Tag each assertion with provenance** (which document, which page, what date).

This is one area where starting manually and automating later is the right call.

---

# PART 6: RECOMMENDED WORKFLOW FOR A FIRST-TIMER

## Week 1: Foundation
- Set up PostgreSQL and run the DDL migrations
- Load the HS6 backbone (Part 2)
- Register your source documents (Part 1)

## Week 2: First Vertical Slice
- Pick ONE tariff schedule (Ghana or Nigeria — whichever is cleanest)
- Parse it end-to-end (Part 3)
- Hand-enter 10-15 PSR rules for products you care about
- Validate with SQL queries

## Week 3: Parser Development
- Build the PDF table extractor for Appendix IV (Stages 1-2)
- Run it and dump to CSV for manual review
- Fix extraction issues

## Week 4: Rule Decomposition
- Build the rule decomposer (Stages 3-6)
- Process all extracted rows
- Generate the review queue
- Fix low-confidence parses

## Week 5: Applicability and Validation
- Build the applicability table (Stage 7)
- Run all validation checks (Stage 9)
- Insert remaining tariff schedules
- Manual status entries for v0.1 corridors

## Week 6: Integration
- Connect the parsed data to the API layer
- Test the rule lookup endpoint
- Test the tariff lookup endpoint
- Run the eligibility engine against your test cases

---

# COMMON PITFALLS (From Experience)

1. **Don't try to parse everything perfectly on the first pass.** Get 80% right automatically, flag the rest for manual review. A zero-confidence component that gets reviewed is infinitely better than a wrong component with false confidence.

2. **Always keep the verbatim text.** When you find a parsing bug six months from now, you'll need to re-derive the structured data from the original text. If you only kept the normalized version, you're stuck.

3. **The "or" vs "and" distinction is life-or-death for your engine.** "CTH or MaxNOM 55%" means the exporter only needs ONE of those. "CTH and MaxNOM 55%" means they need BOTH. Getting this wrong produces wrong eligibility decisions. When in doubt, flag for review rather than guessing.

4. **PDF table extraction will break.** Every PDF is different. Budget time for manual fixes. The tools get you 70-90% of the way; the last 10-30% is manual work.

5. **Inheritance matters.** If Chapter 11 says "WO" and heading 1103 says "CTH", then 1103.11 uses CTH (more specific wins). But if 1103.11 has no specific rule and heading 1103 has no rule either, then 1103.11 inherits the Chapter 11 "WO" rule. Getting inheritance wrong means wrong eligibility answers.

6. **Test with real cases early.** Don't wait until all parsing is done. As soon as you have 5 products parsed, run them through the eligibility engine. You'll find parsing bugs much faster when you see wrong engine outputs than when you're staring at database rows.
