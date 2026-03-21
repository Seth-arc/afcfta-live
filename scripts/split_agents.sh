#!/usr/bin/env bash
# split_agents.sh — Run from your repo root (afcfta-intelligence/)
# Creates all AGENTS.md files in the correct directories.
# The root AGENTS.md is NOT created by this script — place it separately.

set -euo pipefail

create_agents_file() {
    local dir="$1"
    local content="$2"
    mkdir -p "$dir"
    echo "$content" > "$dir/AGENTS.md"
    echo "  Created $dir/AGENTS.md"
}

echo "Creating AGENTS.md files..."
echo ""

# ── app layer ──────────────────────────────────────────────────────────────

create_agents_file "app/core" '# Core Module Rules

These files are the system'"'"'s reference data and type definitions. Most are
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
- Exception names are used in API error handlers — renaming breaks the contract'

create_agents_file "app/db/models" '# ORM Model Rules

Every model in this directory represents a PostgreSQL table. The DDL is the
source of truth, not the other way around.

## Column Fidelity

- Every column name, type, and constraint must match docs/Concrete_Contract.md
- Do not rename columns for "Pythonic" style (e.g., keep hs6_id, not hs6Id)
- Do not add columns that are not in the DDL
- Do not skip columns because they seem optional

## Types

- UUID primary keys: server_default=text("uuid_generate_v4()")
- All timestamps: timestamptz with server_default=func.now()
- Enum columns: use the Python enums from app/core/enums.py, never inline strings
- Numeric columns for rates/thresholds: use Numeric(precision, scale) matching DDL
- Text columns for verbatim legal text: use Text, not String(n)
- JSONB columns: use JSONB from sqlalchemy.dialects.postgresql

## Constraints and Indexes

- Include every CHECK constraint from the DDL
- Include every index from the DDL
- Include every UNIQUE constraint
- Foreign key on_delete behavior must match the DDL exactly:
  RESTRICT, SET NULL, and CASCADE are used differently across tables

## After Creating a Model

- Create an Alembic migration (but do not run it — the human will run it)
- Verify the migration SQL matches the DDL in Concrete_Contract.md'

create_agents_file "app/repositories" '# Repository Rules

Repositories are the data access layer. They contain SQL and return raw results.
No business logic lives here.

## Join Rules

- ALL operational joins resolve through hs_version + hs6_id
- Never join on raw HS text, product descriptions, or display names
- PSR lookup MUST go through hs6_psr_applicability (materialized resolver),
  not live inheritance logic
- Use the exact SQL from docs/Join_Strategy.md Sections 2.1-2.8 as the
  reference implementation for every query

## Boundaries

- Repositories return raw query results (row mappings or ORM objects)
- Never return Pydantic models — transformation happens in the service layer
- No business logic: no if/else on rule_status, no eligibility decisions,
  no derived variable computation
- No direct imports from app/services/

## Polymorphic Lookups

- status_assertion and evidence_requirement use entity_type + entity_key
- Use the key patterns from app/core/entity_keys.py
- Always include the date window filter for effective_date and expiry_date'

create_agents_file "app/schemas" '# Pydantic Schema Rules

Schemas define the API contract. They are what external consumers see.

## Mandatory Response Fields

Every response model that touches eligibility, rules, or tariffs MUST include:
- rule_status
- tariff_status (where applicable)
- confidence_class

The AssessmentResponse contract in docs/v1_scope.md Section 7.1 is canonical.

## Type Rules

- Use enums from app/core/enums.py for all status and type fields — never str
- Use Optional[] with explicit None defaults for fields that may be absent
- Never silently omit a field — Optional[X] = None is different from missing
- Use UUID as str in schemas (not uuid.UUID) for JSON serialization

## Validation

- HS6 codes: must be exactly 6 digits after normalization
- Country codes: must be ISO alpha-3 from app/core/countries.py
- Year: reasonable calendar year (2020-2040)
- persona_mode: one of officer, analyst, exporter, system'

create_agents_file "app/services" '# Service Layer Rules

All business logic lives in services. This is the core of the system.

## Architectural Boundaries

- Services call repositories, never the database session directly
- Services return Pydantic schemas, not ORM objects
- Route handlers call services — services never import from app/api/
- Services may call other services (eligibility_service orchestrates all)

## Critical Separations

- PSR rules and general origin rules are SEPARATE services. Never merge them.
- The expression_evaluator takes an expression + facts dict, returns bool.
  It does not call repositories or know about cases.
- The eligibility_service calls everything else in strict 8-step order.

## Safety Rules

