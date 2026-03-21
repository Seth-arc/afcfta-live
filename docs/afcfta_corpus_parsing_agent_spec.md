# AfCFTA Corpus Parsing — Agent-Executable Specification

**Target executor:** AI coding agent (Codex-class).  
**Constraint:** Execute every instruction literally. Do not infer, improvise, or skip steps. If a step says "do X," do exactly X. If a value is ambiguous in a source document, set `confidence_score = 0.0` and log to the review queue — never guess.

---

## TABLE OF CONTENTS

```
SECTION 0:  GLOBAL CONSTANTS AND ENUM MAPS
SECTION 1:  ENVIRONMENT SETUP
SECTION 2:  DATABASE SCHEMA (complete DDL — run in order)
SECTION 3:  PROJECT FILE STRUCTURE
SECTION 4:  MODULE 1 — source_registry_loader.py
SECTION 5:  MODULE 2 — hs6_backbone_loader.py
SECTION 6:  MODULE 3 — tariff_schedule_parser.py
SECTION 7:  MODULE 4 — appendix_iv_extractor.py  (PDF → raw rows)
SECTION 8:  MODULE 5 — psr_row_classifier.py      (raw rows → classified rows)
SECTION 9:  MODULE 6 — hs_code_normalizer.py       (classified rows → clean HS codes)
SECTION 10: MODULE 7 — rule_decomposer.py          (rule text → components)
SECTION 11: MODULE 8 — pathway_builder.py           (components → expression_json)
SECTION 12: MODULE 9 — applicability_builder.py     (inheritance resolution)
SECTION 13: MODULE 10 — psr_db_inserter.py          (insert all in FK order)
SECTION 14: MODULE 11 — validation_runner.py        (post-insert checks)
SECTION 15: MODULE 12 — review_queue_exporter.py    (low-confidence rows)
SECTION 16: MODULE 13 — status_assertion_loader.py  (manual + pattern-match)
SECTION 17: MODULE 14 — evidence_requirement_seeder.py
SECTION 18: ORCHESTRATOR — run_full_pipeline.py
SECTION 19: TEST VECTORS (exact input → expected output)
SECTION 20: TROUBLESHOOTING DECISION TREE
```

---

# SECTION 0: GLOBAL CONSTANTS AND ENUM MAPS

These are the exact enum values from the PostgreSQL schema. Every Python module MUST use these exact strings. No synonyms. No abbreviations. Case-sensitive.

