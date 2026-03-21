# All AGENTS.md Files for AfCFTA Intelligence System

Instructions: Split this file at each `--- FILE: path/to/AGENTS.md ---` marker.
Create the file at the indicated path. The root AGENTS.md was provided separately.

================================================================================
--- FILE: app/core/AGENTS.md ---
================================================================================

# Core Module Rules

These files are the system's reference data and type definitions. Most are
locked and must not be modified.

## Locked Files — Do Not Modify

- countries.py — v0.1 country codes, ISO mappings, bloc membership, corridors
- fact_keys.py — valid production fact types and which rule types require them
- entity_keys.py — entity key patterns for polymorphic lookups (status, evidence)
- failure_codes.py — canonical failure codes for the eligibility engine

Do not rename, restructure, reformat, add to, or "improve" these files unless
the human explicitly asks you to.

## Enums (enums.py)

- Must match docs/Concrete_Contract.md Section 1.2 exactly
- Do not add, remove, rename, or reorder any enum values
- Use the (str, Enum) pattern so values serialize cleanly in Pydantic
- If a new enum value is needed, check Concrete_Contract.md first — if it is
  not in the DDL, do not add it

## Exceptions (exceptions.py)

- All domain exceptions inherit from AISBaseException
- Each exception accepts a message (str) and optional detail (dict)
- Add new exception types if genuinely needed but do not change existing ones
- Exception names are used in API error handlers — renaming breaks the contract

================================================================================
--- FILE: app/db/models/AGENTS.md ---
================================================================================

# ORM Model Rules

Every model in this directory represents a PostgreSQL table. The DDL is the
source of truth, not the other way around.

## Column Fidelity

- Every column name, type, and constraint must match docs/Concrete_Contract.md
- Do not rename columns for "Pythonic" style (e.g., keep hs6_id, not hs6Id)
- Do not add columns that are not in the DDL
- Do not skip columns because they seem optional

## Types

- UUID primary keys: `server_default=text("uuid_generate_v4()")`
- All timestamps: `timestamptz` with `server_default=func.now()`
- Enum columns: use the Python enums from app/core/enums.py, never inline strings
- Numeric columns for rates/thresholds: use `Numeric(precision, scale)` matching DDL
- Text columns for verbatim legal text: use `Text`, not `String(n)`
- JSONB columns: use `JSONB` from sqlalchemy.dialects.postgresql

## Constraints and Indexes

- Include every CHECK constraint from the DDL
- Include every index from the DDL
- Include every UNIQUE constraint
- Foreign key on_delete behavior must match the DDL exactly:
  RESTRICT, SET NULL, and CASCADE are used differently across tables

## Relationships

- Define SQLAlchemy relationships where foreign keys exist
- Use `lazy="selectin"` for relationships that are always needed together
  (e.g., psr_rule → psr_rule_component)
- Use `lazy="noload"` for optional relationships

## After Creating a Model

- Create an Alembic migration (but do not run it — the human will run it)
- Verify the migration SQL matches the DDL in Concrete_Contract.md

================================================================================
--- FILE: app/repositories/AGENTS.md ---
================================================================================

# Repository Rules

Repositories are the data access layer. They contain SQL and return raw results.
No business logic lives here.

## Join Rules

- ALL operational joins resolve through hs_version + hs6_id
- Never join on raw HS text, product descriptions, or display names
- PSR lookup MUST go through hs6_psr_applicability (materialized resolver),
  not live inheritance logic
- Use the exact SQL from docs/Join_Strategy.md Sections 2.1–2.8 as the
  reference implementation for every query

## Boundaries

- Repositories return raw query results (row mappings or ORM objects)
- Never return Pydantic models — transformation happens in the service layer
- No business logic: no if/else on rule_status, no eligibility decisions,
  no derived variable computation
- No direct imports from app/services/

## Query Style

- Use SQLAlchemy text() with named parameters for complex multi-table joins
- Use ORM queries for simple single-table CRUD
- Always parameterize queries — never use f-strings or string concatenation
- Include ORDER BY and LIMIT where the Join_Strategy.md query has them

## Polymorphic Lookups

- status_assertion and evidence_requirement use entity_type + entity_key
- Use the key patterns from app/core/entity_keys.py
- Always include the date window filter:
  (effective_date IS NULL OR effective_date <= assessment_date)
  AND (expiry_date IS NULL OR expiry_date >= assessment_date)

