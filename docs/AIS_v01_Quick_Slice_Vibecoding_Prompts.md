# AIS v0.1 Quick Slice — Vibecoding Prompts

> **How to use**: Copy-paste each prompt into Claude Code in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Your AGENTS.md shell restriction still applies**: Claude Code creates files;
> you run the commands yourself.
>
> **Reference**: docs/AIS_v01_Quick_Slice_Handbook.md has the full detail behind
> each prompt.

---

## Prompt 1 — HS6 backbone loader script

```
Read docs/AIS_v01_Quick_Slice_Handbook.md section 2 ("Step 1 — Load the HS6 backbone").

Create scripts/load_hs6_backbone.py that:
1. Reads docs/corpus/06_reference_data/hs2017/hscodes.csv — this is the WCO
   HS nomenclature file with two columns: "hscode" (10-digit codes) and
   "description" (colon-separated hierarchical description text, e.g.
   "Live horses, asses, mules and hinnies:Horses:*Pure-bred breeding animals<951>")
2. Extracts unique HS6 codes (first 6 digits of the hscode column)
3. For each unique HS6, derives:
   - chapter (first 2 digits)
   - heading (first 4 digits)
   - display format (e.g. "0101.21")
   - description: take the LAST segment after the final colon, strip leading
     asterisks (*) and any trailing angle-bracket references like "<951>".
     Example: "Live horses, asses, mules and hinnies:Horses:*Pure-bred breeding animals<951>"
     becomes "Pure-bred breeding animals"
   - If a description only has one segment (no colons), use the whole string
4. When multiple 10-digit codes map to the same HS6, keep the description
   from the FIRST row encountered for that HS6
5. Outputs a clean CSV to data/staged/hs6_product.csv with columns:
   hs6_id (UUID), hs_version ("HS2017"), hs6_code, hs6_display, chapter,
   heading, description
6. Deduplicates on hs6_code
7. Sorts by hs6_code
8. Validates: all codes are exactly 6 digits and numeric, chapters are 01-97
9. Prints a count summary at the end (expect ~5,000+ unique HS6 codes)

Use only csv, uuid, pathlib, sys, re from the standard library. No pandas.
Match the hs6_product table schema from docs/Concrete_Contract.md exactly.
```

**After Claude Code creates the file, you run:**
```bash
python scripts/load_hs6_backbone.py
```
# Completed - 22 March
---

## Prompt 2 — SQL load script for HS6 backbone

```
Create scripts/sql/load_hs6_backbone.sql that:
1. Loads data/staged/hs6_product.csv into the hs6_product table using \COPY
2. Then runs validation queries:
   - SELECT COUNT(*) FROM hs6_product;
   - Spot check for codes 010121, 010129, 180100
   - Check for duplicates on (hs_version, hs6_code)
   - SELECT DISTINCT chapter showing all chapters loaded

The \COPY column list must match exactly: hs6_id, hs_version, hs6_code, hs6_display, chapter, heading, description

Add a comment at the top explaining this is Step 1 of the Quick Slice build.
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/load_hs6_backbone.sql
```
(Adjust the psql connection to match your Docker setup.)

---

## Prompt 3 — SQL load script for tariff CSVs

```
Read docs/AIS_v01_Quick_Slice_Handbook.md section 3 ("Step 2 — Load the tariff CSVs").

Create scripts/sql/load_tariff_data.sql that loads the four tariff CSVs from
data/staged/tarrifs/ into PostgreSQL in FK dependency order:

1. source_registry.csv → source_registry
2. tariff_schedule_header.csv → tariff_schedule_header
3. tariff_schedule_line.csv → tariff_schedule_line
4. tariff_schedule_rate_by_year.csv → tariff_schedule_rate_by_year

Use \COPY for each. The column lists must match exactly what the extraction
script produced (see docs/UNCTAD_AIS_Field_Mapping.md for the CSV column names)
and map to the table columns from docs/Concrete_Contract.md.

After all four loads, run validation queries:
- Count rows in each table
- Show the tariff_schedule_header rows (importing_state, exporting_scope, schedule_status)
- Count tariff_schedule_line rows per corridor
- Spot check: show the phase-down for hs_code LIKE '010121%' (join line to rate_by_year, order by calendar_year)

Add clear comments explaining this is Step 2, and that Step 1 (hs6_product) must be loaded first.
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/load_tariff_data.sql
```

