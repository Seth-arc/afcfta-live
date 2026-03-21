# AfCFTA Intelligence System — Vibecoding Handbook

**The complete guide to building AIS with an AI coding agent (Claude Code or Codex).**

Everything in one document: skills needed, project setup, pre-flight checklist,
reference data files to create by hand, the AGENTS.md / CLAUDE.md system,
every prompt in sequence, recovery prompts, and anti-patterns.

---

## Part 1: Skills You Need (and Don't Need)

### What You Must Understand (Non-Negotiable)

**1. The Domain — AfCFTA Trade Compliance**

You don't need to be a trade law expert, but you need to read and internalize
your own docs before you start prompting. Specifically:

- What an HS6 code is and why it's the canonical spine
- The difference between PSR rules (product-specific) and general origin rules
  (cumulation, direct transport, insufficient operations)
- What WO, CTH, CTSH, VNM, VA, and PROCESS mean as rule component types
- Why status (agreed/pending/provisional) is mandatory on every output
- The three personas (officer, analyst, exporter) and how their output modes differ

If the agent generates something that looks right but conflates CTH with CTSH,
or silently drops `rule_status` from a response contract, you need to catch it.
The domain knowledge is your quality gate.

**2. PostgreSQL Fundamentals**

You don't need to write the DDL by hand — the agent will do that from your
Concrete_Contract.md. But you need to:

- Read a CREATE TABLE statement and verify it matches your spec
- Understand foreign keys, indexes, and enum types
- Know what `uuid_generate_v4()` and `timestamptz` do
- Spot when a join is wrong (joining on raw text instead of `hs_version + hs6_id`)
- Run basic psql commands to verify data after seeding

**3. Python / FastAPI Reading Comprehension**

You won't be writing much Python by hand. But you need to:

- Read a FastAPI route handler and verify it matches your API contract
- Understand Pydantic models (request/response schemas)
- Follow the service → repository → database pattern in your FastAPI_layout.md
- Spot when the agent puts business logic in a route handler instead of a service
- Read a pytest test and judge whether it actually tests the right thing

**4. Git Basics**

The agent works in your repo. You need to:

- Commit frequently between prompts (so you can roll back bad generations)
- Branch before risky prompts
- Read diffs to verify what changed
- Use `git stash` when you want to try something exploratory

**5. Terminal Comfort**

You'll be reading agent output in a terminal. You should be comfortable with:
`uvicorn app.main:app --reload`, `pytest`, `alembic upgrade head`, checking
logs, and using curl or httpie to hit API endpoints.

### What You Don't Need

- Frontend skills — v0.1 is API-only, no UI
- DevOps / cloud deployment — not in v0.1 scope
- ML / data science — the engine is deterministic, no models
- Advanced SQLAlchemy — the agent handles the ORM boilerplate
- Docker expertise — helpful but not blocking; a local Postgres works fine

---

## Part 2: Project Setup

### 2.1 — Agent Instruction File

Both Claude Code and Codex read an instruction file from the repo root before
every prompt. Same purpose, different filenames:

| Tool | File | How it works |
|------|------|-------------|
| Claude Code | `CLAUDE.md` | Single file at repo root, read every prompt |
| Codex | `AGENTS.md` | Hierarchical — root file + directory-scoped overrides |

The root AGENTS.md / CLAUDE.md was provided as a separate deliverable. Place it
at your repo root before your first prompt. The content is identical for both
tools.

If using Codex, you also get directory-scoped instruction files. Run
`split_agents.sh` from the repo root after the scaffold is built to create all
20 scoped AGENTS.md files. Don't create them all before you start — add them
as you enter each build phase.

### 2.2 — Architecture Docs in the Repo

Place your architecture docs where the agent can find them:

```
docs/
├── PRD.md
├── v1_scope.md
├── Implementation_Blueprint.md
├── Canonical_Corpus.md
├── Concrete_Contract.md
├── Join_Strategy.md
├── FastAPI_layout.md
└── expression_grammar.md
```

### 2.3 — Reference Data Files (Create By Hand)

These files encode domain knowledge. Without them, the agent will invent
values or ask you every time. Create all of them before your first prompt.

**app/core/countries.py**

```python
"""v0.1 locked countries with ISO codes and regional bloc membership."""

V01_COUNTRIES = {
    "NGA": {"name": "Nigeria", "iso2": "NG", "bloc": "ECOWAS", "language": "en"},
    "GHA": {"name": "Ghana", "iso2": "GH", "bloc": "ECOWAS", "language": "en"},
    "CIV": {"name": "Côte d'Ivoire", "iso2": "CI", "bloc": "ECOWAS", "language": "fr"},
    "SEN": {"name": "Senegal", "iso2": "SN", "bloc": "ECOWAS", "language": "fr"},
    "CMR": {"name": "Cameroon", "iso2": "CM", "bloc": "ECCAS/CEMAC", "language": "fr/en"},
}

V01_CORRIDORS = [
    ("GHA", "NGA"), ("NGA", "GHA"),
    ("CMR", "NGA"), ("NGA", "CMR"),
    ("CIV", "NGA"), ("SEN", "NGA"),
    ("GHA", "CIV"), ("CIV", "SEN"),
]
```

