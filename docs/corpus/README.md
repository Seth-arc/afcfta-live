# AfCFTA Corpus

This directory contains the authoritative corpus of AfCFTA legal documents, operational references, and automated data source integrations.

## Overview

The corpus is organized by **source type and legal authority**, then populated through a combination of:
1. **Manual curation** — official agreement texts, annexes, and policy documents
2. **Automated extraction** — live API integrations with defined ingestion procedures

All files in this corpus feed into the AIS (AfCFTA Intelligence System) data layers, specifically:
- **L1 Backbone** (HS6 canonical product spine)
- **L2 Rules** (Appendix IV product-specific rules of origin)
- **L3 Tariffs** (tariff schedules and rates by corridor)
- **L5 Evidence** (documentation and verification requirements)

---

## Directory Structure

```
corpus/
├── README.md                            ← You are here
├── MANIFEST.md                          ← Inventory of all corpus files
├── INGESTION_LOG.md                     ← Timestamped extraction history
│
├── 00_data_sources/                     ← Automated extraction scripts
│   └── extract_unctad_afcfta.py        ← UNCTAD e-Tariff API ingester
│
├── 01_primary_law/                      ← AfCFTA treaty & binding annexes
│   ├── 36437-treaty-consolidated_text_on_cfta_-_en.pdf
│   └── [11 more — see MANIFEST.md]
│
├── 02_rules_of_origin/                  ← Appendix IV & operational guidance
│   ├── EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf
│   ├── AfCFTA RULES OF ORIGIN MANUAL.pdf
│   └── [7 more — see MANIFEST.md]
│
├── 03_tariff_schedules/                 ← Tariff books, guides, metadata
│   ├── EN - AfCFTA e-Tariff Book - User Guide.pdf
│   └── [2 more — see MANIFEST.md]
│
├── 04_operational_customs/              ← Certification, procedures
│   ├── guidelines-on-certification.pdf
│   └── [4 more — see MANIFEST.md]
│
├── 05_status_and_transition/            ← Ratification & transition data
│   └── data-UcsVQ.csv
│
├── 06_reference_data/                   ← Economic, policy, country data
│   ├── country_currency_registry.csv
│   ├── Factsheet Trading under the AfCFTA Nigeria ...pdf
│   └── [27 more — see MANIFEST.md]
│
└── 07_phase_2_protocols/                ← Digital trade, IPR, investment
    ├── Protocol to the Agreement ... on Digital Trade.pdf
    └── [6 more — see MANIFEST.md]
```

---

## Data Source Integration Pipeline

### 00_data_sources: Automated Extractions

#### UNCTAD AfCFTA e-Tariff API (`extract_unctad_afcfta.py`)

**Purpose:** Extract tariff elimination schedules for all AfCFTA corridors.

**Source Authority Tier:** 2 (Tariff schedules, operational reference)

**API Endpoint:**
```
https://afcfta-api.unctad.org/tariffseliminationnew!{reporter}&{partner}&{product}
```

**Coverage:**
- **Countries (v0.1):** CMR, CIV, GHA, NGA, SEN
- **Corridors:** All 20 permutations (5 × 4 unique pairs)
- **Product:** All HS codes (product=0)
- **Base Year:** 2021 (configurable)

**Output Tables (AIS L3):**
| Table | Columns | Purpose |
|-------|---------|---------|
| `tariff_schedule_header` | schedule_id, importing_state, exporting_scope, effective_date, hs_version | Corridor-level schedule metadata |
| `tariff_schedule_line` | schedule_line_id, hs_code, mfn_base_rate, target_rate, target_year, staging_type | Per-product tariff commitments |
| `tariff_schedule_rate_by_year` | year_rate_id, schedule_line_id, calendar_year, preferential_rate | Year-by-year phase-down rates |
| `source_registry` | source_id, title, version_label, checksum_sha256, citation_preferred | Provenance and audit trail |

