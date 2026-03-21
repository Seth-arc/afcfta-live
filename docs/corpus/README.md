# Corpus — AfCFTA Intelligence System (AIS)

> **Purpose**: This folder contains the canonical document corpus that feeds the AfCFTA Intelligence System. Every document placed here is an authoritative source for rule evaluation, tariff computation, eligibility determination, and status tracking. The system cannot produce trustworthy outputs without this corpus being correctly populated and maintained.

> **Version**: v0.1 (developer handover)
>
> **Last updated**: 2026-03-19

---

## Table of Contents

1. [Architecture Context](#1-architecture-context)
2. [Source Priority Tiers](#2-source-priority-tiers)
3. [Folder Structure](#3-folder-structure)
4. [Folder Specifications](#4-folder-specifications)
   - [01_primary_law](#41-01_primary_law)
   - [02_rules_of_origin](#42-02_rules_of_origin)
   - [03_tariff_schedules](#43-03_tariff_schedules)
   - [04_operational_customs](#44-04_operational_customs)
   - [05_status_and_transition](#45-05_status_and_transition)
   - [06_reference_data](#46-06_reference_data)
5. [Extraction Requirements](#5-extraction-requirements)
6. [Use-Case-to-Folder Mapping](#6-use-case-to-folder-mapping)
7. [Minimum Viable Corpus vs Production-Grade Corpus](#7-minimum-viable-corpus-vs-production-grade-corpus)
8. [Three Parallel Stores](#8-three-parallel-stores)
9. [Naming Conventions](#9-naming-conventions)
10. [Metadata Requirements](#10-metadata-requirements)
11. [Ingestion Checklist](#11-ingestion-checklist)
12. [Change Management](#12-change-management)

---

## 1. Architecture Context

The AIS is a **deterministic RegTech decision-support system**, not a retrieval-augmented chatbot. All outputs must be structured, auditable, and reproducible. The corpus exists to populate three downstream data stores:

| Store | Purpose | Primary Folders |
|---|---|---|
| Legal text store | Verbatim citation and page retrieval for policy Q&A | `01_primary_law`, `02_rules_of_origin`, `04_operational_customs` |
| Structured PSR database | HS-based rule lookup and eligibility evaluation | `02_rules_of_origin`, `06_reference_data` |
| Structured tariff schedule database | Corridor/time-based tariff answers | `03_tariff_schedules`, `06_reference_data` |

Without the structured stores, the system will hallucinate rule status, percentages, and tariff years. Do not rely on vector search alone.

All joins across the system resolve on a single canonical spine:

```
hs_version + hs6_id
```

Every document placed in this corpus must ultimately feed into that spine.

### v0.1 Scope

- **Countries**: Nigeria, Ghana, Côte d'Ivoire, Senegal, Cameroon
- **Product resolution**: HS6 only (HS8/10 stored but not computed)
- **HS version**: Must be tracked per document — crosswalks required if sources use different vintages

---

## 2. Source Priority Tiers

The system enforces a strict citation hierarchy. When sources conflict, the higher tier wins. The parser must tag every ingested document with its tier.

| Tier | Label | Sources | Citation Weight |
|---|---|---|---|
| **Tier 1** | Binding / Canonical | Agreement, Protocol on Trade in Goods, Annexes, Appendices, official schedules, ministerial decisions/directives | Highest — legally binding |
| **Tier 2** | Authoritative Operational | AfCFTA Secretariat manuals, e-Tariff Book data, official customs notices, gazetted schedules | Operational authority — may explain Tier 1 but does not override it |
| **Tier 3** | Interpretive Support | WCO Practical Guide, tralac summaries, implementation explainers | Interpretive only — the WCO guide explicitly states it does not replace the legal texts |

**Rule**: The answer engine must prefer the legal text first, then use manuals only to explain the legal provision.

These tiers map directly to the `authority_tier_enum` in the database schema: `binding`, `official_operational`, `interpretive`, `analytic_enrichment`.

---

## 3. Folder Structure

```
corpus/
├── README.md                        ← this file
├── 01_primary_law/
│   └── README.md
├── 02_rules_of_origin/
│   └── README.md
├── 03_tariff_schedules/
│   └── README.md
├── 04_operational_customs/
│   └── README.md
├── 05_status_and_transition/
│   └── README.md
└── 06_reference_data/
    └── README.md
```

Each sub-folder contains its own `README.md` with folder-specific acceptance criteria. This top-level README governs the entire corpus.

---

## 4. Folder Specifications

---

### 4.1 `01_primary_law`

**Purpose**: The foundational legal instruments that establish the AfCFTA and define the operative rules for trade in goods. These are the highest-authority sources in the system. Every other folder's content derives its legal force from the documents here.

**Authority tier**: Tier 1 — Binding / Canonical

**Required documents**:

| Document | Description | Priority |
|---|---|---|
| Agreement Establishing the AfCFTA | The founding treaty | **Critical** |
| Protocol on Trade in Goods | Governs goods-specific provisions | **Critical** |
| Compiled Annexes to the AfCFTA Agreement | Contains the operative legal text for all trade-in-goods mechanics | **Critical** |
| Official corrigenda | Any corrections to the above instruments | As available |
| Official amendments | Formally adopted changes to the Agreement or Protocols | As available |
| Council / Assembly decisions | Decisions that change interpretation or application of the Agreement | As available |

**Key annexes within the Compiled Annexes** (the parser must handle these individually even if shipped as a single PDF):

| Annex | Subject |
|---|---|
| Annex 1 | Schedules of Tariff Concessions |
| Annex 2 | Rules of Origin |
| Annex 3 | Customs Cooperation and Mutual Administrative Assistance |
| Annex 4 | Trade Facilitation |
| Annex 5 | Non-Tariff Barriers |
| Annex 8 | Transit |
| Annex 10 | Trade Remedies |

**Parser responsibilities**:
- Preserve verbatim legal text with page references
- Tag each provision by article, annex, appendix, section, and subsection
- Record publication date and effective date
- Track supersession chains (which document replaces which)

**Downstream tables populated**: `source_registry`, `legal_provision`

---

### 4.2 `02_rules_of_origin`

**Purpose**: Everything needed to determine whether a product qualifies as originating under the AfCFTA. This is the core source set for the Rule Lookup and Eligibility Engine use cases.

**Authority tier**: Mixed — Annex 2 and Appendices are Tier 1; Manuals and Guides are Tier 2/3

**Required documents**:

| Document | Description | Tier | Priority |
|---|---|---|---|
| Annex 2 — Rules of Origin (full text) | The legal framework for origin determination | 1 | **Critical** |
| Appendix I to Annex 2 | Certificate of Origin specimen | 1 | **Critical** |
| Appendix II to Annex 2 | Origin declaration text | 1 | **Critical** |
| Appendix III to Annex 2 | Supplier declaration | 1 | **Critical** |
| Appendix IV to Annex 2 | Product-Specific Rules (PSRs) by HS chapter/heading/subheading | 1 | **Critical** |
| Agreed RoO compilations | Latest compiled set of agreed product-specific rules | 1 | **Critical** |
| Pending-RoO status lists | Official lists identifying which PSRs remain unresolved | 1 | High |
| RoO amendment decisions | Council/ministerial decisions modifying specific rules | 1 | As available |
| AfCFTA Rules of Origin Manual | Secretariat manual for interpretive mapping and implementation logic | 2 | **Critical** |
| WCO Practical Guide for the Implementation of the AfCFTA Rules of Origin | Operational interpretation guide — does NOT replace legal texts | 3 | **Critical** |

**Critical note on Appendix IV**: This is the single most important document for the Rule Lookup engine. It contains the hybrid/general plus product-specific rules organized by HS structure. The compiled annexes state that goods listed in Appendix IV qualify only if they satisfy the specific rules set out there.

**Parser responsibilities for Appendix IV** — extract per tariff line:

| Field | Description |
|---|---|
| `hs_code` | The HS code the rule applies to |
| `hs_version` | Which HS nomenclature vintage |
| `hs_level` | chapter / heading / subheading |
| `legal_rule_text_verbatim` | Exact text from the source |
| `normalized_rule_tags` | WO, VA, VNM, CTH, CTSH, PROCESS |
| `threshold_percentage` | Numeric threshold where applicable |
| `threshold_basis` | ex_works, fob, value_of_non_originating_materials, customs_value |
| `operator` | and / or / standalone |
| `exceptions_notes` | Any footnotes, exceptions, or qualifications |
| `rule_status` | agreed, pending, partially_agreed |
| `source_doc` | Source document reference |
| `page_ref` | Page number in the source |
| `paragraph_or_table_row` | Paragraph or row identifier |
| `effective_date` | When the rule entered force |
| `superseded_by` | Reference to replacement rule if applicable |

**Downstream tables populated**: `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway`, `hs6_psr_applicability`

---

### 4.3 `03_tariff_schedules`

**Purpose**: All tariff concession data needed to answer "what tariff applies between country A and country B for product X in year Y?" This is the core source set for the Tariff Engine.

**Authority tier**: Mixed — Annex 1 and official schedules are Tier 1; e-Tariff Book data is Tier 2

**Required documents**:

| Document | Description | Tier | Priority |
|---|---|---|---|
| Annex 1 — Schedules of Tariff Concessions | Legal framework for tariff liberalisation | 1 | **Critical** |
| AfCFTA e-Tariff Book export | The key operational dataset for tariff concessions and RoO access | 2 | **Critical** |
| State Party tariff schedules | National tariff offers/schedules for each v0.1 country | 1 | **Critical** |
| Customs-union schedules | ECOWAS, CEMAC schedules where they apply | 1 | High |
| Provisional schedules | Schedules not yet formally gazetted but in operational use | 1 | High |
| Gazetted domestic schedules | National gazettes or customs notices implementing AfCFTA rates | 1 | High |
| Schedule update notices | Amendments or corrections to published schedules | 1 | As available |
| MFN tariff baseline sources | National tariff book or customs tariff reference per importing state | 2 | High |
| Modalities documents | Tariff liberalisation modalities (phase-down categories, timelines) | 1 | High |
| Ministerial directives on provisional schedules | Directives governing application of provisional concessions | 1 | As available |

**v0.1 country-specific schedule requirements**:

| Country | Customs Union Context | Notes |
|---|---|---|
| Nigeria | ECOWAS | Largest economy; complex schedule |
| Ghana | ECOWAS | |
| Côte d'Ivoire | ECOWAS | Francophone legal text |
| Senegal | ECOWAS | Francophone legal text |
| Cameroon | CEMAC / ECCAS | Introduces Central Africa logic; weaker digitisation; stress-tests missing data handling |

**Parser responsibilities for tariff schedules** — extract per corridor and tariff line:

| Field | Description |
|---|---|
| `exporter_state` | ISO country code of exporting state |
| `importer_state` | ISO country code of importing state |
| `hs_code` | HS6 code |
| `mfn_base_rate` | MFN baseline rate |
| `tariff_category` | liberalised / sensitive / excluded |
| `start_year` | First year of phase-down |
| `phase_down_schedule_by_year` | Year-by-year rate reductions |
| `current_preferential_rate` | Rate applicable now |
| `target_liberalised_rate` | Final target rate |
| `target_year` | Year the target rate is reached |
| `schedule_status` | official, provisional, gazetted, superseded, draft |
| `source_doc` | Source document reference |
| `page_or_table_ref` | Page or table identifier |

**Downstream tables populated**: `tariff_schedule_header`, `tariff_schedule_line`, `tariff_schedule_rate_by_year`

---

### 4.4 `04_operational_customs`

**Purpose**: Customs cooperation instruments, certificate issuance procedures, verification protocols, and proof-of-origin administrative requirements. This is the core source set for the Evidence Readiness Engine and the Policy Q&A use case.

**Authority tier**: Mixed — Annex 3 is Tier 1; guidance documents are Tier 2/3

**Required documents**:

| Document | Description | Tier | Priority |
|---|---|---|---|
| Annex 3 — Customs Cooperation and Mutual Administrative Assistance | Legal framework for customs procedures | 1 | **Critical** |
| Annex 4 — Trade Facilitation | Facilitation provisions relevant to documentary burden | 1 | High |
| Customs cooperation guidance | Secretariat-issued implementation guidance | 2 | High |
| Certificate issuance guidance | Procedures for issuing Certificates of Origin | 2 | High |
| Verification procedures | Procedures for post-issuance verification of origin claims | 2 | High |
| National customs circulars | Country-specific implementing regulations for v0.1 states | 2 | High |
| Proof-of-origin administrative templates | Specimen forms, declaration templates | 2 | High |

**Parser responsibilities** — extract per provision:

| Field | Description |
|---|---|
| `topic_label` | valuation, cumulation, de_minimis, proof_of_origin, verification, penalties, certificate_issuance |
| `instrument` | Source instrument name |
| `article_annex_appendix_page` | Precise legal reference |
| `provision_text_verbatim` | Exact text |
| `provision_text_normalized` | Short machine summary |
| `cross_references` | Related articles/provisions |
| `jurisdictional_applicability` | Note if national implementation varies across v0.1 countries |

**Downstream tables populated**: `legal_provision`, `evidence_requirement`, `verification_question`, `document_readiness_template`

---

### 4.5 `05_status_and_transition`

**Purpose**: Documents that track what is agreed, what is pending, what is transitional, and what has changed. This is critical because the AfCFTA is a living negotiation — not all rules of origin and tariff negotiations are completed. As of the latest available data, agreed RoO cover approximately 92.4% of tariff lines, meaning the system must know when to answer "not yet operational" rather than pretending certainty.

**Authority tier**: Mixed — ministerial decisions are Tier 1; implementation bulletins are Tier 2

**Required documents**:

| Document | Description | Tier | Priority |
|---|---|---|---|
| Negotiation status reports | Official lists of agreed vs pending PSRs and tariff lines | 1 | **Critical** |
| Ministerial directives | Council of Ministers decisions on unresolved rules | 1 | **Critical** |
| Committee communiqués | Committee-level communications on negotiation progress | 1 | High |
| Guided Trade Initiative (GTI) notes | GTI implementation notes identifying what can and cannot trade | 2 | High |
| Implementation bulletins | Secretariat bulletins on operational readiness | 2 | High |
| Change logs | Records showing when a rule moved from pending to agreed, or a schedule from provisional to gazetted | 2 | **Critical** |

**Critical design note**: Every API response in the AIS must include `rule_status`, `tariff_status`, `legal_basis`, and `confidence_class`. The documents in this folder are the source of truth for those fields. If a rule's status cannot be confirmed from this folder, the system must flag `confidence_class` as incomplete.

**Parser responsibilities** — extract per status assertion:

| Field | Description |
|---|---|
| `entity_type` | psr_rule, tariff_line, schedule, provision |
| `entity_key` | The HS code or provision reference the status applies to |
| `status_type` | agreed, pending, provisional, under_review, transitional, superseded, in_force, not_yet_operational, expired |
| `effective_date` | When the status took effect |
| `expiry_date` | When the status expires (if applicable) |
| `source_doc` | Source document reference |
| `change_description` | What changed and why |

**Downstream tables populated**: `status_assertion`, `transition_clause`, `change_log`, `alert_event`

---

### 4.6 `06_reference_data`

**Purpose**: Lookup tables, crosswalks, code lists, and classification metadata that the system needs to resolve HS codes, map between nomenclature versions, identify country groupings, and apply phase-in calendars. These are not legal texts — they are the structural plumbing that makes the legal texts machine-readable.

**Authority tier**: Tier 2 / reference

**Required documents**:

| Document | Description | Priority |
|---|---|---|
| HS nomenclature tables | Full HS classification at the version used by AfCFTA sources | **Critical** |
| HS-version crosswalks | Mapping tables between HS vintages (e.g., HS2017 to HS2022) if sources use different versions | **Critical** |
| ISO country codes / AfCFTA State Party codes | Canonical country code list | **Critical** |
| Tariff category flags | Category A (liberalised immediately) / sensitive / excluded per country | High |
| LDC vs non-LDC treatment flags | Identifies which states receive LDC-specific phase-down treatment | High |
| Calendar table for phase-in years | Year-by-year calendar mapping tariff reduction milestones | High |
| Customs union membership mapping | Which countries belong to ECOWAS, CEMAC, SACU, EAC, etc. | High |

**Format guidance**: These files should be delivered as structured data (CSV, JSON, or SQL seed files) rather than PDFs. They will be loaded directly into lookup tables, not parsed from prose.

**Downstream tables populated**: `hs6_product`, `hs6_psr_applicability` (via crosswalk resolution), plus any lookup/enum tables

---

## 5. Extraction Requirements

Do not rely on vector search alone. The parser must extract structured fields from each document class. The three primary extraction schemas are:

### 5.1 PSR Extraction (from `02_rules_of_origin`)

Per tariff line, extract: `hs_code`, `hs_version`, `hs_level` (chapter/heading/subheading), `legal_rule_text_verbatim`, `normalized_rule_tags` (WO, VA, VNM, CTH, CTSH, PROCESS), `threshold_percentage`, `threshold_basis`, `operator` (and/or/standalone), `exceptions_notes`, `rule_status` (agreed/pending/partially_agreed), `source_doc`, `page_ref`, `paragraph_or_table_row`, `effective_date`, `superseded_by`.

### 5.2 Tariff Schedule Extraction (from `03_tariff_schedules`)

Per corridor and tariff line, extract: `exporter_state`, `importer_state`, `hs_code`, `mfn_base_rate`, `tariff_category`, `start_year`, `phase_down_schedule_by_year`, `current_preferential_rate`, `target_liberalised_rate`, `target_year`, `schedule_status` (official/provisional/gazetted/superseded/draft), `source_doc`, `page_or_table_ref`.

### 5.3 Legal Provision Extraction (from `01_primary_law`, `04_operational_customs`)

Per provision, extract: `topic_label` (valuation, cumulation, de_minimis, proof_of_origin, verification, penalties), `instrument`, `article_annex_appendix_page`, `provision_text_verbatim`, `provision_text_normalized` (short machine summary), `cross_references`, `jurisdictional_applicability`.

---

## 6. Use-Case-to-Folder Mapping

The system's four core use cases draw from overlapping but distinct subsets of the corpus:

| Use Case | Description | Primary Folders | Key Documents |
|---|---|---|---|
| **Rule Lookup** | Query HS6 → return PSR pathways, thresholds, legal text, rule status | `02`, `06` | Annex 2, Appendix IV, RoO Manual, WCO Guide, HS nomenclature |
| **Schedule Query** | Query corridor + HS6 + year → return preferential rate, MFN baseline, phase-in timeline | `03`, `06` | Annex 1, e-Tariff Book, State Party schedules, calendar table |
| **Policy Q&A** | Query topic → return verbatim legal provisions with cross-references | `01`, `02`, `04` | Protocol on Trade in Goods, Annex 2, Annex 3, Appendices I–III, manuals |
| **Transition Analysis** | Query HS6 or topic → return status flags, pending items, phase-down positions | `02`, `03`, `05` | Appendix IV, negotiation status lists, ministerial directives, GTI notes |

---

## 7. Minimum Viable Corpus vs Production-Grade Corpus

### Minimum Viable (required for a serious v0.1)

These nine items must be present before the system can be considered functional:

1. Agreement Establishing the AfCFTA
2. Protocol on Trade in Goods
3. Compiled Annexes
4. Annex 2 + Appendix IV (Rules of Origin + Product-Specific Rules)
5. AfCFTA Rules of Origin Manual
6. WCO Practical Guide
7. AfCFTA e-Tariff Book export
8. Available State Party tariff schedules (for the five v0.1 countries)
9. Latest pending/agreed RoO status list

### Production-Grade (for competent authorities and policy analysts)

Everything above, plus:

- National gazettes / customs notices for each v0.1 country
- Ministerial decisions affecting rules or schedules
- Negotiation status documents with full history
- Version history / amendment tracking for all Tier 1 documents
- HS crosswalk tables
- National customs procedures for certificate issuance and verification

---

## 8. Three Parallel Stores

This is the most commonly missed architectural requirement. The corpus does not feed a single data pipeline. It feeds **three parallel stores**, each with different access patterns:

| Store | Access Pattern | What It Serves | Failure Mode If Missing |
|---|---|---|---|
| **Legal text store** | Full-text retrieval by provision reference, topic label, page | Policy Q&A — verbatim citation | System cannot cite legal authority for its answers |
| **Structured PSR database** | Lookup by `hs_version` + `hs6_id` → rule components, thresholds, expressions | Rule Lookup, Eligibility Engine | System hallucinate rule status, threshold percentages, rule types |
| **Structured tariff schedule database** | Lookup by `exporter_state` + `importer_state` + `hs6_id` + `year` → rate | Tariff Engine | System hallucinates tariff rates and phase-in years |

The parser must route extracted content to the correct store. A single document may feed multiple stores (e.g., Annex 2 feeds both the legal text store and the PSR database).

---

## 9. Naming Conventions

### File naming

All files placed in this corpus must follow this pattern:

```
[source_short_title]_[version_or_date]_[language].[extension]
```

Examples:
- `afcfta_agreement_2018_en.pdf`
- `protocol_trade_in_goods_2018_en.pdf`
- `annex2_rules_of_origin_2018_en.pdf`
- `appendix_iv_psr_compilation_2024_en.pdf`
- `etariff_book_export_202503_en.csv`
- `nga_tariff_schedule_2024_en.pdf`
- `cmr_tariff_schedule_2024_fr.pdf`
- `hs_crosswalk_2017_to_2022.csv`
- `roo_status_list_202503_en.pdf`

### Language codes

Use ISO 639-1: `en` (English), `fr` (French).

### Country codes

Use ISO 3166-1 alpha-3: `NGA` (Nigeria), `GHA` (Ghana), `CIV` (Côte d'Ivoire), `SEN` (Senegal), `CMR` (Cameroon).

---

## 10. Metadata Requirements

Every document placed in this corpus must have accompanying metadata, either in a sidecar JSON file (`[filename].meta.json`) or in a central manifest (`manifest.json` at the corpus root). The metadata must include:

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | Yes | Full document title |
| `short_title` | string | Yes | Abbreviated reference name |
| `source_group` | string | Yes | Folder name (e.g., `01_primary_law`) |
| `source_type` | enum | Yes | agreement, protocol, annex, appendix, tariff_schedule, manual, etc. |
| `authority_tier` | enum | Yes | binding, official_operational, interpretive, analytic_enrichment |
| `issuing_body` | string | Yes | AfCFTA Secretariat, AU Assembly, WCO, national customs authority, etc. |
| `jurisdiction_scope` | string | Yes | continental, regional, national |
| `country_code` | string | If national | ISO alpha-3 |
| `customs_union_code` | string | If regional | ECOWAS, CEMAC, etc. |
| `publication_date` | date | Yes | When published |
| `effective_date` | date | Yes | When it entered force |
| `expiry_date` | date | If applicable | When it expires or was superseded |
| `version_label` | string | Yes | Version identifier |
| `status` | enum | Yes | current, superseded, provisional, draft, pending, archived |
| `language` | string | Yes | ISO 639-1 |
| `hs_version` | string | If applicable | e.g., HS2017, HS2022 |
| `file_path` | string | Yes | Relative path within corpus |
| `mime_type` | string | Yes | application/pdf, text/csv, etc. |
| `checksum_sha256` | string | Yes | SHA-256 hash for integrity verification |
| `supersedes` | string | If applicable | `short_title` of the document this replaces |
| `superseded_by` | string | If applicable | `short_title` of the replacement document |

This metadata maps directly to the `source_registry` table in the database schema.

---

## 11. Ingestion Checklist

Before marking a document as ingested, verify:

- [ ] File is placed in the correct sub-folder
- [ ] File follows the naming convention
- [ ] Metadata (sidecar JSON or manifest entry) is complete
- [ ] SHA-256 checksum is recorded and verified
- [ ] `authority_tier` is correctly assigned
- [ ] `hs_version` is recorded (if the document contains HS-referenced data)
- [ ] Language is correctly tagged (critical for Francophone sources from Cameroon, Côte d'Ivoire, Senegal)
- [ ] Supersession chain is recorded (does this document replace an earlier version? Is it replaced by a newer one?)
- [ ] Effective date and expiry date are set
- [ ] Parser has been run and structured output reviewed
- [ ] Extracted data has been routed to the correct downstream store(s)
- [ ] Status flags (agreed/pending/provisional/gazetted/superseded) are set for all extracted rules and schedule lines

---

## 12. Change Management

The corpus is not static. AfCFTA negotiations are ongoing, schedules are updated, and rules move from pending to agreed over time. The system must track these changes.

### When a new document is added

1. Place the file in the correct sub-folder.
2. Create or update the metadata entry.
3. If the new document supersedes an existing one, update the `superseded_by` field on the old document's metadata and set its status to `superseded`.
4. Re-run the parser for the affected sub-folder.
5. Verify that downstream tables reflect the update.
6. Record the change in the corpus change log.

### When a document is updated (new version of an existing source)

1. Do NOT overwrite the old file. Place the new version alongside it with an updated version label in the filename.
2. Update the supersession chain in metadata.
3. Re-run the parser.
4. Verify that status assertions are updated (e.g., rules that were pending may now be agreed).
5. Trigger alert generation for any active cases affected by the change.

### Change log

Maintain a `CHANGELOG.md` at the corpus root with entries in reverse chronological order:

```
## [YYYY-MM-DD] — [Brief description]
- Added: [document short_title]
- Updated: [document short_title] (v1.0 → v1.1)
- Superseded: [old document] by [new document]
- Status change: [HS code or provision] moved from [old status] to [new status]
```

---

## Appendix A — Database Schema Mapping

For developer reference, the mapping from corpus folders to primary database tables:

| Folder | Primary Tables |
|---|---|
| `01_primary_law` | `source_registry`, `legal_provision` |
| `02_rules_of_origin` | `source_registry`, `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway`, `hs6_psr_applicability` |
| `03_tariff_schedules` | `source_registry`, `tariff_schedule_header`, `tariff_schedule_line`, `tariff_schedule_rate_by_year` |
| `04_operational_customs` | `source_registry`, `legal_provision`, `evidence_requirement`, `verification_question`, `document_readiness_template` |
| `05_status_and_transition` | `source_registry`, `status_assertion`, `transition_clause`, `change_log`, `alert_event` |
| `06_reference_data` | `hs6_product`, `hs6_psr_applicability` (crosswalk resolution), lookup/enum seed tables |

---

## Appendix B — Francophone Source Handling

Cameroon, Côte d'Ivoire, and Senegal introduce Francophone legal texts. The parser must:

- Store both the original French text and any official English translation
- Tag the `language` field correctly per document
- For Cameroon specifically: expect weaker digitisation and more ambiguity — the system must handle missing or incomplete data gracefully by flagging it, never by inferring
- For CEMAC-specific instruments: tag with `customs_union_code = CEMAC` to distinguish from ECOWAS-scoped documents

---

## Appendix C — Quick Reference for Source Acquisition

| Source | Likely Acquisition Channel |
|---|---|
| AfCFTA Agreement, Protocols, Annexes | AfCFTA Secretariat website, AU legal repository |
| Appendix IV (PSRs) | AfCFTA Secretariat, compiled annex publications |
| e-Tariff Book | AfCFTA Secretariat e-Tariff portal |
| State Party schedules | National customs authorities, tralac archive |
| RoO Manual | AfCFTA Secretariat publications |
| WCO Practical Guide | WCO publications portal |
| HS nomenclature tables | WCO or national customs |
| National gazettes | Government gazette portals per country |
| Negotiation status lists | AfCFTA Secretariat, Council of Ministers communiqués |