**app/core/fact_keys.py**

```python
"""
Registry of valid fact_type values for case_input_fact.
The expression evaluator and fact_normalization_service use this
to validate inputs and compute derived variables.
"""

PRODUCTION_FACTS = {
    "ex_works": {"type": "number", "unit": "currency", "required_for": ["VNM", "VA"]},
    "non_originating": {"type": "number", "unit": "currency", "required_for": ["VNM", "VA"]},
    "fob_value": {"type": "number", "unit": "currency", "required_for": []},
    "customs_value": {"type": "number", "unit": "currency", "required_for": []},
    "originating_materials_value": {"type": "number", "unit": "currency", "required_for": []},
    "tariff_heading_input": {"type": "text", "required_for": ["CTH", "CTSH"]},
    "tariff_heading_output": {"type": "text", "required_for": ["CTH", "CTSH"]},
    "tariff_subheading_input": {"type": "text", "required_for": ["CTSH"]},
    "tariff_subheading_output": {"type": "text", "required_for": ["CTSH"]},
    "wholly_obtained": {"type": "boolean", "required_for": ["WO"]},
    "specific_process_performed": {"type": "boolean", "required_for": ["PROCESS"]},
    "specific_process_description": {"type": "text", "required_for": ["PROCESS"]},
    "direct_transport": {"type": "boolean", "required_for": ["general"]},
    "transshipment_country": {"type": "text", "required_for": []},
    "cumulation_claimed": {"type": "boolean", "required_for": ["general"]},
    "cumulation_partner_states": {"type": "list", "required_for": []},
}

DERIVED_VARIABLES = {
    "vnom_percent": "non_originating / ex_works * 100",
    "va_percent": "(ex_works - non_originating) / ex_works * 100",
}
```

**app/core/entity_keys.py**

```python
"""
Entity key conventions for polymorphic lookups
(status_assertion, evidence_requirement).
From Join_Strategy.md Section 1.3.
"""

ENTITY_KEY_PATTERNS = {
    "psr_rule": "PSR:{psr_id}",
    "schedule": "SCHEDULE:{schedule_id}",
    "schedule_line": "SCHEDULE_LINE:{schedule_line_id}",
    "corridor": "CORRIDOR:{exporter}:{importer}:{hs6_code}",
    "country": "COUNTRY:{iso3}",
    "pathway": "PATHWAY:{pathway_id}",
    "hs6_rule": "HS6_RULE:{psr_id}",
}

def make_entity_key(entity_type: str, **kwargs) -> str:
    pattern = ENTITY_KEY_PATTERNS[entity_type]
    return pattern.format(**kwargs)
```

**app/core/failure_codes.py**

```python
"""Canonical failure codes for the eligibility engine."""

FAILURE_CODES = {
    # Blocker-level
    "UNKNOWN_HS6": "HS6 code could not be resolved",
    "NO_PSR_FOUND": "No applicable PSR rule found for this HS6",
    "NO_SCHEDULE": "No tariff schedule found for this corridor",
    "NOT_OPERATIONAL": "Corridor or instrument not yet operational",
    "MISSING_CORE_FACTS": "Required production facts are missing",
    # PSR failures
    "FAIL_CTH_NOT_MET": "Change in tariff heading not demonstrated",
    "FAIL_CTSH_NOT_MET": "Change in tariff subheading not demonstrated",
    "FAIL_VNM_EXCEEDED": "Value of non-originating materials exceeds threshold",
    "FAIL_VA_INSUFFICIENT": "Value added percentage below threshold",
    "FAIL_WO_NOT_MET": "Product is not wholly obtained",
    "FAIL_PROCESS_NOT_MET": "Required specific process not performed",
    # General rule failures
    "FAIL_INSUFFICIENT_OPERATIONS": "Only insufficient/minimal operations performed",
    "FAIL_DIRECT_TRANSPORT": "Direct transport requirement not met",
    "FAIL_CUMULATION_INVALID": "Cumulation conditions not satisfied",
    # Status constraints
    "RULE_STATUS_PENDING": "PSR rule status is pending — not yet enforceable",
    "RULE_STATUS_PROVISIONAL": "PSR rule is provisional",
    "SCHEDULE_PROVISIONAL": "Tariff schedule is provisional",
    "SCHEDULE_NOT_GAZETTED": "Tariff schedule not yet gazetted",
}
```