================================================================================
--- FILE: app/schemas/AGENTS.md ---
================================================================================

# Pydantic Schema Rules

Schemas define the API contract. They are what external consumers see.

## Mandatory Response Fields

Every response model that touches eligibility, rules, or tariffs MUST include:
- rule_status
- tariff_status (where applicable)
- confidence_class

The AssessmentResponse contract in docs/v1_scope.md Section 7.1 is the
canonical reference. Every field listed there is mandatory.

## Type Rules

- Use enums from app/core/enums.py for all status and type fields — never str
- Use Optional[] with explicit None defaults for fields that may be absent
- Never silently omit a field from the response — Optional[X] = None is
  different from not having the field at all
- Use UUID as str in schemas (not uuid.UUID) for JSON serialization

## Validation

- HS6 codes: must be exactly 6 digits after normalization
- Country codes: must be ISO alpha-3 and present in app/core/countries.py
- Year: must be a reasonable calendar year (2020–2040 for v0.1)
- persona_mode: must be one of officer, analyst, exporter, system

## Reference Definitions

- docs/FastAPI_layout.md Sections 5–9 define the exact schema shapes
- docs/Concrete_Contract.md API contract sections define response examples
- When in doubt, match the JSON example in docs/v1_scope.md Section 7

================================================================================
--- FILE: app/services/AGENTS.md ---
================================================================================

# Service Layer Rules

All business logic lives in services. This is the core of the system.

## Architectural Boundaries

- Services call repositories, never the database session directly
- Services return Pydantic schemas, not ORM objects
- Route handlers call services — services never import from app/api/
- Services may call other services (the eligibility_service orchestrates all)

## Critical Separations

- PSR rules (product-specific) and general origin rules (cumulation, direct
  transport, insufficient operations) are SEPARATE services with SEPARATE
  evaluation steps. Never merge them.
- The expression_evaluator is its own service. It does not call repositories
  or know about cases. It takes an expression + facts dict and returns bool.
- The eligibility_service is the orchestrator. It calls everything else in
  the strict 8-step execution order from the root AGENTS.md.

## Safety Rules

- Never use eval(), exec(), or compile() in the expression evaluator
- Never infer or default missing fact values — flag them in missing_facts
- Never assume a status if no status_assertion exists — return "unknown"
- Division by zero (ex_works == 0) is an error, not a silent default

## Derived Variables

Computed at evaluation time by fact_normalization_service, never stored:

```
vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100
```

## Testing

- Every public service method must be independently unit-testable
- Mock the repository layer in unit tests
- Use golden cases from tests/fixtures/golden_cases.py for integration tests

================================================================================
--- FILE: app/api/v1/AGENTS.md ---
================================================================================

# Route Handler Rules

Handlers are thin wrappers. Validate input, call a service, return a response.

## Handler Pattern

```python
@router.get("/rules/{hs6}")
async def lookup_rule(hs6: str, service=Depends(get_rule_resolution_service)):
    result = await service.resolve(hs6)
    return result
```

If a handler has more than ~10 lines of logic, extract to a service.

## Mandatory Response Fields

Every response that touches eligibility, rules, or tariffs includes:
- rule_status
- tariff_status (where applicable)
- confidence_class

## Error Handling

- Domain exceptions (from app/core/exceptions.py) are caught by the global
  exception handlers in main.py — do not catch them in handlers
- Use Pydantic response models from app/schemas/ — never return raw dicts
- Error responses use app/schemas/common.ErrorResponse format

## Dependencies

- All services are injected via Depends() using factories from app/api/deps.py
- Do not instantiate services directly in handlers
- Do not import repositories in handlers — that crosses the layer boundary

## Route Prefix

- The /api/v1 prefix is set in app/api/router.py — do not repeat it in handlers

================================================================================
--- FILE: tests/AGENTS.md ---
================================================================================

# Testing Rules

## Structure

- Unit tests: tests/unit/ — mock repositories, test service logic
- Integration tests: tests/integration/ — real database, full pipeline
- Fixtures: tests/fixtures/ — golden test cases and shared data
- conftest.py at tests/ root — database fixtures, async client, seed data

## Golden Test Cases