---

## Prompt 4 — Source registry entry for Appendix IV

```
Create scripts/sql/seed_appendix_iv_source.sql that inserts a single row into
source_registry for the Appendix IV document. Use these exact values:

- source_id: 'a0000000-0000-0000-0000-000000000001'
- title: 'Appendix IV — Product Specific Rules of Origin (December 2023 Compilation)'
- short_title: 'APPENDIX-IV-PSR-2023'
- source_group: '02_rules_of_origin'
- source_type: 'appendix'
- authority_tier: 'binding'
- issuing_body: 'African Union — AfCFTA Secretariat'
- jurisdiction_scope: 'afcfta'
- language: 'en'
- hs_version: 'HS2017'
- file_path: 'docs/corpus/02_rules_of_origin/appendix_iv_psr_compilation_2023.pdf'
- mime_type: 'application/pdf'
- checksum_sha256: 'manual_entry_placeholder'
- citation_preferred: 'Appendix IV to Annex 2 on Rules of Origin, AfCFTA. African Union, 2023.'
- status: 'current'
- notes: 'Hand-entered PSR rules for v0.1 demo. To be replaced by automated parser output.'

Use ON CONFLICT DO NOTHING so it's safe to re-run.

All enum values must match docs/Concrete_Contract.md Section 1.2 exactly.
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/seed_appendix_iv_source.sql
```

---

## Prompt 5 — PSR rule seeder script

```
Read docs/AIS_v01_Quick_Slice_Handbook.md section 4 ("Step 3 — Hand-enter PSR rules")
and docs/Expression_grammar.md for the expression_json format.

Create scripts/seed_psr_rules.py that inserts 15 hand-entered PSR rules into
the database. For each rule it must insert into FOUR tables in FK order:
psr_rule → psr_rule_component → eligibility_rule_pathway → hs6_psr_applicability.

Use the database connection from app/db/session.py or create a standalone
connection using the DATABASE_URL from .env.

The 15 rules to enter (from real Appendix IV):

CHAPTER-LEVEL (WO — Wholly Obtained):
1. Chapter 01 - Live animals - "WO" - agreed
2. Chapter 02 - Meat and edible offal - "WO" - agreed
3. Chapter 03 - Fish and crustaceans - "WO" - agreed
4. Chapter 04 - Dairy produce, eggs, honey - "WO" - agreed

HEADING-LEVEL (CTH — Change of Tariff Heading):
5. 0901 - Coffee - "CTH" - agreed
6. 1103 - Cereal groats, meal, pellets - "CTH" - agreed
7. 1006 - Rice - "CTH" - agreed
8. 1701 - Cane or beet sugar - "CTH" - agreed
9. 1801 - Cocoa beans - "WO" - agreed
10. 2523 - Portland cement - "CTH" - agreed
11. 4407 - Wood sawn or chipped - "CTH" - agreed

HEADING-LEVEL (OR alternatives — two pathways each):
12. 1806 - Chocolate and food preps - "CTH; or MaxNOM 55% (EXW)" - agreed
13. 3923 - Plastic articles for packaging - "CTH; or MaxNOM 50% (EXW)" - agreed

HEADING-LEVEL (VNM only):
14. 7210 - Flat-rolled iron/steel, coated - "MaxNOM 55% (EXW)" - agreed

HEADING-LEVEL (pending rule):
15. 8703 - Motor vehicles - "MaxNOM 55% (EXW)" - pending

For expression_json, use the exact templates from docs/Expression_grammar.md:
- WO: {"op": "fact_eq", "fact": "wholly_obtained", "value": true}
- CTH: {"op": "every_non_originating_input", "test": {"op": "heading_ne_output"}}
- VNM: {"op": "formula_lte", "formula": "vnom_percent", "value": N}
- OR alternatives: separate eligibility_rule_pathway rows with priority_rank 1 and 2

For hs6_psr_applicability:
- Chapter-level rules: applicability_type = 'inherited_chapter', priority_rank = 3,
  match all hs6_product rows WHERE chapter = XX
- Heading-level rules: applicability_type = 'inherited_heading', priority_rank = 2,
  match all hs6_product rows WHERE heading = XXXX

Use deterministic UUIDs (like 'b0000000-0000-0000-0000-000000000001' through 015)
so the script is idempotent. Add ON CONFLICT DO NOTHING on all inserts.

The source_id for all rules is 'a0000000-0000-0000-0000-000000000001' (Appendix IV).

Print a summary at the end: how many rules, components, pathways, and
applicability rows were inserted.
```

