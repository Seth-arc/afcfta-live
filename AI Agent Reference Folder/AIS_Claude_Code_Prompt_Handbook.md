# AfCFTA Intelligence System — Claude Code Vibecoding Handbook

**Purpose:** Everything you need to vibecode AIS with Claude Code — what skills you need, how to set up your project, and the exact prompts to use at each phase.

---

## Part 1: Skills You Need (and Don't Need)

### What You Must Understand (Non-Negotiable)

**1. The Domain — AfCFTA Trade Compliance**

You don't need to be a trade law expert, but you need to read and internalize your own docs before you start prompting. Specifically:

- What an HS6 code is and why it's the canonical spine
- The difference between PSR rules (product-specific) and general origin rules (cumulation, direct transport, insufficient operations)
- What WO, CTH, CTSH, VNM, VA, and PROCESS mean as rule component types
- Why status (agreed/pending/provisional) is mandatory on every output
- The three personas (officer, analyst, exporter) and how their output modes differ

If Claude Code generates something that looks right but conflates CTH with CTSH, or silently drops `rule_status` from a response contract, you need to catch it. The domain knowledge is your quality gate.

**2. PostgreSQL Fundamentals**

You don't need to write the DDL by hand — Claude Code will do that from your Concrete_Contract.md. But you need to:

- Read a CREATE TABLE statement and verify it matches your spec
- Understand foreign keys, indexes, and enum types
- Know what `uuid_generate_v4()` and `timestamptz` do
- Spot when a join is wrong (e.g., joining on raw text instead of `hs_version + hs6_id`)
- Run basic psql commands to verify data after seeding

**3. Python / FastAPI Reading Comprehension**

You won't be writing much Python by hand. But you need to:

- Read a FastAPI route handler and verify it matches your API contract
- Understand Pydantic models (request/response schemas)
- Follow the service → repository → database pattern in your FastAPI_layout.md
- Spot when Claude Code puts business logic in a route handler instead of a service
- Read a pytest test and judge whether it actually tests the right thing

**4. Git Basics**

Claude Code works in your repo. You need to:

- Commit frequently between prompts (so you can roll back bad generations)
- Branch before risky prompts
- Read diffs to verify what changed
- Use `git stash` when you want to try something exploratory

**5. Terminal Comfort**

You'll be reading Claude Code's output in a terminal. You should be comfortable:

- Running the FastAPI dev server (`uvicorn app.main:app --reload`)
- Running tests (`pytest`)
- Running database migrations (`alembic upgrade head`)
- Checking logs when something fails
- Using curl or httpie to hit API endpoints

### What You Don't Need

- **Frontend skills** — v0.1 is API-only, no UI
- **DevOps / cloud deployment** — not in v0.1 scope
- **ML / data science** — the engine is deterministic, no models
- **Advanced SQLAlchemy** — Claude Code handles the ORM boilerplate
- **Docker expertise** — helpful but not blocking; a local Postgres works fine

### Skills That Help But Aren't Required

- Experience with Alembic migrations
- Familiarity with pytest fixtures and conftest patterns
- Understanding of boolean expression parsing (for the expression evaluator)
- JSON Schema / OpenAPI spec reading

---

## Part 2: Project Setup for Claude Code

### 2.1 — CLAUDE.md (The Most Important File)

Create a `CLAUDE.md` file in your repo root. This is Claude Code's persistent instruction set — it reads this before every prompt. This is where you encode your architecture decisions so you don't have to repeat them.