### 2.4 — Golden Test Cases

Create `tests/fixtures/golden_cases.py`:

```python
"""
Golden test cases for v0.1 acceptance criteria.
Each case defines exact inputs and expected outputs.
"""

GOLDEN_CASES = [
    {
        "name": "GHA→NGA groats CTH pass",
        "input": {
            "hs6_code": "110311", "hs_version": "HS2017",
            "exporter": "GHA", "importer": "NGA", "year": 2025,
            "facts": {
                "tariff_heading_input": "1001",
                "tariff_heading_output": "1103",
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "CTH",
            "rule_status": "agreed", "confidence_class": "complete",
            "failures": [], "missing_facts": [],
        },
    },
    {
        "name": "GHA→NGA groats CTH fail — no tariff shift",
        "input": {
            "hs6_code": "110311", "hs_version": "HS2017",
            "exporter": "GHA", "importer": "NGA", "year": 2025,
            "facts": {
                "tariff_heading_input": "1103",
                "tariff_heading_output": "1103",
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {"eligible": False, "failure_codes": ["FAIL_CTH_NOT_MET"]},
    },
    {
        "name": "CMR→NGA petroleum VNM pass",
        "input": {
            "hs6_code": "271019", "hs_version": "HS2017",
            "exporter": "CMR", "importer": "NGA", "year": 2025,
            "facts": {
                "ex_works": 100000, "non_originating": 55000,
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "VNM", "rule_status": "agreed",
        },
    },
    {
        "name": "CMR→NGA petroleum VNM fail — over threshold",
        "input": {
            "hs6_code": "271019", "hs_version": "HS2017",
            "exporter": "CMR", "importer": "NGA", "year": 2025,
            "facts": {
                "ex_works": 100000, "non_originating": 65000,
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {"eligible": False, "failure_codes": ["FAIL_VNM_EXCEEDED"]},
    },
    {
        "name": "Missing facts — incomplete assessment",
        "input": {
            "hs6_code": "271019", "hs_version": "HS2017",
            "exporter": "CMR", "importer": "NGA", "year": 2025,
            "facts": {"direct_transport": True},
        },
        "expected": {
            "eligible": False,
            "missing_facts": ["ex_works", "non_originating"],
            "confidence_class": "incomplete",
        },
    },
    {
        "name": "Provisional rule status",
        "input": {
            "hs6_code": "610910", "hs_version": "HS2017",
            "exporter": "GHA", "importer": "NGA", "year": 2025,
            "facts": {
                "tariff_heading_input": "5208",
                "tariff_heading_output": "6109",
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "CTH",
            "rule_status": "provisional", "confidence_class": "provisional",
        },
    },
]
```

### 2.5 — Expression Grammar Spec

Create `docs/expression_grammar.md`:

```markdown
# Expression Grammar for the Eligibility Engine

## Threshold comparison
vnom_percent <= 60
va_percent >= 40

## Boolean fact check
wholly_obtained == true
specific_process_performed == true

## Tariff shift check
tariff_heading_input != tariff_heading_output

## Compound (AND within a pathway)
vnom_percent <= 60 AND specific_process_performed == true

## OR logic
Handled at the PATHWAY level, not within expressions.
Each pathway has its own expression. First pass wins.

## Variable resolution
1. Check case_input_fact for the variable name
2. If derived variable, compute it (requires source facts present)
3. If still missing, add to missing_variables, return None

## Derived variables
vnom_percent = non_originating / ex_works * 100
va_percent = (ex_works - non_originating) / ex_works * 100
Both require ex_works > 0. Division by zero = error, not default.

## Operators
Comparison: <=, >=, <, >, ==, !=
Logical: AND, OR (case-insensitive)
No parentheses in v0.1.

## Safety
No eval(). No exec(). No function calls. No attribute access.
Whitelist: variable names, numeric literals, boolean literals, operators.
Max expression length: 500 characters.
```

### 2.6 — Infrastructure Files

**docker-compose.yml**

