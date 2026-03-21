# AfCFTA Intelligence System — Claude Code Supplement

**What the Prompt Handbook doesn't cover, but Claude Code still needs.**

---

## 1. Tables the Handbook Missed

The handbook's 28 prompts cover the main tables, but your Concrete_Contract.md and Join_Strategy.md define several more that Claude Code needs to build. Without these, the system has gaps that will surface mid-integration.

### 1.1 — hs6_psr_applicability (CRITICAL)

This is the **materialized resolver** for PSR inheritance. Your Join_Strategy.md is explicit: "Use the applicability table, not live inheritance logic." Without it, Claude Code will try to write inheritance resolution logic inline in the rule_resolution_service, which is fragile and wrong.

**Add this prompt between 1.1 and 1.2:**

```
Read @docs/Join_Strategy.md Section 1.3 and 2.1. Create hs6_psr_applicability
— the materialized table that resolves which PSR applies to a given HS6 code.

This table handles inheritance: a rule can apply at chapter level (2-digit),
heading level (4-digit), or subheading level (6-digit). The applicability
table pre-computes which PSR governs each HS6 code, with:
- hs6_id (FK to hs6_product)
- psr_id (FK to psr_rule)
- applicability_type (direct / inherited_heading / inherited_chapter)
- priority_rank (lower = higher priority)
- effective_date, expiry_date

Create:
- app/db/models/rules.py (add to existing)
- Alembic migration
- Add to rules_repository: resolve_applicable_psr(hs6_id, assessment_date)
  using the exact SQL from Join_Strategy.md Section 2.1

This is the join that EVERY rule lookup passes through. It replaces live
inheritance logic with a materialized lookup.
```

### 1.2 — source_registry and legal_provision

These are the provenance backbone. Every PSR rule, tariff schedule, and status assertion traces back to a source document through these tables. Without them, the "auditable" guarantee is hollow.

**Add this prompt in Phase 1 (before rules):**

```
Read @docs/Concrete_Contract.md Sections 1.3 and 1.4. Create:

1. source_registry — tracks every ingested legal document with:
   authority_tier, source_type, issuing_body, jurisdiction, effective_date,
   checksum_sha256, supersedes/superseded_by chain.

2. legal_provision — stores individual legal provisions extracted from sources:
   article_ref, annex_ref, verbatim text, normalized text, status, topic.

These tables are the provenance layer. Every psr_rule.source_id and
evidence_requirement.legal_basis_provision_id points here.

Create:
- app/db/models/sources.py
- Alembic migration
- app/repositories/sources_repository.py (basic CRUD + lookup by topic)
- app/schemas/sources.py
```

### 1.3 — eligibility_evaluation and eligibility_check_result

These are the audit persistence tables from Join_Strategy.md Section 5.2. The eligibility_service produces an assessment, and these tables store every atomic check for replay.

**Add this prompt in Phase 2:**

```
Read @docs/Join_Strategy.md Sections 5.2 and 3.5. Create:

1. eligibility_evaluation — stores one row per assessment run:
   case_id, evaluation_date, overall_outcome, pathway_used, confidence_class,
   rule_status_at_evaluation, tariff_status_at_evaluation.

2. eligibility_check_result — stores each atomic check within an evaluation:
   evaluation_id, check_type (psr/general_rule/status/blocker),
   check_code, passed (bool), details_json, component_id (nullable FK).

These enable the case replay / audit pattern from Section 3.5:
fetch past evaluation → fetch all check_results → reconstruct decision trail.

Create:
- app/db/models/evaluations.py
- Alembic migration
- app/repositories/evaluations_repository.py with:
  persist_evaluation(evaluation_data, check_results)
  get_evaluation_with_checks(evaluation_id)
  get_evaluations_for_case(case_id)
- app/schemas/evaluations.py
```

### 1.4 — hs_code_alias and hs_version_crosswalk

These are in the README's L1 Backbone layer. They handle version mapping (HS2012 → HS2017 → HS2022) and alternative code representations. Not blocking for v0.1 golden path, but Claude Code will hit issues if someone passes an HS2022 code and your system only knows HS2017.

**Optional prompt (add if time permits):**