- Never use eval(), exec(), or compile() in the expression evaluator
- Never infer or default missing fact values — flag them in missing_facts
- Never assume a status — return "unknown" if no status_assertion exists
- Division by zero (ex_works == 0) is an error, not a silent default

## Derived Variables (computed, never stored)

vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100'

create_agents_file "app/api/v1" '# Route Handler Rules

Handlers are thin wrappers. Validate input, call a service, return a response.
If a handler has more than ~10 lines of logic, extract to a service.

## Mandatory Response Fields

Every response touching eligibility, rules, or tariffs includes:
- rule_status
- tariff_status (where applicable)
- confidence_class

## Error Handling

- Domain exceptions are caught by global handlers in main.py — do not catch here
- Use Pydantic response models from app/schemas/ — never return raw dicts
- Error responses use app/schemas/common.ErrorResponse format

## Dependencies

- All services injected via Depends() using factories from app/api/deps.py
- Do not instantiate services directly in handlers
- Do not import repositories in handlers — that crosses the layer boundary

## Route Prefix

/api/v1 prefix is set in app/api/router.py — do not repeat it in handlers'

create_agents_file "tests" '# Testing Rules

## Structure

- Unit tests: tests/unit/ (mock repositories, test service logic)
- Integration tests: tests/integration/ (real database, full pipeline)
- Fixtures: tests/fixtures/ (golden test cases — do not modify)

## Golden Test Cases

tests/fixtures/golden_cases.py is the acceptance criteria. Use these exact
inputs and expected outputs. Do not invent separate test data.

## What to Test

Expression evaluator: every rule type (WO, CTH, CTSH, VNM, VA, PROCESS),
missing facts, zero division, compound AND/OR.

Eligibility service: full 8-step orchestration, execution order, blocker
short-circuit behavior.

## Failure Assertions

- Assert specific failure_codes from app/core/failure_codes.py
- Assert exact missing_facts lists
- Assert confidence_class for provisional status cases

## Do Not

- Do not run tests in the sandbox — the human runs them
- Do not create test databases or run migrations — conftest.py handles this'

# ── data layer ─────────────────────────────────────────────────────────────

create_agents_file "data" '# Data Directory Rules

Source document corpus organized by authority tier. File store, not code.

## Structure

- raw/      — original source documents, NEVER modified after ingestion
- staged/   — intermediate extraction and normalization outputs
- processed/ — final structured outputs ready for database loading

## Immutability

- Files in raw/ are never modified after ingestion
- Each file must have a source_registry record with SHA-256 checksum
- Superseded documents stay in raw/; source_registry tracks the chain

## v0.1 Scope

Only documents for: NGA, GHA, CIV, SEN, CMR'

create_agents_file "data/raw" '# Raw Source Documents — Never Modified After Ingestion

## Authority Tiers

| Tier | Directory | Role |
|------|-----------|------|
| 1 | tier1_binding/ | Binding legal authority (Agreement, Annexes, Appendix IV, Schedules) |
| 2 | tier2_operational/ | Operational reference (e-Tariff Book, circulars, guidance) |
| 3 | tier3_support/ | Interpretive support (manuals, guides) |
| 4 | tier4_analytics/ | Analytic enrichment (corridor metrics, trade baselines) |

Higher tiers override lower tiers in all conflict resolution.

## Ingestion Checklist

For every file added:
1. Compute SHA-256 checksum
2. Create source_registry record
3. Record file_path relative to data/raw/
4. If superseding an older version, update supersedes/superseded_by chain'

create_agents_file "data/staged" '# Staged Data — Intermediate Pipeline Outputs

Working files between raw source documents and final processed outputs.

- extracted_text/ — full text from PDFs
- extracted_tables/ — tables from rule/tariff documents
- ocr/ — OCR outputs for scanned documents
- metadata/ — document metadata, structure maps
- normalized/ — standardized text before final processing

## Rules

- Every file traceable to a source in raw/ via source_id
- Staged files are regenerable — pipeline reruns overwrite them
- Do not manually edit — fix the parser instead
- Staged outputs do NOT go into the database. Only processed/ feeds the DB.'

create_agents_file "data/processed" '# Processed Data — Database-Ready Structured Outputs

## Directory → Database Table Mapping

| Directory | Target Tables |
|-----------|---------------|
| entities/ | hs6_product, hs_code_alias |
| provisions/ | legal_provision |
| rules/ | psr_rule, psr_rule_component, eligibility_rule_pathway, hs6_psr_applicability |
| tariffs/ | tariff_schedule_header, tariff_schedule_line, tariff_schedule_rate_by_year |
| statuses/ | status_assertion, transition_clause |
| evidence/ | evidence_requirement, verification_question, document_readiness_template |
| analytics/ | corridor_profile, alert_event |