```markdown
# CLAUDE.md — AfCFTA Intelligence System

## Project Identity
This is a deterministic RegTech decision-support engine for AfCFTA trade compliance.
No ML. No probabilistic scoring. No RAG-only answers. All outputs are structured,
auditable, and reproducible.

## Architecture Invariants (Never Violate These)
- Every table joins through `hs_version + hs6_id` — this is the canonical spine
- Every API response includes: rule_status, tariff_status, legal_basis, confidence_class
- PSR rules and general origin rules are separate engine layers — never merge them
- Verbatim legal text is always preserved alongside normalized/executable forms
- Status is mandatory, never optional — the system never presents provisional rules as settled

## Tech Stack (Locked)
- Python 3.11+
- FastAPI
- PostgreSQL 15+ with uuid-ossp and pg_trgm extensions
- SQLAlchemy 2.0 (async)
- Pydantic v2
- Alembic for migrations
- pytest for testing

## Code Organization (Follow FastAPI_layout.md exactly)
```
app/
├── api/v1/           → Thin route handlers only
├── services/         → All business logic lives here
├── repositories/     → Data access only, no business logic
├── db/models/        → SQLAlchemy ORM models
├── schemas/          → Pydantic request/response models
└── core/             → Enums, exceptions, utilities
```

## Coding Rules
- Route handlers must be thin: validate input → call service → return response
- Services call repositories, never the database directly
- Repositories return ORM objects, services transform to Pydantic schemas
- All enums must match Concrete_Contract.md exactly — do not rename or reorder
- All table/column names must match Concrete_Contract.md exactly
- Use UUID primary keys everywhere
- Use timestamptz for all timestamps
- Every new table needs an Alembic migration
- Write tests for every service method

## Deterministic Engine Execution Order (Strict)
1. Resolve HS6 (classification_service)
2. Fetch PSR(s) (rule_resolution_service)
3. Expand pathways AND/OR (rule_resolution_service)
4. Evaluate expressions (expression_evaluator)
5. Apply general rules (general_origin_rules_service)
6. Apply status constraints (status_service)
7. Compute tariff (tariff_resolution_service)
8. Generate evidence requirements (evidence_service)

## Derived Variables (Computed, Never Stored)
vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100

## v0.1 Scope Boundaries
Countries: Nigeria, Ghana, Côte d'Ivoire, Senegal, Cameroon
Product resolution: HS6 only (HS8/10 stored but not computed)
No frontend. API-only.

## Testing
- Unit tests for every service
- Integration tests for the full eligibility pipeline
- Test with edge cases: missing facts, ambiguous rules, provisional status
- Golden test cases: HS6 110311 (groats), corridor GHA→NGA and CMR→NGA
```

### 2.2 — Feed It Your Docs

Claude Code can read files in your repo. Place your architecture docs where it can find them:

```
docs/
├── PRD.md
├── v1_scope.md
├── Implementation_Blueprint.md
├── Canonical_Corpus.md
├── Concrete_Contract.md
├── Join_Strategy.md
└── FastAPI_layout.md
```

You'll reference these docs in prompts with `@docs/Concrete_Contract.md` syntax.

### 2.3 — Commit Discipline

**Golden rule: commit after every successful prompt.** If the next prompt goes sideways, you can `git reset --hard` to a known good state. Use descriptive commit messages that match what you prompted:

```
git commit -m "L1: hs6_product table + ORM model + repository"
git commit -m "rule_resolution_service: PSR lookup by hs6"
git commit -m "eligibility_service: expression evaluator AND/OR logic"
```

---

## Part 3: The Prompt Handbook

### Prompting Philosophy

Your project docs are extremely detailed. The biggest risk in vibecoding this is not "Claude Code can't code" — it's **drift from your spec**. Every prompt should anchor to a specific document, table, contract, or execution step. Vague prompts produce vague code. Anchored prompts produce spec-compliant code.

**Pattern to internalize:**

```
[What to build] + [Which doc defines it] + [What to verify]
```

---

### Phase 0: Skeleton & Infrastructure

These prompts establish the project structure before any business logic.

---

**Prompt 0.1 — Project scaffold**

```
Read @docs/FastAPI_layout.md and create the full project directory structure
exactly as defined in Section 1. Create empty __init__.py files in every
Python package. Create app/main.py with a minimal FastAPI app that has a
health check at GET /v1/health returning {"status": "ok"}. Create
app/config.py with Pydantic Settings loading DATABASE_URL from environment.
Create pyproject.toml with dependencies: fastapi, uvicorn, sqlalchemy[asyncio],
asyncpg, pydantic, pydantic-settings, alembic, pytest, pytest-asyncio, httpx.
Do not add any business logic yet.
```