```python
# constants.py — import this in every module

# === PostgreSQL enum: rule_component_type_enum ===
VALID_COMPONENT_TYPES = [
    "WO",        # Wholly Obtained
    "VA",        # Value Added (minimum local/regional content)
    "VNM",       # Value of Non-originating Materials (maximum)
    "CTH",       # Change of Tariff Heading (4-digit shift)
    "CTSH",      # Change of Tariff Subheading (6-digit shift)
    "CC",        # Change of Chapter (2-digit shift)
    "PROCESS",   # Specific manufacturing process
    "ALT_RULE",  # Alternative rule (container for OR pathways)
    "EXCEPTION", # Exception clause within a rule
    "NOTE",      # Unparseable or annotation — always needs human review
]

# === PostgreSQL enum: operator_type_enum ===
VALID_OPERATOR_TYPES = [
    "and",         # Combined requirement (both must pass)
    "or",          # Alternative pathway (either can pass)
    "not",         # Negation (used in exceptions)
    "standalone",  # Single atomic rule, no combination
]

# === PostgreSQL enum: hs_level_enum ===
VALID_HS_LEVELS = [
    "chapter",      # 2-digit (e.g., "11")
    "heading",      # 4-digit (e.g., "1103")
    "subheading",   # 6-digit (e.g., "110311")
    "tariff_line",  # 8+ digit (stored but NOT used in v0.1 logic)
]

# === PostgreSQL enum: rule_status_enum ===
VALID_RULE_STATUSES = [
    "agreed",
    "pending",
    "partially_agreed",
    "provisional",
    "superseded",
]

# === PostgreSQL enum: threshold_basis_enum ===
VALID_THRESHOLD_BASES = [
    "ex_works",
    "fob",
    "value_of_non_originating_materials",
    "customs_value",
    "unknown",
]

# === PostgreSQL enum: schedule_status_enum ===
VALID_SCHEDULE_STATUSES = [
    "official",
    "provisional",
    "gazetted",
    "superseded",
    "draft",
]

# === PostgreSQL enum: tariff_category_enum ===
VALID_TARIFF_CATEGORIES = [
    "liberalised",
    "sensitive",
    "excluded",
    "unknown",
]

# === PostgreSQL enum: staging_type_enum ===
VALID_STAGING_TYPES = [
    "immediate",
    "linear",
    "stepwise",
    "unknown",
]

# === PostgreSQL enum: rate_status_enum ===
VALID_RATE_STATUSES = [
    "in_force",
    "projected",
    "provisional",
    "superseded",
]

# === PostgreSQL enum: status_type_enum ===
VALID_STATUS_TYPES = [
    "agreed",
    "pending",
    "provisional",
    "under_review",
    "transitional",
    "superseded",
    "in_force",
    "not_yet_operational",
    "expired",
]

# === PostgreSQL enum: authority_tier_enum ===
VALID_AUTHORITY_TIERS = [
    "binding",
    "official_operational",
    "interpretive",
    "analytic_enrichment",
]

# === PostgreSQL enum: source_type_enum ===
VALID_SOURCE_TYPES = [
    "agreement",
    "protocol",
    "annex",
    "appendix",
    "tariff_schedule",
    "ministerial_decision",
    "status_notice",
    "implementation_circular",
    "guidance_note",
    "manual",
    "analytics_reference",
    "other",
]

# === PostgreSQL enum: source_status_enum ===
VALID_SOURCE_STATUSES = [
    "current",
    "superseded",
    "provisional",
    "draft",
    "pending",
    "archived",
]

# === PostgreSQL enum: requirement_type_enum ===
VALID_REQUIREMENT_TYPES = [
    "certificate_of_origin",
    "supplier_declaration",
    "process_record",
    "bill_of_materials",
    "cost_breakdown",
    "invoice",
    "transport_record",
    "customs_supporting_doc",
    "valuation_support",
    "inspection_record",
    "other",
]

# === PostgreSQL enum: persona_mode_enum ===
VALID_PERSONA_MODES = [
    "officer",
    "analyst",
    "exporter",
    "system",
]

# === V0.1 LOCKED SCOPE ===
V01_COUNTRIES = ["NGA", "GHA", "CIV", "SEN", "CMR"]
V01_COUNTRY_NAMES = {
    "NGA": "Nigeria",
    "GHA": "Ghana",
    "CIV": "Côte d'Ivoire",
    "SEN": "Senegal",
    "CMR": "Cameroon",
}
V01_HS_VERSION = "HS2017"
V01_DEFAULT_RULE_STATUS = "agreed"

# === EXPRESSION_JSON OP CODES ===
# These are the only valid "op" values in expression_json.
# The ExpressionEvaluator in the FastAPI service only supports these.
VALID_EXPRESSION_OPS = [
    "all",                          # AND — all children must pass
    "any",                          # OR — at least one child must pass
    "formula_lte",                  # variable <= threshold
    "formula_gte",                  # variable >= threshold
    "fact_eq",                      # fact == expected value
    "every_non_originating_input",  # iterate over non-orig inputs
]

# === EXPRESSION_JSON TEST OP CODES ===
# Used inside "every_non_originating_input" nodes.
VALID_TEST_OPS = [
    "heading_ne_output",     # input HS4 != output HS4 (for CTH)
    "subheading_ne_output",  # input HS6 != output HS6 (for CTSH)
    "chapter_ne_output",     # input HS2 != output HS2 (for CC)
]

# === DERIVED VARIABLE DEFINITIONS ===
# These are the ONLY derived variables the engine computes.
# Parser must use these exact names in expression_json.
DERIVED_VARIABLE_DEFS = {
    "vnom_percent": {
        "name": "vnom_percent",
        "formula": "non_originating / ex_works * 100",
        "description": "Non-originating materials as % of ex-works price",
        "required_facts": ["non_originating", "ex_works"],
    },
    "va_percent": {
        "name": "va_percent",
        "formula": "(ex_works - non_originating) / ex_works * 100",
        "description": "Value added as % of ex-works price",
        "required_facts": ["non_originating", "ex_works"],
    },
}

# === CONFIDENCE SCORE THRESHOLDS ===
CONFIDENCE_PERFECT = 1.000       # Parser is certain. No review needed.
CONFIDENCE_HIGH = 0.900          # Minor ambiguity. Review recommended.
CONFIDENCE_MEDIUM = 0.500        # Significant ambiguity. Review required.
CONFIDENCE_LOW = 0.200           # Mostly guessing. Must be reviewed.
CONFIDENCE_ZERO = 0.000          # Could not parse. Definitely needs review.
REVIEW_THRESHOLD = 1.000         # Anything BELOW this goes to review queue.
```