tests/fixtures/golden_cases.py is the acceptance criteria. Use these exact
inputs and expected outputs. Do not invent separate test data for the cases
it already covers.

## What to Test

For services:
- Mock the repository layer, test the business logic in isolation
- Test the happy path AND at least one failure case per service

For the expression evaluator:
- Test EVERY rule type: WO, CTH, CTSH, VNM, VA, PROCESS
- Test missing facts (must produce missing_facts list, not crash or default)
- Test zero ex_works (must error, not return 0% or infinity)
- Test compound AND/OR expressions
- Verify no eval()/exec() is used (security)

For the eligibility service:
- Test the full 8-step orchestration with mocked sub-services
- Verify execution ORDER (classification before rules before expressions, etc.)
- Test blocker short-circuit (if blocker fires, pathways are not evaluated)

For repositories:
- Use the test database (afcfta_test)
- Test actual SQL queries against seeded data
- Mark with @pytest.mark.integration

## Failure Assertions

- Every test for a failing case must assert specific failure_codes from
  app/core/failure_codes.py — not just "eligible == false"
- Every test for missing facts must verify the exact list of missing keys
- Every test for provisional status must verify confidence_class == "provisional"

## Do Not

- Do not run tests in the sandbox — mark with @pytest.mark.integration and
  the human will run them
- Do not create test databases or run migrations — conftest.py handles this
- Do not mock the expression evaluator when testing the eligibility service
  unless specifically testing orchestration order

================================================================================
--- FILE: data/AGENTS.md ---
================================================================================

# Data Directory Rules

This directory holds the source document corpus organized by authority tier.
It is a file store, not a code directory.

## Structure

```
data/
├── raw/          ← original source documents, never modified after ingestion
├── staged/       ← intermediate extraction and normalization outputs
└── processed/    ← final structured outputs ready for database loading
```

## Authority Tiers (raw/)

| Directory | Tier | Contents | Role |
|-----------|------|----------|------|
| tier1_binding/ | 1 | Agreement, Protocol, Annexes, Appendices, Schedules, Ministerial Decisions | Binding legal authority |
| tier2_operational/ | 2 | e-Tariff Book, Customs circulars, Guidance, Implementation notes | Operational reference |
| tier3_support/ | 3 | Manuals, Guides (WCO, tralac, etc.) | Interpretive support |
| tier4_analytics/ | 4 | Corridor metrics, Customs readiness, Trade baselines | Analytic enrichment |

Higher tiers override lower tiers in all conflict resolution.

## Immutability Rules

- Files in raw/ are NEVER modified after ingestion
- Each file must have a corresponding source_registry record in the database
- Each file must have a SHA-256 checksum recorded at ingestion time
- If a document is superseded, the old version stays in raw/ and the
  source_registry record is updated with superseded_by_source_id
- Version history is tracked in source_registry, not by overwriting files

## Naming Convention

```
{tier}/{category}/{iso3_country_or_ALL}_{document_type}_{date_YYYYMMDD}.{ext}
```

Examples:
- tier1_binding/tariff_schedules/NGA_tariff_schedule_20240101.xlsx
- tier1_binding/appendices/ALL_appendix_iv_rules_of_origin_20230901.pdf
- tier2_operational/e_tariff_book/ALL_etariff_export_20240615.csv
- tier4_analytics/corridor_metrics/GHA_NGA_corridor_profile_20240301.json

## v0.1 Scope

Only documents for the 5 locked countries: NGA, GHA, CIV, SEN, CMR.
Do not ingest documents for other countries.

================================================================================
--- FILE: data/raw/AGENTS.md ---
================================================================================

# Raw Source Documents

Original source documents. Never modified after ingestion.

## Tier 1 — Binding (tier1_binding/)

The highest-authority sources. These override everything else.

- legal/ — Agreement Establishing the AfCFTA, Protocol on Trade in Goods
- annexes/ — Compiled Annexes 1–10 (tariff concessions, rules of origin,
  customs cooperation, trade facilitation, NTBs, transit, trade remedies)
- appendices/ — Appendices under Annex 2, especially Appendix IV (PSR tables)
- tariff_schedules/ — State Party schedules, customs union schedules,
  provisional schedules, gazetted implementing tariff notices