**Usage:**
```bash
# Full extraction (all 20 corridors)
python 00_data_sources/extract_unctad_afcfta.py

# With custom output directory
python 00_data_sources/extract_unctad_afcfta.py --output-dir ./tariff_data

# Specific corridors only (EXPORTER-IMPORTER format)
python 00_data_sources/extract_unctad_afcfta.py --corridors GHA-NGA,CMR-GHA

# Dry run (show what would be fetched)
python 00_data_sources/extract_unctad_afcfta.py --dry-run

# Custom base year
python 00_data_sources/extract_unctad_afcfta.py --base-year 2021 --verbose
```

**Staging Type Classification:**
- `immediate` — 0% MFN or complete elimination in t0
- `linear` — equal annual reductions
- `stepwise` — non-linear reductions
- `unknown` — insufficient data

**Tariff Category Mapping (UNCTAD → AIS enum):**
| UNCTAD | AIS `tariff_category_enum` | Phase-down Timeline |
|--------|------|---|
| A | liberalised | 5yr (non-LDC) / 10yr (LDC) |
| B | sensitive | 10yr (non-LDC) / 13yr (LDC) |
| C | excluded | No elimination |
| D | sensitive | Product-specific period |
| E | excluded | Product-specific exclusion |

**Provenance:**
- Raw API responses saved to `raw_api_responses/` subdirectory as JSON
- Extraction metadata (timestamp, base_year, source_id, record counts) logged to `extraction_metadata.json`
- Checksum (SHA-256) computed over all aggregated data
- Source registry row includes citation and retrieval timestamp

**Error Handling:**
- Retry logic: 3 attempts with 5s delay on timeout/connection error
- Rate limiting: 2s between corridor requests
- HTML fallback detection: If API returns SPA (no data for corridor), gracefully skip
- Missing data prodding: Recorded in `missing_facts` output field

**Last Run:** See `INGESTION_LOG.md`

---

## File Authority & Refresh Cycles

| Directory | Authority Tier | Refresh Cycle | Mechanism |
|-----------|--------|---|---|
| `01_primary_law` | 1 (Binding legal) | Ad hoc / Amendment | Manual update on AU/UNCTAD publication — not automated |
| `02_rules_of_origin` | 1–2 (Appendix IV is legal, manual is guidance) | Annual or on amendment | Manual review of COM changes; Appendix IV tracked in version_label |
| `03_tariff_schedules` | 2 (Operational reference) | Quarterly or on submission | `extract_unctad_afcfta.py` runs on demand or schedule; version_label records run timestamp |
| `04_operational_customs` | 2–3 (Procedural guidance) | Ad hoc | Manual update on issuing body directive |
| `05_status_and_transition` | 3–4 (Analytic enrichment) | Annual | Manual update on ratification changes or AU announcements |
| `06_reference_data` | 3–4 (Analytic enrichment) | Annual or event-driven | Manual curation of economic reports and policy releases |
| `07_phase_2_protocols` | 1–2 (Binding if ratified, pending if not) | Event-driven | Manual update on protocol signature/ratification by member states |

---

## Versioning & Compatibility

### Corpus Version

The corpus follows semantic versioning tied to **AIS release versions**:
- **Corpus v0.1.x** aligns with **AIS v0.1 (Prototype)**
  - Supports 5 countries: CMR, CIV, GHA, NGA, SEN
  - Supports 20 corridors (all permutations)
  - Uses HS2017 classification
  - Appendix IV as of 2023-12-12

### HS Version Lock

All tariff and product data use **HS2017**. Do not import or mix HS2012 or HS2022 data.

### Appendix IV Version Tracking

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| COM-12 | 2023-12-12 | Current (v0.1) | `EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf` |
| COM-13 | TBD | Pending | To be integrated on AU council adoption |

---

## Using the Corpus

### For Parsing & Ingestion (Data Engineers)