---

# SECTION 1: ENVIRONMENT SETUP

Execute these commands in order. Do not skip any. Do not substitute packages.

```bash
# Step 1: Create project directory
mkdir -p ~/afcfta-intelligence
cd ~/afcfta-intelligence

# Step 2: Create Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Step 3: Install exact dependencies
pip install --upgrade pip

pip install \
    psycopg2-binary==2.9.9 \
    sqlalchemy==2.0.36 \
    alembic==1.14.1 \
    pandas==2.2.3 \
    openpyxl==3.1.5 \
    pdfplumber==0.11.4 \
    tabula-py==2.9.3 \
    python-dotenv==1.0.1 \
    uuid7==0.1.0

# Step 4: Create source document directories
mkdir -p data/raw/{01_primary_law,02_rules_of_origin,03_tariff_schedules,04_operational_customs,05_status_and_transition,06_reference_data}
mkdir -p data/staged/{extracted_tables,raw_csv,review_queue,parse_errors}
mkdir -p data/processed/{rules,tariffs,status,evidence}

# Step 5: Create parser module directory
mkdir -p scripts/parsers
touch scripts/__init__.py
touch scripts/parsers/__init__.py

# Step 6: Create .env file for database connection
cat > .env << 'EOF'
DATABASE_URL=postgresql://afcfta_user:afcfta_pass@localhost:5432/afcfta_db
HS_VERSION=HS2017
EOF

# Step 7: Verify PostgreSQL is running and accessible
psql -U afcfta_user -d afcfta_db -c "SELECT 1;" || echo "ERROR: Cannot connect to PostgreSQL. Fix connection before proceeding."
```

---

# SECTION 2: DATABASE SCHEMA

Run this SQL in order. Every statement depends on the ones before it.

Save as `scripts/000_create_schema.sql` and execute with:
```bash
psql -U afcfta_user -d afcfta_db -f scripts/000_create_schema.sql
```