- ministerial_decisions/ — Council/ministerial decisions, committee communiqués
- status_decisions/ — Official negotiation status updates, implementation directives

## Tier 2 — Operational (tier2_operational/)

- e_tariff_book/ — e-Tariff Book exports (structured tariff data)
- customs_circulars/ — Customs circulars, origin certification procedures
- guidance/ — Secretariat guidance, verification procedure guidance
- implementation_notes/ — Official domestic customs notices

## Tier 3 — Support (tier3_support/)

- manuals/ — AfCFTA Rules of Origin Manual, WCO Practical Guide
- guides/ — Implementation guides, structured explainers

## Tier 4 — Analytics (tier4_analytics/)

- corridor_metrics/ — Border delay data, route profiles, infrastructure assessments
- customs_readiness/ — Customs system digitization levels, procedural readiness
- trade_baselines/ — Bilateral trade volumes, product mix, historical patterns

## Ingestion Checklist

For every file added to raw/:
1. Compute SHA-256 checksum
2. Create source_registry record in database with authority_tier, source_type,
   issuing_body, jurisdiction_scope, effective_date
3. Record file_path relative to data/raw/
4. Set status to "current" (or "provisional" if appropriate)
5. If superseding an older version, update supersedes/superseded_by chain

================================================================================
--- FILE: data/staged/AGENTS.md ---
================================================================================

# Staged Data

Intermediate outputs from the parsing and extraction pipeline. These are
working files between raw source documents and final processed outputs.

## Subdirectories

- extracted_text/ — full text extraction from PDFs and other formats
- extracted_tables/ — table extraction from rule tables and tariff schedules
- ocr/ — OCR outputs for scanned documents
- metadata/ — document metadata, page counts, language detection, structure maps
- normalized/ — normalized text with standardized formatting before final processing

## Rules

- Every file in staged/ must be traceable to a source file in raw/ via
  a source_id or filename convention
- Staged files are regenerable — if the pipeline reruns, they get overwritten
- Do not manually edit staged files — fix the parser/extractor instead
- Staged outputs are NOT loaded into the database. Only processed/ outputs
  feed the database.

## Quality Markers

When extracting from raw sources, record quality indicators:
- extraction_method: "text_layer", "ocr", "table_parser", "manual"
- confidence: high/medium/low based on extraction clarity
- language: "en", "fr", or "en/fr" for bilingual documents
- page_range: which pages were extracted

================================================================================
--- FILE: data/processed/AGENTS.md ---
================================================================================

# Processed Data

Final structured outputs ready for database loading. Each subdirectory maps
to a database layer.

## Subdirectories → Database Layers

| Directory | Target Tables | Format |
|-----------|---------------|--------|
| chunks/ | Retrieval index (future, not v0.1) | JSONL |
| entities/ | hs6_product, hs_code_alias | CSV or JSONL |
| provisions/ | legal_provision | JSONL |
| rules/ | psr_rule, psr_rule_component, eligibility_rule_pathway, hs6_psr_applicability | JSONL |
| tariffs/ | tariff_schedule_header, tariff_schedule_line, tariff_schedule_rate_by_year | JSONL |
| statuses/ | status_assertion, transition_clause | JSONL |
| evidence/ | evidence_requirement, verification_question, document_readiness_template | JSONL |
| cases/ | Reserved for exported/imported case data | JSONL |
| analytics/ | corridor_profile, alert_event | JSONL |

## Rules

- Every record must include source_id tracing back to source_registry
- Every record must include provenance fields: page_ref, row_ref where applicable
- HS codes must be normalized to 6 digits (no dots, no spaces)
- Country codes must be ISO alpha-3 from app/core/countries.py
- Enum values must exactly match the PostgreSQL enums in docs/Concrete_Contract.md
- Verbatim legal text must be preserved alongside any normalized version
- UUIDs should be pre-generated and stable across pipeline reruns (deterministic
  UUID from content hash where possible)

## Loading Order

Load in dependency order (foreign keys must resolve):