1. **Route legal texts** (`01_primary_law`) through the **afcfta_corpus_parsing_agent** (see `docs/afcfta_corpus_parsing_agent_spec.md`)
2. **Extract Appendix IV rules** → normalize into `psr_rule` and `psr_rule_component` tables
3. **Extract tariff schedules** → use `extract_unctad_afcfta.py` to populate `tariff_schedule_*` tables
4. **Track versions** → record source_id and checksum in `source_registry`
5. **Log run** → append to `INGESTION_LOG.md` with timestamp, row counts, and any manual overrides

### For Assessment Logic (Backend Engineers)

Use the **source_id** from ingestion to trace any tariff or rule decision back to:
- Original legal text (via `legal_provision` → source file)
- Exact API response (raw JSON in `raw_api_responses/`)
- Parsing methodology (via `afcfta_corpus_parsing_agent_spec.md`)
- Checksum validation (SHA-256 in `source_registry`)

**Never hardcode tariff rates or rules.** Always query through the appropriate service layer:
- `tariff_resolution_service` for rates
- `rule_resolution_service` for PSR lookups
- `evidence_service` for documentation requirements

### For Audit & Compliance (Legal/Governance)

1. Check `INGESTION_LOG.md` for last update timestamp
2. Verify `source_registry.checksum_sha256` matches known-good value
3. Trace back to original source document via `legal_provision.source_id`
4. Review `MANIFEST.md` for file version and authority tier

---

## Adding New Data Sources

To ingest a new tariff schedule, trade baseline, or reference dataset:

1. **Create a script** in `00_data_sources/` following the pattern of `extract_unctad_afcfta.py`:
   - Define source authority tier and refresh cycle
   - Implement retry & rate-limiting logic
   - Preserve raw responses for provenance
   - Compute SHA-256 checksums
   - Generate `source_registry` row

2. **Update MANIFEST.md**:
   - Add new file to appropriate category
   - Populate "Source" and "API/Endpoint" columns
   - Link to ingestion script

3. **Update INGESTION_LOG.md**:
   - Record extraction timestamp
   - Note row counts and success/fail counts
   - Flag any manual reconciliation steps

4. **Document in README.md**:
   - Add section under "Automated Extractions"
   - Explain output tables and schema mapping
   - Provide usage examples

---

## Maintenance & Cleanup

### Deduplication

Duplicate files are documented in `MANIFEST.md` under "Duplicate Files". They are intentionally preserved in multiple categories to support:
- **Legal cross-reference workflows** (find all versions of Appendix I)
- **Operational checklists** (Appendix I for both rules AND customs certification)
- **Audit trails** (multiple reference copies for reconciliation)

**Do not consolidate or delete duplicates without governance approval.**

### Out-of-Date Documents

When a document is superseded:
1. Mark it as "superseded" in `MANIFEST.md`
2. Add a "Supersedes" column pointing to replacement
3. Keep the old file (for audit trail)
4. Do not delete

Example:
```
| Filename | Status | Supersedes | Replaced By |
| EN-APPENDIX-IV-AS-AT-COM-11-JUNE-2023.pdf | superseded | — | EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf |
```

---

## References

| Document | Purpose |
|----------|---------|
| `docs/Concrete_Contract.md` | AIS schema (tables, enums, constraints) |
| `docs/afcfta_corpus_parsing_agent_spec.md` | Parsing rules for legal texts → executable rules |
| `docs/Join_Strategy.md` | How to query corpus-derived tables |
| `app/core/countries.py` | Locked list of v0.1 countries |
| `INGESTION_LOG.md` | Historical record of all extractions |
| `extract_unctad_afcfta.py` | UNCTAD integration logic |

---

## Questions?

- **"What version of Appendix IV is in the system?"** → Check `MANIFEST.md` for date, then `INGESTION_LOG.md` for when it was loaded
- **"Who changed the tariff data?"** → Check `source_registry.source_id` and trace back to extraction run in `INGESTION_LOG.md`
- **"Is this tariff rate current?"** → Check `source_registry.status` and `effective_date`
- **"I need to add Nigeria's new schedule"** → Use or extend `extract_unctad_afcfta.py`; update `MANIFEST.md` and `INGESTION_LOG.md`

**Last updated:** 2026-03-22