```sql
-- ============================================================
-- AfCFTA Intelligence System — Complete DDL for Parsing Pipeline
-- Run this file ONCE to initialize the database.
-- Prerequisite: PostgreSQL 15+ with superuser or CREATE rights.
-- ============================================================

-- 0. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Enums (exact values from Concrete_Contract.md)
CREATE TYPE authority_tier_enum AS ENUM (
  'binding','official_operational','interpretive','analytic_enrichment'
);
CREATE TYPE source_type_enum AS ENUM (
  'agreement','protocol','annex','appendix','tariff_schedule',
  'ministerial_decision','status_notice','implementation_circular',
  'guidance_note','manual','analytics_reference','other'
);
CREATE TYPE source_status_enum AS ENUM (
  'current','superseded','provisional','draft','pending','archived'
);
CREATE TYPE hs_level_enum AS ENUM (
  'chapter','heading','subheading','tariff_line'
);
CREATE TYPE rule_status_enum AS ENUM (
  'agreed','pending','partially_agreed','provisional','superseded'
);
CREATE TYPE rule_component_type_enum AS ENUM (
  'WO','VA','VNM','CTH','CTSH','CC','PROCESS','ALT_RULE','EXCEPTION','NOTE'
);
CREATE TYPE operator_type_enum AS ENUM (
  'and','or','not','standalone'
);
CREATE TYPE threshold_basis_enum AS ENUM (
  'ex_works','fob','value_of_non_originating_materials','customs_value','unknown'
);
CREATE TYPE schedule_status_enum AS ENUM (
  'official','provisional','gazetted','superseded','draft'
);
CREATE TYPE tariff_category_enum AS ENUM (
  'liberalised','sensitive','excluded','unknown'
);
CREATE TYPE staging_type_enum AS ENUM (
  'immediate','linear','stepwise','unknown'
);
CREATE TYPE rate_status_enum AS ENUM (
  'in_force','projected','provisional','superseded'
);
CREATE TYPE status_type_enum AS ENUM (
  'agreed','pending','provisional','under_review','transitional',
  'superseded','in_force','not_yet_operational','expired'
);
CREATE TYPE persona_mode_enum AS ENUM (
  'officer','analyst','exporter','system'
);
CREATE TYPE requirement_type_enum AS ENUM (
  'certificate_of_origin','supplier_declaration','process_record',
  'bill_of_materials','cost_breakdown','invoice','transport_record',
  'customs_supporting_doc','valuation_support','inspection_record','other'
);

-- 2. source_registry
CREATE TABLE source_registry (
  source_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  title text NOT NULL,
  short_title text NOT NULL,
  source_group text NOT NULL,
  source_type source_type_enum NOT NULL,
  authority_tier authority_tier_enum NOT NULL,
  issuing_body text NOT NULL,
  jurisdiction_scope text NOT NULL,
  country_code text,
  customs_union_code text,
  publication_date date,
  effective_date date,
  expiry_date date,
  version_label text,
  status source_status_enum NOT NULL DEFAULT 'current',
  language text NOT NULL DEFAULT 'en',
  hs_version text,
  file_path text NOT NULL,
  mime_type text NOT NULL,
  source_url text,
  checksum_sha256 text NOT NULL UNIQUE,
  supersedes_source_id uuid REFERENCES source_registry(source_id),
  superseded_by_source_id uuid REFERENCES source_registry(source_id),
  citation_preferred text,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_source_registry_type ON source_registry(source_type);
CREATE INDEX idx_source_registry_tier ON source_registry(authority_tier);
CREATE INDEX idx_source_registry_status ON source_registry(status);
CREATE INDEX idx_source_registry_country ON source_registry(country_code);

-- 3. hs6_product (NOT in Concrete_Contract.md — derived from Join_Strategy.md)
CREATE TABLE hs6_product (
  hs6_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  hs_version text NOT NULL,
  hs6_code text NOT NULL,
  hs6_display text NOT NULL,
  chapter text NOT NULL,
  heading text NOT NULL,
  description text NOT NULL,
  section text,
  section_name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (hs_version, hs6_code)
);
CREATE INDEX idx_hs6_product_ver_code ON hs6_product(hs_version, hs6_code);
CREATE INDEX idx_hs6_product_chapter ON hs6_product(chapter);
CREATE INDEX idx_hs6_product_heading ON hs6_product(heading);
CREATE INDEX idx_hs6_product_desc_trgm ON hs6_product USING GIN(description gin_trgm_ops);

-- 4. psr_rule
CREATE TABLE psr_rule (
  psr_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
  appendix_version text,
  hs_version text NOT NULL,
  hs_code text NOT NULL,
  hs_code_start text,
  hs_code_end text,
  hs_level hs_level_enum NOT NULL,
  product_description text NOT NULL,
  legal_rule_text_verbatim text NOT NULL,
  legal_rule_text_normalized text,
  rule_status rule_status_enum NOT NULL,
  effective_date date,
  page_ref integer,
  table_ref text,
  row_ref text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, hs_version, hs_code, COALESCE(row_ref, ''))
);
CREATE INDEX idx_psr_rule_hs_code ON psr_rule(hs_code);
CREATE INDEX idx_psr_rule_hs_version ON psr_rule(hs_version);
CREATE INDEX idx_psr_rule_status ON psr_rule(rule_status);
CREATE INDEX idx_psr_rule_hs_level ON psr_rule(hs_level);

-- 5. psr_rule_component
CREATE TABLE psr_rule_component (
  component_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  psr_id uuid NOT NULL REFERENCES psr_rule(psr_id) ON DELETE CASCADE,
  component_type rule_component_type_enum NOT NULL,
  operator_type operator_type_enum NOT NULL DEFAULT 'standalone',
  threshold_percent numeric(7,3),
  threshold_basis threshold_basis_enum,
  tariff_shift_level hs_level_enum,
  specific_process_text text,
  component_text_verbatim text NOT NULL,
  normalized_expression text,
  confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
  component_order integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_psr_rule_component_psr_id ON psr_rule_component(psr_id);
CREATE INDEX idx_psr_rule_component_type ON psr_rule_component(component_type);
CREATE INDEX idx_psr_rule_component_order ON psr_rule_component(psr_id, component_order);
ALTER TABLE psr_rule_component ADD CONSTRAINT chk_psr_component_threshold
  CHECK (threshold_percent IS NULL OR (threshold_percent >= 0 AND threshold_percent <= 100));
ALTER TABLE psr_rule_component ADD CONSTRAINT chk_psr_component_confidence
  CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000);

-- 6. eligibility_rule_pathway (NOT in Concrete_Contract.md — derived from Join_Strategy.md + FastAPI_layout.md)
CREATE TABLE eligibility_rule_pathway (
  pathway_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  psr_id uuid NOT NULL REFERENCES psr_rule(psr_id) ON DELETE CASCADE,
  pathway_code text NOT NULL,
  pathway_label text NOT NULL,
  pathway_type text NOT NULL DEFAULT 'specific',
  expression_json jsonb NOT NULL,
  threshold_percent numeric(7,3),
  threshold_basis threshold_basis_enum,
  tariff_shift_level hs_level_enum,
  required_process_text text,
  allows_cumulation boolean NOT NULL DEFAULT true,
  allows_tolerance boolean NOT NULL DEFAULT true,
  priority_rank integer NOT NULL DEFAULT 1,
  effective_date date,
  expiry_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_eligibility_rule_pathway_psr ON eligibility_rule_pathway(psr_id, priority_rank, effective_date, expiry_date);

-- 7. hs6_psr_applicability (NOT in Concrete_Contract.md — derived from Join_Strategy.md)
CREATE TABLE hs6_psr_applicability (
  applicability_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  hs6_id uuid NOT NULL REFERENCES hs6_product(hs6_id) ON DELETE CASCADE,
  psr_id uuid NOT NULL REFERENCES psr_rule(psr_id) ON DELETE CASCADE,
  applicability_type text NOT NULL,  -- 'direct', 'range', 'inherited_heading', 'inherited_chapter'
  priority_rank integer NOT NULL DEFAULT 1,
  effective_date date,
  expiry_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (hs6_id, psr_id)
);
CREATE INDEX idx_hs6_psr_applicability_lookup ON hs6_psr_applicability(hs6_id, priority_rank, effective_date, expiry_date);

-- 8. tariff_schedule_header
CREATE TABLE tariff_schedule_header (
  schedule_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
  importing_state text NOT NULL,
  exporting_scope text NOT NULL,
  schedule_status schedule_status_enum NOT NULL,
  publication_date date,
  effective_date date,
  expiry_date date,
  hs_version text NOT NULL,
  category_system text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, importing_state, exporting_scope, hs_version)
);
CREATE INDEX idx_tariff_schedule_header_importing_state ON tariff_schedule_header(importing_state);
CREATE INDEX idx_tariff_schedule_header_status ON tariff_schedule_header(schedule_status);
CREATE INDEX idx_tariff_schedule_header_corridor ON tariff_schedule_header(importing_state, exporting_scope, schedule_status, effective_date);

-- 9. tariff_schedule_line
CREATE TABLE tariff_schedule_line (
  schedule_line_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  schedule_id uuid NOT NULL REFERENCES tariff_schedule_header(schedule_id) ON DELETE CASCADE,
  hs_code text NOT NULL,
  product_description text NOT NULL,
  tariff_category tariff_category_enum NOT NULL DEFAULT 'unknown',
  mfn_base_rate numeric(8,4),
  base_year integer,
  target_rate numeric(8,4),
  target_year integer,
  staging_type staging_type_enum NOT NULL DEFAULT 'unknown',
  page_ref integer,
  table_ref text,
  row_ref text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (schedule_id, hs_code, COALESCE(row_ref, ''))
);
CREATE INDEX idx_tariff_schedule_line_schedule ON tariff_schedule_line(schedule_id);
CREATE INDEX idx_tariff_schedule_line_hs_code ON tariff_schedule_line(hs_code);

-- 10. tariff_schedule_rate_by_year
CREATE TABLE tariff_schedule_rate_by_year (
  year_rate_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  schedule_line_id uuid NOT NULL REFERENCES tariff_schedule_line(schedule_line_id) ON DELETE CASCADE,
  calendar_year integer NOT NULL,
  preferential_rate numeric(8,4) NOT NULL,
  rate_status rate_status_enum NOT NULL DEFAULT 'in_force',
  source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
  page_ref integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (schedule_line_id, calendar_year)
);
CREATE INDEX idx_tariff_rate_year_lookup ON tariff_schedule_rate_by_year(schedule_line_id, calendar_year);

-- 11. status_assertion
CREATE TABLE status_assertion (
  status_assertion_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  status_type status_type_enum NOT NULL,
  status_text_verbatim text NOT NULL,
  effective_from date,
  effective_to date,
  page_ref integer,
  clause_ref text,
  confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_status_assertion_entity ON status_assertion(entity_type, entity_key);
CREATE INDEX idx_status_assertion_entity_window ON status_assertion(entity_type, entity_key, effective_from, effective_to);

-- 12. evidence_requirement
CREATE TABLE evidence_requirement (
  evidence_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  persona_mode persona_mode_enum NOT NULL DEFAULT 'exporter',
  requirement_type requirement_type_enum NOT NULL,
  requirement_label text NOT NULL,
  requirement_description text,
  is_mandatory boolean NOT NULL DEFAULT true,
  priority_level integer NOT NULL DEFAULT 1,
  conditional_on jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidence_requirement_entity ON evidence_requirement(entity_type, entity_key);
CREATE INDEX idx_evidence_requirement_match ON evidence_requirement(persona_mode, entity_type, entity_key, priority_level);

-- 13. Parse tracking table (not in original schema — added for pipeline observability)
CREATE TABLE parse_log (
  log_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  module_name text NOT NULL,
  source_file text NOT NULL,
  total_rows_extracted integer NOT NULL DEFAULT 0,
  rows_parsed_ok integer NOT NULL DEFAULT 0,
  rows_low_confidence integer NOT NULL DEFAULT 0,
  rows_failed integer NOT NULL DEFAULT 0,
  errors jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
```

