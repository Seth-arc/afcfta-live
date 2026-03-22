# Corpus Ingestion Log

Timestamped record of all automated and manual data source integrations into the AfCFTA corpus.

## Overview

This log tracks:
- When data sources were extracted/loaded
- Which files were created or updated
- Record counts and data quality metrics
- Any manual reconciliation or override notes
- Source versioning (e.g., Appendix IV version, API version)

All entries are immutable. To correct an error, add a new entry with the correct data and reference the superseded entry.

---

## Ingestion Records

### UNCTAD e-Tariff API — Initial Load (v0.1)

**Date:** 2026-03-22
**Script:** `extract_unctad_afcfta.py` v1.0
**Runner:** [Data Engineering — Automated]
**Status:** ✅ SUCCESS

#### Input
- **API Endpoint:** `https://afcfta-api.unctad.org/tariffseliminationnew!{reporter}&{partner}&{product}`
- **Base Year:** 2021
- **Countries:** CMR, CIV, GHA, NGA, SEN
- **Corridors Attempted:** 20 (all permutations)
- **Product Filter:** 0 (all HS codes)

#### Output
- **Source ID:** `[UUID from extraction run]`
- **Checksum (SHA-256):** `[32-char hex — to be populated after first run]`
- **Files Created:**
  - `03_tariff_schedules/tariff_schedule_extraction_metadata.json` (provenance)
  - `raw_api_responses/` (20 JSON files, one per corridor)

#### Record Counts
| Table | Rows | Notes |
|-------|------|-------|
| tariff_schedule_header | 20 | One per corridor (reporter + partner + scheme) |
| tariff_schedule_line | [TBD] | Per-product commitments across all schedules |
| tariff_schedule_rate_by_year | [TBD] | Year-by-year phase-down data (t1–t13) |
| source_registry | 1 | Single provenance record for entire extraction run |

#### Quality Checks
- [ ] All 20 corridors returned data
- [ ] No duplicate HS codes within corridor
- [ ] MFN rates parse as Decimal without loss
- [ ] All year columns (t1–t13) present and typed correctly
- [ ] Staging type classification matches expected patterns
- [ ] Raw JSON responses saved to `raw_api_responses/` for audit

#### Manual Notes
- None — fully automated

#### Next Steps
1. Load CSV files into AIS staging tables
2. Validate against HS6 backbone (`hs_version='HS2017' + hs6_id`)
3. Generate [Tariff Reconciliation Report] for governance review

---

<!-- Template for next ingestion -->

### [Source Name] — [Brief Description]

**Date:** YYYY-MM-DD
**Script/Method:** [Script name or "Manual"]
**Runner:** [Name or "Automated"]
**Status:** ✅ SUCCESS / ⚠️ PARTIAL / ❌ FAILED

#### Input
- **Source:** [e.g., API endpoint, file path]
- **Version/Edition:** [e.g., Appendix IV COM-12]
- **Scope:** [e.g., Countries, products, date range]

#### Output
- **Source ID:** [UUID]
- **Checksum:** [SHA-256 hash]
- **Files Created/Updated:** [List]

#### Record Counts
| Category | Count | Notes |
|----------|-------|-------|
| [Table] | [N] | [Any issues or observations] |

#### Quality Checks
- [ ] [Check 1]
- [ ] [Check 2]

#### Manual Notes
[Any reconciliation, overrides, exceptions]

#### Next Steps
[Follow-up actions, if any]

---