**Verify:** Run `uvicorn app.main:app --reload` and hit `/v1/health`.

---

**Prompt 0.2 — Database connection**

```
Set up the database layer. Create app/db/base.py with SQLAlchemy 2.0 async
engine and declarative base. Create app/db/session.py with async session
factory and a get_db dependency for FastAPI. Configure Alembic in the alembic/
directory pointing to our async engine. Make sure alembic/env.py imports our
Base metadata. Test that `alembic revision --autogenerate -m "init"` produces
an empty migration.
```

**Verify:** Run the alembic command. It should succeed with an empty migration.

---

**Prompt 0.3 — Enums**

```
Read @docs/Concrete_Contract.md Section 1.2 (Enums). Create app/core/enums.py
with Python enums matching EVERY PostgreSQL enum defined there. Use Python's
enum.Enum with string values matching the SQL enum values exactly. Include:
authority_tier_enum, source_type_enum, source_status_enum, instrument_type_enum,
provision_status_enum, hs_level_enum, rule_status_enum, rule_component_type_enum,
operator_type_enum, threshold_basis_enum, schedule_status_enum,
tariff_category_enum, staging_type_enum, rate_status_enum, status_type_enum,
persona_mode_enum, requirement_type_enum, decision_outcome_enum,
confidence_level_enum, case_submission_status_enum, fact_source_type_enum,
fact_value_type_enum, verification_risk_category_enum, change_type_enum,
failure_type_enum, severity_enum, counterfactual_type_enum,
projected_outcome_enum, alert_type_enum, alert_severity_enum,
alert_status_enum, corridor_status_enum. Do not skip any. Do not rename any
values.
```

**Verify:** Open the file. Diff against Concrete_Contract.md. Every enum must match 1:1.

---

### Phase 1: Data Layer (L1–L3: Backbone, Rules, Tariffs)

Build tables bottom-up. Each prompt = one table or tightly coupled pair.

---

**Prompt 1.1 — hs6_product table**

```
Read @docs/Concrete_Contract.md and create:
1. app/db/models/hs.py — SQLAlchemy model for hs6_product exactly matching
   the DDL. Include all columns, constraints, and indexes.
2. An Alembic migration for this table (including the uuid-ossp and pg_trgm
   extensions).
3. app/repositories/hs_repository.py with: get_by_code(hs_version, hs6_code),
   search_by_description(query), list_all(limit, offset).
4. app/schemas/hs.py with Pydantic models: HS6ProductResponse.

The hs6_product table is the canonical backbone. Every other table joins
through hs_version + hs6_id. Get this right.
```

**Verify:** Run migration. Insert a test row via psql. Call repository method from a Python shell.

---

**Prompt 1.2 — PSR rule tables**

```
Read @docs/Concrete_Contract.md and @docs/Join_Strategy.md. Create the rules
layer — three tightly coupled tables:

1. psr_rule — the parent rule record
2. psr_rule_component — individual components (WO, CTH, VNM, etc.)
3. eligibility_rule_pathway — AND/OR pathway combinations

All three must join through hs_version + hs6_id back to hs6_product.

Create:
- app/db/models/rules.py with all three SQLAlchemy models
- Alembic migration
- app/repositories/rules_repository.py with:
  get_rules_by_hs6(hs_version, hs6_code) → returns rule + components + pathways
- app/schemas/rules.py with nested Pydantic response models

Critical: psr_rule_component.expression_template stores the boolean expression
that the expression_evaluator will execute. Do not lose this column.
```

**Verify:** Migration runs. Schema matches DDL exactly. Repository returns nested structure.

---

**Prompt 1.3 — Tariff tables**

