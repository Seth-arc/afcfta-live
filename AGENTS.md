# AfCFTA Intelligence System (AIS)

Deterministic RegTech decision-support engine for AfCFTA trade compliance.
Version: v0.1 (Prototype)

Read this file completely before writing any code. Then read the specific
architecture doc referenced by the task you've been given.

---

## What This System Is

A deterministic trade-compliance engine that answers five questions for any
HS6 product across supported AfCFTA corridors:

1. Qualification — can this product qualify under AfCFTA preferential treatment?
2. Pathway — under which legal rule (WO, CTH, VNM, VA, PROCESS)?
3. Tariff — what preferential and base rates apply?
4. Evidence — what documentation is required to prove origin?
5. Constraints — what legal or status limitations exist?

Every output is structured, auditable, and reproducible.

## What This System Is NOT

- Not probabilistic. No ML scoring. No confidence estimation.
- Not RAG-only. The engine executes boolean expressions, not retrieval.
- Not a search engine. Outputs are pass/fail with explicit failure codes.
- Not inferential. Missing data produces explicit flags, never silent defaults.

---

## Architecture Invariants

These rules are non-negotiable. If your code violates any of them, it is wrong
regardless of whether it "works."

### 1. HS6 is the canonical spine

Every table in the system joins through `hs_version + hs6_id`. There is no
join on raw HS text, product descriptions, or display names. The HS6 layer is
the single stable spine for the entire system.

### 2. Status is mandatory on every output

Every API response that touches eligibility, rules, or tariffs must include
`rule_status`, `tariff_status`, and `confidence_class`. The system never
presents a provisional rule as settled law.

### 3. PSR rules and general origin rules are separate engine layers

Product-specific rules (Appendix IV: WO, CTH, VNM, VA, PROCESS) and general
origin rules (cumulation, direct transport, insufficient operations) are
evaluated independently and then combined. Never merge them into a single
evaluation step. A product can pass PSR but fail general rules.

### 4. Verbatim legal text is always preserved

The parser layer normalizes rules into executable components but always retains
the original legal text with full provenance. Nothing is paraphrased or inferred.

### 5. No silent inference

If a required fact is missing, flag it explicitly in missing_facts. Never
assume a default value. Never infer a missing input. If ex_works is not
provided, do not set vnom_percent to 0 — leave it absent and report it missing.

### 6. No eval() or exec()

The expression evaluator must use a safe parser with a whitelist of allowed
operations. Never use Python's eval(), exec(), or compile() to execute
boolean expressions from the database.

---

## Tech Stack

- Python 3.11+
- FastAPI
- PostgreSQL 15+ with uuid-ossp and pg_trgm extensions
- SQLAlchemy 2.0 (async, using asyncpg)
- Pydantic v2
- Alembic for migrations
- pytest + pytest-asyncio for testing

---

## Code Organization

Follow docs/FastAPI_layout.md exactly. The layering is strict:

```
app/
├── api/v1/           → Thin route handlers ONLY (validate → call service → return)
├── services/         → ALL business logic lives here
├── repositories/     → Data access ONLY (SQL queries, no business logic)
├── db/models/        → SQLAlchemy ORM models (must match DDL exactly)
├── schemas/          → Pydantic request/response models
└── core/             → Enums, exceptions, reference data (mostly locked files)
```

Rules:
- Route handlers must be thin. If a handler has more than ~10 lines of logic,
  extract to a service.
- Services call repositories, never the database session directly.
- Repositories return ORM objects or row mappings. Services transform to Pydantic.
- All enums must match docs/Concrete_Contract.md Section 1.2 exactly.
- All table and column names must match docs/Concrete_Contract.md exactly.
- Use UUID primary keys everywhere.
- Use timestamptz for all timestamps.

---

## Deterministic Engine Execution Order

The eligibility service orchestrates this sequence. The order is strict and
must not be rearranged.

```
1. Resolve HS6              → classification_service
2. Fetch PSR(s)             → rule_resolution_service (via hs6_psr_applicability)
3. Expand pathways (AND/OR) → rule_resolution_service
4. Run blocker checks       → eligibility_service (BEFORE pathway evaluation)
5. Evaluate expressions     → expression_evaluator
6. Apply general rules      → general_origin_rules_service (SEPARATE layer)
7. Apply status constraints → status_service
8. Compute tariff           → tariff_resolution_service
9. Generate evidence reqs   → evidence_service
```

### Blocker Checks (Step 4 — run BEFORE pathway evaluation)

Hard blockers halt the assessment immediately. Pathway evaluation is skipped.

1. Is rule_status pending or partially_agreed? → BLOCKER
2. Is tariff_schedule_line missing for this corridor? → BLOCKER
3. Are core facts missing for ALL pathways? → BLOCKER
4. Is the corridor status not_yet_operational? → BLOCKER

Non-blocking issues (provisional schedule, provisional rule) reduce
confidence_class but do not prevent evaluation.

### Pathway Logic

- `OR` at the pathway level = alternative eligibility routes (first pass wins)
- `AND` within a pathway = all conditions must be met
- Pathways are tried in priority_rank order

### Derived Variables (computed at evaluation time, never stored)

```
vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100
```

Both require ex_works > 0. Division by zero is an error, not a silent default.

---

## Transaction Isolation

Assessment requests must use REPEATABLE READ isolation level so that PSR,
tariff, status, and evidence are all resolved against the same database
snapshot within a single assessment.

Persisted evaluations (writing eligibility_evaluation + eligibility_check_result
rows) must be atomic — all rows committed together or none.

---

## Data Layers