```yaml
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: afcfta
      POSTGRES_USER: afcfta
      POSTGRES_PASSWORD: afcfta_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

**.env**

```
DATABASE_URL=postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta
DATABASE_URL_SYNC=postgresql://afcfta:afcfta_dev@localhost:5432/afcfta
ENV=development
LOG_LEVEL=DEBUG
```

### 2.7 — Commit Discipline

**Golden rule: commit after every successful prompt.** If the next prompt goes
sideways, you can `git reset --hard` to a known good state. Use descriptive
commit messages:

```
git commit -m "L1: hs6_product table + ORM model + repository"
git commit -m "rule_resolution_service: PSR lookup by hs6"
```

---

## Part 3: Pre-Flight Checklist

Complete every item before opening the coding agent.

```
[ ] AGENTS.md (or CLAUDE.md) exists at repo root
[ ] docs/ has all 7 architecture files + expression_grammar.md
[ ] app/core/ has countries.py, fact_keys.py, entity_keys.py, failure_codes.py
[ ] tests/fixtures/golden_cases.py exists
[ ] docker-compose.yml exists
[ ] .env exists (copy from .env section above)
[ ] Postgres is running (docker compose up -d)
[ ] Test database exists (createdb -h localhost -U afcfta afcfta_test)
[ ] git init && git add -A && git commit -m "initial: docs + reference data"
```

---

## Part 4: The Prompt Handbook

### Prompting Philosophy

Your project docs are extremely detailed. The biggest risk is not "the agent
can't code" — it's **drift from your spec**. Every prompt should anchor to a
specific document, table, contract, or execution step.

**Pattern:** `[What to build] + [Which doc defines it] + [What to verify]`

**Tool-specific syntax:**

| Action | Claude Code | Codex |
|--------|-------------|-------|
| Reference a file | `Read @docs/Concrete_Contract.md` | `Read the file docs/Concrete_Contract.md` |
| Instruction file | CLAUDE.md at root | AGENTS.md at root + directory-scoped |
| Running commands | Agent proposes, you approve | Add "Do NOT run [cmd]" for sandbox safety |

### Phase 0: Scaffold & Infrastructure

**Prompt 0.1 — Full project bootstrap**

This is the initial prompt. It's provided as a separate deliverable because of
its length. See "AIS_Initial_Prompt.md" for the complete text.

What it creates: pyproject.toml, full directory structure with stubs, config,
database layer, all 32+ enums, domain exceptions, common schemas, FastAPI app
with error handlers, Alembic setup, health endpoint, and a working test.

**Verify:** `pytest tests/unit/test_health.py -v` passes, `curl /api/v1/health`
returns 200.

---

**Prompt 0.2 — Test infrastructure**

```
Create tests/conftest.py with pytest-asyncio fixtures:

1. A test database setup that creates all tables using Alembic migrations
   against a test database (DATABASE_URL with "_test" suffix).
2. A db_session fixture that wraps each test in a transaction and
   rolls back after the test completes.
3. An async_client fixture using httpx.AsyncClient pointing at the FastAPI
   app with the test db_session injected.
4. A seed_golden_data fixture that inserts the 5 golden HS6 products,
   rules, tariffs, and statuses needed for integration tests.

Use pytest-asyncio with mode="auto". Ensure every fixture properly
cleans up connections.

Read the file tests/fixtures/golden_cases.py to understand the test data
shape. Read the file app/db/session.py for the session pattern to follow.
```

**Verify:** `pytest --co` shows fixtures available. No import errors.

---

### Phase 1: Data Layer (Backbone + Provenance + Rules + Tariffs)

---

**Prompt 1.0 — Source registry and legal provision**

```
Read the file docs/Concrete_Contract.md Sections 1.3 and 1.4. Create:

1. source_registry — tracks every ingested legal document with:
   authority_tier, source_type, issuing_body, jurisdiction, effective_date,
   checksum_sha256, supersedes/superseded_by chain.

2. legal_provision — stores individual legal provisions:
   article_ref, annex_ref, verbatim text, normalized text, status, topic.

These are the provenance backbone. Every psr_rule.source_id and
evidence_requirement.legal_basis_provision_id points here.

Create:
- app/db/models/sources.py (SQLAlchemy models matching DDL exactly)
- Alembic migration (do NOT run it)
- app/repositories/sources_repository.py (basic CRUD + lookup by topic)
- app/schemas/sources.py (Pydantic response models)
```

**Verify:** Migration file exists. Model columns match DDL.

---

**Prompt 1.1 — hs6_product backbone**

```
Read the file docs/Concrete_Contract.md. Create:

1. app/db/models/hs.py — SQLAlchemy model for hs6_product exactly matching
   the DDL. Include all columns, constraints, and indexes.
2. Alembic migration (do NOT run it).
3. app/repositories/hs_repository.py with: get_by_code(hs_version, hs6_code),
   search_by_description(query), list_all(limit, offset).
4. app/schemas/hs.py with Pydantic models: HS6ProductResponse.

The hs6_product table is the canonical backbone. Every other table joins
through hs_version + hs6_id. Get this right.
```

**Verify:** Model columns match DDL. Repository methods have correct signatures.

---

**Prompt 1.1b — hs6_psr_applicability (CRITICAL)**

```
Read the file docs/Join_Strategy.md Section 1.3 and 2.1. Create
hs6_psr_applicability — the materialized table that resolves which PSR
applies to a given HS6 code.