```
Read @docs/Concrete_Contract.md. Create the tariff layer — three tables:

1. tariff_schedule_header — schedule metadata per country
2. tariff_schedule_line — line items with HS6, base rate, category
3. tariff_schedule_rate_by_year — year-by-year preferential rates and staging

All join through hs_version + hs6_id.

Create:
- app/db/models/tariffs.py
- Alembic migration
- app/repositories/tariffs_repository.py with:
  get_tariff(exporter, importer, hs_version, hs6_code, year)
  → returns header + line + applicable rate for that year
- app/schemas/tariffs.py

The tariff query must be corridor-aware: it needs both exporter_country and
importer_country to resolve the correct schedule.
```

---

### Phase 2: Data Layer (L4–L7: Status, Evidence, Decision, Intelligence)

---

**Prompt 2.1 — Status layer**

```
Read @docs/Concrete_Contract.md. Create status_assertion and
transition_clause tables.

status_assertion tracks whether a rule/schedule/corridor is agreed, pending,
provisional, etc. It joins to entities by entity_type + entity_key (polymorphic).

transition_clause tracks time-bound transitional provisions.

Create:
- app/db/models/status.py
- Alembic migration
- app/repositories/status_repository.py with:
  get_status(entity_type, entity_key) → current status assertion
  get_active_transitions(entity_type, entity_key) → non-expired transitions
- app/schemas/status.py
```

---

**Prompt 2.2 — Evidence layer**

```
Create evidence_requirement, verification_question, and
document_readiness_template tables per @docs/Concrete_Contract.md.

These are persona-aware (officer/analyst/exporter get different requirements).

Create:
- app/db/models/evidence.py
- Alembic migration
- app/repositories/evidence_repository.py with:
  get_requirements(entity_type, entity_key, persona_mode)
  get_verification_questions(entity_type, entity_key, risk_category)
- app/schemas/evidence.py
```

---

**Prompt 2.3 — Case and decision layer**

```
Create case_file, case_input_fact, case_failure_mode, and
case_counterfactual tables per @docs/Concrete_Contract.md.

case_file is the assessment wrapper. case_input_fact stores production facts.
case_failure_mode stores why a claim fails. case_counterfactual stores what
changes would improve the outcome.

Create:
- app/db/models/cases.py
- Alembic migration
- app/repositories/cases_repository.py with:
  create_case(data) → new case_file
  add_facts(case_id, facts) → case_input_fact records
  get_case_with_facts(case_id) → case + all facts
- app/schemas/cases.py
```

---

**Prompt 2.4 — Intelligence layer**

```
Create corridor_profile and alert_event tables per @docs/Concrete_Contract.md.

corridor_profile stores per-corridor metadata (route type, avg delay, risk
flags). alert_event stores change notifications.

Create:
- app/db/models/evaluations.py (corridor + alerts)
- Alembic migration
- app/repositories/evaluations_repository.py
- app/schemas/assessments.py (corridor + alert response models)
```

---

### Phase 3: Services (The Business Logic)

This is the core of the system. Each service maps to the deterministic engine execution order.

---

**Prompt 3.1 — Classification service**

```
Create app/services/classification_service.py.

This service resolves an input to a canonical HS6 record.

Input: hs_code (string, might be HS8/10), hs_version (optional)
Output: HS6ProductResponse

Logic:
1. If input is already HS6 → look up directly
2. If input is HS8/10 → truncate to 6 digits, look up
3. If hs_version not provided → use latest version
4. If not found → raise ClassificationError with the attempted code

Use hs_repository. Write unit tests with at least: exact match, truncation,
not found.
```

---

**Prompt 3.2 — Rule resolution service**

```
Create app/services/rule_resolution_service.py.

Input: hs_version, hs6_code
Output: RuleResolutionResult containing:
  - psr_rules (list)
  - components per rule (list)
  - pathways per rule (list, with AND/OR semantics)
  - rule_status

Logic:
1. Call rules_repository.get_rules_by_hs6()
2. For each rule, fetch components and pathways
3. Group pathways by logic_group (AND groups within OR alternatives)
4. Return structured result

Read @docs/Join_Strategy.md for exactly how the pathway AND/OR expansion works.
The key insight: "or" in Appendix IV = alternative eligibility routes.
Combined conditions within a single pathway = all must be met (AND).

Write tests for: single rule, multiple pathways, AND-group, OR-alternatives.
```