1. source_registry (provenance — no FK dependencies)
2. legal_provision (depends on source_registry)
3. hs6_product (backbone — no FK dependencies beyond source)
4. psr_rule (depends on hs6_product, source_registry)
5. psr_rule_component (depends on psr_rule)
6. eligibility_rule_pathway (depends on psr_rule)
7. hs6_psr_applicability (depends on hs6_product, psr_rule)
8. tariff_schedule_header (depends on source_registry)
9. tariff_schedule_line (depends on tariff_schedule_header)
10. tariff_schedule_rate_by_year (depends on tariff_schedule_line, source_registry)
11. status_assertion (depends on source_registry)
12. evidence_requirement (depends on legal_provision)
13. verification_question (depends on legal_provision)
14. corridor_profile
15. alert_event

================================================================================
--- FILE: schemas/AGENTS.md ---
================================================================================

# Schema Definitions

This directory contains the formal schema definitions for the system —
separate from the Pydantic schemas in app/schemas/ which are runtime models.

## Subdirectories

- sql/ — PostgreSQL DDL files. The source of truth for all table definitions.
  Must match docs/Concrete_Contract.md exactly. Used for clean-slate database
  creation and as reference during development.
- json/ — JSON Schema definitions for pipeline data formats, API request/response
  validation, and expression_json structure used in eligibility_rule_pathway.
- contracts/ — OpenAPI/REST API contract definitions. Must match the endpoint
  definitions in docs/FastAPI_layout.md and response shapes in docs/v1_scope.md.

## Rules

- sql/ files are the canonical DDL — docs/Concrete_Contract.md is the human-readable
  version. If they conflict, Concrete_Contract.md wins and sql/ must be updated.
- json/ schemas for expression_json must match docs/expression_grammar.md
- contracts/ must reflect the actual API behavior. Update when endpoints change.
- Do not auto-generate these from code. These are specifications that code
  must conform to, not the other way around.

================================================================================
--- FILE: pipelines/AGENTS.md ---
================================================================================

# Pipeline Rules

Pipelines move data from raw source documents through extraction, normalization,
and validation into structured records ready for database loading.

## Pipeline Stages (in order)

```
acquire → parse → normalize → enrich → assess → index → alerts → qa
```

Each stage reads from the previous stage's output and writes to the next.

## Stage Responsibilities

| Stage | Input | Output | Purpose |
|-------|-------|--------|---------|
| acquire/ | External sources | data/raw/ | Download, register in source_registry, compute checksums |
| parse/ | data/raw/ | data/staged/extracted_text/, extracted_tables/ | Extract text, tables, structure from PDFs and spreadsheets |
| normalize/ | data/staged/ | data/staged/normalized/ | Standardize HS codes, rates, dates, country codes, legal references |
| enrich/ | data/staged/normalized/ | data/processed/ | Convert normalized extractions into database-ready records with UUIDs and FKs |
| assess/ | data/processed/ | Validation reports | Run structural and legal fidelity checks before loading |
| index/ | data/processed/ | Database | Load processed records into PostgreSQL in dependency order |
| alerts/ | Database (change_log) | alert_event records | Detect changes between pipeline runs, generate alerts |
| qa/ | Database + eval/gold_sets/ | QA reports | Run benchmark and regression tests against loaded data |

## Document Classification

The parse stage must classify each source document before extraction:

- LEGAL_TEXT — full text extraction, article/paragraph chunking
- APPENDIX_RULE_TABLE — row-by-row PSR extraction with HS code, rule text, components
- TARIFF_SCHEDULE_TABLE — row extraction with corridor, HS code, rates, years
- STATUS_NOTICE — entity + status phrase + effective date extraction
- IMPLEMENTATION_CIRCULAR — procedure steps, required documents, officer actions
- GUIDANCE_DOC — operational guidance chunking by requirement/procedure block
- FORM_TEMPLATE — field definitions and submission requirements
- ANALYTIC_REFERENCE — metric extraction, corridor profiling data

## Critical Rules

- Verbatim legal text is always preserved alongside any normalization
- HS codes are normalized to digits only, stored with hs_version
- Every output record must trace to a source_id in source_registry
- Never infer a status — if the document does not state agreed/pending/provisional,
  flag it as ambiguous
- Rates must preserve original precision — do not round
- The parser must flag ambiguity, never resolve it silently
- Pipeline reruns must be idempotent — same input produces same output

## v0.1 Scope

For v0.1, pipelines can be scripts in scripts/ rather than a full framework.
The key requirement is that the structured outputs in data/processed/ match
the database schema exactly and can be loaded via the index stage.