---

# SECTION 3: PROJECT FILE STRUCTURE

After running all setup commands, the directory tree MUST look exactly like this:

```
~/afcfta-intelligence/
├── .env
├── .venv/
├── data/
│   ├── raw/
│   │   ├── 01_primary_law/          ← AfCFTA Agreement, Protocol, Annexes PDFs
│   │   ├── 02_rules_of_origin/      ← Annex 2, Appendix IV PDF
│   │   ├── 03_tariff_schedules/     ← e-Tariff Book exports (.xlsx/.csv per country)
│   │   ├── 04_operational_customs/  ← Annex 3, customs guidance
│   │   ├── 05_status_and_transition/← Ministerial decisions, status reports
│   │   └── 06_reference_data/       ← HS nomenclature CSV, ISO country codes
│   ├── staged/
│   │   ├── extracted_tables/        ← Raw CSV dumps from PDF extraction
│   │   ├── raw_csv/                 ← Intermediate cleaned CSVs
│   │   ├── review_queue/            ← CSVs of rows needing human review
│   │   └── parse_errors/            ← CSVs of rows that failed parsing
│   └── processed/
│       ├── rules/                   ← Final JSON per parsed PSR rule
│       ├── tariffs/                 ← Final JSON per parsed tariff line
│       ├── status/                  ← Final JSON per status assertion
│       └── evidence/                ← Final JSON per evidence requirement
├── scripts/
│   ├── __init__.py
│   ├── 000_create_schema.sql
│   ├── constants.py                 ← From SECTION 0 above
│   ├── db.py                        ← Database connection helper
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── source_registry_loader.py
│   │   ├── hs6_backbone_loader.py
│   │   ├── tariff_schedule_parser.py
│   │   ├── appendix_iv_extractor.py
│   │   ├── psr_row_classifier.py
│   │   ├── hs_code_normalizer.py
│   │   ├── rule_decomposer.py
│   │   ├── pathway_builder.py
│   │   ├── applicability_builder.py
│   │   ├── psr_db_inserter.py
│   │   ├── validation_runner.py
│   │   ├── review_queue_exporter.py
│   │   ├── status_assertion_loader.py
│   │   └── evidence_requirement_seeder.py
│   └── run_full_pipeline.py         ← Orchestrator
└── tests/
    ├── test_rule_decomposer.py
    ├── test_pathway_builder.py
    └── test_vectors.json
```