| Layer | Key Tables | Purpose |
|-------|------------|---------|
| L1 Backbone | hs6_product, hs_code_alias, hs_version_crosswalk | Canonical product spine |
| L2 Rules | psr_rule, psr_rule_component, eligibility_rule_pathway, hs6_psr_applicability | Appendix IV normalized rules |
| L3 Tariffs | tariff_schedule_header, tariff_schedule_line, tariff_schedule_rate_by_year | Schedule rates by corridor and year |
| L4 Status | status_assertion, transition_clause | Pending/provisional/agreed tracking |
| L5 Evidence | evidence_requirement, verification_question, document_readiness_template | Documentation requirements |
| L6 Decision | case_file, case_input_fact, case_failure_mode, case_counterfactual, eligibility_evaluation, eligibility_check_result | Case assessment and audit |
| L7 Intelligence | corridor_profile, alert_event | Corridor risk and alerting |
| Provenance | source_registry, legal_provision | Audit trail to source documents |

All operational joins resolve through `hs_version + hs6_id`. PSR lookup goes
through the hs6_psr_applicability materialized table, not live inheritance.

---

## v0.1 Scope (Locked)

### Countries
Nigeria (NGA), Ghana (GHA), Côte d'Ivoire (CIV), Senegal (SEN), Cameroon (CMR)

No other countries. If a request uses a country not in this list, return
CorridorNotSupportedError.

### Product Resolution
HS6 only. HS8/10 codes are stored but not used in computation. If an HS8/10
code is provided, truncate to 6 digits for lookup.

### Capabilities In Scope
Rule lookup, tariff lookup, eligibility engine, evidence readiness,
status-aware outputs.

### Not In Scope
HS8/10 computation, ML/probabilistic scoring, auto HS classification,
full Africa coverage, real-time legal update feeds, any frontend/UI.

### Success Criteria
Evaluate 5+ HS6 products end-to-end across 2+ corridors (GHA→NGA, CMR→NGA),
producing eligibility decisions, tariff outcomes, failure reasoning, and
evidence checklists — including graceful handling of missing facts, ambiguous
rules, and status variability.

---

## API Output Contract

Every assessment response must include ALL of these fields:

```json
{
  "hs6_code": "110311",
  "eligible": true,
  "pathway_used": "CTH",
  "rule_status": "agreed",
  "tariff_outcome": {
    "preferential_rate": 0,
    "base_rate": 15,
    "status": "provisional"
  },
  "failures": [],
  "missing_facts": [],
  "evidence_required": ["certificate_of_origin"],
  "confidence_class": "complete"
}
```

confidence_class values:
- "complete" — status is agreed, all required data present
- "provisional" — status is provisional or pending
- "incomplete" — data gaps exist

---

## Source Authority Tiers

Higher tiers override lower tiers in all conflict resolution.

| Tier | Source | Role |
|------|--------|------|
| 1 | Agreement + Appendix IV | Binding legal authority |
| 2 | Tariff schedules, circulars | Operational reference |
| 3 | Manuals, guides | Interpretive support |
| 4 | Corridor data, trade baselines | Analytic enrichment |

---

## Key Reference Files

Read these when the task requires them. Do not guess — look up the spec.

| File | When to read it |
|------|-----------------|
| docs/Concrete_Contract.md | Creating any table, enum, column, or constraint |
| docs/Join_Strategy.md | Writing any SQL query or repository method |
| docs/FastAPI_layout.md | Creating any route, schema, service, or repository |
| docs/v1_scope.md | Checking what is in or out of scope |
| docs/PRD.md | Understanding user personas or capability requirements |
| docs/expression_grammar.md | Implementing the expression evaluator |
| app/core/countries.py | Valid country codes and corridors for v0.1 |
| app/core/fact_keys.py | Valid production fact types and which rules need them |
| app/core/entity_keys.py | Entity key patterns for polymorphic lookups |
| app/core/failure_codes.py | Canonical failure codes for the eligibility engine |
| tests/fixtures/golden_cases.py | Expected inputs and outputs for acceptance tests |

---

## Locked Files — Do Not Modify

These files contain hand-written reference data. Do not rename, restructure,
reformat, "improve," or add to them unless explicitly asked:

- app/core/countries.py
- app/core/fact_keys.py
- app/core/entity_keys.py
- app/core/failure_codes.py
- tests/fixtures/golden_cases.py
- docs/expression_grammar.md
- Everything in docs/ (read-only architecture specifications)

---

## Testing

- Unit tests in tests/unit/, integration tests in tests/integration/
- Use golden test cases from tests/fixtures/golden_cases.py as acceptance criteria
- For services: mock the repository layer, test business logic
- For repositories: use test database (afcfta_test), test actual SQL
- Every test for a failing case must assert specific failure_codes from
  app/core/failure_codes.py — not just "eligible == false"
- Mark integration tests requiring database with @pytest.mark.integration

---

## Build Order

Build in dependency order. Do not skip ahead.

1. hs_repository + classification_service
2. rules_repository + rule_resolution_service
3. tariffs_repository + tariff_resolution_service
4. cases_repository
5. expression_evaluator
6. general_origin_rules_service
7. evidence_service
8. eligibility_service (orchestrator — calls all of the above)
9. Assessment endpoint
10. Audit endpoint

---

## Shell Command Restrictions

Do NOT run these commands — I will run them myself in my local environment:

- pip install (or any package installation)
- alembic upgrade/revision (or any migration commands)
- pytest (or any test execution)
- uvicorn (or any server startup)
- docker commands
- createdb / psql / any database commands

Only create and edit files. I handle all execution.