================================================================================
--- FILE: pipelines/parse/AGENTS.md ---
================================================================================

# Parser Rules

The parser converts raw source documents into structured extractions.

## Extraction by Document Type

### Appendix IV / PSR Tables (APPENDIX_RULE_TABLE)

Per row extract:
- hs_code, hs_version, hs_level (chapter/heading/subheading)
- product_description
- legal_rule_text_verbatim (exact text from source)
- rule components: WO, VA, VNM, CTH, CTSH, PROCESS with thresholds
- threshold_percent and threshold_basis where applicable
- rule_status: agreed, pending, partially_agreed
- page_ref, row_ref
- source_id

### Tariff Schedules (TARIFF_SCHEDULE_TABLE)

Per row extract:
- exporter_state, importer_state
- hs_code, hs_version
- product_description
- mfn_base_rate
- tariff_category: liberalised, sensitive, excluded
- staging columns: rate by year (expand into tariff_schedule_rate_by_year rows)
- target_rate, target_year
- schedule_status: official, provisional, gazetted
- page_ref, source_id

### Legal Text (LEGAL_TEXT)

Per provision extract:
- instrument_name, instrument_type
- article_ref, annex_ref, appendix_ref, section_ref
- provision_text_verbatim
- topic_primary, topic_secondary[]
- cross_reference_refs[]
- effective_date, status
- page_start, page_end, source_id

### Status Notices (STATUS_NOTICE)

Per assertion extract:
- entity_type, entity_key (what the status applies to)
- status_type: agreed, pending, provisional, in_force, etc.
- status_text_verbatim
- effective_from, effective_to
- clause_ref, page_ref, source_id

## Rules

- Preserve verbatim text always — normalization is a separate field
- Never infer status from absence of information
- Flag ambiguous or unclear entries rather than guessing
- HS codes in Appendix IV may be at chapter (2-digit) or heading (4-digit)
  level — record the actual hs_level, do not assume subheading

================================================================================
--- FILE: pipelines/normalize/AGENTS.md ---
================================================================================

# Normalization Rules

Normalization converts extracted text into standardized, machine-readable values.

## HS Code Normalization

- Strip all dots, spaces, and punctuation — store digits only
- Record the original format in a separate field if needed
- Store hs_version (HS2012, HS2017, HS2022) alongside every code
- 2-digit = chapter, 4-digit = heading, 6-digit = subheading
- Do not zero-pad beyond what the source provides

## Rate Normalization

- Convert percentage strings to numeric: "15%" → 15.0000
- Preserve original precision — do not round
- "Free" or "0" → 0.0000
- "Excluded" → null rate with tariff_category = "excluded"
- Handle mixed formats: "10% or $5/kg" → flag as complex, store verbatim

## Country Code Normalization

- All country references → ISO alpha-3 from app/core/countries.py
- "Nigeria" → "NGA", "Ghana" → "GHA", etc.
- Customs union references: "ECOWAS" applies to member states individually
- For v0.1, only normalize to the 5 locked countries

## Rule Component Normalization

Convert rule text into structured signals:
- "wholly obtained" → WO
- "value added of not less than X%" → VA with threshold_percent = X
- "maximum value of non-originating materials of X%" → VNM with threshold = X
- "change in tariff heading" → CTH
- "change in tariff subheading" → CTSH
- Specific process descriptions → PROCESS with specific_process_text preserved
- "or" between conditions → separate pathways (OR logic)
- Combined conditions within one rule → single pathway with AND logic

## Status Normalization

Map text patterns to status_type_enum values:
- "agreed", "adopted", "approved" → agreed
- "pending", "under negotiation", "not yet concluded" → pending
- "provisional", "provisionally applied" → provisional
- "in force", "entered into force" → in_force
- Do NOT infer — if the text does not clearly match a pattern, flag as ambiguous

================================================================================
--- FILE: eval/AGENTS.md ---
================================================================================

# Evaluation and Benchmarking Rules

This directory contains gold standard datasets and benchmark suites for
validating the system's accuracy.

## Subdirectories

- gold_sets/ — manually verified correct answers for rule lookups, tariff
  queries, eligibility assessments, and evidence readiness checks
- benchmarks/ — performance benchmarks: query latency, throughput, concurrent
  assessment capacity
- regression/ — regression test suites that must pass before any release

