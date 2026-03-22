# Appendix IV Parser — Vibecoding Prompts

> **How to use**: Copy-paste each prompt into Claude Code in order. Run the
> commands it tells you to run. Each prompt depends on the one before it.
>
> **Primary references** (Claude Code should read these):
> - `docs/afcfta_corpus_parsing_agent_spec.md` — agent-executable spec with
>   complete DDL, constants, test vectors, and module specifications
> - `docs/corpus_parsing_guide.md` — step-by-step parsing guide with code
> - `docs/Expression_grammar.md` — expression_json format specification
> - `docs/Concrete_Contract.md` — database schema and enum values
>
> **Input PDF**: `docs/corpus/02_rules_of_origin/EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf`
>
> **Output tables**: `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway`,
>   `hs6_psr_applicability`
>
> **Existing data**: The quick slice already loaded 15 hand-entered rules. The
>   parser will replace these with the full automated extraction. Clear the
>   hand-entered data before loading parser output.

---

## Prompt 1 — PDF table extractor

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 7 (MODULE 4 —
appendix_iv_extractor.py) and docs/corpus_parsing_guide.md PART 4 Stage 1.

Create scripts/parsers/appendix_iv_extractor.py that:

1. Opens docs/corpus/02_rules_of_origin/EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf
   using pdfplumber
2. Extracts tables from every page
3. For each table row, captures: page number, raw HS code text, raw product
   description, raw qualifying rule text
4. Handles multi-line rows (where rule text spans multiple lines within a cell)
   by concatenating them
5. Handles merged cells (section/chapter headers that span the full row) by
   detecting them and tagging as header rows
6. Outputs a CSV to data/staged/extracted_tables/appendix_iv_raw.csv with columns:
   page_num, row_index, raw_hs_code, raw_description, raw_rule_text, row_type
   (where row_type is 'data', 'header', or 'note')
7. Prints extraction stats: total pages scanned, tables found, data rows
   extracted, header rows, note rows

Use pdfplumber only (already installed). Handle edge cases:
- Empty cells
- Rows where the HS code cell is empty (continuation of previous row)
- Footnote numbers embedded in text (e.g. "692", "077" concatenated)
- Pages with no tables (skip silently)

Do NOT attempt to parse or normalize HS codes or rule text — just extract raw
text faithfully. That's for subsequent modules.
```

**You run:**
```bash
python scripts/parsers/appendix_iv_extractor.py
```
Review `data/staged/extracted_tables/appendix_iv_raw.csv` — open in a
spreadsheet and spot-check 20-30 rows across different chapters.
# Completed - 22 March
---

## Prompt 2 — Row classifier

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 8 (MODULE 5 —
psr_row_classifier.py) and docs/corpus_parsing_guide.md PART 4 Stage 2.

Create scripts/parsers/psr_row_classifier.py that:

1. Reads data/staged/extracted_tables/appendix_iv_raw.csv
2. For each row, classifies it as one of:
   - 'section_header': Section title (e.g. "Section I — Live Animals")
   - 'chapter_header': Chapter title (e.g. "Chapter 1")
   - 'rule_row': A row containing an HS code and a qualifying rule
   - 'continuation': A row that continues the rule text from the previous row
     (empty HS code, non-empty rule text)
   - 'note': A footnote or annotation row
   - 'skip': Empty or irrelevant row
3. For rule_row and continuation types, also detects:
   - Whether the rule text contains "Yet to be agreed" or similar pending
     language → tag as pending_flag=True
   - Whether the rule text contains transition language ("for X years",
     "after which") → tag as transition_flag=True
4. Merges continuation rows into their parent rule_row (concatenate rule text)
5. Outputs data/staged/raw_csv/appendix_iv_classified.csv with columns:
   page_num, raw_hs_code, raw_description, raw_rule_text, row_type,
   pending_flag, transition_flag, parent_row_index
6. Prints stats: total rows processed, rule rows, continuations merged,
   pending rules, transition rules, skipped rows

Use only standard library + csv. Reference the constants in
docs/afcfta_corpus_parsing_agent_spec.md SECTION 0 for rule status patterns.
```

**You run:**
```bash
python scripts/parsers/psr_row_classifier.py
```
# Completed - 22 March
---

## Prompt 3 — HS code normalizer

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 9 (MODULE 6 —
hs_code_normalizer.py) and docs/corpus_parsing_guide.md PART 4 Stage 3.

Create scripts/parsers/hs_code_normalizer.py that:

1. Reads data/staged/raw_csv/appendix_iv_classified.csv (only row_type='rule_row')
2. For each row, parses raw_hs_code into:
   - hs_code: cleaned numeric code (dots, dashes, spaces removed)
   - hs_level: 'chapter' (2 digits), 'heading' (4 digits), or 'subheading' (6 digits)
   - hs_code_start / hs_code_end: if the raw text contains a range
     (e.g. "03.02-03.04"), split into start and end codes
   - hs_display: formatted display version (e.g. "0101.21")
3. Handles these patterns:
   - Simple: "01.02" → hs_code="0102", hs_level="heading"
   - Chapter: "Chapter 1" or just "01" → hs_code="01", hs_level="chapter"
   - Subheading: "0101.21" → hs_code="010121", hs_level="subheading"
   - Range: "03.02-03.04" → hs_code_start="0302", hs_code_end="0304"
   - "ex" prefix: "ex 09.01" → strip "ex", note it in a flag
4. Validates: all non-range codes are 2, 4, or 6 digits and fully numeric
5. Outputs data/staged/raw_csv/appendix_iv_hs_normalized.csv adding columns:
   hs_code, hs_level, hs_code_start, hs_code_end, hs_display, ex_prefix_flag
6. Rows that fail validation get confidence_score=0.0 and are preserved (for
   the review queue)
7. Prints stats: total rules, by hs_level, ranges found, ex-prefixed, failed

Use only standard library + csv + re.
```

**You run:**
```bash
python scripts/parsers/hs_code_normalizer.py
```
# Completed - 22 March
---

## Prompt 4 — Rule decomposer

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 10 (MODULE 7 —
rule_decomposer.py) and SECTION 19 (TEST VECTORS) carefully.

Also read docs/corpus_parsing_guide.md PART 4 Stages 4-5 for the regex
patterns and decomposition logic.

Create scripts/parsers/rule_decomposer.py that:

1. Reads data/staged/raw_csv/appendix_iv_hs_normalized.csv
2. For each rule_row, decomposes raw_rule_text into one or more components,
   each with:
   - component_type: one of WO, VA, VNM, CTH, CTSH, CC, PROCESS, NOTE
   - operator_type: 'standalone', 'and', 'or'
   - threshold_percent: numeric value if applicable
   - threshold_basis: 'ex_works', 'fob', or null
   - tariff_shift_level: 'heading', 'subheading', 'chapter', or null
   - specific_process_text: verbatim text for PROCESS rules
   - normalized_expression: simple text expression for the component
   - confidence_score: 0.0 to 1.0

3. Uses these detection patterns (from the agent spec):
   - "WO" or "Wholly obtained" → WO, confidence 1.0
   - "CTH" → CTH with tariff_shift_level='heading', confidence 1.0
   - "CTSH" → CTSH with tariff_shift_level='subheading', confidence 1.0
   - "CC" → CC with tariff_shift_level='chapter', confidence 1.0
   - "MaxNOM X%" or "maximum.*non-originating.*X%" → VNM, confidence 1.0
   - "minimum.*value.*added.*X%" or "RVC X%" → VA, confidence 1.0
   - "Manufacture from..." → PROCESS, confidence 0.5
   - Anything else → NOTE, confidence 0.0

4. Handles compound rules:
   - ";" or " or " between parts → operator_type='or' on the second component
   - " and " between parts → operator_type='and' on the second component
   - First component is always operator_type='standalone'

5. Handles "Yet to be agreed" → single NOTE component, confidence 0.0,
   rule_status stays 'pending'

6. Outputs data/staged/raw_csv/appendix_iv_decomposed.csv with one row per
   component (multiple rows per rule if compound):
   All columns from the input PLUS: component_order, component_type,
   operator_type, threshold_percent, threshold_basis, tariff_shift_level,
   specific_process_text, normalized_expression, confidence_score

7. Prints stats: total rules processed, by component_type, OR alternatives,
   AND combinations, low confidence (< 1.0), zero confidence

Validate against test vectors 1-7 from docs/afcfta_corpus_parsing_agent_spec.md
SECTION 19. Print PASS/FAIL for each test vector.
```

**You run:**
```bash
python scripts/parsers/rule_decomposer.py
```

---

## Prompt 5 — Pathway builder

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 11 (MODULE 8 —
pathway_builder.py) and docs/Expression_grammar.md for the exact expression_json
format.

Create scripts/parsers/pathway_builder.py that:

1. Reads data/staged/raw_csv/appendix_iv_decomposed.csv
2. Groups components by their parent rule (same hs_code + page_num)
3. For each rule, builds eligibility_rule_pathway records:
   - Components connected by 'or' → SEPARATE pathways with ascending priority_rank
   - Components connected by 'and' → SINGLE pathway with op='all' combining them
   - Standalone components → SINGLE pathway

4. For each pathway, builds the expression_json using the exact format from
   docs/Expression_grammar.md:
   - WO: {"pathway_code":"WO","variables":[],"expression":{"op":"fact_eq","fact":"wholly_obtained","value":true}}
   - CTH: {"pathway_code":"CTH","variables":[],"expression":{"op":"every_non_originating_input","test":{"op":"heading_ne_output"}}}
   - CTSH: {"pathway_code":"CTSH","variables":[],"expression":{"op":"every_non_originating_input","test":{"op":"subheading_ne_output"}}}
   - VNM: {"pathway_code":"VNM","variables":[{"name":"vnom_percent","formula":"non_originating / ex_works * 100"}],"expression":{"op":"formula_lte","formula":"vnom_percent","value":N}}
   - VA: {"pathway_code":"VA","variables":[{"name":"va_percent","formula":"(ex_works - non_originating) / ex_works * 100"}],"expression":{"op":"formula_gte","formula":"va_percent","value":N}}
   - PROCESS: {"pathway_code":"PROCESS","variables":[],"expression":null}
   - AND combos: {"pathway_code":"CTH+VNM","variables":[...],"expression":{"op":"all","args":[...]}}

5. Outputs data/processed/rules/appendix_iv_pathways.csv with columns:
   hs_code, hs_level, hs_display, product_description, legal_rule_text_verbatim,
   rule_status, pathway_code, pathway_label, pathway_type, expression_json,
   threshold_percent, threshold_basis, tariff_shift_level, allows_cumulation,
   allows_tolerance, priority_rank, confidence_score, page_ref

6. Prints stats: total rules, total pathways (should be >= rules due to OR
   alternatives), by pathway_code, with expression vs null expression

Validate expression_json output against test vectors 1-7 from
docs/afcfta_corpus_parsing_agent_spec.md SECTION 19.
```

**You run:**
```bash
python scripts/parsers/pathway_builder.py
```

---

## Prompt 6 — Applicability builder

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 12 (MODULE 9 —
applicability_builder.py) and docs/corpus_parsing_guide.md PART 4 Stage 7.

Create scripts/parsers/applicability_builder.py that:

1. Reads data/processed/rules/appendix_iv_pathways.csv for the parsed rules
2. Reads data/staged/hs6_product.csv (or queries hs6_product table) for all
   HS6 codes
3. For every HS6 code, determines which PSR rule applies using the
   inheritance resolution order:
   - Priority 1 (rank 1): Direct subheading match (hs_level='subheading',
     exact 6-digit match)
   - Priority 2 (rank 1): Range match (hs6 falls between hs_code_start and
     hs_code_end)
   - Priority 3 (rank 2): Heading match (hs_level='heading', first 4 digits match)
   - Priority 4 (rank 3): Chapter match (hs_level='chapter', first 2 digits match)
   Most specific wins. If a product has both heading and chapter rules, heading wins.

4. Outputs data/processed/rules/appendix_iv_applicability.csv with columns:
   hs6_code, hs6_id (from hs6_product), psr_hs_code (the rule's HS code),
   applicability_type ('direct', 'range', 'inherited_heading', 'inherited_chapter'),
   priority_rank

5. Prints stats:
   - Total HS6 codes in backbone
   - HS6 codes with PSR coverage (should be high — most chapters have rules)
   - HS6 codes with NO coverage (these need attention)
   - Coverage by applicability_type
   - Coverage percentage

Use data/staged/hs6_product.csv to read the HS6 backbone (avoids needing a
database connection for this step).
```

**You run:**
```bash
python scripts/parsers/applicability_builder.py
```

---

## Prompt 7 — Database inserter

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 13 (MODULE 10 —
psr_db_inserter.py).

Create scripts/parsers/psr_db_inserter.py that:

1. First CLEARS existing hand-entered PSR data (from the quick slice) in
   FK-safe order:
   - DELETE FROM hs6_psr_applicability WHERE psr_id IN (SELECT psr_id FROM psr_rule WHERE source_id = 'a0000000-0000-0000-0000-000000000001')
   - DELETE FROM eligibility_rule_pathway WHERE psr_id IN (SELECT psr_id FROM psr_rule WHERE source_id = 'a0000000-0000-0000-0000-000000000001')
   - DELETE FROM psr_rule_component WHERE psr_id IN (SELECT psr_id FROM psr_rule WHERE source_id = 'a0000000-0000-0000-0000-000000000001')
   - DELETE FROM psr_rule WHERE source_id = 'a0000000-0000-0000-0000-000000000001'

2. Then inserts parser output in FK order:
   a. psr_rule — one row per unique HS code rule from appendix_iv_pathways.csv
   b. psr_rule_component — from appendix_iv_decomposed.csv
   c. eligibility_rule_pathway — from appendix_iv_pathways.csv
   d. hs6_psr_applicability — from appendix_iv_applicability.csv

3. Uses the existing source_id 'a0000000-0000-0000-0000-000000000001'
   (Appendix IV) for all rows

4. Generates fresh UUIDs for psr_id, component_id, pathway_id, applicability_id

5. Uses ON CONFLICT DO NOTHING for idempotent re-runs

6. Uses the database connection from app/db/session.py or DATABASE_URL from .env

7. Prints insert counts for each table and any FK violation errors

All enum values must match docs/Concrete_Contract.md Section 1.2 exactly.
Specifically:
- rule_status: 'agreed', 'pending', 'partially_agreed', 'provisional', 'superseded'
- component_type: 'WO','VA','VNM','CTH','CTSH','CC','PROCESS','ALT_RULE','EXCEPTION','NOTE'
- operator_type: 'and','or','not','standalone'
- hs_level: 'chapter','heading','subheading','tariff_line'
- threshold_basis: 'ex_works','fob','value_of_non_originating_materials','customs_value','unknown'
```

**You run:**
```bash
python scripts/parsers/psr_db_inserter.py
```

---

## Prompt 8 — Validation runner

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 14 (MODULE 11 —
validation_runner.py).

Create scripts/parsers/validation_runner.py that connects to the database and
runs these checks, printing PASS/FAIL for each:

1. Row counts: psr_rule > 100 (expect 200-500+ from full Appendix IV)
2. Row counts: psr_rule_component >= psr_rule count
3. Row counts: eligibility_rule_pathway >= psr_rule count
4. Row counts: hs6_psr_applicability > 1000

5. Referential integrity: every psr_rule_component.psr_id exists in psr_rule
6. Referential integrity: every eligibility_rule_pathway.psr_id exists in psr_rule
7. Referential integrity: every hs6_psr_applicability.psr_id exists in psr_rule
8. Referential integrity: every hs6_psr_applicability.hs6_id exists in hs6_product

9. Enum validity: all psr_rule.rule_status values are in the valid set
10. Enum validity: all psr_rule_component.component_type values are in the valid set
11. Enum validity: all psr_rule.hs_level values are in the valid set

12. Expression check: count pathways with null expression_json (these are
    PROCESS/NOTE rules that need manual review)
13. Expression check: count pathways with valid JSON expression_json

14. Confidence distribution: count rules by confidence bucket
    (1.0, 0.5-0.99, 0.01-0.49, 0.0)

15. Coverage: percentage of hs6_product rows that have at least one
    applicability row

16. Specific spot checks (from Appendix IV):
    - Chapter 01 should have a WO rule
    - Heading 1806 should exist
    - At least one rule should have rule_status='pending'

Print a final summary: PASS count, FAIL count, total checks.
```

**You run:**
```bash
python scripts/parsers/validation_runner.py
```

---

## Prompt 9 — Review queue exporter

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 15 (MODULE 12 —
review_queue_exporter.py).

Create scripts/parsers/review_queue_exporter.py that:

1. Queries the database for all psr_rule rows where confidence_score < 1.0
   (join with psr_rule_component to get component-level confidence)
2. For each low-confidence rule, includes: hs_code, hs_level, product
   description, legal_rule_text_verbatim, component_type, confidence_score,
   the reason it's low confidence (PROCESS type, NOTE type, parse failure)
3. Exports to data/staged/review_queue/psr_review_queue.csv
4. Also exports a summary: data/staged/review_queue/psr_review_summary.txt
   with counts by confidence bucket and by component_type
5. Prints: total rules needing review, by category