---

# SECTION 4: MODULE — db.py (Database Connection)

```python
"""
scripts/db.py
Database connection helper. Used by every other module.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """Return a new SQLAlchemy session. Caller MUST call session.close()."""
    return SessionLocal()


def execute_sql(sql_string: str, params: dict = None):
    """Execute a single SQL statement. Returns result proxy."""
    with engine.connect() as conn:
        result = conn.execute(text(sql_string), params or {})
        conn.commit()
        return result


def fetch_all(sql_string: str, params: dict = None) -> list[dict]:
    """Execute SELECT and return list of dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(sql_string), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


def fetch_one(sql_string: str, params: dict = None) -> dict | None:
    """Execute SELECT and return single dict or None."""
    rows = fetch_all(sql_string, params)
    return rows[0] if rows else None


def fetch_scalar(sql_string: str, params: dict = None):
    """Execute SELECT and return single scalar value."""
    with engine.connect() as conn:
        result = conn.execute(text(sql_string), params or {})
        row = result.fetchone()
        return row[0] if row else None
```

---

# SECTION 19: TEST VECTORS

These are exact input-to-output mappings. Use them to validate every module.

## Test Vector 1: Simple WO rule

**Input rule text:** `"WO"`
**Expected components:**
```json
[
  {
    "component_type": "WO",
    "operator_type": "standalone",
    "threshold_percent": null,
    "threshold_basis": null,
    "tariff_shift_level": null,
    "specific_process_text": null,
    "confidence_score": 1.000,
    "component_order": 1
  }
]
```
**Expected pathway expression_json:**
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

