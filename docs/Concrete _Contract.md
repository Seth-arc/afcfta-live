Below is a **concrete PostgreSQL schema** and a matching **API contract** for the first ten core tables you named.

I’m assuming:

* **PostgreSQL 15+**
* `uuid` primary keys
* `jsonb` where flexibility is useful but not core
* `numeric` for tariff and threshold precision
* `text` for verbatim legal text
* API is **REST-first**, with predictable JSON contracts
* all timestamps are `timestamptz`
* canonical codes use **ISO alpha-2/alpha-3 or your internal standard**, but should be normalized consistently

---

# 1) PostgreSQL schema

## 1.1 Shared setup

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 1.2 Enums

```sql
CREATE TYPE authority_tier_enum AS ENUM (
  'binding',
  'official_operational',
  'interpretive',
  'analytic_enrichment'
);

CREATE TYPE source_type_enum AS ENUM (
  'agreement',
  'protocol',
  'annex',
  'appendix',
  'tariff_schedule',
  'ministerial_decision',
  'status_notice',
  'implementation_circular',
  'guidance_note',
  'manual',
  'analytics_reference',
  'other'
);

CREATE TYPE source_status_enum AS ENUM (
  'current',
  'superseded',
  'provisional',
  'draft',
  'pending',
  'archived'
);

CREATE TYPE instrument_type_enum AS ENUM (
  'agreement',
  'protocol',
  'annex',
  'appendix',
  'decision',
  'circular',
  'guidance',
  'manual',
  'other'
);

CREATE TYPE provision_status_enum AS ENUM (
  'in_force',
  'provisional',
  'pending',
  'superseded',
  'expired'
);

CREATE TYPE hs_level_enum AS ENUM (
  'chapter',
  'heading',
  'subheading',
  'tariff_line'
);

CREATE TYPE rule_status_enum AS ENUM (
  'agreed',
  'pending',
  'partially_agreed',
  'provisional',
  'superseded'
);

CREATE TYPE rule_component_type_enum AS ENUM (
  'WO',
  'VA',
  'VNM',
  'CTH',
  'CTSH',
  'CC',
  'PROCESS',
  'ALT_RULE',
  'EXCEPTION',
  'NOTE'
);

CREATE TYPE operator_type_enum AS ENUM (
  'and',
  'or',
  'not',
  'standalone'
);

CREATE TYPE threshold_basis_enum AS ENUM (
  'ex_works',
  'fob',
  'value_of_non_originating_materials',
  'customs_value',
  'unknown'
);

CREATE TYPE schedule_status_enum AS ENUM (
  'official',
  'provisional',
  'gazetted',
  'superseded',
  'draft'
);

CREATE TYPE tariff_category_enum AS ENUM (
  'liberalised',
  'sensitive',
  'excluded',
  'unknown'
);

CREATE TYPE staging_type_enum AS ENUM (
  'immediate',
  'linear',
  'stepwise',
  'unknown'
);

CREATE TYPE rate_status_enum AS ENUM (
  'in_force',
  'projected',
  'provisional',
  'superseded'
);

CREATE TYPE status_type_enum AS ENUM (
  'agreed',
  'pending',
  'provisional',
  'under_review',
  'transitional',
  'superseded',
  'in_force',
  'not_yet_operational',
  'expired'
);

CREATE TYPE persona_mode_enum AS ENUM (
  'officer',
  'analyst',
  'exporter',
  'system'
);

CREATE TYPE requirement_type_enum AS ENUM (
  'certificate_of_origin',
  'supplier_declaration',
  'process_record',
  'bill_of_materials',
  'cost_breakdown',
  'invoice',
  'transport_record',
  'customs_supporting_doc',
  'valuation_support',
  'inspection_record',
  'other'
);

CREATE TYPE decision_outcome_enum AS ENUM (
  'likely_eligible',
  'likely_not_eligible',
  'uncertain',
  'insufficient_information'
);

CREATE TYPE confidence_level_enum AS ENUM (
  'high',
  'medium',
  'low'
);
```

---

## 1.3 `source_registry`

```sql
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
CREATE INDEX idx_source_registry_effective_date ON source_registry(effective_date);
```

### Constraints worth enforcing

```sql
ALTER TABLE source_registry
ADD CONSTRAINT chk_source_dates
CHECK (
  expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date
);
```

---

## 1.4 `legal_provision`

```sql
CREATE TABLE legal_provision (
  provision_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
  instrument_name text NOT NULL,
  instrument_type instrument_type_enum NOT NULL,
  article_ref text,
  annex_ref text,
  appendix_ref text,
  section_ref text,
  subsection_ref text,
  page_start integer,
  page_end integer,
  topic_primary text NOT NULL,
  topic_secondary text[],
  provision_text_verbatim text NOT NULL,
  provision_text_normalized text,
  effective_date date,
  expiry_date date,
  status provision_status_enum NOT NULL DEFAULT 'in_force',
  cross_reference_refs text[],
  authority_weight numeric(4,3) NOT NULL DEFAULT 1.000,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_legal_provision_source ON legal_provision(source_id);
CREATE INDEX idx_legal_provision_topic_primary ON legal_provision(topic_primary);
CREATE INDEX idx_legal_provision_status ON legal_provision(status);
CREATE INDEX idx_legal_provision_article_ref ON legal_provision(article_ref);
CREATE INDEX idx_legal_provision_annex_ref ON legal_provision(annex_ref);
CREATE INDEX idx_legal_provision_topic_secondary_gin ON legal_provision USING GIN(topic_secondary);
CREATE INDEX idx_legal_provision_crossrefs_gin ON legal_provision USING GIN(cross_reference_refs);
CREATE INDEX idx_legal_provision_text_trgm ON legal_provision USING GIN(provision_text_verbatim gin_trgm_ops);
```

```sql
ALTER TABLE legal_provision
ADD CONSTRAINT chk_legal_provision_pages
CHECK (
  page_start IS NULL OR page_end IS NULL OR page_end >= page_start
);

ALTER TABLE legal_provision
ADD CONSTRAINT chk_legal_provision_weight
CHECK (authority_weight >= 0.000 AND authority_weight <= 9.999);
```

---

## 1.5 `psr_rule`

```sql
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

CREATE INDEX idx_psr_rule_source ON psr_rule(source_id);
CREATE INDEX idx_psr_rule_hs_code ON psr_rule(hs_code);
CREATE INDEX idx_psr_rule_hs_version ON psr_rule(hs_version);
CREATE INDEX idx_psr_rule_status ON psr_rule(rule_status);
CREATE INDEX idx_psr_rule_hs_level ON psr_rule(hs_level);
CREATE INDEX idx_psr_rule_desc_trgm ON psr_rule USING GIN(product_description gin_trgm_ops);
```

---

## 1.6 `psr_rule_component`

```sql
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
```

```sql
ALTER TABLE psr_rule_component
ADD CONSTRAINT chk_psr_component_threshold
CHECK (
  threshold_percent IS NULL OR (threshold_percent >= 0 AND threshold_percent <= 100)
);

ALTER TABLE psr_rule_component
ADD CONSTRAINT chk_psr_component_confidence
CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000);
```

---

## 1.7 `tariff_schedule_header`

```sql
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

CREATE INDEX idx_tariff_schedule_header_source ON tariff_schedule_header(source_id);
CREATE INDEX idx_tariff_schedule_header_importing_state ON tariff_schedule_header(importing_state);
CREATE INDEX idx_tariff_schedule_header_status ON tariff_schedule_header(schedule_status);
CREATE INDEX idx_tariff_schedule_header_effective_date ON tariff_schedule_header(effective_date);
```

---

## 1.8 `tariff_schedule_line`

```sql
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
CREATE INDEX idx_tariff_schedule_line_category ON tariff_schedule_line(tariff_category);
CREATE INDEX idx_tariff_schedule_line_target_year ON tariff_schedule_line(target_year);
CREATE INDEX idx_tariff_schedule_line_desc_trgm ON tariff_schedule_line USING GIN(product_description gin_trgm_ops);
```

```sql
ALTER TABLE tariff_schedule_line
ADD CONSTRAINT chk_tariff_schedule_line_rates
CHECK (
  (mfn_base_rate IS NULL OR (mfn_base_rate >= 0 AND mfn_base_rate <= 1000))
  AND (target_rate IS NULL OR (target_rate >= 0 AND target_rate <= 1000))
);

ALTER TABLE tariff_schedule_line
ADD CONSTRAINT chk_tariff_schedule_line_years
CHECK (
  target_year IS NULL OR base_year IS NULL OR target_year >= base_year
);
```

---

## 1.9 `tariff_schedule_rate_by_year`

```sql
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

CREATE INDEX idx_tariff_rate_year_line ON tariff_schedule_rate_by_year(schedule_line_id);
CREATE INDEX idx_tariff_rate_year_calendar ON tariff_schedule_rate_by_year(calendar_year);
CREATE INDEX idx_tariff_rate_year_status ON tariff_schedule_rate_by_year(rate_status);
```

```sql
ALTER TABLE tariff_schedule_rate_by_year
ADD CONSTRAINT chk_tariff_rate_preferential_rate
CHECK (preferential_rate >= 0 AND preferential_rate <= 1000);
```

---

## 1.10 `status_assertion`

```sql
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
CREATE INDEX idx_status_assertion_status_type ON status_assertion(status_type);
CREATE INDEX idx_status_assertion_source ON status_assertion(source_id);
```

```sql
ALTER TABLE status_assertion
ADD CONSTRAINT chk_status_assertion_dates
CHECK (
  effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from
);

ALTER TABLE status_assertion
ADD CONSTRAINT chk_status_assertion_confidence
CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000);
```