This file is for you to review manually. Rules with confidence 0.0 (NOTE type)
definitely need human attention. Rules with 0.5 (PROCESS type) might be
parseable with more sophisticated patterns later.
```

**You run:**
```bash
python scripts/parsers/review_queue_exporter.py
```

---

## Prompt 10 — Pipeline orchestrator

```
Read docs/afcfta_corpus_parsing_agent_spec.md SECTION 18 (ORCHESTRATOR —
run_full_pipeline.py).

Create scripts/parsers/run_full_pipeline.py that runs all parser modules in
sequence:

1. appendix_iv_extractor.py    (PDF → raw CSV)
2. psr_row_classifier.py       (raw → classified)
3. hs_code_normalizer.py       (classified → HS-normalized)
4. rule_decomposer.py          (normalized → decomposed components)
5. pathway_builder.py          (components → pathways with expression_json)
6. applicability_builder.py    (pathways → HS6 applicability mapping)
7. psr_db_inserter.py          (insert everything into PostgreSQL)
8. validation_runner.py        (verify database state)
9. review_queue_exporter.py    (export low-confidence rows for review)

Each step:
- Prints a banner with the step name
- Runs the module
- Checks for the expected output file before proceeding to the next step
- If any step fails, stops and reports which step failed and why
- Tracks elapsed time per step and total

Accept a --start-from argument so you can resume from a specific step
if earlier steps already completed (e.g. --start-from 4 to skip extraction
and classification if those CSVs already exist).

Accept a --skip-insert argument to run everything except the database
insertion (useful for reviewing CSV output before committing to the DB).

Print a final summary with step timings and row counts.
```

**You run (full pipeline):**
```bash
python scripts/parsers/run_full_pipeline.py
```

**Or step by step:**
```bash
python scripts/parsers/run_full_pipeline.py --skip-insert
# review the CSVs in data/staged/ and data/processed/
python scripts/parsers/run_full_pipeline.py --start-from 7
```

---

## Prompt 11 — Re-run integration tests

```
The parser has replaced the hand-entered PSR rules with automated extraction
from the full Appendix IV. Re-run the integration tests to verify the engine
still works:

In tests/integration/test_quick_slice_e2e.py, check whether any test
assertions need updating now that the rules come from the parser instead of
hand-entered data. The key things that might differ:

- pathway_used names might be slightly different if the parser produces
  different pathway_code values than the hand-entered ones
- confidence_class might change if the parser-produced rules have different
  confidence scores
- More pathways might be available for OR-alternative products

Review each test case and adjust assertions if needed. Do not change the
test intent — only adjust expected values to match parser output.

Then add 4 new test cases that exercise parser-generated rules from chapters
NOT covered by the original quick slice:

Test 7: A textile product (chapters 50-63) — likely pending rule
Test 8: A chemical product (chapter 28-29) — likely CTH or PROCESS rule
Test 9: A machinery product (chapter 84) — likely VNM rule
Test 10: An agricultural product (chapter 06-08) — likely WO rule

Use HS6 codes that you know exist in hs6_product and have tariff data.
```

**You run:**
```bash
python -m pytest tests/integration/test_quick_slice_e2e.py -v
```

---

## Summary — execution order

```
Prompt 1  → appendix_iv_extractor.py     → PDF to raw CSV
Prompt 2  → psr_row_classifier.py        → classify and merge rows
Prompt 3  → hs_code_normalizer.py        → clean HS codes
Prompt 4  → rule_decomposer.py           → decompose rule text to components
Prompt 5  → pathway_builder.py           → build expression_json pathways
Prompt 6  → applicability_builder.py     → map rules to HS6 codes
Prompt 7  → psr_db_inserter.py           → load into PostgreSQL
Prompt 8  → validation_runner.py         → verify database state
Prompt 9  → review_queue_exporter.py     → export low-confidence for review
Prompt 10 → run_full_pipeline.py         → orchestrate all steps
Prompt 11 → update integration tests     → verify engine still works
```

**Recommended approach**: Run prompts 1-6 first (CSV-only, no DB changes).
Review the intermediate CSVs at each stage. Once you're satisfied with the
extraction quality, run prompt 7 to load into the database, then 8-9 to
validate, then 10 for the orchestrator, then 11 to re-test.

**Commit after each milestone:**
```
feat: appendix IV PDF extractor (prompt 1-2)
feat: HS code normalizer + rule decomposer (prompt 3-4)
feat: pathway builder + applicability resolver (prompt 5-6)
data: load full Appendix IV into database (prompt 7-9)
feat: parser pipeline orchestrator (prompt 10)
test: integration tests updated for parser output (prompt 11)
```