```
Create hs_code_alias (alternative names/codes for an HS6 product) and
hs_version_crosswalk (maps HS codes across version years: HS2012, HS2017,
HS2022). Add to app/db/models/hs.py. These are L1 backbone tables.
For v0.1, the crosswalk can be minimal — just store the mapping rows,
classification_service will use it as a fallback if direct HS6 lookup fails.
```

---

## 2. Infrastructure Files Claude Code Needs in the Repo

These files should exist BEFORE you start prompting. Create them by hand or with a single setup prompt.

### 2.1 — docker-compose.yml

Claude Code can't set up Postgres for you, but it needs to know the connection string. Put this in the repo root:

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

### 2.2 — .env.example

```
DATABASE_URL=postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta
DATABASE_URL_SYNC=postgresql://afcfta:afcfta_dev@localhost:5432/afcfta
ENV=development
LOG_LEVEL=DEBUG
```

### 2.3 — conftest.py (test infrastructure)

Claude Code will generate tests, but those tests need a database. Create `tests/conftest.py` that:

- Creates a test database (or uses a test schema)
- Runs migrations before the test suite
- Provides a `db_session` fixture with rollback after each test
- Provides a `client` fixture (httpx.AsyncClient) for API tests

**Prompt for this:**

```
Create tests/conftest.py with pytest-asyncio fixtures:

1. A test database setup that creates all tables using Alembic migrations
   against a test database (DATABASE_URL with "_test" suffix).
2. A `db_session` fixture that wraps each test in a transaction and
   rolls back after the test completes.
3. An `async_client` fixture that creates an httpx.AsyncClient pointing
   at the FastAPI app with the test db_session injected.
4. A `seed_golden_data` fixture that inserts the 5 golden HS6 products,
   rules, tariffs, and statuses needed for integration tests.

Use pytest-asyncio with mode="auto". Make sure every fixture properly
cleans up connections.
```

### 2.4 — pyproject.toml test configuration

Add to pyproject.toml:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = ["ignore::DeprecationWarning"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

---

## 3. Reference Data Files Claude Code Needs

These are small data files that encode domain knowledge. Without them, Claude Code will make up values or ask you every time.

### 3.1 — Country code registry

Create `app/core/countries.py`:

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
    ("GHA", "NGA"),
    ("NGA", "GHA"),
    ("CMR", "NGA"),
    ("NGA", "CMR"),
    ("CIV", "NGA"),
    ("SEN", "NGA"),
    ("GHA", "CIV"),
    ("CIV", "SEN"),
]
```

### 3.2 — Fact key registry

The expression evaluator needs to know what fact keys are valid. Create `app/core/fact_keys.py`:

```python
"""
Registry of valid fact_type values for case_input_fact.
The expression evaluator and fact_normalization_service use this
to validate inputs and compute derived variables.
"""

# Core production facts (user-provided)
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

# Derived variables (computed, never stored as input facts)
DERIVED_VARIABLES = {
    "vnom_percent": "non_originating / ex_works * 100",
    "va_percent": "(ex_works - non_originating) / ex_works * 100",
}
```

### 3.3 — Entity key conventions

The status_assertion and evidence_requirement tables use polymorphic `entity_type + entity_key`. Claude Code needs to know the conventions from Join_Strategy.md:

Create `app/core/entity_keys.py`:

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

### 3.4 — Failure code registry

The eligibility engine emits machine-readable failure codes. Define them up front:

Create `app/core/failure_codes.py`:

```python
"""
Canonical failure codes for the eligibility engine.
Every failure in case_failure_mode uses one of these.
"""

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

---

## 4. Golden Test Cases (Exact Input/Output)

The handbook mentions golden path tests, but Claude Code needs the exact data. Create `tests/fixtures/golden_cases.py`:

```python
"""
Golden test cases for the v0.1 acceptance criteria.
Each case defines exact inputs and expected outputs.
"""

GOLDEN_CASES = [
    {
        "name": "GHA→NGA groats CTH pass",
        "input": {
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "1001",
                "tariff_heading_output": "1103",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "CTH",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "GHA→NGA groats CTH fail — no tariff shift",
        "input": {
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "1103",
                "tariff_heading_output": "1103",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_CTH_NOT_MET"],
        },
    },
    {
        "name": "CMR→NGA petroleum VNM pass",
        "input": {
            "hs6_code": "271019",
            "hs_version": "HS2017",
            "exporter": "CMR",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "ex_works": 100000,
                "non_originating": 55000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "VNM",
            "rule_status": "agreed",
            # vnom_percent = 55000/100000*100 = 55%, under 60% threshold
        },
    },
    {
        "name": "CMR→NGA petroleum VNM fail — over threshold",
        "input": {
            "hs6_code": "271019",
            "hs_version": "HS2017",
            "exporter": "CMR",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "ex_works": 100000,
                "non_originating": 65000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_VNM_EXCEEDED"],
            # vnom_percent = 65%, exceeds 60% threshold
        },
    },
    {
        "name": "Missing facts — incomplete assessment",
        "input": {
            "hs6_code": "271019",
            "hs_version": "HS2017",
            "exporter": "CMR",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "direct_transport": True,
                # Missing: ex_works, non_originating
            },
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
            "hs6_code": "610910",
            "hs_version": "HS2017",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "5208",
                "tariff_heading_output": "6109",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "CTH",
            "rule_status": "provisional",
            "confidence_class": "provisional",
        },
    },
]
```

---

## 5. Expression Grammar Spec

The expression evaluator is the highest-risk component. Claude Code needs a formal grammar, not just examples. Create `docs/expression_grammar.md`:

```markdown
# Expression Grammar for the Eligibility Engine

## Supported expression types

### Threshold comparison
```
vnom_percent <= 60
va_percent >= 40
```

### Boolean fact check
```
wholly_obtained == true
specific_process_performed == true
```

### Tariff shift check
```
tariff_heading_input != tariff_heading_output
tariff_subheading_input != tariff_subheading_output
```

### Compound (AND)
```
vnom_percent <= 60 AND specific_process_performed == true
```

### Compound (OR) — represented as separate pathways, NOT inline
OR logic is handled at the pathway level, not within expressions.
Each pathway has its own expression. The eligibility service tries
pathways in priority_rank order; first pass wins.

## Variable resolution order
1. Check case_input_fact for the variable name
2. If not found, check if it's a derived variable and compute it
3. If still not found, add to missing_variables and return None

## Derived variable computation
- vnom_percent = non_originating / ex_works * 100
- va_percent = (ex_works - non_originating) / ex_works * 100
- Both require ex_works > 0 (division by zero → error, not silent default)

## Operators
- Comparison: <=, >=, <, >, ==, !=
- Logical: AND, OR (case-insensitive)
- No parentheses in v0.1 (flatten to multiple pathways instead)

## Safety constraints
- No eval() or exec()
- No function calls
- No attribute access
- Whitelist: variable names, numeric literals, boolean literals, operators
- Maximum expression length: 500 characters
```

---

## 6. Blocker Check Logic

Your Join_Strategy.md defines a specific blocker check sequence that runs BEFORE pathway evaluation. The handbook's eligibility_service prompt (3.8) doesn't include this explicitly. Claude Code needs it.

Add to `CLAUDE.md`:

```markdown
## Blocker Checks (Run Before Pathway Evaluation)
The eligibility service must run hard blocker checks in order before
evaluating any pathway expressions:

1. Is rule_status pending or partially_agreed? → BLOCKER
2. Is tariff_schedule_line missing for this corridor? → BLOCKER  
3. Are core facts missing for ALL pathways? → BLOCKER
4. Is the corridor status not_yet_operational? → BLOCKER

If any blocker fires, the assessment returns immediately with the
blocker failure code. Pathway evaluation is skipped entirely.

Non-blocking status issues (provisional schedule, provisional rule)
are warnings that reduce confidence_class but do not prevent evaluation.
```

---

## 7. Transaction Isolation Requirement

Your Join_Strategy.md Section 5.1 requires `REPEATABLE READ` isolation for assessment reads. Claude Code won't know this unless you tell it.

Add to `CLAUDE.md`:

```markdown
## Transaction Isolation
Assessment requests must use REPEATABLE READ isolation level so that
PSR, tariff, status, and evidence are all resolved against the same
database snapshot. This prevents inconsistency between rules and their
statuses within a single assessment.

Persisted evaluations (writing eligibility_evaluation + check_results)
must be atomic — all rows committed together or none.
```

---

## 8. Missing Prompt: fact_normalization_service

The architecture diagrams show this service but the handbook doesn't have a prompt for it. It sits between raw case_input_fact data and the expression evaluator.