---

**Prompt 3.3 — Expression evaluator**

```
Create app/services/expression_evaluator.py.

This is the core computation engine. It takes a boolean expression template
from psr_rule_component.expression_template and evaluates it against
production facts.

Input:
  - expression_template (string, e.g., "vnom_percent <= 60")
  - facts (dict of fact_key → value from case_input_fact)

Output:
  - result: bool (pass/fail)
  - evaluated_expression: string (with values substituted)
  - missing_variables: list[str] (facts needed but not provided)

Derived variables to compute:
  vnom_percent = non_originating / ex_works * 100
  va_percent = (ex_works - non_originating) / ex_works * 100

Rules:
- If a required fact is missing → result is None, add to missing_variables
- Never infer missing values
- Support operators: <=, >=, <, >, ==, !=
- Support: AND, OR for compound expressions
- The evaluator must be SAFE — no eval(), no exec(). Parse the expression
  and evaluate against a whitelist of allowed operations.

Write extensive tests: VNM pass, VNM fail, CTH (boolean), missing facts,
compound AND/OR, edge cases (zero ex_works).
```

**This is the highest-risk prompt.** Review the generated code carefully. The expression evaluator is the core IP — it must be deterministic and safe.

---

**Prompt 3.4 — Tariff resolution service**

```
Create app/services/tariff_resolution_service.py.

Input: exporter_country, importer_country, hs_version, hs6_code, year
Output: TariffResolutionResult containing:
  - base_rate (MFN)
  - preferential_rate
  - staging_year
  - tariff_status
  - tariff_category (liberalised/sensitive/excluded)

Logic:
1. Find tariff_schedule_header for the exporter→importer corridor
2. Find tariff_schedule_line for the HS6 code
3. Find tariff_schedule_rate_by_year for the requested year
4. If no rate for the exact year, use the most recent rate before that year
5. Attach status from status_service

Write tests for: normal lookup, missing schedule, missing rate for year
(fallback), excluded product.
```

---

**Prompt 3.5 — Status service**

```
Create app/services/status_service.py.

This service overlays status constraints on any entity.

Input: entity_type (e.g., "psr_rule", "tariff_schedule"), entity_key
Output: StatusOverlay containing:
  - status_type (agreed/pending/provisional/etc.)
  - effective_from, effective_to
  - confidence_class (computed from status completeness)
  - active_transitions (list)
  - constraints (list of text warnings)

confidence_class logic:
  - "complete" if status is agreed and all required data present
  - "provisional" if status is provisional or pending
  - "incomplete" if data gaps exist

Write tests for: agreed status, provisional with transition, missing status
(should return explicit "unknown" not null).
```

---

**Prompt 3.6 — Evidence service**

```
Create app/services/evidence_service.py.

Input: entity_type, entity_key, persona_mode, existing_documents (list)
Output: EvidenceReadinessResult containing:
  - required_documents (list with descriptions)
  - missing_documents (required minus existing)
  - verification_questions (persona-appropriate)
  - readiness_score (simple: provided / required)

Logic:
1. Fetch evidence_requirements for the entity + persona
2. Diff against existing_documents
3. Fetch verification_questions filtered by persona
4. Compute readiness score

Write tests for: officer persona (more requirements), exporter persona
(fewer), no existing docs, all docs present.
```

---

**Prompt 3.7 — General origin rules service**