**You run:**
```bash
python scripts/seed_psr_rules.py
```

---

## Prompt 6 — PSR validation queries

```
Create scripts/sql/validate_psr_rules.sql that runs these validation queries
and prints results:

1. All PSR rules with their HS code, level, status, and rule text (truncated)
2. Components per rule: join psr_rule to psr_rule_component, show component_type,
   operator_type, threshold_percent
3. Pathways per rule: join psr_rule to eligibility_rule_pathway, show pathway_code
   and priority_rank
4. Total HS6 codes covered by applicability table
5. Specific check: HS6 code '110311' should inherit from heading 1103 — join
   hs6_psr_applicability → hs6_product → psr_rule and show the result
6. Specific check: HS6 code '180631' should inherit from heading 1806 and have
   TWO pathways (CTH and VNM) — show both
7. Count of rules by rule_status (agreed vs pending)
8. Any HS6 codes in the tariff data that have NO PSR applicability row
   (join tariff_schedule_line to hs6_product to hs6_psr_applicability, show orphans)
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/validate_psr_rules.sql
```

---

## Prompt 7 — Status assertions seeder

```
Read docs/AIS_v01_Quick_Slice_Handbook.md section 5 ("Step 4 — Load status assertions").

Create scripts/sql/seed_status_assertions.sql that inserts:

1. Corridor status for GHA→CMR: entity_type='corridor', entity_key='GHA:CMR',
   status_type='in_force', effective_from='2021-01-01', confidence_score=0.800

2. Corridor status for CMR→GHA: same pattern, entity_key='CMR:GHA'

3. A 'pending' status for the motor vehicles rule (psr_id
   'b0000000-0000-0000-0000-000000000015'): entity_type='psr',
   entity_key='b0000000-0000-0000-0000-000000000015', status_type='pending'

All rows reference source_id 'a0000000-0000-0000-0000-000000000001'.

Use uuid_generate_v4() for status_assertion_id.
Use ON CONFLICT DO NOTHING or wrap in a DO block for idempotency.

All enum values must match docs/Concrete_Contract.md Section 1.2 exactly.
Verify status_type values are from status_type_enum.
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/seed_status_assertions.sql
```

---

## Prompt 8 — Evidence requirements seeder

```
Read docs/AIS_v01_Quick_Slice_Handbook.md section 6 ("Step 5 — Seed evidence requirements").

Create scripts/sql/seed_evidence_requirements.sql that inserts template-based
evidence requirements. Check the evidence_requirement table DDL in
docs/Concrete_Contract.md first for the exact column names.

Insert requirements for each rule type:

WO rules need:
- certificate_of_origin (mandatory) - "AfCFTA Certificate of Origin (Annex 2, Appendix I)"
- supplier_declaration (mandatory) - "Supplier declaration confirming wholly obtained status"

CTH rules need:
- certificate_of_origin (mandatory)
- bill_of_materials (mandatory) - "Bill of materials showing HS codes of all inputs"
- invoice (mandatory) - "Commercial invoice with HS classification of inputs"

VNM rules need:
- certificate_of_origin (mandatory)
- cost_breakdown (mandatory) - "Cost breakdown showing originating and non-originating content"
- valuation_support (mandatory) - "Valuation documentation supporting materials calculation"

All corridors need:
- transport_record (mandatory) - "Through bill of lading demonstrating direct consignment"
  (one for GHA:CMR, one for CMR:GHA)

Use entity_type='rule_type' and entity_key='WO'/'CTH'/'VNM' for the rule-based ones.
Use entity_type='corridor' and entity_key='GHA:CMR'/'CMR:GHA' for the corridor ones.

Source_id is 'a0000000-0000-0000-0000-000000000001'.
Use uuid_generate_v4() for requirement_id.
All requirement_type values must be from requirement_type_enum in docs/Concrete_Contract.md.
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/seed_evidence_requirements.sql
```

---

## Prompt 9 — Integration test cases