**Add between Prompts 3.2 and 3.3:**

```
Create app/services/fact_normalization_service.py.

This service takes raw case_input_fact records and produces a clean
dict of fact_key → typed value that the expression evaluator can use.

Input: list of case_input_fact records (from repository)
Output: dict[str, Any] with normalized values

Logic:
1. For each fact, extract the typed value based on fact_value_type:
   - "number" → fact_value_number (Decimal)
   - "text" → fact_value_text (str)
   - "boolean" → fact_value_boolean (bool)
   - "json" → fact_value_json (parsed)
   - "list" → fact_value_json (parsed as list)
2. Validate fact_type against the fact key registry
   (app/core/fact_keys.py)
3. Compute derived variables (vnom_percent, va_percent) if
   ex_works and non_originating are both present
4. Return the complete facts dict

Do NOT silently default missing values. If ex_works is missing,
do not set vnom_percent to 0 — leave it absent.

Write tests for: complete facts, partial facts, invalid fact_type,
zero ex_works (should error, not default).
```

---

## 9. Updated Prompt Sequence

With the additions above, here's the corrected build order:

| #     | Prompt                       | What it adds                                |
|-------|------------------------------|---------------------------------------------|
| 0.1   | Project scaffold             | Directory, health endpoint                  |
| 0.2   | Database connection          | SQLAlchemy, Alembic                         |
| 0.3   | Enums                        | All PostgreSQL enums                        |
| 0.4   | **Infrastructure files**     | conftest.py, reference data files           |
| 1.0   | **source_registry + legal_provision** | Provenance tables               |
| 1.1   | hs6_product                  | Backbone table                              |
| 1.1b  | **hs6_psr_applicability**    | Materialized PSR resolver                   |
| 1.2   | PSR rule tables              | psr_rule, component, pathway                |
| 1.3   | Tariff tables                | header, line, rate_by_year                  |
| 2.1   | Status layer                 | status_assertion, transition_clause         |
| 2.2   | Evidence layer               | requirement, question, template             |
| 2.3   | Case layer                   | case_file, input_fact, failure, counterfact  |
| 2.3b  | **Evaluation tables**        | eligibility_evaluation, check_result        |
| 2.4   | Intelligence layer           | corridor_profile, alert_event               |
| 3.1   | Classification service       | HS6 resolution                              |
| 3.2   | Rule resolution service      | PSR lookup via applicability table           |
| 3.2b  | **Fact normalization svc**   | Raw facts → typed dict                      |
| 3.3   | Expression evaluator         | Boolean expression engine                   |
| 3.4   | Tariff resolution service    | Corridor-aware rates                        |
| 3.5   | Status service               | Status overlay + confidence                 |
| 3.6   | Evidence service             | Readiness computation                       |
| 3.7   | General origin rules         | Insufficient ops, cumulation, transport     |
| 3.8   | Eligibility service          | Full orchestrator (with blockers)           |
| 4.1–4 | API routes                   | All endpoints                               |
| 5.1   | Seed data                    | 5 products, 2 corridors                     |
| 5.2   | Golden path tests            | Uses golden_cases.py fixtures               |
| 6.1   | Error handling               | Domain exceptions                           |
| 6.2   | Audit service                | Decision trace persistence                  |

---

## 10. Checklist: Files to Create Before First Prompt

Do these by hand before you start prompting Claude Code:

```
[ ] docker-compose.yml (Section 2.1 above)
[ ] .env.example (Section 2.2)
[ ] .env (copy from .env.example, fill in local values)
[ ] CLAUDE.md (from the handbook, with additions from Sections 6-7 above)
[ ] docs/ folder with all 7 architecture docs
[ ] docs/expression_grammar.md (Section 5 above)
[ ] app/core/countries.py (Section 3.1)
[ ] app/core/fact_keys.py (Section 3.2)
[ ] app/core/entity_keys.py (Section 3.3)
[ ] app/core/failure_codes.py (Section 3.4)
[ ] tests/fixtures/golden_cases.py (Section 4)
[ ] Run: docker compose up -d (Postgres must be running)
[ ] Run: createdb afcfta_test (test database)
[ ] git init && git add -A && git commit -m "initial: docs + reference data"
```

Once these exist, Claude Code has everything it needs for Prompt 0.1.