## Rules

- Every record must include source_id tracing to source_registry
- HS codes normalized to 6 digits, no dots, no spaces
- Country codes ISO alpha-3 from app/core/countries.py
- Enum values must exactly match docs/Concrete_Contract.md
- Verbatim legal text preserved alongside normalized versions
- Load in FK dependency order (see loading order in full AGENTS.md reference)'

# ── schemas, pipelines, eval, docs, scripts, alembic ──────────────────────

create_agents_file "schemas" '# Schema Definitions

Formal schema definitions — separate from runtime Pydantic models in app/schemas/.

- sql/ — PostgreSQL DDL. Must match docs/Concrete_Contract.md exactly.
- json/ — JSON Schema for pipeline formats and expression_json structure.
- contracts/ — OpenAPI/REST API contracts matching docs/FastAPI_layout.md.

These are specifications that code must conform to, not generated from code.'

create_agents_file "pipelines" '# Pipeline Rules

Pipelines move data: raw sources → extraction → normalization → database.

## Stages (in order)

acquire → parse → normalize → enrich → assess → index → alerts → qa

## Critical Rules

- Verbatim legal text always preserved alongside normalization
- HS codes normalized to digits only, stored with hs_version
- Every output record traces to a source_id in source_registry
- Never infer status — flag ambiguity instead
- Rates preserve original precision — do not round
- Pipeline reruns must be idempotent'

create_agents_file "pipelines/parse" '# Parser Rules

Convert raw source documents into structured extractions.

## By Document Type

- APPENDIX_RULE_TABLE: row-by-row PSR extraction (HS code, rule text, components, thresholds)
- TARIFF_SCHEDULE_TABLE: corridor + HS code + rates + year expansion
- LEGAL_TEXT: provision extraction (article_ref, verbatim text, topic, cross-refs)
- STATUS_NOTICE: entity + status_type + effective dates

## Rules

- Preserve verbatim text always
- Never infer status from absence of information
- HS codes may be chapter (2-digit) or heading (4-digit) — record actual hs_level
- Flag ambiguous entries rather than guessing'

create_agents_file "pipelines/normalize" '# Normalization Rules

Convert extracted text into standardized machine-readable values.

## HS Codes: strip dots/spaces, digits only, record hs_version
## Rates: percentage strings → numeric, preserve precision, "Free" → 0.0000
## Countries: all references → ISO alpha-3 from app/core/countries.py
## Rule Components: "wholly obtained" → WO, "value added X%" → VA, etc.
## Status: map text patterns to status_type_enum. Never infer — flag ambiguity.

See the full reference in the combined AGENTS.md file for detailed mappings.'

create_agents_file "eval" '# Evaluation and Benchmarking

- gold_sets/ — manually verified correct answers (rule lookups, tariff queries,
  eligibility cases, evidence readiness)
- benchmarks/ — performance: query latency, throughput
- regression/ — must-pass suites before any release

## Gold Set Coverage Targets

75 rule lookups, 75 tariff queries, 50 eligibility cases, 50 evidence cases,
30 counterfactual scenarios.

## Regression Rules

Re-run full suite when: new source ingested, parser changes, service logic
changes, or schema changes.'

create_agents_file "docs" '# Documentation — Read Only

Architecture specifications. Do not modify any file here.

## Reading Order

1. PRD.md  2. v1_scope.md  3. Implementation_Blueprint.md
4. Canonical_Corpus.md  5. Concrete_Contract.md  6. Join_Strategy.md
7. FastAPI_layout.md  8. expression_grammar.md

If code contradicts a doc, the doc wins and the code must be fixed.
If a doc is genuinely wrong, ask the human before changing it.'

create_agents_file "scripts" '# Scripts

Utility scripts for data loading and maintenance.

## Rules

- Scripts must be idempotent (safe to run multiple times)
- Scripts must validate data before inserting
- Scripts must log what they insert (record counts per table)
- Read database URL from .env via app/config.py — never hardcode
- Do not run scripts in the sandbox — the human runs them'

create_agents_file "alembic" '# Alembic Migrations

- Every new table or schema change requires a migration
- The human runs all alembic commands — do not run them in the sandbox
- Migration SQL must match docs/Concrete_Contract.md
- Include uuid-ossp and pg_trgm extensions in the first migration
- Include CREATE TYPE for all enums
- Never modify a migration that has already been applied — create a new one'

echo ""
echo "Done. Created AGENTS.md in $(find . -name AGENTS.md -not -path ./AGENTS.md | wc -l) directories."
echo ""
echo "NOTE: The root AGENTS.md must be placed separately at the repo root."