```
Create app/services/general_origin_rules_service.py.

This is a SEPARATE engine layer from PSR evaluation. It applies three
general rules from the AfCFTA Protocol on Rules of Origin:

1. Insufficient operations — certain minimal operations never confer origin
   (simple packaging, labeling, mixing, etc.)
2. Cumulation — materials from other AfCFTA state parties can be treated
   as originating
3. Direct transport — goods must be shipped directly or through permitted
   transshipment

Input: case_facts (dict), psr_result (from expression evaluator)
Output: GeneralRulesResult containing:
  - insufficient_operations_check: pass/fail/not_applicable
  - cumulation_applied: bool
  - direct_transport_check: pass/fail/not_applicable
  - general_rules_passed: bool (all must pass for final eligibility)

For v0.1, these can be template-based checks against declared facts.
The key architectural point is that they are SEPARATE from PSR evaluation
and applied AFTER it. A product can pass PSR but fail general rules.

Write tests for: all pass, insufficient operations fail, direct transport
fail, cumulation applied.
```

---

**Prompt 3.8 — Eligibility service (orchestrator)**

```
Create app/services/eligibility_service.py.

This is the ORCHESTRATOR. It calls all other services in the strict
execution order defined in CLAUDE.md and @docs/v1_scope.md Section 4.1:

1. classification_service.resolve() → canonical HS6
2. rule_resolution_service.resolve() → PSR rules + pathways
3. For each pathway: expression_evaluator.evaluate() → pass/fail
4. general_origin_rules_service.evaluate() → pass/fail
5. status_service.get_overlay() → constraints
6. tariff_resolution_service.resolve() → rates
7. evidence_service.get_readiness() → documents needed

Input: EligibilityRequest (hs6, exporter, importer, year, production_facts)
Output: EligibilityAssessmentResponse matching the API contract in
@docs/v1_scope.md Section 7.1:
{
  hs6_code, eligible, pathway_used, rule_status,
  tariff_outcome: {preferential_rate, base_rate, status},
  failures: [], missing_facts: [], evidence_required: [],
  confidence_class
}

If eligible via ANY pathway (OR logic) → eligible = true, pathway_used =
the first passing pathway.
If no pathway passes → eligible = false, failures = list of failure codes
from each pathway.

Write integration tests using the full service chain (mock repositories).
Test: eligible product, ineligible product, missing facts, provisional
status overlay.
```

---

### Phase 4: API Routes

---

**Prompt 4.1 — Rule lookup endpoint**

```
Read @docs/FastAPI_layout.md Section 3. Create app/api/v1/rules.py with:

GET /v1/rules/{hs6}
- Query params: hs_version (optional)
- Calls classification_service then rule_resolution_service
- Returns: PSR rules, components, pathways, rule_status, legal_text
- Response model from app/schemas/rules.py

Keep the handler thin: validate → call service → return.
Add to app/api/router.py.
```

---

**Prompt 4.2 — Tariff lookup endpoint**

```
Create app/api/v1/tariffs.py with:

GET /v1/tariffs
- Query params: exporter, importer, hs6, year, hs_version (optional)
- All params required except hs_version
- Calls tariff_resolution_service
- Returns: base_rate, preferential_rate, staging_year, tariff_status

Keep the handler thin. Add to router.
```

---

**Prompt 4.3 — Case and assessment endpoints**

```
Create app/api/v1/cases.py with:

POST /v1/cases — Create a new case
- Body: CaseCreateRequest (exporter, importer, hs6, production_facts)
- Creates case_file + case_input_fact records
- Returns: case_id + case summary

POST /v1/assessments — Run eligibility assessment
- Body: AssessmentRequest (case_id OR inline hs6 + facts)
- Calls eligibility_service orchestrator
- Returns: full EligibilityAssessmentResponse per API contract

GET /v1/cases/{case_id} — Retrieve case with results

Keep handlers thin. Add to router.
```

---

**Prompt 4.4 — Evidence endpoint**

```
Create app/api/v1/evidence.py with:

POST /v1/evidence/readiness
- Body: EvidenceReadinessRequest (entity_type, entity_key, persona_mode,
  existing_documents)
- Calls evidence_service
- Returns: required, missing, verification questions, readiness score

Add to router.
```