This table handles inheritance: a rule can apply at chapter (2-digit),
heading (4-digit), or subheading (6-digit) level. The applicability table
pre-computes which PSR governs each HS6 code, with:
- hs6_id (FK to hs6_product)
- psr_id (FK to psr_rule)
- applicability_type (direct / inherited_heading / inherited_chapter)
- priority_rank (lower = higher priority)
- effective_date, expiry_date

Add to app/db/models/rules.py. Create Alembic migration (do NOT run it).
Add to rules_repository: resolve_applicable_psr(hs6_id, assessment_date)
using the exact SQL from Join_Strategy.md Section 2.1.

This is the join that EVERY rule lookup passes through.
```

---

**Prompt 1.2 — PSR rule tables**

```
Read the file docs/Concrete_Contract.md and docs/Join_Strategy.md. Create
the rules layer — three tightly coupled tables:

1. psr_rule — the parent rule record
2. psr_rule_component — individual components (WO, CTH, VNM, etc.)
3. eligibility_rule_pathway — AND/OR pathway combinations

All three must join through hs_version + hs6_id back to hs6_product.

Create:
- app/db/models/rules.py (add to existing file with hs6_psr_applicability)
- Alembic migration (do NOT run it)
- app/repositories/rules_repository.py with:
  get_rules_by_hs6(hs_version, hs6_code) → returns rule + components + pathways
- app/schemas/rules.py with nested Pydantic response models

Critical: psr_rule_component.expression_template stores the boolean expression
that the expression_evaluator will execute. Do not lose this column.
```

---

**Prompt 1.3 — Tariff tables**

```
Read the file docs/Concrete_Contract.md. Create the tariff layer:

1. tariff_schedule_header — schedule metadata per country
2. tariff_schedule_line — line items with HS6, base rate, category
3. tariff_schedule_rate_by_year — year-by-year preferential rates

All join through hs_version + hs6_id.

Create:
- app/db/models/tariffs.py
- Alembic migration (do NOT run it)
- app/repositories/tariffs_repository.py with:
  get_tariff(exporter, importer, hs_version, hs6_code, year)
- app/schemas/tariffs.py

The tariff query must be corridor-aware: needs both exporter_country and
importer_country to resolve the correct schedule.
```

---

### Phase 2: Data Layer (Status + Evidence + Decision + Intelligence)

---

**Prompt 2.1 — Status layer**

```
Read the file docs/Concrete_Contract.md. Create status_assertion and
transition_clause tables.

status_assertion tracks whether a rule/schedule/corridor is agreed, pending,
provisional, etc. Joins to entities by entity_type + entity_key (polymorphic).
Use the key patterns from app/core/entity_keys.py.

Create:
- app/db/models/status.py
- Alembic migration (do NOT run it)
- app/repositories/status_repository.py with:
  get_status(entity_type, entity_key) → current status assertion
  get_active_transitions(entity_type, entity_key)
- app/schemas/status.py
```

---

**Prompt 2.2 — Evidence layer**

```
Create evidence_requirement, verification_question, and
document_readiness_template tables per docs/Concrete_Contract.md.

These are persona-aware (officer/analyst/exporter get different requirements).

Create:
- app/db/models/evidence.py
- Alembic migration (do NOT run it)
- app/repositories/evidence_repository.py with:
  get_requirements(entity_type, entity_key, persona_mode)
  get_verification_questions(entity_type, entity_key, risk_category)
- app/schemas/evidence.py
```

---

**Prompt 2.3 — Case and decision layer**

```
Create case_file, case_input_fact, case_failure_mode, and
case_counterfactual tables per docs/Concrete_Contract.md.

Create:
- app/db/models/cases.py
- Alembic migration (do NOT run it)
- app/repositories/cases_repository.py with:
  create_case(data), add_facts(case_id, facts),
  get_case_with_facts(case_id)
- app/schemas/cases.py
```

---

**Prompt 2.3b — Evaluation audit tables**

```
Read the file docs/Join_Strategy.md Sections 5.2 and 3.5. Create:

1. eligibility_evaluation — one row per assessment run:
   case_id, evaluation_date, overall_outcome, pathway_used, confidence_class,
   rule_status_at_evaluation, tariff_status_at_evaluation.

2. eligibility_check_result — each atomic check within an evaluation:
   evaluation_id, check_type, check_code, passed (bool), details_json,
   component_id (nullable FK).

Create:
- app/db/models/evaluations.py
- Alembic migration (do NOT run it)
- app/repositories/evaluations_repository.py with:
  persist_evaluation(evaluation_data, check_results)
  get_evaluation_with_checks(evaluation_id)
  get_evaluations_for_case(case_id)