## Test Vector 2: Simple CTH rule

**Input rule text:** `"CTH"`
**Expected components:**
```json
[
  {
    "component_type": "CTH",
    "operator_type": "standalone",
    "threshold_percent": null,
    "threshold_basis": null,
    "tariff_shift_level": "heading",
    "specific_process_text": null,
    "confidence_score": 1.000,
    "component_order": 1
  }
]
```
**Expected pathway expression_json:**
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

## Test Vector 3: VNM threshold rule

**Input rule text:** `"MaxNOM 55% (EXW)"`
**Expected components:**
```json
[
  {
    "component_type": "VNM",
    "operator_type": "standalone",
    "threshold_percent": 55.000,
    "threshold_basis": "ex_works",
    "tariff_shift_level": null,
    "specific_process_text": null,
    "confidence_score": 1.000,
    "component_order": 1
  }
]
```
**Expected pathway expression_json:**
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

## Test Vector 4: OR alternative — two pathways

**Input rule text:** `"CTH; or MaxNOM 55% (EXW)"`
**Expected components:**
```json
[
  {
    "component_type": "CTH",
    "operator_type": "standalone",
    "threshold_percent": null,
    "threshold_basis": null,
    "tariff_shift_level": "heading",
    "confidence_score": 1.000,
    "component_order": 1
  },
  {
    "component_type": "VNM",
    "operator_type": "or",
    "threshold_percent": 55.000,
    "threshold_basis": "ex_works",
    "tariff_shift_level": null,
    "confidence_score": 1.000,
    "component_order": 2
  }
]
```
**Expected: TWO separate pathway records.**
Pathway 1 expression_json:
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
Pathway 2 expression_json:
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

## Test Vector 5: AND combination — one pathway

**Input rule text:** `"CTH and MaxNOM 50% (EXW)"`
**Expected components:**
```json
[
  {
    "component_type": "CTH",
    "operator_type": "standalone",
    "threshold_percent": null,
    "tariff_shift_level": "heading",
    "confidence_score": 1.000,
    "component_order": 1
  },
  {
    "component_type": "VNM",
    "operator_type": "and",
    "threshold_percent": 50.000,
    "threshold_basis": "ex_works",
    "confidence_score": 1.000,
    "component_order": 2
  }
]
```
**Expected: ONE pathway record.**
Expression_json:
```json
{
  "pathway_code": "CTH+VNM",
  "variables": [
    {"name": "vnom_percent", "formula": "non_originating / ex_works * 100"}
  ],
  "expression": {
    "op": "all",
    "args": [
      {
        "op": "every_non_originating_input",
        "test": {"op": "heading_ne_output"}
      },
      {
        "op": "formula_lte",
        "formula": "vnom_percent",
        "value": 50
      }
    ]
  }
}
```

## Test Vector 6: CTH with exception

**Input rule text:** `"CTH except from heading 10.06"`
**Expected components:**
```json
[
  {
    "component_type": "CTH",
    "operator_type": "standalone",
    "threshold_percent": null,
    "tariff_shift_level": "heading",
    "specific_process_text": "except from heading 10.06",
    "confidence_score": 1.000,
    "component_order": 1
  }
]
```
**Expected pathway expression_json:**
```json
{
  "pathway_code": "CTH",
  "variables": [],
  "expression": {
    "op": "every_non_originating_input",
    "test": {"op": "heading_ne_output"},
    "exceptions": "except from heading 10.06"
  }
}
```

## Test Vector 7: Unparseable rule (PROCESS type)