---

### Phase 5: Seed Data & Integration Testing

---

**Prompt 5.1 — Seed data**

```
Create scripts/seed_data.py that populates the database with enough data
to run the v0.1 success criteria:

1. At least 5 HS6 products (including 110311 — groats/meal of cereals)
2. PSR rules for each with realistic components and pathways
3. Tariff schedules for GHA→NGA and CMR→NGA corridors
4. Status assertions (mix of agreed, provisional, pending)
5. Evidence requirements per persona
6. At least one corridor_profile

Use realistic AfCFTA data where possible. For products, use:
- 110311 (groats/meal) — CTH pathway
- 271019 (petroleum oils) — VNM 60% pathway
- 610910 (t-shirts cotton) — CTH + VNM alternative
- 870421 (trucks) — complex multi-component
- 030389 (frozen fish) — WO pathway

Make the data internally consistent: rules reference real HS6 records,
tariffs reference real corridors, statuses reference real rules.
```

---

**Prompt 5.2 — Golden path integration test**

```
Create tests/integration/test_golden_path.py that exercises the full
v0.1 success criteria:

1. Create a case for HS6 110311, corridor GHA→NGA, with production facts
   that should PASS CTH
2. Run assessment → assert eligible=true, pathway_used="CTH",
   rule_status="agreed", confidence_class="complete"
3. Verify tariff_outcome has preferential and base rates
4. Verify evidence_required is non-empty

Then create a FAILING case:
5. Same product, but production facts that FAIL CTH (no tariff heading change)
6. Run assessment → assert eligible=false, failure_codes include
   "FAIL_CTH_NOT_MET"
7. Verify counterfactual suggestion exists

Then test edge cases:
8. Missing production facts → missing_facts populated, confidence_class
   not "complete"
9. Provisional rule status → confidence_class="provisional"

This test is the system's acceptance test. It should be runnable with:
pytest tests/integration/test_golden_path.py -v
```

---

### Phase 6: Hardening

---

**Prompt 6.1 — Error handling**

```
Create app/core/exceptions.py with domain-specific exceptions:

- ClassificationError (HS6 not found)
- RuleNotFoundError
- TariffNotFoundError
- StatusUnknownError
- ExpressionEvaluationError
- InsufficientFactsError
- CorridorNotSupportedError

Then create app/api/deps.py error handlers that catch these and return
proper HTTP responses:
- 404 for not-found errors
- 422 for insufficient facts
- 500 for expression evaluation errors

Add to main.py as exception handlers. Ensure every error response includes
a machine-readable error_code and human-readable message.
```

---

**Prompt 6.2 — Audit service**

```
Create app/services/audit_service.py.

Every eligibility assessment must produce an audit trail. The audit service:

1. Logs the full input (case facts)
2. Logs each step's output (HS6 resolved, rules found, expressions
   evaluated, general rules applied, status overlaid, tariff computed)
3. Stores the complete decision trace in the case_file or a linked
   evaluation record

This is critical for the "auditable and reproducible" guarantee.
Log to both the database (for retrieval) and structured logging (for ops).

Create the audit trail schema if not already in Concrete_Contract.md.
```

---

## Part 4: Anti-Patterns to Watch For

These are the ways vibecoding this system will go wrong if you're not watching.

**1. Merged engine layers.** Claude Code may try to evaluate PSR rules and general origin rules in the same function. They must be separate. If you see `insufficient_operations` being checked inside `expression_evaluator`, that's wrong.

**2. Dropped status fields.** It's easy to return a clean eligibility result without `rule_status` or `confidence_class`. Every response contract requires them. Check every response model.

**3. eval() in the expression evaluator.** Claude Code might use Python's `eval()` to execute boolean expressions. This is a security risk. Require a safe parser.

**4. Joining on text instead of HS6 IDs.** If you see a query that joins `psr_rule.hs_code_text` to `tariff_schedule_line.description`, that's wrong. All joins go through `hs_version + hs6_id`.