- app/schemas/evaluations.py
```

---

**Prompt 2.4 — Intelligence layer**

```
Create corridor_profile and alert_event tables per docs/Concrete_Contract.md.

Create:
- Add to app/db/models/evaluations.py (or new file)
- Alembic migration (do NOT run it)
- app/repositories/evaluations_repository.py (add corridor + alert methods)
- app/schemas/assessments.py (corridor + alert response models)
```

---

### Phase 3: Services (The Business Logic)

Each service maps to a step in the deterministic engine execution order.

---

**Prompt 3.1 — Classification service**

```
Create app/services/classification_service.py.

Input: hs_code (string, might be HS8/10), hs_version (optional)
Output: HS6ProductResponse

Logic:
1. If input is already HS6 → look up directly
2. If input is HS8/10 → truncate to 6 digits, look up
3. If hs_version not provided → use latest version
4. If not found → raise ClassificationError with the attempted code

Use hs_repository. Write unit tests: exact match, truncation, not found.
Read the file app/db/models/hs.py for the ORM model pattern to follow.
```

---

**Prompt 3.2 — Rule resolution service**

```
Create app/services/rule_resolution_service.py.

Input: hs_version, hs6_code
Output: RuleResolutionResult (psr_rules, components, pathways, rule_status)

Logic:
1. Call rules_repository.resolve_applicable_psr() — goes through
   hs6_psr_applicability, NOT direct lookup
2. For each rule, fetch components and pathways
3. Group pathways by logic_group (AND within, OR between)
4. Return structured result

Read the file docs/Join_Strategy.md for the pathway AND/OR expansion logic.
Write tests: single rule, multiple pathways, AND-group, OR-alternatives.
```

---

**Prompt 3.2b — Fact normalization service**

```
Create app/services/fact_normalization_service.py.

Input: list of case_input_fact records
Output: dict[str, Any] with normalized typed values

Logic:
1. Extract typed value based on fact_value_type (number/text/boolean/json/list)
2. Validate fact_type against app/core/fact_keys.py
3. Compute derived variables (vnom_percent, va_percent) if both
   ex_works and non_originating are present
4. Return complete facts dict

Do NOT default missing values. If ex_works is missing, do not set
vnom_percent to 0 — leave it absent.

Write tests: complete facts, partial facts, invalid fact_type, zero ex_works.
```

---

**Prompt 3.3 — Expression evaluator (HIGHEST RISK)**

```
Create app/services/expression_evaluator.py.

Read the file docs/expression_grammar.md for the full specification.

Input:
  - expression_template (string, e.g., "vnom_percent <= 60")
  - facts (dict from fact_normalization_service)
Output:
  - result: bool (pass/fail) or None if missing variables
  - evaluated_expression: string with values substituted
  - missing_variables: list[str]

Rules:
- SAFE parser only — no eval(), no exec(), no compile()
- Parse expression, evaluate against whitelist of allowed operations
- Support: <=, >=, <, >, ==, != comparisons
- Support: AND, OR for compound expressions
- If a required fact is missing → result is None, add to missing_variables
- Never infer missing values

Write extensive tests: VNM pass, VNM fail, CTH (boolean), missing facts,
compound AND/OR, zero ex_works, max expression length.
```

**Review this output carefully. The expression evaluator is the core IP.**

---

**Prompt 3.4 — Tariff resolution service**

```
Create app/services/tariff_resolution_service.py.

Input: exporter_country, importer_country, hs_version, hs6_code, year
Output: TariffResolutionResult (base_rate, preferential_rate, staging_year,
  tariff_status, tariff_category)

Logic:
1. Find schedule header for exporter→importer corridor
2. Find schedule line for HS6
3. Find rate for requested year (fallback: most recent before that year)
4. Attach status from status_service

Write tests: normal, missing schedule, missing rate (fallback), excluded.
```

---

**Prompt 3.5 — Status service**

```
Create app/services/status_service.py.

Input: entity_type, entity_key
Output: StatusOverlay (status_type, effective dates, confidence_class,
  active_transitions, constraints)

confidence_class logic:
- "complete" if agreed and all data present
- "provisional" if provisional or pending
- "incomplete" if data gaps exist

Missing status → explicit "unknown", never null.
```

---

**Prompt 3.6 — Evidence service**

```
Create app/services/evidence_service.py.

Input: entity_type, entity_key, persona_mode, existing_documents
Output: EvidenceReadinessResult (required, missing, verification_questions,
  readiness_score)

Logic: fetch requirements by persona, diff against existing, compute score.
```

---

**Prompt 3.7 — General origin rules service**

```
Create app/services/general_origin_rules_service.py.