```
Read docs/AIS_v01_Quick_Slice_Handbook.md section 7 ("Step 6 — Integration test").

Create tests/integration/test_quick_slice_e2e.py with 6 integration test cases
that call POST /v1/assessments with real data. Use pytest and the async test
client pattern already established in the project.

Mark all tests with @pytest.mark.integration.

Test case 1 — WO pass:
  hs6_code=010121, exporter=GHA, importer=CMR
  facts: {wholly_obtained: true}
  Assert: eligible=true, pathway_used contains "WO", confidence_class="complete"

Test case 2 — CTH pass:
  hs6_code=110311, exporter=GHA, importer=CMR
  facts: {tariff_heading_input: "1001", tariff_heading_output: "1103"}
  Assert: eligible=true, pathway_used contains "CTH"

Test case 3 — CTH fail (no tariff shift):
  hs6_code=110311, exporter=GHA, importer=CMR
  facts: {tariff_heading_input: "1103", tariff_heading_output: "1103"}
  Assert: eligible=false, failures non-empty

Test case 4 — VNM pass (under threshold):
  hs6_code=721049, exporter=GHA, importer=CMR
  facts: {ex_works: 10000, non_originating: 5000}
  Assert: eligible=true, pathway_used contains "VNM"

Test case 5 — OR fallback (CTH fails, VNM passes):
  hs6_code=180631, exporter=CMR, importer=GHA
  facts: {tariff_heading_input: "1806", tariff_heading_output: "1806",
          ex_works: 10000, non_originating: 5000}
  Assert: eligible=true, pathway_used contains "VNM" (CTH failed, fell through to VNM)

Test case 6 — Missing facts:
  hs6_code=110311, exporter=GHA, importer=CMR
  facts: {}
  Assert: missing_facts is non-empty, confidence_class="incomplete"

Use the existing test fixtures and conftest.py patterns. Reference
tests/fixtures/golden_cases.py for the expected response shape.
Check app/schemas/assessments.py for the request/response Pydantic models.
```

**You run:**
```bash
python -m pytest tests/integration/test_quick_slice_e2e.py -v
```

---

## Prompt 10 — Full validation script

```
Create scripts/sql/validate_quick_slice.sql that runs the complete validation
checklist from docs/AIS_v01_Quick_Slice_Handbook.md section 8.

For each check, print a clear label and the result:

 1. hs6_product row count (expect 1000+)
 2. source_registry row count (expect 2+)
 3. tariff_schedule_header rows with importing_state and exporting_scope
 4. tariff_schedule_line row count (expect 5000+)
 5. tariff_schedule_rate_by_year row count (expect 30000+)
 6. psr_rule row count (expect 10-15)
 7. psr_rule_component row count
 8. eligibility_rule_pathway row count
 9. hs6_psr_applicability distinct hs6_id count
10. status_assertion row count
11. evidence_requirement row count
12. psr_rule breakdown by rule_status
13. Pathway count for heading 1806 (should be 2 — CTH and VNM)
14. Any tariff lines with no HS6 backbone match (orphan check)

Format output with clear PASS/FAIL indicators where possible, e.g.:
  SELECT CASE WHEN COUNT(*) >= 1000 THEN 'PASS' ELSE 'FAIL' END AS hs6_check,
         COUNT(*) AS actual_count FROM hs6_product;
```

**You run:**
```bash
psql -U afcfta_user -d afcfta_db -f scripts/sql/validate_quick_slice.sql
```

---

## Summary — execution order

```
Prompt 1  → creates scripts/load_hs6_backbone.py     → you run it
Prompt 2  → creates scripts/sql/load_hs6_backbone.sql → you run it
Prompt 3  → creates scripts/sql/load_tariff_data.sql  → you run it
Prompt 4  → creates scripts/sql/seed_appendix_iv_source.sql → you run it
Prompt 5  → creates scripts/seed_psr_rules.py         → you run it
Prompt 6  → creates scripts/sql/validate_psr_rules.sql → you run it (check output)
Prompt 7  → creates scripts/sql/seed_status_assertions.sql → you run it
Prompt 8  → creates scripts/sql/seed_evidence_requirements.sql → you run it
Prompt 9  → creates tests/integration/test_quick_slice_e2e.py → you run it
Prompt 10 → creates scripts/sql/validate_quick_slice.sql → you run it (final check)
```

If all 10 prompts execute cleanly and the final validation passes, you have a
working v0.1 demo with real data.