---

## 1.11 `evidence_requirement`

```sql
CREATE TABLE evidence_requirement (
  evidence_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  persona_mode persona_mode_enum NOT NULL,
  requirement_type requirement_type_enum NOT NULL,
  requirement_description text NOT NULL,
  legal_basis_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
  required boolean NOT NULL DEFAULT true,
  conditional_on jsonb,
  priority_level smallint NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_requirement_entity ON evidence_requirement(entity_type, entity_key);
CREATE INDEX idx_evidence_requirement_persona ON evidence_requirement(persona_mode);
CREATE INDEX idx_evidence_requirement_type ON evidence_requirement(requirement_type);
CREATE INDEX idx_evidence_requirement_conditional_gin ON evidence_requirement USING GIN(conditional_on);
```

```sql
ALTER TABLE evidence_requirement
ADD CONSTRAINT chk_evidence_priority
CHECK (priority_level BETWEEN 1 AND 5);
```

---

## 1.12 `case_assessment`

This is the summary decision table. In practice you will also want `case_file` and `case_input_fact`, but since you asked for these ten first, I’ll keep it scoped.

```sql
CREATE TABLE case_assessment (
  assessment_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  case_external_ref text NOT NULL,
  assessment_type text NOT NULL,
  decision_outcome decision_outcome_enum NOT NULL,
  confidence_level confidence_level_enum NOT NULL,
  decision_reasoning text NOT NULL,
  exporter_state text,
  importer_state text,
  hs_code text,
  linked_psr_id uuid REFERENCES psr_rule(psr_id) ON DELETE SET NULL,
  linked_schedule_line_id uuid REFERENCES tariff_schedule_line(schedule_line_id) ON DELETE SET NULL,
  linked_provision_ids uuid[],
  missing_evidence jsonb,
  risk_flags jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  generated_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_assessment_case_ref ON case_assessment(case_external_ref);
CREATE INDEX idx_case_assessment_outcome ON case_assessment(decision_outcome);
CREATE INDEX idx_case_assessment_hs_code ON case_assessment(hs_code);
CREATE INDEX idx_case_assessment_missing_evidence_gin ON case_assessment USING GIN(missing_evidence);
CREATE INDEX idx_case_assessment_risk_flags_gin ON case_assessment USING GIN(risk_flags);
```

---

# 2) Recommended view

## 2.1 `corridor_tariff_view`

```sql
CREATE VIEW corridor_tariff_view AS
SELECT
  tsh.schedule_id,
  tsl.schedule_line_id,
  tsh.importing_state,
  tsh.exporting_scope,
  tsl.hs_code,
  tsl.product_description,
  tsl.tariff_category,
  tsl.mfn_base_rate,
  tsl.base_year,
  tsl.target_rate,
  tsl.target_year,
  tsy.calendar_year,
  tsy.preferential_rate,
  tsh.schedule_status,
  tsh.hs_version,
  tsh.source_id
FROM tariff_schedule_header tsh
JOIN tariff_schedule_line tsl
  ON tsh.schedule_id = tsl.schedule_id
LEFT JOIN tariff_schedule_rate_by_year tsy
  ON tsl.schedule_line_id = tsy.schedule_line_id;
```

---

# 3) API contract

I recommend versioned REST:

* Base path: `/api/v1`
* Content type: `application/json`
* Errors: consistent machine-readable error object
* Pagination: cursor or limit/offset for admin/search endpoints
* Idempotency: use `PUT` for deterministic upserts where relevant

---

## 3.1 Common response envelope

### Success