This is SEPARATE from PSR evaluation. Three checks:

1. Insufficient operations — minimal operations never confer origin
2. Cumulation — materials from AfCFTA parties treated as originating
3. Direct transport — shipped directly or permitted transshipment

Input: case_facts, psr_result
Output: GeneralRulesResult (each check pass/fail, general_rules_passed bool)

A product can pass PSR but fail general rules. They are applied AFTER PSR.
```

---

**Prompt 3.8 — Eligibility service (orchestrator)**

```
Create app/services/eligibility_service.py.

This orchestrates the strict execution order from the root AGENTS.md:

1. classification_service.resolve() → canonical HS6
2. rule_resolution_service.resolve() → PSR + pathways
3. Run BLOCKER CHECKS before pathway evaluation:
   - rule_status pending? → BLOCKER
   - no tariff schedule? → BLOCKER
   - core facts missing for ALL pathways? → BLOCKER
   - corridor not operational? → BLOCKER
   If any blocker fires → return immediately, skip pathway eval.
4. For each pathway: expression_evaluator.evaluate()
5. general_origin_rules_service.evaluate()
6. status_service.get_overlay()
7. tariff_resolution_service.resolve()
8. evidence_service.get_readiness()

Use REPEATABLE READ transaction isolation for the full assessment.
Persist results via evaluations_repository (eligibility_evaluation +
eligibility_check_result rows, atomic commit).

Output must match docs/v1_scope.md Section 7.1 exactly:
{hs6_code, eligible, pathway_used, rule_status, tariff_outcome,
 failures, missing_facts, evidence_required, confidence_class}

Write integration tests with mocked services. Test: eligible, ineligible,
missing facts, blocker short-circuit, provisional status.
```

---

### Phase 4: API Routes

---

**Prompt 4.1 — Rule lookup endpoint**

```
Read the file docs/FastAPI_layout.md Section 3. Create app/api/v1/rules.py:

GET /v1/rules/{hs6}
- Query params: hs_version (optional)
- Calls classification_service then rule_resolution_service
- Returns: PSR rules, components, pathways, rule_status, legal_text
- Response model from app/schemas/rules.py

Keep handler thin. Add to app/api/router.py.
```

---

**Prompt 4.2 — Tariff lookup endpoint**

```
Create app/api/v1/tariffs.py:

GET /v1/tariffs?exporter={}&importer={}&hs6={}&year={}
- All params required except hs_version
- Calls tariff_resolution_service
- Returns: base_rate, preferential_rate, staging_year, tariff_status
```

---

**Prompt 4.3 — Case and assessment endpoints**

```
Create app/api/v1/cases.py:

POST /v1/cases — create case with input facts
POST /v1/assessments — run eligibility assessment
GET /v1/cases/{case_id} — retrieve case with results

Assessment response must match docs/v1_scope.md Section 7.1 exactly.
```

---

**Prompt 4.4 — Evidence endpoint**

```
Create app/api/v1/evidence.py:

POST /v1/evidence/readiness — returns required, missing, questions, score
```

---

### Phase 5: Seed Data & Integration Testing

---

**Prompt 5.1 — Seed data**

```
Create scripts/seed_data.py that populates the database with v0.1 data:

1. 5 HS6 products: 110311 (groats), 271019 (petroleum), 610910 (t-shirts),
   870421 (trucks), 030389 (frozen fish)
2. PSR rules for each with realistic components and pathways
3. Tariff schedules for GHA→NGA and CMR→NGA corridors
4. Status assertions (mix of agreed, provisional, pending)
5. Evidence requirements per persona
6. At least one corridor_profile

Data must be internally consistent: rules reference real HS6 records,
tariffs reference real corridors, statuses reference real rules.
```

---

**Prompt 5.2 — Golden path integration test**

```
Create tests/integration/test_golden_path.py using the golden cases
from tests/fixtures/golden_cases.py.

Test the full v0.1 success criteria:
1. Eligible case (GHA→NGA, 110311, CTH pass)
2. Ineligible case (same product, no tariff shift)
3. VNM pass and fail cases (CMR→NGA, 271019)
4. Missing facts case (incomplete confidence_class)
5. Provisional status case

Every test asserts specific failure_codes, missing_facts lists, and
confidence_class values — not just eligible/ineligible.

Runnable with: pytest tests/integration/test_golden_path.py -v
```

---

### Phase 6: Hardening

---

**Prompt 6.1 — Error handling**

```
Create app/core/exceptions.py domain exceptions (if not already complete)
and app/api error handlers returning proper HTTP responses:
- 404 for not-found errors
- 422 for insufficient facts
- 500 for expression evaluation errors

Every error response includes machine-readable error_code and message.
```

---

**Prompt 6.2 — Audit service**

```
Create app/services/audit_service.py.