**5. Business logic in route handlers.** If a route handler has more than ~10 lines of logic, it's doing too much. Extract to a service.

**6. Silent inference.** If the system doesn't have a fact, it must flag it as missing — never assume a default or infer a value. Check for `default=True` or `default=0` on fact-dependent fields.

**7. Monolithic prompts.** Don't try to build the entire eligibility engine in one prompt. The layered approach in Phase 3 exists because each service is independently testable. One service per prompt.

---

## Part 5: Prompt Sequencing Cheat Sheet

| # | Prompt | Creates | Verify By |
|---|--------|---------|-----------|
| 0.1 | Project scaffold | Directory structure, health endpoint | `curl /v1/health` |
| 0.2 | Database connection | SQLAlchemy, Alembic | Empty migration runs |
| 0.3 | Enums | app/core/enums.py | Diff vs Concrete_Contract.md |
| 1.1 | HS6 backbone | hs6_product table + repo | Insert test row |
| 1.2 | PSR rules | 3 rule tables + repo | Nested query returns |
| 1.3 | Tariffs | 3 tariff tables + repo | Corridor query works |
| 2.1 | Status | status_assertion + repo | Status lookup works |
| 2.2 | Evidence | 3 evidence tables + repo | Persona-filtered query |
| 2.3 | Cases | 4 case tables + repo | Case creation + fact storage |
| 2.4 | Intelligence | corridor + alerts + repo | Corridor profile query |
| 3.1 | Classification svc | HS6 resolution | Unit tests pass |
| 3.2 | Rule resolution svc | PSR lookup + pathway expansion | AND/OR tests pass |
| 3.3 | Expression evaluator | Boolean expression engine | VNM/CTH/missing tests |
| 3.4 | Tariff resolution svc | Corridor-aware rate lookup | Fallback year test |
| 3.5 | Status service | Status overlay + confidence | Provisional test |
| 3.6 | Evidence service | Readiness computation | Persona diff test |
| 3.7 | General rules svc | Insufficient ops/cumulation/transport | Separate layer test |
| 3.8 | Eligibility svc | Full orchestrator | Integration test |
| 4.1 | Rules endpoint | GET /v1/rules/{hs6} | curl returns rules |
| 4.2 | Tariff endpoint | GET /v1/tariffs | curl returns rates |
| 4.3 | Case endpoints | POST /v1/cases, /v1/assessments | Full API flow |
| 4.4 | Evidence endpoint | POST /v1/evidence/readiness | Persona test |
| 5.1 | Seed data | 5 products, 2 corridors | Data in DB |
| 5.2 | Golden path test | Acceptance test suite | pytest passes |
| 6.1 | Error handling | Domain exceptions + HTTP handlers | Error responses clean |
| 6.2 | Audit service | Decision trace logging | Trace stored per case |

---

## Part 6: Recovery Prompts (When Things Break)

**When a migration fails:**
```
The migration for [table] failed with: [error]. Read the error and the
DDL in @docs/Concrete_Contract.md. Fix the migration file in
alembic/versions/. Do not create a new migration — fix the existing one.
Then run `alembic upgrade head` to verify.
```

**When tests fail after a service change:**
```
The following tests are failing: [paste test output]. The service was
changed in the last prompt. Read the test expectations and the service
code. Fix the service to match the expected behavior defined in the test,
not the other way around — the tests encode our spec.
```

**When the response contract drifts:**
```
The response from POST /v1/assessments is missing [field]. Read
@docs/v1_scope.md Section 7.1 for the exact API contract. Every response
must include: hs6_code, eligible, pathway_used, rule_status,
tariff_outcome, failures, missing_facts, evidence_required,
confidence_class. Fix the Pydantic response model and the eligibility
service to include all fields.
```

**When you need to backtrack:**
```
The last [N] changes introduced [problem]. I'm reverting to commit [hash].
Starting fresh from that point. Read the current state of [file] and
continue from where that commit left off. The next thing to build is
[specific task].
```
