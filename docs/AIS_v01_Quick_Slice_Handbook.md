# AIS v0.1 Quick Vertical Slice — Build Handbook

> **Goal**: Get a fully working end-to-end demo — 5+ HS6 products evaluated across the GHA↔CMR corridor — with eligibility decisions, tariff outcomes, failure reasoning, and evidence checklists.
>
> **Time estimate**: 3–5 working days
>
> **Prerequisite**: Engine is built and tested (67 tests passing, all services wired, API endpoints live, running on seed data).

---

## Table of contents

1. [Overview and build sequence](#1-overview-and-build-sequence)
2. [Step 1 — Load the HS6 backbone (L1)](#2-step-1--load-the-hs6-backbone-l1)
3. [Step 2 — Load the tariff CSVs (L3)](#3-step-2--load-the-tariff-csvs-l3)
4. [Step 3 — Hand-enter PSR rules (L2)](#4-step-3--hand-enter-psr-rules-l2)
5. [Step 4 — Load status assertions (L4)](#5-step-4--load-status-assertions-l4)
6. [Step 5 — Seed evidence requirements (L5)](#6-step-5--seed-evidence-requirements-l5)
7. [Step 6 — Integration test](#7-step-6--integration-test)
8. [Validation checklist](#8-validation-checklist)
9. [What this unlocks](#9-what-this-unlocks)

---

## 1. Overview and build sequence

The engine already works — it just has no real data. Every service, repository, and API endpoint is wired and tested against seed data. The remaining work is loading real data into the seven database layers in foreign-key order.

The key insight: your v0.1 success criteria only require 5+ products across 2+ corridors. You already have tariff data for GHA↔CMR (the only corridor UNCTAD had data for). So you focus everything on that one corridor pair, hand-enter enough PSR rules to cover the products in that corridor, and prove the architecture end-to-end.

**Build sequence (strict FK dependency order):**

```
Step 1: hs6_product              (L1 — backbone, everything joins on this)
   ↓
Step 2: source_registry          (provenance — referenced by L3, L4, L5)
        tariff_schedule_header   (L3 — corridor context)
        tariff_schedule_line     (L3 — product-level rates)
        tariff_schedule_rate_by_year (L3 — year-by-year phase-down)
   ↓
Step 3: psr_rule                 (L2 — product-specific rules)
        psr_rule_component       (L2 — decomposed rule parts)
        eligibility_rule_pathway (L2 — executable expression trees)
        hs6_psr_applicability    (L2 — which rule applies to which HS6)
   ↓
Step 4: status_assertion         (L4 — rule/corridor/schedule statuses)
   ↓
Step 5: evidence_requirement     (L5 — required documents per rule type)
   ↓
Step 6: POST /v1/assessments     (integration test — prove it all works)
```

---

## 2. Step 1 — Load the HS6 backbone (L1)

**Time**: ~2 hours
**Table**: `hs6_product`
**Why first**: Every other table joins on `hs_version + hs6_id`. Without this, nothing cross-references.

### 2.1 Obtain the HS2017 nomenclature

You need a CSV or Excel file with the full HS2017 6-digit nomenclature. Sources:

- UN COMTRADE reference tables (free download from https://comtrade.un.org)
- WCO HS nomenclature (requires registration)
- The HS codes already present in your UNCTAD tariff extraction data (partial — only covers codes in the GHA↔CMR corridor)

If you cannot find a full HS2017 download quickly, you can bootstrap from your UNCTAD data. Open `tariff_schedule_line.csv` and extract the unique HS6 codes:

```python
import pandas as pd

df = pd.read_csv("data/staged/tarrifs/tariff_schedule_line.csv")
hs6_codes = df["hs_code"].str[:6].drop_duplicates().sort_values()
print(f"Unique HS6 codes from tariff data: {len(hs6_codes)}")
```

This gives you the ~5,000+ HS6 codes that appear in the GHA↔CMR corridor. For a v0.1 demo this is sufficient. You can load the full WCO nomenclature later.

### 2.2 Prepare the data

Whether you have a full nomenclature file or are bootstrapping from the tariff data, you need to produce rows matching this schema:

```
hs6_id        UUID (auto-generated)
hs_version    "HS2017"
hs6_code      "010121"              (6 digits, zero-padded, no dots)
hs6_display   "0101.21"             (dotted display format)
chapter       "01"                  (first 2 digits)
heading       "0101"                (first 4 digits)
description   "Horses; live, pure-bred breeding animals"
section       null                  (optional for v0.1)
section_name  null                  (optional for v0.1)
```

### 2.3 Cleaning script

Create this as `scripts/load_hs6_backbone.py`:

```python
"""
scripts/load_hs6_backbone.py
Load HS6 backbone from tariff extraction data or full nomenclature CSV.
"""
import csv
import uuid
import sys
from pathlib import Path

def load_from_tariff_csv(tariff_csv_path, output_csv_path):
    """
    Extract unique HS6 codes from the tariff_schedule_line.csv
    and produce a clean hs6_product CSV.
    """
    seen = set()
    rows = []

    with open(tariff_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for record in reader:
            hs_code_raw = record.get("hs_code", "").strip()
            description = record.get("product_description", "").strip()

            # Derive HS6 from the 10-digit national tariff line
            hs6 = hs_code_raw[:6].zfill(6)

            # Skip invalid codes
            if len(hs6) != 6 or not hs6.isdigit():
                continue

            # Skip duplicates
            if hs6 in seen:
                continue
            seen.add(hs6)

            chapter = hs6[:2]
            heading = hs6[:4]
            display = f"{heading}.{hs6[4:]}"

            rows.append({
                "hs6_id": str(uuid.uuid4()),
                "hs_version": "HS2017",
                "hs6_code": hs6,
                "hs6_display": display,
                "chapter": chapter,
                "heading": heading,
                "description": description if description else f"HS {display}",
            })

    # Sort by HS6 code
    rows.sort(key=lambda r: r["hs6_code"])

    # Write output
    fieldnames = [
        "hs6_id", "hs_version", "hs6_code", "hs6_display",
        "chapter", "heading", "description",
    ]
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} HS6 codes to {output_csv_path}")


if __name__ == "__main__":
    tariff_csv = Path("data/staged/tarrifs/tariff_schedule_line.csv")
    output_csv = Path("data/staged/hs6_product.csv")

    if not tariff_csv.exists():
        print(f"ERROR: {tariff_csv} not found")
        sys.exit(1)

    load_from_tariff_csv(tariff_csv, output_csv)
```

### 2.4 Load into PostgreSQL

Use Claude Code or run manually. The SQL for loading from the CSV:

```sql
-- Option A: Direct COPY (fastest, run from psql)
\COPY hs6_product(hs6_id, hs_version, hs6_code, hs6_display, chapter, heading, description)
FROM 'data/staged/hs6_product.csv' WITH (FORMAT csv, HEADER true);

-- Option B: If COPY doesn't work, use INSERT via Python
-- (see the load script above — adapt to use your db.py connection)
```

### 2.5 Validate

```sql
-- Count: should be several thousand rows
SELECT COUNT(*) FROM hs6_product;

-- Spot check: these should exist (from your UNCTAD data)
SELECT hs6_code, hs6_display, description
FROM hs6_product
WHERE hs6_code IN ('010121', '010129', '010130', '180100', '030289')
ORDER BY hs6_code;

-- No duplicates
SELECT hs_version, hs6_code, COUNT(*)
FROM hs6_product
GROUP BY hs_version, hs6_code
HAVING COUNT(*) > 1;

-- All chapters valid (01-97)
SELECT DISTINCT chapter FROM hs6_product ORDER BY chapter;
```

---

## 3. Step 2 — Load the tariff CSVs (L3)

**Time**: ~1 hour
**Tables**: `source_registry`, `tariff_schedule_header`, `tariff_schedule_line`, `tariff_schedule_rate_by_year`
**Depends on**: Step 1 (hs6_product must be loaded first)

### 3.1 Load order (FK dependencies)

The CSVs in `data/staged/tarrifs/` must be loaded in this exact order:

```
1. source_registry.csv              → source_registry
2. tariff_schedule_header.csv       → tariff_schedule_header
3. tariff_schedule_line.csv         → tariff_schedule_line
4. tariff_schedule_rate_by_year.csv → tariff_schedule_rate_by_year
```

### 3.2 Loading with psql COPY

From Git Bash, connect to your Docker PostgreSQL and run:

```sql
\COPY source_registry(source_id, title, short_title, source_group, source_type,
  authority_tier, issuing_body, jurisdiction_scope, country_code,
  customs_union_code, publication_date, effective_date, expiry_date,
  version_label, status, language, hs_version, file_path, mime_type,
  source_url, checksum_sha256, citation_preferred, notes, created_at, updated_at)
FROM 'data/staged/tarrifs/source_registry.csv' WITH (FORMAT csv, HEADER true);

\COPY tariff_schedule_header(schedule_id, source_id, importing_state,
  exporting_scope, schedule_status, publication_date, effective_date,
  expiry_date, hs_version, category_system, notes, created_at, updated_at)
FROM 'data/staged/tarrifs/tariff_schedule_header.csv' WITH (FORMAT csv, HEADER true);

\COPY tariff_schedule_line(schedule_line_id, schedule_id, hs_code,
  product_description, tariff_category, mfn_base_rate, base_year,
  target_rate, target_year, staging_type, page_ref, table_ref, row_ref,
  created_at, updated_at)
FROM 'data/staged/tarrifs/tariff_schedule_line.csv' WITH (FORMAT csv, HEADER true);

\COPY tariff_schedule_rate_by_year(year_rate_id, schedule_line_id,
  calendar_year, preferential_rate, rate_status, source_id, page_ref,
  created_at, updated_at)
FROM 'data/staged/tarrifs/tariff_schedule_rate_by_year.csv' WITH (FORMAT csv, HEADER true);
```

### 3.3 If COPY fails

Common issues and fixes:

**"column X does not exist"** — The CSV column names might not match the table column names exactly. Check with `\d tariff_schedule_header` and compare to the CSV header row.

**"violates foreign key constraint"** — You loaded tables out of order, or the source_registry row wasn't loaded first. Check: `SELECT COUNT(*) FROM source_registry;`

**"invalid input value for enum"** — A value in the CSV doesn't match the PostgreSQL enum. The extraction script used the correct enum values from your schema, but double-check that `schedule_status` values are one of: `official`, `provisional`, `gazetted`, `superseded`, `draft`.

**File path issues on Windows** — Use forward slashes in the path, or provide the full absolute path.

### 3.4 Validate

```sql
-- Headers: should be 2 (GHA→CMR and CMR→GHA, possibly with scheme variants)
SELECT schedule_id, importing_state, exporting_scope, schedule_status
FROM tariff_schedule_header;

-- Lines: should be ~6,000 per corridor direction
SELECT h.importing_state, h.exporting_scope, COUNT(l.*)
FROM tariff_schedule_header h
JOIN tariff_schedule_line l ON l.schedule_id = h.schedule_id
GROUP BY h.importing_state, h.exporting_scope;

-- Year rates: should be ~10x the line count (10 years per line for Cat A)
SELECT COUNT(*) FROM tariff_schedule_rate_by_year;

-- Spot check a specific product's phase-down
SELECT l.hs_code, l.product_description, l.mfn_base_rate,
       r.calendar_year, r.preferential_rate
FROM tariff_schedule_line l
JOIN tariff_schedule_rate_by_year r ON r.schedule_line_id = l.schedule_line_id
WHERE l.hs_code LIKE '010121%'
ORDER BY r.calendar_year;
```

---

## 4. Step 3 — Hand-enter PSR rules (L2)

**Time**: ~1 day
**Tables**: `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway`, `hs6_psr_applicability`
**Depends on**: Step 1 (hs6_product)

This is the critical step. You are manually entering 10-15 PSR rules from Appendix IV for products that exist in the GHA↔CMR tariff data. You need enough variety to exercise the engine's different rule types: WO, CTH, VNM, and at least one OR alternative.

### 4.1 Which products to enter

Pick products from early HS chapters where the Appendix IV rules are simple and well-known. Here are 15 recommended entries covering all rule types. These HS codes are from real Appendix IV rules:

| # | HS code | Chapter | Description | Rule text | Rule type |
|---|---------|---------|-------------|-----------|-----------|
| 1 | 01 (chapter) | 01 | Live animals | WO | WO |
| 2 | 02 (chapter) | 02 | Meat and edible offal | WO | WO |
| 3 | 03 (chapter) | 03 | Fish and crustaceans | WO | WO |
| 4 | 04 (chapter) | 04 | Dairy produce, eggs, honey | WO | WO |
| 5 | 0901 (heading) | 09 | Coffee | CTH | CTH |
| 6 | 1103 (heading) | 11 | Cereal groats, meal, pellets | CTH | CTH |
| 7 | 1006 (heading) | 10 | Rice | CTH except from heading 10.06 | CTH |
| 8 | 1701 (heading) | 17 | Cane or beet sugar | CTH | CTH |
| 9 | 1801 (heading) | 18 | Cocoa beans | WO | WO |
| 10 | 1806 (heading) | 18 | Chocolate and food preps | CTH; or MaxNOM 55% (EXW) | CTH or VNM |
| 11 | 2523 (heading) | 25 | Portland cement | CTH | CTH |
| 12 | 3923 (heading) | 39 | Plastic articles for packaging | CTH; or MaxNOM 50% (EXW) | CTH or VNM |
| 13 | 4407 (heading) | 44 | Wood sawn or chipped | CTH | CTH |
| 14 | 7210 (heading) | 72 | Flat-rolled iron/steel, coated | MaxNOM 55% (EXW) | VNM |
| 15 | 8703 (heading) | 87 | Motor vehicles (pending) | MaxNOM 55% (EXW) | VNM (pending) |

**Important**: Verify these against your actual Appendix IV PDF. The rules above are representative of the real rules but you should confirm the exact wording for your five chosen demo products.

### 4.2 Source registry entry for Appendix IV

Before inserting any PSR rules, you need a source_registry entry for Appendix IV:

```sql
INSERT INTO source_registry (
  source_id, title, short_title, source_group, source_type,
  authority_tier, issuing_body, jurisdiction_scope,
  language, hs_version, file_path, mime_type, checksum_sha256,
  citation_preferred, status, notes
) VALUES (
  'a0000000-0000-0000-0000-000000000001',
  'Appendix IV — Product Specific Rules of Origin (December 2023 Compilation)',
  'APPENDIX-IV-PSR-2023',
  '02_rules_of_origin',
  'appendix',
  'binding',
  'African Union — AfCFTA Secretariat',
  'afcfta',
  'en',
  'HS2017',
  'docs/corpus/02_rules_of_origin/appendix_iv_psr_compilation_2023.pdf',
  'application/pdf',
  'manual_entry_placeholder',
  'Appendix IV to Annex 2 on Rules of Origin, AfCFTA. African Union, 2023.',
  'current',
  'Hand-entered PSR rules for v0.1 demo. To be replaced by automated parser output.'
);
```

### 4.3 Insert PSR rules

For each product, you insert four related records. Here is the complete SQL for three representative products (one WO, one CTH, one OR alternative). Follow this pattern for all 15.

**Product 1: Chapter 01 — Live animals (WO)**

```sql
-- 1a. psr_rule
INSERT INTO psr_rule (
  psr_id, source_id, hs_code, hs_level, product_description,
  legal_rule_text_verbatim, rule_status, confidence_score
) VALUES (
  'b0000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  '01',
  'chapter',
  'Live animals',
  'WO',
  'agreed',
  1.000
);

-- 1b. psr_rule_component
INSERT INTO psr_rule_component (
  component_id, psr_id, component_type, operator_type,
  component_order, normalized_expression, confidence_score
) VALUES (
  'c0000000-0000-0000-0000-000000000001',
  'b0000000-0000-0000-0000-000000000001',
  'WO',
  'standalone',
  1,
  'wholly_obtained == true',
  1.000
);

-- 1c. eligibility_rule_pathway
INSERT INTO eligibility_rule_pathway (
  pathway_id, psr_id, pathway_code, pathway_label, pathway_type,
  expression_json, allows_cumulation, allows_tolerance, priority_rank
) VALUES (
  'd0000000-0000-0000-0000-000000000001',
  'b0000000-0000-0000-0000-000000000001',
  'WO',
  'Wholly Obtained',
  'specific',
  '{"pathway_code": "WO", "variables": [], "expression": {"op": "fact_eq", "fact": "wholly_obtained", "value": true}}',
  false,
  false,
  1
);

-- 1d. hs6_psr_applicability (for ALL HS6 codes in chapter 01)
INSERT INTO hs6_psr_applicability (applicability_id, hs6_id, psr_id, applicability_type, priority_rank)
SELECT
  uuid_generate_v4(),
  hp.hs6_id,
  'b0000000-0000-0000-0000-000000000001',
  'inherited_chapter',
  3
FROM hs6_product hp
WHERE hp.hs_version = 'HS2017' AND hp.chapter = '01';
```

**Product 6: Heading 1103 — Cereal groats, meal (CTH)**

```sql
-- 6a. psr_rule
INSERT INTO psr_rule (
  psr_id, source_id, hs_code, hs_level, product_description,
  legal_rule_text_verbatim, rule_status, confidence_score
) VALUES (
  'b0000000-0000-0000-0000-000000000006',
  'a0000000-0000-0000-0000-000000000001',
  '1103',
  'heading',
  'Cereal groats, meal and pellets',
  'CTH',
  'agreed',
  1.000
);

-- 6b. psr_rule_component
INSERT INTO psr_rule_component (
  component_id, psr_id, component_type, operator_type,
  component_order, tariff_shift_level, normalized_expression, confidence_score
) VALUES (
  'c0000000-0000-0000-0000-000000000006',
  'b0000000-0000-0000-0000-000000000006',
  'CTH',
  'standalone',
  1,
  'heading',
  'tariff_heading_input != tariff_heading_output',
  1.000
);

-- 6c. eligibility_rule_pathway
INSERT INTO eligibility_rule_pathway (
  pathway_id, psr_id, pathway_code, pathway_label, pathway_type,
  expression_json, tariff_shift_level,
  allows_cumulation, allows_tolerance, priority_rank
) VALUES (
  'd0000000-0000-0000-0000-000000000006',
  'b0000000-0000-0000-0000-000000000006',
  'CTH',
  'Change of Tariff Heading',
  'specific',
  '{"pathway_code": "CTH", "variables": [], "expression": {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}}}',
  'heading',
  true,
  true,
  1
);

-- 6d. hs6_psr_applicability (for ALL HS6 codes under heading 1103)
INSERT INTO hs6_psr_applicability (applicability_id, hs6_id, psr_id, applicability_type, priority_rank)
SELECT
  uuid_generate_v4(),
  hp.hs6_id,
  'b0000000-0000-0000-0000-000000000006',
  'inherited_heading',
  2
FROM hs6_product hp
WHERE hp.hs_version = 'HS2017' AND hp.heading = '1103';
```

**Product 10: Heading 1806 — Chocolate (CTH or VNM 55%)**

This one has TWO pathways (OR alternative):

```sql
-- 10a. psr_rule
INSERT INTO psr_rule (
  psr_id, source_id, hs_code, hs_level, product_description,
  legal_rule_text_verbatim, rule_status, confidence_score
) VALUES (
  'b0000000-0000-0000-0000-000000000010',
  'a0000000-0000-0000-0000-000000000001',
  '1806',
  'heading',
  'Chocolate and other food preparations containing cocoa',
  'CTH; or MaxNOM 55% (EXW)',
  'agreed',
  1.000
);

-- 10b. psr_rule_component — CTH part
INSERT INTO psr_rule_component (
  component_id, psr_id, component_type, operator_type,
  component_order, tariff_shift_level, normalized_expression, confidence_score
) VALUES (
  'c0000000-0000-0000-0000-000000000010',
  'b0000000-0000-0000-0000-000000000010',
  'CTH',
  'standalone',
  1,
  'heading',
  'tariff_heading_input != tariff_heading_output',
  1.000
);

-- 10b2. psr_rule_component — VNM part
INSERT INTO psr_rule_component (
  component_id, psr_id, component_type, operator_type,
  component_order, threshold_percent, threshold_basis,
  normalized_expression, confidence_score
) VALUES (
  'c0000000-0000-0000-0000-000000000011',
  'b0000000-0000-0000-0000-000000000010',
  'VNM',
  'or',
  2,
  55.000,
  'ex_works',
  'vnom_percent <= 55',
  1.000
);

-- 10c. eligibility_rule_pathway — Pathway 1: CTH (try first)
INSERT INTO eligibility_rule_pathway (
  pathway_id, psr_id, pathway_code, pathway_label, pathway_type,
  expression_json, tariff_shift_level,
  allows_cumulation, allows_tolerance, priority_rank
) VALUES (
  'd0000000-0000-0000-0000-000000000010',
  'b0000000-0000-0000-0000-000000000010',
  'CTH',
  'Change of Tariff Heading',
  'specific',
  '{"pathway_code": "CTH", "variables": [], "expression": {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}}}',
  'heading',
  true,
  true,
  1
);

-- 10c2. eligibility_rule_pathway — Pathway 2: VNM 55% (fallback)
INSERT INTO eligibility_rule_pathway (
  pathway_id, psr_id, pathway_code, pathway_label, pathway_type,
  expression_json, threshold_percent, threshold_basis,
  allows_cumulation, allows_tolerance, priority_rank
) VALUES (
  'd0000000-0000-0000-0000-000000000011',
  'b0000000-0000-0000-0000-000000000010',
  'VNM',
  'Maximum Non-Originating Materials 55% (EXW)',
  'specific',
  '{"pathway_code": "VNM", "variables": [{"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}], "expression": {"op": "formula_lte", "formula": "vnom_percent", "value": 55}}',
  55.000,
  'ex_works',
  true,
  true,
  2
);

-- 10d. hs6_psr_applicability
INSERT INTO hs6_psr_applicability (applicability_id, hs6_id, psr_id, applicability_type, priority_rank)
SELECT
  uuid_generate_v4(),
  hp.hs6_id,
  'b0000000-0000-0000-0000-000000000010',
  'inherited_heading',
  2
FROM hs6_product hp
WHERE hp.hs_version = 'HS2017' AND hp.heading = '1806';
```

### 4.4 Expression JSON reference

When entering more rules, use these exact templates:

**WO (Wholly Obtained):**
```json
{
  "pathway_code": "WO",
  "variables": [],
  "expression": {
    "op": "fact_eq",
    "fact": "wholly_obtained",
    "value": true
  }
}
```

**CTH (Change of Tariff Heading):**
```json
{
  "pathway_code": "CTH",
  "variables": [],
  "expression": {
    "op": "every_non_originating_input",
    "test": {"op": "heading_ne_output"}
  }
}
```

**CTSH (Change of Tariff Subheading):**
```json
{
  "pathway_code": "CTSH",
  "variables": [],
  "expression": {
    "op": "every_non_originating_input",
    "test": {"op": "subheading_ne_output"}
  }
}
```

**VNM (Max Non-Originating Materials) — adjust the value field:**
```json
{
  "pathway_code": "VNM",
  "variables": [
    {"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}
  ],
  "expression": {
    "op": "formula_lte",
    "formula": "vnom_percent",
    "value": 55
  }
}
```

**VA (Value Added) — adjust the value field:**
```json
{
  "pathway_code": "VA",
  "variables": [
    {"name": "va_percent", "formula": "(ex_works - non_originating) / ex_works * 100"}
  ],
  "expression": {
    "op": "formula_gte",
    "formula": "va_percent",
    "value": 40
  }
}
```

**CTH + VNM combined (AND — single pathway):**
```json
{
  "pathway_code": "CTH+VNM",
  "variables": [
    {"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}
  ],
  "expression": {
    "op": "all",
    "args": [
      {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}},
      {"op": "formula_lte", "formula": "vnom_percent", "value": 50}
    ]
  }
}
```

**OR alternatives** are NOT represented inside a single expression. Instead, create separate `eligibility_rule_pathway` rows with different `priority_rank` values. The engine tries them in order; first pass wins.

### 4.5 Validate

```sql
-- PSR rules entered
SELECT psr_id, hs_code, hs_level, rule_status,
       LEFT(legal_rule_text_verbatim, 40) AS rule_text
FROM psr_rule
ORDER BY hs_code;

-- Components per rule
SELECT r.hs_code, c.component_type, c.operator_type, c.threshold_percent
FROM psr_rule r
JOIN psr_rule_component c ON c.psr_id = r.psr_id
ORDER BY r.hs_code, c.component_order;

-- Pathways per rule
SELECT r.hs_code, p.pathway_code, p.priority_rank
FROM psr_rule r
JOIN eligibility_rule_pathway p ON p.psr_id = r.psr_id
ORDER BY r.hs_code, p.priority_rank;

-- Applicability coverage: how many HS6 codes have rules?
SELECT COUNT(DISTINCT hs6_id) FROM hs6_psr_applicability;

-- Verify specific product: HS 110311 should inherit from heading 1103
SELECT hp.hs6_code, hp.description, a.applicability_type, r.legal_rule_text_verbatim
FROM hs6_psr_applicability a
JOIN hs6_product hp ON hp.hs6_id = a.hs6_id
JOIN psr_rule r ON r.psr_id = a.psr_id
WHERE hp.hs6_code = '110311';
```

---

## 5. Step 4 — Load status assertions (L4)

**Time**: ~3 hours
**Table**: `status_assertion`
**Depends on**: Steps 1-3

### 5.1 Corridor status entries

Enter manual status assertions for the GHA↔CMR corridor:

```sql
-- GHA→CMR corridor is operational
INSERT INTO status_assertion (
  status_assertion_id, source_id, entity_type, entity_key,
  status_type, status_text_verbatim,
  effective_from, confidence_score
) VALUES (
  uuid_generate_v4(),
  'a0000000-0000-0000-0000-000000000001',
  'corridor',
  'GHA:CMR',
  'in_force',
  'Ghana-Cameroon trade corridor under AfCFTA preferential treatment.',
  '2021-01-01',
  0.800
);

-- CMR→GHA corridor is operational
INSERT INTO status_assertion (
  status_assertion_id, source_id, entity_type, entity_key,
  status_type, status_text_verbatim,
  effective_from, confidence_score
) VALUES (
  uuid_generate_v4(),
  'a0000000-0000-0000-0000-000000000001',
  'corridor',
  'CMR:GHA',
  'in_force',
  'Cameroon-Ghana trade corridor under AfCFTA preferential treatment.',
  '2021-01-01',
  0.800
);
```

### 5.2 Rule status entries for pending rules

If you entered any rules with `rule_status = 'pending'` (like motor vehicles HS 87), add a status assertion:

```sql
INSERT INTO status_assertion (
  status_assertion_id, source_id, entity_type, entity_key,
  status_type, status_text_verbatim, confidence_score
) VALUES (
  uuid_generate_v4(),
  'a0000000-0000-0000-0000-000000000001',
  'psr',
  'b0000000-0000-0000-0000-000000000015',
  'pending',
  'Motor vehicles PSR (HS 87) — yet to be agreed by State Parties.',
  0.900
);
```

### 5.3 Load from the transition candidates CSV (optional enrichment)

If you want to load the 44 entries from `appendix_iv_transition_candidates.csv`, the key columns are `hs_key`, `rule_status`, and `transition_text`. Each row becomes a `status_assertion` and optionally a `transition_clause` record.

---

## 6. Step 5 — Seed evidence requirements (L5)

**Time**: ~4 hours
**Table**: `evidence_requirement`
**Depends on**: Step 3 (psr_rule entries)

Evidence requirements are template-based — they depend on the rule type, not the specific product. Enter one set per rule type:

```sql
-- WO rules require: proof of wholly obtained status
INSERT INTO evidence_requirement (
  requirement_id, source_id, entity_type, entity_key,
  requirement_type, description, mandatory
) VALUES
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'WO', 'certificate_of_origin',
   'AfCFTA Certificate of Origin (Annex 2, Appendix I)', true),
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'WO', 'supplier_declaration',
   'Supplier declaration confirming wholly obtained status', true);

-- CTH rules require: proof of tariff shift
INSERT INTO evidence_requirement (
  requirement_id, source_id, entity_type, entity_key,
  requirement_type, description, mandatory
) VALUES
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'CTH', 'certificate_of_origin',
   'AfCFTA Certificate of Origin (Annex 2, Appendix I)', true),
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'CTH', 'bill_of_materials',
   'Bill of materials showing HS codes of all inputs', true),
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'CTH', 'invoice',
   'Commercial invoice with HS classification of inputs', true);

-- VNM rules require: cost breakdown
INSERT INTO evidence_requirement (
  requirement_id, source_id, entity_type, entity_key,
  requirement_type, description, mandatory
) VALUES
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'VNM', 'certificate_of_origin',
   'AfCFTA Certificate of Origin (Annex 2, Appendix I)', true),
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'VNM', 'cost_breakdown',
   'Cost breakdown of ex-works price showing originating and non-originating content', true),
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'rule_type', 'VNM', 'valuation_support',
   'Valuation documentation supporting non-originating materials calculation', true);

-- All corridors require: transport documentation
INSERT INTO evidence_requirement (
  requirement_id, source_id, entity_type, entity_key,
  requirement_type, description, mandatory
) VALUES
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'corridor', 'GHA:CMR', 'transport_record',
   'Through bill of lading or transport documents demonstrating direct consignment', true),
  (uuid_generate_v4(), 'a0000000-0000-0000-0000-000000000001',
   'corridor', 'CMR:GHA', 'transport_record',
   'Through bill of lading or transport documents demonstrating direct consignment', true);
```

---

## 7. Step 6 — Integration test

**Time**: ~1 day
**Endpoint**: `POST /v1/assessments`

### 7.1 Start the API

```bash
cd ~/Local\ Sites/afcfta-live
python -m uvicorn app.main:app --reload --port 8000
```

### 7.2 Test case 1: WO product (should pass with wholly_obtained = true)

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "010121",
    "exporter_state": "GHA",
    "importer_state": "CMR",
    "production_facts": {
      "wholly_obtained": true
    }
  }'
```

**Expected response shape:**
```json
{
  "data": {
    "hs6_code": "010121",
    "eligible": true,
    "pathway_used": "WO",
    "rule_status": "agreed",
    "tariff_outcome": {
      "preferential_rate": "...",
      "base_rate": "...",
      "status": "official"
    },
    "failures": [],
    "missing_facts": [],
    "evidence_required": ["certificate_of_origin", "supplier_declaration"],
    "confidence_class": "complete"
  }
}
```

### 7.3 Test case 2: CTH product (should pass with tariff shift)

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "110311",
    "exporter_state": "GHA",
    "importer_state": "CMR",
    "production_facts": {
      "tariff_heading_input": "1001",
      "tariff_heading_output": "1103"
    }
  }'
```

### 7.4 Test case 3: CTH product (should FAIL — no tariff shift)

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "110311",
    "exporter_state": "GHA",
    "importer_state": "CMR",
    "production_facts": {
      "tariff_heading_input": "1103",
      "tariff_heading_output": "1103"
    }
  }'
```

**Expected**: `eligible: false`, `failure_codes: ["FAIL_CTH_NOT_MET"]`

### 7.5 Test case 4: VNM product (should pass — under threshold)

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "721049",
    "exporter_state": "GHA",
    "importer_state": "CMR",
    "production_facts": {
      "ex_works": 10000,
      "non_originating": 5000
    }
  }'
```

**Expected**: `eligible: true`, `pathway_used: "VNM"`, `vnom_percent = 50 <= 55`

### 7.6 Test case 5: OR alternative (CTH fails, VNM passes)

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "180631",
    "exporter_state": "CMR",
    "importer_state": "GHA",
    "production_facts": {
      "tariff_heading_input": "1806",
      "tariff_heading_output": "1806",
      "ex_works": 10000,
      "non_originating": 5000
    }
  }'
```

**Expected**: CTH fails (same heading), falls through to VNM pathway which passes (50% <= 55%).

### 7.7 Test case 6: Missing facts

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "110311",
    "exporter_state": "GHA",
    "importer_state": "CMR",
    "production_facts": {}
  }'
```

**Expected**: `eligible: null` or `uncertain`, `missing_facts` populated, `confidence_class: "incomplete"`

---

## 8. Validation checklist

Run these checks after completing all six steps:

```
[ ] hs6_product has 1,000+ rows
[ ] source_registry has at least 2 entries (UNCTAD + Appendix IV)
[ ] tariff_schedule_header has 2+ rows (GHA→CMR, CMR→GHA)
[ ] tariff_schedule_line has 5,000+ rows
[ ] tariff_schedule_rate_by_year has 30,000+ rows
[ ] psr_rule has 10-15 rows covering chapters 01-04 and headings across varied types
[ ] psr_rule_component has at least as many rows as psr_rule
[ ] eligibility_rule_pathway has at least as many rows as psr_rule (more if OR alternatives exist)
[ ] hs6_psr_applicability covers all HS6 codes in chapters 01-04 plus targeted headings
[ ] status_assertion has corridor status entries for GHA:CMR and CMR:GHA
[ ] evidence_requirement has entries for WO, CTH, and VNM rule types
[ ] POST /v1/assessments returns structured responses for all 6 test cases
[ ] At least one test case produces eligible: true
[ ] At least one test case produces eligible: false with failure codes
[ ] At least one test case demonstrates OR fallback
[ ] At least one test case shows missing_facts handling
```

---

## 9. What this unlocks

Once these six steps are done, you have:

1. **A working v0.1 demo** meeting all success criteria — 5+ products, 2 corridor directions, full output contract.

2. **Proof the architecture works end-to-end** — from HS6 resolution through PSR lookup, expression evaluation, tariff computation, status checking, and evidence generation.

3. **A testbed for the automated parser** — when you build the Appendix IV parser later, you can validate its output against your hand-entered rules. If the parser produces different `expression_json` for heading 1103 than what you entered by hand, that's a bug to investigate.

4. **A foundation for stakeholder conversations** — you can show a customs officer or policy analyst an actual API response for "chocolate from Ghana to Cameroon" with a real tariff rate, a real rule evaluation, and a real evidence checklist.

The next steps after this are: building the automated Appendix IV parser (scales from 15 rules to 5,000+), sourcing tariff schedules for the other 18 corridors, and acquiring the remaining corpus gaps (Agreement text, full HS2017 nomenclature).