## Gold Set Structure

Each gold set entry must include:
- input (exact query or case facts)
- expected_output (exact expected response)
- source_reference (which document and page the answer comes from)
- verified_by (who verified this entry)
- verified_date

## Gold Set Coverage Targets (from Implementation Blueprint)

- 75 rule lookups
- 75 tariff corridor queries
- 50 eligibility cases (pass and fail)
- 50 evidence-readiness cases
- 30 counterfactual scenarios

## Evaluation Dimensions

### Structured Answer Accuracy
- HS code match accuracy
- Tariff rate accuracy (exact numeric match)
- Status label accuracy (agreed vs provisional vs pending)
- Threshold extraction accuracy

### Decision Accuracy
- Eligibility outcome: correct pass/fail
- Failure mode identification: correct failure_codes
- Evidence checklist completeness

### Critical Failure Tracking
Flag and track these explicitly:
- Hallucinated rule text (text not in any source document)
- Wrong tariff year or rate
- Wrong status flag (e.g., reporting "agreed" when actually "pending")
- Overconfident answer on incomplete data (confidence_class should be "incomplete")
- Missing or wrong source citation

## Regression Rules

Re-run the full regression suite when:
- A new source document is ingested
- Parser or normalization logic changes
- Any service logic changes
- Database schema changes

================================================================================
--- FILE: docs/AGENTS.md ---
================================================================================

# Documentation Directory

Read-only architecture specifications. Do not modify any file in this directory.

## Reading Order

Read these in order. Each document assumes context from the ones before it.

1. PRD.md — product purpose, user personas, core capabilities
2. v1_scope.md — what is in/out for v0.1, locked countries, success criteria
3. Implementation_Blueprint.md — five-layer architecture, source tiers, governance
4. Canonical_Corpus.md — exact source documents to ingest, authority mapping
5. Concrete_Contract.md — PostgreSQL DDL, column types, enums, API contracts
6. Join_Strategy.md — how tables connect via HS6 spine, production query patterns
7. FastAPI_layout.md — repo structure, route handlers, Pydantic models, service boundaries
8. expression_grammar.md — boolean expression syntax for the eligibility engine

## Subdirectories

- source_registry/ — documentation about the source ingestion process and
  provenance tracking. References Canonical_Corpus.md.
- ontology/ — domain ontology: HS code hierarchy, rule type taxonomy,
  status lifecycle, evidence type classification
- parser_notes/ — per-document-type parsing notes, extraction edge cases,
  known ambiguities in source documents
- governance/ — change control procedures, review requirements, version
  management policies per Implementation_Blueprint.md Section 18

## Rules

- These files are specifications. Code must conform to them.
- If code behavior contradicts a doc, the doc wins and the code must be fixed.
- If a doc is genuinely wrong or outdated, ask the human before changing it.
- Do not add auto-generated documentation here. This is for human-authored specs.

================================================================================
--- FILE: scripts/AGENTS.md ---
================================================================================

# Scripts Directory

Utility scripts for data loading, pipeline execution, and maintenance tasks.

## Key Scripts

- seed_data.py — populates the database with v0.1 test data (5 HS6 products,
  2 corridors, rules, tariffs, statuses, evidence)
- load_processed.py — loads data from data/processed/ into the database in
  correct dependency order (see data/processed/AGENTS.md for loading order)

## Rules

- Scripts must be idempotent — safe to run multiple times
- Scripts must validate data before inserting (check FK references, enum values)
- Scripts must log what they insert (count of records per table)
- Scripts must use the same database connection and session patterns as the app
- Do not hardcode database URLs — read from .env via app/config.py
- Do not run these scripts in the sandbox — the human will run them

================================================================================
--- FILE: alembic/AGENTS.md ---
================================================================================

# Alembic Migrations

## Rules

- Every new table or schema change requires a migration
- Migration files are generated with `alembic revision --autogenerate`
- The human runs all alembic commands — do not run them in the sandbox
- Migration SQL must match the DDL in docs/Concrete_Contract.md
- Include PostgreSQL extensions (uuid-ossp, pg_trgm) in the first migration
- Include all enum type creation in migrations (CREATE TYPE ... AS ENUM)
- Down migrations (downgrade) should drop tables/types in reverse dependency order
- Never modify a migration that has already been applied — create a new one