```json
{
  "data": {},
  "meta": {
    "request_id": "req_123",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Error

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "hs_code is required",
    "details": {
      "field": "hs_code"
    }
  },
  "meta": {
    "request_id": "req_123",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

# 4) CRUD/admin endpoints for the ten tables

These are internal/admin-facing.

---

## 4.1 `source_registry`

### Create source

`POST /api/v1/sources`

#### Request

```json
{
  "title": "Compiled Annexes to the AfCFTA Agreement",
  "short_title": "Compiled Annexes",
  "source_group": "tier1_binding",
  "source_type": "annex",
  "authority_tier": "binding",
  "issuing_body": "African Union",
  "jurisdiction_scope": "continental",
  "country_code": null,
  "customs_union_code": null,
  "publication_date": "2022-01-01",
  "effective_date": "2022-01-01",
  "expiry_date": null,
  "version_label": "v2022-01",
  "status": "current",
  "language": "en",
  "hs_version": "HS2017",
  "file_path": "raw/tier1_binding/legal/compiled_annexes.pdf",
  "mime_type": "application/pdf",
  "source_url": "https://example.org/compiled_annexes.pdf",
  "checksum_sha256": "abc123",
  "supersedes_source_id": null,
  "citation_preferred": "Compiled Annexes, Annex 2",
  "notes": "Canonical English compilation"
}
```

### Response

```json
{
  "data": {
    "source_id": "uuid"
  },
  "meta": {
    "request_id": "req_1",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Get source

`GET /api/v1/sources/{source_id}`

### Search/list sources

`GET /api/v1/sources?source_type=annex&authority_tier=binding&status=current`

### Update source

`PATCH /api/v1/sources/{source_id}`

---

## 4.2 `legal_provision`

### Create provision

`POST /api/v1/legal-provisions`

#### Request

```json
{
  "source_id": "uuid",
  "instrument_name": "Annex 2 on Rules of Origin",
  "instrument_type": "annex",
  "article_ref": "Article 9",
  "annex_ref": "Annex 2",
  "appendix_ref": null,
  "section_ref": "Verification",
  "subsection_ref": "9(1)",
  "page_start": 88,
  "page_end": 89,
  "topic_primary": "verification",
  "topic_secondary": ["proof_of_origin", "officer_review"],
  "provision_text_verbatim": "Full verbatim text...",
  "provision_text_normalized": "Normalized text...",
  "effective_date": "2022-01-01",
  "expiry_date": null,
  "status": "in_force",
  "cross_reference_refs": ["Annex 2 Article 12"],
  "authority_weight": 1.0
}
```

### Get provision

`GET /api/v1/legal-provisions/{provision_id}`

### Search provisions

`GET /api/v1/legal-provisions?topic_primary=verification&annex_ref=Annex%202`

### Query by natural-language topic

`POST /api/v1/legal-provisions/search`

#### Request

```json
{
  "query": "What does AfCFTA say about de minimis?",
  "topics": ["de_minimis"],
  "authority_tiers": ["binding", "official_operational"],
  "limit": 10
}
```

#### Response

```json
{
  "data": [
    {
      "provision_id": "uuid",
      "instrument_name": "Annex 2 on Rules of Origin",
      "article_ref": "Article 4",
      "annex_ref": "Annex 2",
      "page_start": 42,
      "page_end": 43,
      "topic_primary": "de_minimis",
      "provision_text_verbatim": "..."
    }
  ],
  "meta": {
    "request_id": "req_2",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 4.3 `psr_rule`

### Create PSR rule

`POST /api/v1/psr-rules`

```json
{
  "source_id": "uuid",
  "appendix_version": "v2025-12",
  "hs_version": "HS2017",
  "hs_code": "1902.19",
  "hs_code_start": null,
  "hs_code_end": null,
  "hs_level": "subheading",
  "product_description": "Uncooked pasta, not stuffed",
  "legal_rule_text_verbatim": "Manufacture from ...",
  "legal_rule_text_normalized": "CTH OR VA>=40",
  "rule_status": "agreed",
  "effective_date": "2025-12-01",
  "page_ref": 143,
  "table_ref": "Appendix IV",
  "row_ref": "18"
}
```

### Get PSR rule

`GET /api/v1/psr-rules/{psr_id}`

### Lookup by HS

`GET /api/v1/psr-rules/lookup?hs_code=1902.19&hs_version=HS2017`

### Response

```json
{
  "data": {
    "psr_id": "uuid",
    "hs_code": "1902.19",
    "hs_version": "HS2017",
    "product_description": "Uncooked pasta, not stuffed",
    "legal_rule_text_verbatim": "Manufacture from ...",
    "rule_status": "agreed",
    "page_ref": 143,
    "table_ref": "Appendix IV",
    "row_ref": "18"
  },
  "meta": {
    "request_id": "req_3",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 4.4 `psr_rule_component`

### Add component

`POST /api/v1/psr-rule-components`

```json
{
  "psr_id": "uuid",
  "component_type": "CTH",
  "operator_type": "or",
  "threshold_percent": null,
  "threshold_basis": null,
  "tariff_shift_level": "heading",
  "specific_process_text": null,
  "component_text_verbatim": "Change in tariff heading",
  "normalized_expression": "CTH",
  "confidence_score": 0.99,
  "component_order": 1
}
```

### List components for rule

`GET /api/v1/psr-rules/{psr_id}/components`

---

## 4.5 `tariff_schedule_header`

### Create schedule header

`POST /api/v1/tariff-schedules`

```json
{
  "source_id": "uuid",
  "importing_state": "KEN",
  "exporting_scope": "all_afcfta",
  "schedule_status": "official",
  "publication_date": "2025-01-01",
  "effective_date": "2025-01-01",
  "expiry_date": null,
  "hs_version": "HS2017",
  "category_system": "AfCFTA standard",
  "notes": "Kenya schedule"
}
```

### Get schedule header

`GET /api/v1/tariff-schedules/{schedule_id}`

### List/filter schedule headers

`GET /api/v1/tariff-schedules?importing_state=KEN&schedule_status=official`

---

## 4.6 `tariff_schedule_line`

### Create schedule line

`POST /api/v1/tariff-schedule-lines`

```json
{
  "schedule_id": "uuid",
  "hs_code": "8703.23",
  "product_description": "Motor cars, spark-ignition...",
  "tariff_category": "sensitive",
  "mfn_base_rate": 25.0,
  "base_year": 2024,
  "target_rate": 0.0,
  "target_year": 2031,
  "staging_type": "linear",
  "page_ref": 55,
  "table_ref": "Schedule A",
  "row_ref": "221"
}
```

### Get line

`GET /api/v1/tariff-schedule-lines/{schedule_line_id}`

### Lookup by schedule + HS

`GET /api/v1/tariff-schedule-lines/lookup?schedule_id=uuid&hs_code=8703.23`

---

## 4.7 `tariff_schedule_rate_by_year`

### Create yearly rate

`POST /api/v1/tariff-schedule-rates`

```json
{
  "schedule_line_id": "uuid",
  "calendar_year": 2026,
  "preferential_rate": 20.0,
  "rate_status": "in_force",
  "source_id": "uuid",
  "page_ref": 55
}
```

### Get yearly rate

`GET /api/v1/tariff-schedule-rates/{year_rate_id}`

### List yearly rates for a line

`GET /api/v1/tariff-schedule-lines/{schedule_line_id}/rates`

---

## 4.8 `status_assertion`

### Create status assertion

`POST /api/v1/status-assertions`

```json
{
  "source_id": "uuid",
  "entity_type": "psr_rule",
  "entity_key": "1902.19",
  "status_type": "agreed",
  "status_text_verbatim": "This rule has been agreed by State Parties.",
  "effective_from": "2025-12-01",
  "effective_to": null,
  "page_ref": 3,
  "clause_ref": "Para 4",
  "confidence_score": 0.95
}
```

### Get status assertion

`GET /api/v1/status-assertions/{status_assertion_id}`

### Query assertions

`GET /api/v1/status-assertions?entity_type=psr_rule&entity_key=1902.19`

---

## 4.9 `evidence_requirement`

### Create evidence requirement

`POST /api/v1/evidence-requirements`

```json
{
  "entity_type": "psr_rule",
  "entity_key": "1902.19",
  "persona_mode": "exporter",
  "requirement_type": "bill_of_materials",
  "requirement_description": "Detailed BOM showing originating and non-originating inputs",
  "legal_basis_provision_id": "uuid",
  "required": true,
  "conditional_on": {
    "rule_component_types": ["VA", "VNM"]
  },
  "priority_level": 1
}
```

### Get requirement

`GET /api/v1/evidence-requirements/{evidence_id}`

### Query requirements

`GET /api/v1/evidence-requirements?entity_type=psr_rule&entity_key=1902.19&persona_mode=exporter`

---

## 4.10 `case_assessment`

### Create assessment

`POST /api/v1/case-assessments`

```json
{
  "case_external_ref": "CASE-2026-0001",
  "assessment_type": "eligibility_assessment",
  "decision_outcome": "uncertain",
  "confidence_level": "medium",
  "decision_reasoning": "The claimed rule path may be satisfied, but supplier declarations are missing.",
  "exporter_state": "GHA",
  "importer_state": "KEN",
  "hs_code": "1902.19",
  "linked_psr_id": "uuid",
  "linked_schedule_line_id": "uuid",
  "linked_provision_ids": ["uuid", "uuid"],
  "missing_evidence": {
    "required": ["supplier_declaration", "cost_breakdown"]
  },
  "risk_flags": {
    "status_exposure": "low",
    "documentary_gap": "medium"
  }
}
```

### Get assessment

`GET /api/v1/case-assessments/{assessment_id}`

### List by case ref

`GET /api/v1/case-assessments?case_external_ref=CASE-2026-0001`

---

# 5) Workflow endpoints

These are the real product endpoints. They compose the underlying tables.

---

## 5.1 Rule lookup endpoint

`GET /api/v1/workflows/rule-lookup?hs_code=1902.19&hs_version=HS2017`

### Response

```json
{
  "data": {
    "hs_code": "1902.19",
    "hs_version": "HS2017",
    "product_description": "Uncooked pasta, not stuffed",
    "rule": {
      "psr_id": "uuid",
      "legal_rule_text_verbatim": "Manufacture from ...",
      "rule_status": "agreed",
      "effective_date": "2025-12-01",
      "citation": {
        "source_id": "uuid",
        "page_ref": 143,
        "table_ref": "Appendix IV",
        "row_ref": "18"
      }
    },
    "components": [
      {
        "component_type": "CTH",
        "operator_type": "or",
        "threshold_percent": null,
        "threshold_basis": null,
        "tariff_shift_level": "heading",
        "normalized_expression": "CTH"
      }
    ],
    "status_assertions": [
      {
        "status_type": "agreed",
        "effective_from": "2025-12-01",
        "clause_ref": "Para 4"
      }
    ]
  },
  "meta": {
    "request_id": "req_4",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 5.2 Tariff corridor query endpoint

`GET /api/v1/workflows/tariff-query?exporter_state=GHA&importer_state=KEN&hs_code=1902.19&calendar_year=2026`

### Response

```json
{
  "data": {
    "exporter_state": "GHA",
    "importer_state": "KEN",
    "hs_code": "1902.19",
    "calendar_year": 2026,
    "schedule_status": "official",
    "mfn_base_rate": 20.0,
    "preferential_rate": 10.0,
    "target_rate": 0.0,
    "target_year": 2028,
    "tariff_category": "liberalised",
    "citation": {
      "source_id": "uuid",
      "page_ref": 55,
      "row_ref": "221"
    }
  },
  "meta": {
    "request_id": "req_5",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

If the schedule is missing or provisional, return that explicitly.

---

## 5.3 Legal Q&A retrieval endpoint

`POST /api/v1/workflows/legal-qa`

### Request

```json
{
  "query": "What does AfCFTA say about verification procedures?",
  "persona_mode": "officer",
  "limit": 5
}
```

### Response

```json
{
  "data": {
    "answer_type": "legal_qa",
    "query": "What does AfCFTA say about verification procedures?",
    "top_provisions": [
      {
        "provision_id": "uuid",
        "instrument_name": "Annex 2 on Rules of Origin",
        "article_ref": "Article 9",
        "page_start": 88,
        "page_end": 89,
        "topic_primary": "verification",
        "provision_text_verbatim": "..."
      }
    ]
  },
  "meta": {
    "request_id": "req_6",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 5.4 Evidence readiness endpoint

`POST /api/v1/workflows/evidence-readiness`

### Request

```json
{
  "entity_type": "psr_rule",
  "entity_key": "1902.19",
  "persona_mode": "exporter",
  "context": {
    "exporter_state": "GHA",
    "importer_state": "KEN",
    "claimed_rule_path": ["VA"]
  }
}
```

### Response

```json
{
  "data": {
    "entity_type": "psr_rule",
    "entity_key": "1902.19",
    "persona_mode": "exporter",
    "requirements": [
      {
        "requirement_type": "bill_of_materials",
        "required": true,
        "priority_level": 1,
        "requirement_description": "Detailed BOM showing originating and non-originating inputs"
      },
      {
        "requirement_type": "cost_breakdown",
        "required": true,
        "priority_level": 1,
        "requirement_description": "Cost structure sufficient to evaluate value-added threshold"
      }
    ]
  },
  "meta": {
    "request_id": "req_7",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 5.5 Eligibility assessment endpoint

`POST /api/v1/workflows/eligibility-assessment`

### Request

```json
{
  "case_external_ref": "CASE-2026-0001",
  "assessment_type": "eligibility_assessment",
  "exporter_state": "GHA",
  "importer_state": "KEN",
  "hs_code": "1902.19",
  "facts": {
    "non_originating_material_percent": 35.0,
    "ex_works_value": 100000,
    "supplier_declaration_present": false,
    "certificate_of_origin_present": true,
    "process_steps": [
      "mixing",
      "extrusion",
      "drying",
      "packaging"
    ]
  }
}
```

### Response

```json
{
  "data": {
    "assessment_id": "uuid",
    "decision_outcome": "uncertain",
    "confidence_level": "medium",
    "decision_reasoning": "The value threshold may be satisfied, but key supporting evidence is missing.",
    "linked_psr_id": "uuid",
    "missing_evidence": {
      "required": ["supplier_declaration"]
    },
    "risk_flags": {
      "documentary_gap": "medium"
    }
  },
  "meta": {
    "request_id": "req_8",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

# 6) Validation rules for the API

These should be enforced at the API layer in addition to DB constraints.

## 6.1 `source_registry`

* `title`, `short_title`, `source_group`, `source_type`, `authority_tier`, `issuing_body`, `jurisdiction_scope`, `file_path`, `mime_type`, `checksum_sha256` required
* `checksum_sha256` unique
* if `status = superseded`, encourage `superseded_by_source_id`

## 6.2 `legal_provision`

* `provision_text_verbatim` required
* `topic_primary` required
* `page_end >= page_start` if both present

## 6.3 `psr_rule`

* `hs_code`, `hs_version`, `hs_level`, `legal_rule_text_verbatim`, `rule_status` required
* `hs_code` must be normalized by service before insert

## 6.4 `psr_rule_component`

* `psr_id`, `component_type`, `component_text_verbatim` required
* `threshold_percent` required only when component is VA or VNM
* `tariff_shift_level` required only for CTH, CTSH, CC where relevant

## 6.5 `tariff_schedule_line`

* `schedule_id`, `hs_code`, `product_description` required
* if `target_rate` present and `target_year` missing, reject
* if `target_year` present and `base_year` present, enforce `target_year >= base_year`

## 6.6 `tariff_schedule_rate_by_year`

* `schedule_line_id`, `calendar_year`, `preferential_rate`, `source_id` required

## 6.7 `status_assertion`

* `entity_type`, `entity_key`, `status_type`, `status_text_verbatim` required

## 6.8 `evidence_requirement`

* `entity_type`, `entity_key`, `persona_mode`, `requirement_type`, `requirement_description` required

## 6.9 `case_assessment`

* `case_external_ref`, `assessment_type`, `decision_outcome`, `confidence_level`, `decision_reasoning` required
* `hs_code` should be normalized if provided

---

# 7) Recommended naming conventions

Use these normalized `entity_type` values consistently across `status_assertion` and `evidence_requirement`:

* `psr_rule`
* `tariff_schedule_line`
* `legal_provision`
* `corridor`
* `hs_code`
* `schedule`
* `case`

And these `entity_key` patterns:

* for PSR: `HS2017:1902.19`
* for tariff line: `schedule_uuid:HS2017:1902.19`
* for corridor: `GHA-KEN:HS2017:1902.19`
* for provision: `provision_uuid`

That will save you pain later.

---

# 8) Recommended next tables

You asked for these first, but to make the assessment workflow clean, the next tables should be:

* `case_file`
* `case_input_fact`
* `verification_question`
* `change_log`
* `document_readiness_template`

Without `case_input_fact`, `case_assessment` becomes too summary-heavy.

---

# 9) Minimal OpenAPI-style contract sketch

```yaml
openapi: 3.1.0
info:
  title: AfCFTA Intelligence API
  version: 1.0.0

paths:
  /api/v1/sources:
    post:
      summary: Create source registry record
    get:
      summary: List sources

  /api/v1/legal-provisions:
    post:
      summary: Create legal provision
    get:
      summary: Search legal provisions

  /api/v1/psr-rules/lookup:
    get:
      summary: Lookup PSR by HS code

  /api/v1/workflows/rule-lookup:
    get:
      summary: Return rule, components, and status by HS code

  /api/v1/workflows/tariff-query:
    get:
      summary: Return corridor tariff data for a given year

  /api/v1/workflows/legal-qa:
    post:
      summary: Retrieve relevant legal provisions for a natural-language query

  /api/v1/workflows/evidence-readiness:
    post:
      summary: Return evidence requirements by entity and persona

  /api/v1/workflows/eligibility-assessment:
    post:
      summary: Generate or store a case assessment
```

---

# 10) My strongest implementation advice

Before you write application code, do these three things:

1. **Add service-layer normalization rules**
   for HS codes, country codes, entity keys, and dates.

2. **Separate admin CRUD from workflow endpoints**
   because the workflow responses are composed views, not raw table dumps.

3. **Treat `case_assessment` as generated output, not source truth**
   because the true source of truth is:

   * legal provisions,
   * rule tables,
   * tariff tables,
   * evidence requirements,
   * case facts.

Below are the **next five tables** in the same style: exact PostgreSQL schema, constraints, indexes, and the matching API contracts.

These complete the first serious version of the **case workflow**, **verification workflow**, **change tracking**, and **readiness pack generation**.

---

# 1) PostgreSQL schema additions

## 1.1 Additional enums

```sql
CREATE TYPE case_submission_status_enum AS ENUM (
  'draft',
  'submitted',
  'under_review',
  'closed',
  'archived'
);

CREATE TYPE fact_source_type_enum AS ENUM (
  'user_input',
  'document_upload',
  'system_inferred',
  'officer_note',
  'external_data'
);

CREATE TYPE fact_value_type_enum AS ENUM (
  'text',
  'number',
  'boolean',
  'date',
  'json',
  'list'
);

CREATE TYPE verification_risk_category_enum AS ENUM (
  'origin_claim',
  'documentary_gap',
  'valuation_risk',
  'cumulation_risk',
  'process_risk',
  'tariff_classification_risk',
  'schedule_status_risk',
  'general'
);

CREATE TYPE change_type_enum AS ENUM (
  'created',
  'updated',
  'deleted',
  'status_changed',
  'superseded',
  'effective_date_changed',
  'structure_changed',
  'value_changed'
);
```

---

## 1.2 `case_file`

Purpose:

* canonical header record for a user/officer/exporter case
* stores corridor, product, declared basis, and workflow status

```sql
CREATE TABLE case_file (
  case_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  case_external_ref text NOT NULL UNIQUE,
  persona_mode persona_mode_enum NOT NULL,
  exporter_state text,
  importer_state text,
  hs_code text,
  hs_version text,
  declared_origin text,
  declared_pathway text,
  submission_status case_submission_status_enum NOT NULL DEFAULT 'draft',
  title text,
  notes text,
  opened_at timestamptz NOT NULL DEFAULT now(),
  submitted_at timestamptz,
  closed_at timestamptz,
  created_by text,
  updated_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_file_persona_mode ON case_file(persona_mode);
CREATE INDEX idx_case_file_submission_status ON case_file(submission_status);
CREATE INDEX idx_case_file_exporter_state ON case_file(exporter_state);
CREATE INDEX idx_case_file_importer_state ON case_file(importer_state);
CREATE INDEX idx_case_file_hs_code ON case_file(hs_code);
CREATE INDEX idx_case_file_declared_pathway ON case_file(declared_pathway);
```

### Constraints

```sql
ALTER TABLE case_file
ADD CONSTRAINT chk_case_file_dates
CHECK (
  (submitted_at IS NULL OR submitted_at >= opened_at)
  AND (closed_at IS NULL OR closed_at >= opened_at)
);
```

---

## 1.3 `case_input_fact`

Purpose:

* normalized storage for the facts used in assessment
* supports mixed fact types without collapsing everything into opaque JSON

```sql
CREATE TABLE case_input_fact (
  fact_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  case_id uuid NOT NULL REFERENCES case_file(case_id) ON DELETE CASCADE,
  fact_type text NOT NULL,
  fact_key text NOT NULL,
  fact_value_type fact_value_type_enum NOT NULL,
  fact_value_text text,
  fact_value_number numeric(18,6),
  fact_value_boolean boolean,
  fact_value_date date,
  fact_value_json jsonb,
  unit text,
  source_type fact_source_type_enum NOT NULL DEFAULT 'user_input',
  source_reference text,
  confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
  fact_order integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_case_fact UNIQUE (case_id, fact_key, fact_order)
);

CREATE INDEX idx_case_input_fact_case_id ON case_input_fact(case_id);
CREATE INDEX idx_case_input_fact_fact_type ON case_input_fact(fact_type);
CREATE INDEX idx_case_input_fact_fact_key ON case_input_fact(fact_key);
CREATE INDEX idx_case_input_fact_source_type ON case_input_fact(source_type);
CREATE INDEX idx_case_input_fact_json_gin ON case_input_fact USING GIN(fact_value_json);
```

### Constraints

```sql
ALTER TABLE case_input_fact
ADD CONSTRAINT chk_case_input_fact_confidence
CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000);

ALTER TABLE case_input_fact
ADD CONSTRAINT chk_case_input_fact_one_value
CHECK (
  (
    CASE WHEN fact_value_text IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN fact_value_number IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN fact_value_boolean IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN fact_value_date IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN fact_value_json IS NOT NULL THEN 1 ELSE 0 END
  ) >= 1
);
```

### Recommended fact keys

Use a controlled vocabulary in application logic:

* `ex_works_value`
* `non_originating_material_percent`
* `supplier_declaration_present`
* `certificate_of_origin_present`
* `process_step`
* `input_origin_country`
* `input_hs_code`
* `transport_mode`
* `cumulation_claimed`

---

## 1.4 `verification_question`

Purpose:

* officer-mode and system-mode prompts/checklist questions
* tied to entity and legal basis

```sql
CREATE TABLE verification_question (
  question_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  persona_mode persona_mode_enum NOT NULL,
  question_text text NOT NULL,
  purpose text NOT NULL,
  legal_basis_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
  risk_category verification_risk_category_enum NOT NULL DEFAULT 'general',
  priority_level smallint NOT NULL DEFAULT 1,
  active boolean NOT NULL DEFAULT true,
  question_order integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_verification_question_entity ON verification_question(entity_type, entity_key);
CREATE INDEX idx_verification_question_persona ON verification_question(persona_mode);
CREATE INDEX idx_verification_question_risk ON verification_question(risk_category);
CREATE INDEX idx_verification_question_active ON verification_question(active);
```

### Constraints

```sql
ALTER TABLE verification_question
ADD CONSTRAINT chk_verification_question_priority
CHECK (priority_level BETWEEN 1 AND 5);

ALTER TABLE verification_question
ADD CONSTRAINT chk_verification_question_order
CHECK (question_order >= 1);
```

---

## 1.5 `change_log`

Purpose:

* entity-level audit and change-detection history
* used for alerts, status tracking, and legal/update intelligence

```sql
CREATE TABLE change_log (
  change_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  change_type change_type_enum NOT NULL,
  old_value jsonb,
  new_value jsonb,
  source_id uuid REFERENCES source_registry(source_id) ON DELETE SET NULL,
  detected_at timestamptz NOT NULL DEFAULT now(),
  effective_from date,
  effective_to date,
  change_summary text NOT NULL,
  method_version text,
  reviewer text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_change_log_entity ON change_log(entity_type, entity_key);
CREATE INDEX idx_change_log_type ON change_log(change_type);
CREATE INDEX idx_change_log_source ON change_log(source_id);
CREATE INDEX idx_change_log_detected_at ON change_log(detected_at);
CREATE INDEX idx_change_log_old_value_gin ON change_log USING GIN(old_value);
CREATE INDEX idx_change_log_new_value_gin ON change_log USING GIN(new_value);
```

### Constraints

```sql
ALTER TABLE change_log
ADD CONSTRAINT chk_change_log_dates
CHECK (
  effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from
);
```

---

## 1.6 `document_readiness_template`

Purpose:

* reusable readiness packs by HS/corridor/pathway
* outputs required docs, optional docs, weak points, and officer focus points

```sql
CREATE TABLE document_readiness_template (
  template_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  hs_code text NOT NULL,
  hs_version text,
  corridor_scope text NOT NULL,
  origin_pathway_type text,
  required_docs jsonb NOT NULL,
  optional_docs jsonb,
  common_weaknesses jsonb,
  officer_focus_points jsonb,
  legal_basis_provision_ids uuid[],
  active boolean NOT NULL DEFAULT true,
  version_label text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_document_readiness_template UNIQUE (
    hs_code,
    COALESCE(hs_version, ''),
    corridor_scope,
    COALESCE(origin_pathway_type, ''),
    COALESCE(version_label, '')
  )
);

CREATE INDEX idx_document_readiness_template_hs_code ON document_readiness_template(hs_code);
CREATE INDEX idx_document_readiness_template_corridor_scope ON document_readiness_template(corridor_scope);
CREATE INDEX idx_document_readiness_template_active ON document_readiness_template(active);
CREATE INDEX idx_document_readiness_template_required_docs_gin ON document_readiness_template USING GIN(required_docs);
CREATE INDEX idx_document_readiness_template_optional_docs_gin ON document_readiness_template USING GIN(optional_docs);
CREATE INDEX idx_document_readiness_template_common_weaknesses_gin ON document_readiness_template USING GIN(common_weaknesses);
CREATE INDEX idx_document_readiness_template_officer_focus_points_gin ON document_readiness_template USING GIN(officer_focus_points);
```

### Suggested JSON shapes

`required_docs`

```json
[
  {"type":"certificate_of_origin","label":"AfCFTA Certificate of Origin","required":true},
  {"type":"bill_of_materials","label":"Detailed BOM","required":true}
]
```

`common_weaknesses`

```json
[
  {"type":"valuation_support","issue":"Insufficient cost breakdown for VA test"},
  {"type":"supplier_declaration","issue":"Supplier declarations missing for key inputs"}
]
```

---

# 2) API contract

Base path remains:

* `/api/v1`

---

## 2.1 `case_file`

### Create case

`POST /api/v1/cases`

#### Request

```json
{
  "case_external_ref": "CASE-2026-0001",
  "persona_mode": "exporter",
  "exporter_state": "GHA",
  "importer_state": "KEN",
  "hs_code": "1902.19",
  "hs_version": "HS2017",
  "declared_origin": "Ghana",
  "declared_pathway": "VA",
  "submission_status": "draft",
  "title": "Pasta export eligibility review",
  "notes": "Initial exporter self-check",
  "created_by": "user_123"
}
```

### Response

```json
{
  "data": {
    "case_id": "uuid",
    "case_external_ref": "CASE-2026-0001"
  },
  "meta": {
    "request_id": "req_case_create",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Get case

`GET /api/v1/cases/{case_id}`

### List cases

`GET /api/v1/cases?persona_mode=exporter&submission_status=draft`

### Update case

`PATCH /api/v1/cases/{case_id}`

Example patch body:

```json
{
  "submission_status": "submitted",
  "submitted_at": "2026-03-19T18:15:00Z",
  "updated_by": "user_123"
}
```

---

## 2.2 `case_input_fact`

### Add fact

`POST /api/v1/cases/{case_id}/facts`

#### Request

```json
{
  "fact_type": "financial",
  "fact_key": "ex_works_value",
  "fact_value_type": "number",
  "fact_value_number": 100000,
  "unit": "USD",
  "source_type": "user_input",
  "source_reference": null,
  "confidence_score": 1.0,
  "fact_order": 1
}
```

### Add list-like repeated fact

```json
{
  "fact_type": "process",
  "fact_key": "process_step",
  "fact_value_type": "text",
  "fact_value_text": "extrusion",
  "source_type": "user_input",
  "confidence_score": 1.0,
  "fact_order": 2
}
```

### Response

```json
{
  "data": {
    "fact_id": "uuid"
  },
  "meta": {
    "request_id": "req_fact_create",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### List facts for case

`GET /api/v1/cases/{case_id}/facts`

### Update fact

`PATCH /api/v1/cases/{case_id}/facts/{fact_id}`

### Delete fact

`DELETE /api/v1/cases/{case_id}/facts/{fact_id}`

---

## 2.3 `verification_question`

### Create verification question

`POST /api/v1/verification-questions`

#### Request

```json
{
  "entity_type": "psr_rule",
  "entity_key": "HS2017:1902.19",
  "persona_mode": "officer",
  "question_text": "Can the applicant demonstrate the origin and tariff classification of all non-originating inputs?",
  "purpose": "Test whether the tariff-shift claim is supported by documentary evidence.",
  "legal_basis_provision_id": "uuid",
  "risk_category": "origin_claim",
  "priority_level": 1,
  "active": true,
  "question_order": 1
}
```

### Get question

`GET /api/v1/verification-questions/{question_id}`

### Query questions

`GET /api/v1/verification-questions?entity_type=psr_rule&entity_key=HS2017:1902.19&persona_mode=officer`

### Response

```json
{
  "data": [
    {
      "question_id": "uuid",
      "question_text": "Can the applicant demonstrate the origin and tariff classification of all non-originating inputs?",
      "purpose": "Test whether the tariff-shift claim is supported by documentary evidence.",
      "risk_category": "origin_claim",
      "priority_level": 1,
      "question_order": 1
    }
  ],
  "meta": {
    "request_id": "req_verification_query",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Update verification question

`PATCH /api/v1/verification-questions/{question_id}`

---

## 2.4 `change_log`

### Create change log record

Usually system-generated, but expose admin create for corrections.

`POST /api/v1/change-logs`

#### Request

```json
{
  "entity_type": "psr_rule",
  "entity_key": "HS2017:1902.19",
  "change_type": "status_changed",
  "old_value": {
    "rule_status": "pending"
  },
  "new_value": {
    "rule_status": "agreed"
  },
  "source_id": "uuid",
  "detected_at": "2026-03-19T18:00:00Z",
  "effective_from": "2026-03-01",
  "effective_to": null,
  "change_summary": "Rule status changed from pending to agreed based on updated official source.",
  "method_version": "status-diff-v1",
  "reviewer": "analyst_1",
  "reviewed_at": "2026-03-19T18:05:00Z"
}
```

### Get change log record

`GET /api/v1/change-logs/{change_id}`

### Query change logs

`GET /api/v1/change-logs?entity_type=psr_rule&entity_key=HS2017:1902.19`

### Query recent changes

`GET /api/v1/change-logs?detected_after=2026-03-01T00:00:00Z`

---

## 2.5 `document_readiness_template`

### Create template

`POST /api/v1/document-readiness-templates`

#### Request

```json
{
  "hs_code": "1902.19",
  "hs_version": "HS2017",
  "corridor_scope": "GHA-KEN",
  "origin_pathway_type": "VA",
  "required_docs": [
    {
      "type": "certificate_of_origin",
      "label": "AfCFTA Certificate of Origin",
      "required": true
    },
    {
      "type": "bill_of_materials",
      "label": "Detailed bill of materials",
      "required": true
    },
    {
      "type": "cost_breakdown",
      "label": "Cost breakdown supporting value-added calculation",
      "required": true
    }
  ],
  "optional_docs": [
    {
      "type": "supplier_declaration",
      "label": "Supplier declaration for originating inputs"
    }
  ],
  "common_weaknesses": [
    {
      "type": "valuation_support",
      "issue": "Cost records do not clearly support the claimed threshold"
    }
  ],
  "officer_focus_points": [
    {
      "type": "origin_claim",
      "focus": "Check consistency between BOM, invoices, and declared originating content"
    }
  ],
  "legal_basis_provision_ids": ["uuid", "uuid"],
  "active": true,
  "version_label": "v1",
  "notes": "Exporter-focused readiness pack for VA pathway"
}
```

### Get template

`GET /api/v1/document-readiness-templates/{template_id}`

### Query templates

`GET /api/v1/document-readiness-templates?hs_code=1902.19&corridor_scope=GHA-KEN&origin_pathway_type=VA`

### Update template

`PATCH /api/v1/document-readiness-templates/{template_id}`

---

# 3) Workflow endpoints using the new tables

These are where the new tables become useful.

---

## 3.1 Case creation + fact capture workflow

### Create case and facts in one call

`POST /api/v1/workflows/cases/intake`

#### Request

```json
{
  "case": {
    "case_external_ref": "CASE-2026-0001",
    "persona_mode": "exporter",
    "exporter_state": "GHA",
    "importer_state": "KEN",
    "hs_code": "1902.19",
    "hs_version": "HS2017",
    "declared_origin": "Ghana",
    "declared_pathway": "VA",
    "title": "Pasta export eligibility review"
  },
  "facts": [
    {
      "fact_type": "financial",
      "fact_key": "ex_works_value",
      "fact_value_type": "number",
      "fact_value_number": 100000,
      "unit": "USD"
    },
    {
      "fact_type": "origin",
      "fact_key": "non_originating_material_percent",
      "fact_value_type": "number",
      "fact_value_number": 35
    },
    {
      "fact_type": "document",
      "fact_key": "supplier_declaration_present",
      "fact_value_type": "boolean",
      "fact_value_boolean": false
    }
  ]
}
```

### Response

```json
{
  "data": {
    "case_id": "uuid",
    "case_external_ref": "CASE-2026-0001",
    "fact_ids": ["uuid", "uuid", "uuid"]
  },
  "meta": {
    "request_id": "req_case_intake",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 3.2 Officer verification checklist workflow

`POST /api/v1/workflows/verification-checklist`

#### Request

```json
{
  "entity_type": "psr_rule",
  "entity_key": "HS2017:1902.19",
  "persona_mode": "officer",
  "case_id": "uuid"
}
```

### Response

```json
{
  "data": {
    "case_id": "uuid",
    "questions": [
      {
        "question_id": "uuid",
        "question_text": "Can the applicant demonstrate the origin and tariff classification of all non-originating inputs?",
        "purpose": "Test whether the tariff-shift claim is supported by documentary evidence.",
        "risk_category": "origin_claim",
        "priority_level": 1
      }
    ]
  },
  "meta": {
    "request_id": "req_verification_checklist",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 3.3 Document readiness pack workflow

`POST /api/v1/workflows/document-readiness-pack`

#### Request

```json
{
  "hs_code": "1902.19",
  "hs_version": "HS2017",
  "corridor_scope": "GHA-KEN",
  "origin_pathway_type": "VA",
  "persona_mode": "exporter"
}
```

### Response

```json
{
  "data": {
    "template_id": "uuid",
    "required_docs": [
      {
        "type": "certificate_of_origin",
        "label": "AfCFTA Certificate of Origin",
        "required": true
      },
      {
        "type": "bill_of_materials",
        "label": "Detailed bill of materials",
        "required": true
      }
    ],
    "optional_docs": [
      {
        "type": "supplier_declaration",
        "label": "Supplier declaration for originating inputs"
      }
    ],
    "common_weaknesses": [
      {
        "type": "valuation_support",
        "issue": "Cost records do not clearly support the claimed threshold"
      }
    ],
    "officer_focus_points": [
      {
        "type": "origin_claim",
        "focus": "Check consistency between BOM, invoices, and declared originating content"
      }
    ]
  },
  "meta": {
    "request_id": "req_doc_pack",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 3.4 Change-monitoring workflow

`GET /api/v1/workflows/changes/feed?entity_type=psr_rule&detected_after=2026-03-01T00:00:00Z`

### Response

```json
{
  "data": [
    {
      "change_id": "uuid",
      "entity_type": "psr_rule",
      "entity_key": "HS2017:1902.19",
      "change_type": "status_changed",
      "change_summary": "Rule status changed from pending to agreed based on updated official source.",
      "effective_from": "2026-03-01",
      "detected_at": "2026-03-19T18:00:00Z"
    }
  ],
  "meta": {
    "request_id": "req_change_feed",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

# 4) Validation rules

## `case_file`

* `case_external_ref` required and unique
* `persona_mode` required
* if `submission_status = submitted`, `submitted_at` should be set by service
* `hs_code` should be normalized before insert

## `case_input_fact`

* exactly one of the typed value fields should normally be populated
* `fact_key` required
* `fact_value_type` must match populated field
* repeated facts should use `fact_order`

## `verification_question`

* `question_text`, `purpose`, `entity_type`, `entity_key`, `persona_mode` required
* `priority_level` must be 1–5
* officer-mode should be default for adjudication checklists

## `change_log`

* `entity_type`, `entity_key`, `change_type`, `change_summary` required
* at least one of `old_value` or `new_value` should be non-null

## `document_readiness_template`

* `hs_code`, `corridor_scope`, `required_docs` required
* `required_docs` must be a non-empty JSON array
* pathway-specific packs should fall back to corridor generic, then global generic

---

# 5) Recommended entity key standards

Keep these consistent across all five new tables:

* PSR rule: `HS2017:1902.19`
* tariff line: `schedule_uuid:HS2017:1902.19`
* corridor: `GHA-KEN:HS2017:1902.19`
* legal provision: `provision_uuid`
* case: `case_uuid`

For `document_readiness_template.corridor_scope`, use:

* exact corridor: `GHA-KEN`
* importer-wide: `*-KEN`
* exporter-wide: `GHA-*`
* global generic: `ALL`

That lets you implement fallback logic cleanly.

---

# 6) Recommended service logic for template fallback

For `document_readiness_template`, lookup order should be:

1. exact `hs_code + corridor_scope + origin_pathway_type`
2. exact `hs_code + corridor_scope + null pathway`
3. exact `hs_code + ALL + origin_pathway_type`
4. exact `hs_code + ALL + null pathway`

This will make the readiness workflow much more usable.

---

# 7) What these tables unlock

These five tables move the system from static intelligence to actual workflow support:

* `case_file` → case lifecycle
* `case_input_fact` → explainable adjudication inputs
* `verification_question` → officer-mode review logic
* `change_log` → legal/status watch capability
* `document_readiness_template` → exporter and officer pack generation

The clean next step is to define:

* `case_failure_mode`
* `case_counterfactual`
* `alert_event`
* `corridor_profile`

because that completes the decision-support loop.

Below are the next four tables in the same implementation style: **exact PostgreSQL schema**, **constraints**, **indexes**, and the **API contracts**.

These complete the decision-support loop:

* `case_failure_mode` = why the claim fails or is weak
* `case_counterfactual` = what change could improve the outcome
* `alert_event` = what changed and who should care
* `corridor_profile` = reusable corridor intelligence layer

---

# 1) PostgreSQL schema additions

## 1.1 Additional enums

```sql
CREATE TYPE failure_type_enum AS ENUM (
  'rule_not_met',
  'threshold_not_met',
  'tariff_shift_not_met',
  'specific_process_not_met',
  'missing_document',
  'insufficient_evidence',
  'cumulation_not_supported',
  'valuation_not_supported',
  'classification_uncertain',
  'schedule_not_operational',
  'status_pending',
  'status_provisional',
  'data_gap',
  'other'
);

CREATE TYPE severity_enum AS ENUM (
  'critical',
  'high',
  'medium',
  'low'
);

CREATE TYPE counterfactual_type_enum AS ENUM (
  'sourcing_change',
  'value_adjustment',
  'process_change',
  'documentation_addition',
  'cumulation_change',
  'classification_review',
  'corridor_change',
  'timing_change',
  'other'
);

CREATE TYPE projected_outcome_enum AS ENUM (
  'likely_eligible',
  'likely_not_eligible',
  'still_uncertain',
  'requires_more_evidence'
);

CREATE TYPE alert_type_enum AS ENUM (
  'rule_status_changed',
  'schedule_updated',
  'rate_changed',
  'provision_updated',
  'transition_expiring',
  'document_requirement_changed',
  'corridor_risk_changed',
  'case_review_needed',
  'data_quality_issue',
  'other'
);

CREATE TYPE alert_severity_enum AS ENUM (
  'critical',
  'high',
  'medium',
  'low',
  'info'
);

CREATE TYPE alert_status_enum AS ENUM (
  'open',
  'acknowledged',
  'resolved',
  'dismissed'
);

CREATE TYPE corridor_status_enum AS ENUM (
  'operational',
  'partially_operational',
  'provisional',
  'not_yet_operational',
  'unknown'
);
```

---

## 1.2 `case_failure_mode`

Purpose:

* stores the specific reasons an assessment is weak, uncertain, or failing
* attaches reasons to legal rule components, provisions, and evidence gaps

```sql
CREATE TABLE case_failure_mode (
  failure_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  assessment_id uuid NOT NULL REFERENCES case_assessment(assessment_id) ON DELETE CASCADE,
  failure_type failure_type_enum NOT NULL,
  severity severity_enum NOT NULL DEFAULT 'medium',
  failure_reason text NOT NULL,
  linked_rule_component_id uuid REFERENCES psr_rule_component(component_id) ON DELETE SET NULL,
  linked_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
  linked_evidence_id uuid REFERENCES evidence_requirement(evidence_id) ON DELETE SET NULL,
  remediation_suggestion text,
  blocking boolean NOT NULL DEFAULT true,
  confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
  failure_order integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_failure_mode_assessment ON case_failure_mode(assessment_id);
CREATE INDEX idx_case_failure_mode_type ON case_failure_mode(failure_type);
CREATE INDEX idx_case_failure_mode_severity ON case_failure_mode(severity);
CREATE INDEX idx_case_failure_mode_blocking ON case_failure_mode(blocking);
CREATE INDEX idx_case_failure_mode_order ON case_failure_mode(assessment_id, failure_order);
```

### Constraints

```sql
ALTER TABLE case_failure_mode
ADD CONSTRAINT chk_case_failure_mode_confidence
CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000);

ALTER TABLE case_failure_mode
ADD CONSTRAINT chk_case_failure_mode_order
CHECK (failure_order >= 1);
```

---

## 1.3 `case_counterfactual`

Purpose:

* stores alternative scenarios that could improve or alter eligibility
* supports exporter advice and officer what-if review

```sql
CREATE TABLE case_counterfactual (
  counterfactual_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  assessment_id uuid NOT NULL REFERENCES case_assessment(assessment_id) ON DELETE CASCADE,
  counterfactual_type counterfactual_type_enum NOT NULL,
  scenario_label text NOT NULL,
  input_change jsonb NOT NULL,
  projected_outcome projected_outcome_enum NOT NULL,
  projected_reasoning text NOT NULL,
  projected_linked_rule_component_id uuid REFERENCES psr_rule_component(component_id) ON DELETE SET NULL,
  projected_linked_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
  estimated_tariff_impact jsonb,
  feasibility_note text,
  confidence_score numeric(4,3) NOT NULL DEFAULT 0.800,
  scenario_order integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_counterfactual_assessment ON case_counterfactual(assessment_id);
CREATE INDEX idx_case_counterfactual_type ON case_counterfactual(counterfactual_type);
CREATE INDEX idx_case_counterfactual_outcome ON case_counterfactual(projected_outcome);
CREATE INDEX idx_case_counterfactual_input_change_gin ON case_counterfactual USING GIN(input_change);
CREATE INDEX idx_case_counterfactual_tariff_impact_gin ON case_counterfactual USING GIN(estimated_tariff_impact);
CREATE INDEX idx_case_counterfactual_order ON case_counterfactual(assessment_id, scenario_order);
```

### Constraints

```sql
ALTER TABLE case_counterfactual
ADD CONSTRAINT chk_case_counterfactual_confidence
CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000);

ALTER TABLE case_counterfactual
ADD CONSTRAINT chk_case_counterfactual_order
CHECK (scenario_order >= 1);
```

### Suggested `input_change` shape

```json
{
  "change_key": "non_originating_material_percent",
  "current_value": 45.0,
  "proposed_value": 38.0,
  "unit": "percent",
  "explanation": "Reduce non-originating input share below modeled threshold"
}
```

---

## 1.4 `alert_event`

Purpose:

* stores actionable alerts for rule changes, corridor risk shifts, case review triggers, and expiring transitional clauses

```sql
CREATE TABLE alert_event (
  alert_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  alert_type alert_type_enum NOT NULL,
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  related_case_id uuid REFERENCES case_file(case_id) ON DELETE SET NULL,
  related_assessment_id uuid REFERENCES case_assessment(assessment_id) ON DELETE SET NULL,
  related_change_id uuid REFERENCES change_log(change_id) ON DELETE SET NULL,
  severity alert_severity_enum NOT NULL DEFAULT 'medium',
  alert_status alert_status_enum NOT NULL DEFAULT 'open',
  alert_message text NOT NULL,
  alert_payload jsonb,
  triggered_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz,
  resolved_at timestamptz,
  owner text,
  resolution_note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_alert_event_type ON alert_event(alert_type);
CREATE INDEX idx_alert_event_entity ON alert_event(entity_type, entity_key);
CREATE INDEX idx_alert_event_status ON alert_event(alert_status);
CREATE INDEX idx_alert_event_severity ON alert_event(severity);
CREATE INDEX idx_alert_event_triggered_at ON alert_event(triggered_at);
CREATE INDEX idx_alert_event_case ON alert_event(related_case_id);
CREATE INDEX idx_alert_event_assessment ON alert_event(related_assessment_id);
CREATE INDEX idx_alert_event_payload_gin ON alert_event USING GIN(alert_payload);
```

### Constraints

```sql
ALTER TABLE alert_event
ADD CONSTRAINT chk_alert_event_dates
CHECK (
  (acknowledged_at IS NULL OR acknowledged_at >= triggered_at)
  AND (resolved_at IS NULL OR resolved_at >= triggered_at)
);
```

---

## 1.5 `corridor_profile`

Purpose:

* reusable corridor intelligence record
* stores maturity, burden, risk, transition exposure, and usable notes for analytics and workflow routing

```sql
CREATE TABLE corridor_profile (
  corridor_profile_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  exporter_state text NOT NULL,
  importer_state text NOT NULL,
  corridor_status corridor_status_enum NOT NULL DEFAULT 'unknown',
  schedule_maturity_score numeric(5,2) NOT NULL DEFAULT 0.00,
  documentation_complexity_score numeric(5,2) NOT NULL DEFAULT 0.00,
  verification_risk_score numeric(5,2) NOT NULL DEFAULT 0.00,
  transition_exposure_score numeric(5,2) NOT NULL DEFAULT 0.00,
  average_tariff_relief_score numeric(5,2),
  pending_rule_exposure_score numeric(5,2),
  operational_notes text,
  source_summary jsonb,
  method_version text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  effective_from date,
  effective_to date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_corridor_profile UNIQUE (
    exporter_state,
    importer_state,
    method_version,
    COALESCE(effective_from, DATE '1900-01-01')
  )
);

CREATE INDEX idx_corridor_profile_states ON corridor_profile(exporter_state, importer_state);
CREATE INDEX idx_corridor_profile_status ON corridor_profile(corridor_status);
CREATE INDEX idx_corridor_profile_active ON corridor_profile(active);
CREATE INDEX idx_corridor_profile_effective_from ON corridor_profile(effective_from);
CREATE INDEX idx_corridor_profile_source_summary_gin ON corridor_profile USING GIN(source_summary);
```

### Constraints

```sql
ALTER TABLE corridor_profile
ADD CONSTRAINT chk_corridor_profile_scores
CHECK (
  schedule_maturity_score BETWEEN 0 AND 100
  AND documentation_complexity_score BETWEEN 0 AND 100
  AND verification_risk_score BETWEEN 0 AND 100
  AND transition_exposure_score BETWEEN 0 AND 100
  AND (average_tariff_relief_score IS NULL OR average_tariff_relief_score BETWEEN 0 AND 100)
  AND (pending_rule_exposure_score IS NULL OR pending_rule_exposure_score BETWEEN 0 AND 100)
);

ALTER TABLE corridor_profile
ADD CONSTRAINT chk_corridor_profile_dates
CHECK (
  effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from
);
```

### Suggested `source_summary` shape

```json
{
  "schedule_sources": ["uuid1", "uuid2"],
  "status_sources": ["uuid3"],
  "notes_basis": ["official_schedule", "status_notice", "operational_guidance"]
}
```

---

# 2) API contract

Base path remains:

* `/api/v1`

---

## 2.1 `case_failure_mode`

### Create failure mode

`POST /api/v1/case-assessments/{assessment_id}/failure-modes`

#### Request

```json
{
  "failure_type": "missing_document",
  "severity": "high",
  "failure_reason": "Supplier declarations are missing for non-originating inputs used in the origin calculation.",
  "linked_rule_component_id": "uuid",
  "linked_provision_id": "uuid",
  "linked_evidence_id": "uuid",
  "remediation_suggestion": "Obtain supplier declarations for all inputs included in the claimed originating content.",
  "blocking": true,
  "confidence_score": 0.95,
  "failure_order": 1
}
```

### Response

```json
{
  "data": {
    "failure_id": "uuid"
  },
  "meta": {
    "request_id": "req_failure_create",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### List failure modes for assessment

`GET /api/v1/case-assessments/{assessment_id}/failure-modes`

### Response

```json
{
  "data": [
    {
      "failure_id": "uuid",
      "failure_type": "missing_document",
      "severity": "high",
      "failure_reason": "Supplier declarations are missing for non-originating inputs used in the origin calculation.",
      "remediation_suggestion": "Obtain supplier declarations for all inputs included in the claimed originating content.",
      "blocking": true,
      "confidence_score": 0.95,
      "failure_order": 1
    }
  ],
  "meta": {
    "request_id": "req_failure_list",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Update failure mode

`PATCH /api/v1/case-failure-modes/{failure_id}`

### Delete failure mode

`DELETE /api/v1/case-failure-modes/{failure_id}`

---

## 2.2 `case_counterfactual`

### Create counterfactual

`POST /api/v1/case-assessments/{assessment_id}/counterfactuals`

#### Request

```json
{
  "counterfactual_type": "sourcing_change",
  "scenario_label": "Source one key flour input from an AfCFTA-originating supplier",
  "input_change": {
    "change_key": "input_origin_country",
    "current_value": "non_afcfta",
    "proposed_value": "afcfta_originating",
    "affected_input": "wheat_flour"
  },
  "projected_outcome": "likely_eligible",
  "projected_reasoning": "This sourcing shift is expected to reduce non-originating material exposure enough to support the claimed pathway.",
  "projected_linked_rule_component_id": "uuid",
  "projected_linked_provision_id": "uuid",
  "estimated_tariff_impact": {
    "current_preferential_rate": 10.0,
    "projected_preferential_rate": 0.0,
    "calendar_year": 2026
  },
  "feasibility_note": "Commercial feasibility depends on availability of compliant supplier documentation.",
  "confidence_score": 0.82,
  "scenario_order": 1
}
```

### List counterfactuals for assessment

`GET /api/v1/case-assessments/{assessment_id}/counterfactuals`

### Response

```json
{
  "data": [
    {
      "counterfactual_id": "uuid",
      "counterfactual_type": "sourcing_change",
      "scenario_label": "Source one key flour input from an AfCFTA-originating supplier",
      "projected_outcome": "likely_eligible",
      "projected_reasoning": "This sourcing shift is expected to reduce non-originating material exposure enough to support the claimed pathway.",
      "estimated_tariff_impact": {
        "current_preferential_rate": 10.0,
        "projected_preferential_rate": 0.0,
        "calendar_year": 2026
      },
      "confidence_score": 0.82,
      "scenario_order": 1
    }
  ],
  "meta": {
    "request_id": "req_counterfactual_list",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Update counterfactual

`PATCH /api/v1/case-counterfactuals/{counterfactual_id}`

### Delete counterfactual

`DELETE /api/v1/case-counterfactuals/{counterfactual_id}`

---

## 2.3 `alert_event`

### Create alert

Usually system-generated, but allow admin creation.

`POST /api/v1/alerts`

#### Request

```json
{
  "alert_type": "rule_status_changed",
  "entity_type": "psr_rule",
  "entity_key": "HS2017:1902.19",
  "related_case_id": "uuid",
  "related_assessment_id": "uuid",
  "related_change_id": "uuid",
  "severity": "high",
  "alert_status": "open",
  "alert_message": "The rule status for HS2017:1902.19 has changed and may affect this case assessment.",
  "alert_payload": {
    "old_status": "pending",
    "new_status": "agreed",
    "effective_from": "2026-03-01"
  },
  "owner": "officer_17"
}
```

### Get alert

`GET /api/v1/alerts/{alert_id}`

### List alerts

`GET /api/v1/alerts?alert_status=open&severity=high`

### Response

```json
{
  "data": [
    {
      "alert_id": "uuid",
      "alert_type": "rule_status_changed",
      "entity_type": "psr_rule",
      "entity_key": "HS2017:1902.19",
      "severity": "high",
      "alert_status": "open",
      "alert_message": "The rule status for HS2017:1902.19 has changed and may affect this case assessment.",
      "triggered_at": "2026-03-19T18:00:00Z",
      "owner": "officer_17"
    }
  ],
  "meta": {
    "request_id": "req_alert_list",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Acknowledge alert

`POST /api/v1/alerts/{alert_id}/acknowledge`

#### Request

```json
{
  "owner": "officer_17"
}
```

### Resolve alert

`POST /api/v1/alerts/{alert_id}/resolve`

#### Request

```json
{
  "resolution_note": "Case reassessed and updated based on new rule status."
}
```

---

## 2.4 `corridor_profile`

### Create corridor profile

`POST /api/v1/corridor-profiles`

#### Request

```json
{
  "exporter_state": "GHA",
  "importer_state": "KEN",
  "corridor_status": "partially_operational",
  "schedule_maturity_score": 82.5,
  "documentation_complexity_score": 61.0,
  "verification_risk_score": 54.0,
  "transition_exposure_score": 27.5,
  "average_tariff_relief_score": 68.0,
  "pending_rule_exposure_score": 14.0,
  "operational_notes": "Corridor is usable for many lines, but some sectors remain exposed to documentary and transition complexity.",
  "source_summary": {
    "schedule_sources": ["uuid1"],
    "status_sources": ["uuid2", "uuid3"],
    "notes_basis": ["official_schedule", "status_notice"]
  },
  "method_version": "corridor-score-v1",
  "active": true,
  "effective_from": "2026-01-01",
  "effective_to": null
}
```

### Get corridor profile

`GET /api/v1/corridor-profiles/{corridor_profile_id}`

### Query corridor profile

`GET /api/v1/corridor-profiles?exporter_state=GHA&importer_state=KEN&active=true`

### Response

```json
{
  "data": [
    {
      "corridor_profile_id": "uuid",
      "exporter_state": "GHA",
      "importer_state": "KEN",
      "corridor_status": "partially_operational",
      "schedule_maturity_score": 82.5,
      "documentation_complexity_score": 61.0,
      "verification_risk_score": 54.0,
      "transition_exposure_score": 27.5,
      "average_tariff_relief_score": 68.0,
      "pending_rule_exposure_score": 14.0,
      "operational_notes": "Corridor is usable for many lines, but some sectors remain exposed to documentary and transition complexity.",
      "method_version": "corridor-score-v1",
      "effective_from": "2026-01-01"
    }
  ],
  "meta": {
    "request_id": "req_corridor_profile",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

### Update corridor profile

`PATCH /api/v1/corridor-profiles/{corridor_profile_id}`

---

# 3) Workflow endpoints using these tables

These are the useful composed endpoints.

---

## 3.1 Assessment explanation workflow

`GET /api/v1/workflows/assessment-explanation/{assessment_id}`

### Response

```json
{
  "data": {
    "assessment_id": "uuid",
    "decision_outcome": "uncertain",
    "confidence_level": "medium",
    "decision_reasoning": "The claimed pathway may be viable, but critical documentary gaps remain.",
    "failure_modes": [
      {
        "failure_type": "missing_document",
        "severity": "high",
        "failure_reason": "Supplier declarations are missing for non-originating inputs used in the origin calculation.",
        "blocking": true,
        "remediation_suggestion": "Obtain supplier declarations for all inputs included in the claimed originating content."
      }
    ],
    "counterfactuals": [
      {
        "scenario_label": "Source one key flour input from an AfCFTA-originating supplier",
        "projected_outcome": "likely_eligible",
        "projected_reasoning": "This sourcing shift is expected to reduce non-originating material exposure enough to support the claimed pathway."
      }
    ]
  },
  "meta": {
    "request_id": "req_assessment_explanation",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 3.2 Case alert feed

`GET /api/v1/workflows/cases/{case_id}/alerts`

### Response

```json
{
  "data": [
    {
      "alert_id": "uuid",
      "alert_type": "case_review_needed",
      "severity": "high",
      "alert_status": "open",
      "alert_message": "A related rule status change may affect this case outcome.",
      "triggered_at": "2026-03-19T18:00:00Z"
    }
  ],
  "meta": {
    "request_id": "req_case_alerts",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 3.3 Corridor intelligence workflow

`GET /api/v1/workflows/corridor-intelligence?exporter_state=GHA&importer_state=KEN`

### Response

```json
{
  "data": {
    "exporter_state": "GHA",
    "importer_state": "KEN",
    "corridor_profile": {
      "corridor_status": "partially_operational",
      "schedule_maturity_score": 82.5,
      "documentation_complexity_score": 61.0,
      "verification_risk_score": 54.0,
      "transition_exposure_score": 27.5,
      "average_tariff_relief_score": 68.0,
      "pending_rule_exposure_score": 14.0,
      "operational_notes": "Corridor is usable for many lines, but some sectors remain exposed to documentary and transition complexity."
    }
  },
  "meta": {
    "request_id": "req_corridor_intelligence",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

## 3.4 Counterfactual recommendation workflow

`POST /api/v1/workflows/counterfactual-recommendations`

### Request

```json
{
  "assessment_id": "uuid",
  "max_scenarios": 3
}
```

### Response

```json
{
  "data": {
    "assessment_id": "uuid",
    "scenarios": [
      {
        "counterfactual_id": "uuid",
        "scenario_label": "Source one key flour input from an AfCFTA-originating supplier",
        "counterfactual_type": "sourcing_change",
        "projected_outcome": "likely_eligible",
        "confidence_score": 0.82
      }
    ]
  },
  "meta": {
    "request_id": "req_counterfactual_recommendations",
    "timestamp": "2026-03-19T18:10:00Z"
  }
}
```

---

# 4) Validation rules

## `case_failure_mode`

* `assessment_id`, `failure_type`, `severity`, `failure_reason` required
* `blocking=true` for critical legal/documentary failures by default
* `confidence_score` must be 0–1

## `case_counterfactual`

* `assessment_id`, `counterfactual_type`, `scenario_label`, `input_change`, `projected_outcome`, `projected_reasoning` required
* `input_change` must be non-empty JSON object
* `scenario_order` must be positive

## `alert_event`

* `alert_type`, `entity_type`, `entity_key`, `severity`, `alert_message` required
* `acknowledged_at` and `resolved_at` should be set by service actions, not raw client patch, unless admin

## `corridor_profile`

* `exporter_state`, `importer_state`, `corridor_status`, `method_version` required
* all scores must be 0–100
* keep one active profile per exporter/importer/method/effective period in service logic

---

# 5) Recommended scoring interpretations for `corridor_profile`

Keep these meanings stable:

* `schedule_maturity_score`

  * 0 = no usable schedule clarity
  * 100 = stable and well-defined operational schedule

* `documentation_complexity_score`

  * 0 = low burden
  * 100 = highly burdensome

* `verification_risk_score`

  * 0 = low scrutiny / easy substantiation
  * 100 = high scrutiny / difficult substantiation

* `transition_exposure_score`

  * 0 = little transition risk
  * 100 = heavily exposed to pending/provisional/expiring arrangements

* `average_tariff_relief_score`

  * 0 = little economic benefit
  * 100 = very strong preferential benefit

* `pending_rule_exposure_score`

  * 0 = few unresolved-rule dependencies
  * 100 = major unresolved-rule dependence

That consistency matters more than the exact formula at first.

---

# 6) Service logic recommendations

## For `case_failure_mode`

Generate from:

* failed rule component checks
* missing required evidence
* schedule/status uncertainty
* contradictory case facts

## For `case_counterfactual`

Generate only from realistic levers:

* sourcing change
* documentation improvement
* process change
* timing change
* corridor choice
  Avoid speculative fantasy scenarios.

## For `alert_event`

Create automatically when:

* a linked `change_log` affects a case
* a transition clause is near expiry
* corridor score worsens materially
* new evidence changes case outcome

## For `corridor_profile`

Recompute on:

* schedule update
* status update
* rule-status update
* major methodology change

---

# 7) What this completes

These four tables close the loop from:

* **facts**
* to **assessment**
* to **why it failed**
* to **what could change**
* to **what the corridor environment looks like**
* to **what alerts require action**

That is the core of an adjudication-grade system rather than a static RAG.

The next clean deliverable is a **single full migration bundle** that includes all tables defined so far in dependency order, plus a seed-data template for enums, sample sources, one case, one assessment, one failure mode, one counterfactual, one alert, and one corridor profile.