**Input rule text:** `"Manufacture from chemical materials of any heading"`
**Expected components:**
```json
[
  {
    "component_type": "PROCESS",
    "operator_type": "standalone",
    "threshold_percent": null,
    "threshold_basis": null,
    "tariff_shift_level": null,
    "specific_process_text": "Manufacture from chemical materials of any heading",
    "normalized_expression": null,
    "confidence_score": 0.500,
    "component_order": 1
  }
]
```
**Expected pathway expression_json:**
```json
{
  "pathway_code": "PROCESS",
  "variables": [],
  "expression": null
}
```
**Note:** `expression` is null because PROCESS rules cannot be auto-decomposed into the expression DSL. The pathway record is still created (so the data model is complete), but with a null expression. The validation runner will flag this. The review queue will export it. A human must write the expression manually.

## Test Vector 8: Applicability inheritance

**Given these psr_rule records:**
- Chapter 01, hs_code="01", hs_level="chapter", rule="WO"
- Heading 0301, hs_code="0301", hs_level="heading", rule="CTH"
- Subheading 030111, hs_code="030111", hs_level="subheading", rule="CTSH"

**Given these hs6_product records:**
- 010111 (chapter 01, heading 0101)
- 010121 (chapter 01, heading 0101)
- 030111 (chapter 03, heading 0301)
- 030119 (chapter 03, heading 0301)
- 030211 (chapter 03, heading 0302)

**Expected applicability:**
| hs6_code | matched_rule | applicability_type | priority_rank |
|----------|-------------|-------------------|---------------|
| 010111   | Chapter 01 WO | inherited_chapter | 3 |
| 010121   | Chapter 01 WO | inherited_chapter | 3 |
| 030111   | Subheading 030111 CTSH | direct | 1 |
| 030119   | Heading 0301 CTH | inherited_heading | 2 |
| 030211   | (no match) | — | — |

---

# SECTION 20: TROUBLESHOOTING DECISION TREE

When a step fails, follow this tree exactly:

```
PDF extraction returns empty tables?
  → Try different extraction settings: pdfplumber.open(path).pages[n].extract_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"})
  → If still empty: the PDF may use OCR-only images. Run OCR first: pip install pytesseract; then use pdfplumber with the text strategy.
  → If still empty: manually export the table to CSV and place in data/staged/extracted_tables/

HS code cell is empty for a row?
  → Check if row_type is CONTINUATION. If yes, merge this row's rule text with the previous row's rule text.
  → If row_type is SECTION_HEADER, skip entirely.
  → If row_type is UNPARSEABLE, log to data/staged/parse_errors/ and continue.

Rule decomposer returns confidence_score = 0.0?
  → This is expected for unusual rule phrasings. The row will appear in the review queue.
  → Do NOT attempt to fix the parser for edge cases until you have processed the full document.
  → A human reviewer fills in the corrected values in the review queue CSV, then a re-import script applies corrections.

Database insert fails with UNIQUE constraint violation?
  → The same source + HS code + row_ref combination already exists.
  → This means you are re-running the pipeline without clearing previous data.
  → Solution: either DELETE FROM psr_rule WHERE source_id = '<source_id>' first, or add ON CONFLICT DO UPDATE logic.

expression_json fails JSONSchema validation?
  → Check that all "op" values are in VALID_EXPRESSION_OPS.
  → Check that "formula" references are exactly "vnom_percent" or "va_percent" (no other names).
  → Check that "value" for formula_lte is a number, not a string.
  → Check that "fact" for fact_eq is a valid fact name.

Coverage report shows < 50% HS6 codes covered?
  → This is likely correct for v0.1. Appendix IV does not cover all HS6 codes.
  → Verify that chapter-level rules are being inherited properly.
  → Check that the inheritance builder is running AFTER all psr_rule inserts.

Tariff rate values > 100?
  → Some tariff lines use specific duties (e.g., "$5/kg + 10%"). These are compound rates.
  → Store mfn_base_rate as NULL for compound rates. Log the raw text to row_ref or notes.
  → The v0.1 engine only handles ad valorem (percentage) rates.
```

---

*This specification is complete. Every module referenced in the TABLE OF CONTENTS (Sections 4-18) should be implemented as a standalone Python file following the patterns, constants, enum values, and JSON schemas defined in Sections 0, 2, and 19. Each module receives typed input and produces typed output. Each module logs errors to data/staged/parse_errors/. Each module writes review items to data/staged/review_queue/. The orchestrator in Section 18 calls them in the exact order listed in the TABLE OF CONTENTS.*