Logs the full decision trace for every assessment:
1. Input facts
2. Each step's output (HS6 resolved, rules found, expressions evaluated,
   general rules applied, status overlaid, tariff computed)
3. Stores trace in eligibility_evaluation + eligibility_check_result

Log to both database and structured logging.
```

---

## Part 5: Anti-Patterns to Watch For

**1. Merged engine layers.** PSR rules and general origin rules evaluated in
the same function. They must be separate services, called in sequence.

**2. Dropped status fields.** Response returned without `rule_status` or
`confidence_class`. Check every Pydantic response model.

**3. eval() in the expression evaluator.** Security risk. Require safe parser.

**4. Joining on text instead of HS6 IDs.** Any query joining `psr_rule.hs_code`
to `tariff_schedule_line.description` is wrong. All joins: `hs_version + hs6_id`.

**5. Business logic in route handlers.** If a handler exceeds ~10 lines of logic,
extract to a service.

**6. Silent inference.** Missing fact → must flag as missing. Never default to 0
or True. Check for `default=True` on fact-dependent fields.

**7. Skipping hs6_psr_applicability.** Direct PSR lookup instead of going through
the materialized applicability table. The agent will try to shortcut this.

**8. Monolithic prompts.** Don't build the entire eligibility engine in one prompt.
One service per prompt, each independently testable.

---

## Part 6: Recovery Prompts

**Migration failed:**
```
The migration for [table] failed with: [error]. Read the DDL in
docs/Concrete_Contract.md. Fix the existing migration file — do not create
a new one. Do NOT run alembic.
```

**Tests fail after a service change:**
```
These tests are failing: [paste output]. The tests encode our spec.
Fix the service to match test expectations, not the other way around.
```

**Response contract drift:**
```
POST /v1/assessments is missing [field]. Read docs/v1_scope.md Section 7.1.
Every response must include: hs6_code, eligible, pathway_used, rule_status,
tariff_outcome, failures, missing_facts, evidence_required, confidence_class.
Fix the Pydantic model and service.
```

**Need to backtrack:**
```
Reverting to commit [hash]. Read the current state of [file] and continue
from there. Next task: [specific thing to build].
```

---

## Part 7: Complete Build Sequence

| #    | Prompt | Creates | Verify |
|------|--------|---------|--------|
| 0.1  | Bootstrap scaffold | Full structure, enums, health endpoint | `curl /api/v1/health` → 200 |
| 0.2  | Test infrastructure | conftest.py, fixtures | `pytest --co` clean |
| 1.0  | Source + provision | Provenance tables | Migration file exists |
| 1.1  | hs6_product | Backbone table + repo | Columns match DDL |
| 1.1b | hs6_psr_applicability | Materialized PSR resolver | SQL matches Join_Strategy |
| 1.2  | PSR rules | 3 rule tables + repo | Nested query works |
| 1.3  | Tariffs | 3 tariff tables + repo | Corridor query works |
| 2.1  | Status | status_assertion + repo | Status lookup works |
| 2.2  | Evidence | 3 evidence tables + repo | Persona filter works |
| 2.3  | Cases | 4 case tables + repo | Case creation works |
| 2.3b | Evaluations | Audit tables + repo | Persist works |
| 2.4  | Intelligence | corridor + alerts | Profile query works |
| 3.1  | Classification svc | HS6 resolution | Unit tests pass |
| 3.2  | Rule resolution svc | PSR + pathway expansion | AND/OR tests pass |
| 3.2b | Fact normalization | Raw facts → typed dict | Missing fact test |
| 3.3  | Expression evaluator | Boolean engine | VNM/CTH/missing tests |
| 3.4  | Tariff resolution svc | Corridor-aware rates | Fallback year test |
| 3.5  | Status service | Overlay + confidence | Provisional test |
| 3.6  | Evidence service | Readiness computation | Persona diff test |
| 3.7  | General rules svc | Insufficent/cumulation/transport | Separate layer test |
| 3.8  | Eligibility svc | Full orchestrator | Integration test |
| 4.1  | Rules endpoint | GET /v1/rules/{hs6} | curl returns rules |
| 4.2  | Tariff endpoint | GET /v1/tariffs | curl returns rates |
| 4.3  | Case endpoints | POST cases + assessments | Full API flow |
| 4.4  | Evidence endpoint | POST /v1/evidence/readiness | Persona test |
| 5.1  | Seed data | 5 products, 2 corridors | Data in DB |
| 5.2  | Golden path test | Acceptance suite | pytest passes |
| 6.1  | Error handling | Exceptions + HTTP handlers | Clean errors |
| 6.2  | Audit service | Decision trace | Trace stored |
