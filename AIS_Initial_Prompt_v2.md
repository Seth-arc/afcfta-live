# Initial Prompt for AI Coding Agent

Works with both Claude Code and Codex CLI. Copy the prompt text in the
PROMPT section below and paste it into your agent.

---

## Pre-Flight (complete before opening the agent)

```
[ ] AGENTS.md (or CLAUDE.md) exists at repo root
[ ] docs/ has: PRD.md, v1_scope.md, Implementation_Blueprint.md,
    Canonical_Corpus.md, Concrete_Contract.md, Join_Strategy.md,
    FastAPI_layout.md, expression_grammar.md, afcfta_corpus_parsing_agent_spec.md, corpus_parsing_guide.md.
[ ] app/core/ has: countries.py, fact_keys.py, entity_keys.py, failure_codes.py
[ ] tests/fixtures/golden_cases.py exists
[ ] docker-compose.yml and .env exist
[ ] Postgres running (docker compose up -d)
[ ] Test database created (createdb -h localhost -U afcfta afcfta_test)
[ ] git init && git add -A && git commit -m "initial: docs + reference data"
```

All file contents for the pre-flight items are in the Vibecoding Handbook
Parts 2.3–2.6. Create them by hand before proceeding.

---

## PROMPT

Copy everything between the `---START---` and `---END---` markers.

---START---

Read the following files in this exact order before writing any code:

1. AGENTS.md (repo root — your operating instructions for this project)
2. docs/FastAPI_layout.md (exact repo structure and service boundaries)
3. docs/Concrete_Contract.md (all PostgreSQL enums — Section 1.2 specifically)
4. docs/v1_scope.md (what we're building and what's out of scope)

Take time to understand the architecture before generating anything.

Now bootstrap the project. Create everything needed for a running FastAPI app
with database connectivity and all domain enums. Here is exactly what to build:

## A. pyproject.toml

Create pyproject.toml with:
- Project name: afcfta-intelligence
- Python >=3.11
- Dependencies: fastapi, uvicorn[standard], sqlalchemy[asyncio]>=2.0,
  asyncpg, pydantic>=2.0, pydantic-settings, alembic, python-dotenv
- Dev dependencies group: pytest, pytest-asyncio, httpx, ruff
- [tool.pytest.ini_options]: asyncio_mode = "auto", testpaths = ["tests"]
- [tool.ruff]: line-length = 100, target-version = "py311"

## B. Full directory structure

Create the complete directory structure from docs/FastAPI_layout.md Section 1
with __init__.py in every Python package. Include all subdirectories:
app/db/models/, app/schemas/, app/api/v1/, app/services/, app/repositories/,
app/core/, tests/unit/, tests/integration/, tests/fixtures/, alembic/,
scripts/, data/raw/tier1_binding/, data/raw/tier2_operational/,
data/raw/tier3_support/, data/raw/tier4_analytics/, data/staged/,
data/processed/

Stub files: Every .py file listed in docs/FastAPI_layout.md Section 1 should
exist. For services, repositories, and route files, create them with only a
module docstring explaining the module's purpose (taken from Section 2 service
boundary descriptions). Do NOT implement any business logic yet.

## C. app/config.py

Use pydantic-settings to load from environment:
- DATABASE_URL (required)
- DATABASE_URL_SYNC (optional, for Alembic)
- ENV (default "development")
- LOG_LEVEL (default "INFO")
- APP_TITLE = "AfCFTA Intelligence API"
- APP_VERSION = "0.1.0"

## D. app/db/base.py

SQLAlchemy 2.0 async setup:
- create_async_engine from DATABASE_URL
- async_sessionmaker
- DeclarativeBase class

## E. app/db/session.py

- Async session context manager
- FastAPI dependency: get_db() that yields an AsyncSession with proper cleanup

## F. app/core/enums.py

Read docs/Concrete_Contract.md Section 1.2. Create Python enums matching
EVERY PostgreSQL enum defined there. Use the (str, Enum) pattern:

    class RuleStatusEnum(str, Enum):
        AGREED = "agreed"
        ...

Include ALL of these — do not skip any:
authority_tier_enum, source_type_enum, source_status_enum,
instrument_type_enum, provision_status_enum, hs_level_enum,
rule_status_enum, rule_component_type_enum, operator_type_enum,
threshold_basis_enum, schedule_status_enum, tariff_category_enum,
staging_type_enum, rate_status_enum, status_type_enum, persona_mode_enum,
requirement_type_enum, decision_outcome_enum, confidence_level_enum,
case_submission_status_enum, fact_source_type_enum, fact_value_type_enum,
verification_risk_category_enum, change_type_enum, failure_type_enum,
severity_enum, counterfactual_type_enum, projected_outcome_enum,
alert_type_enum, alert_severity_enum, alert_status_enum,
corridor_status_enum

Also include the operational enums from docs/FastAPI_layout.md Section 3:
PersonaMode, LegalOutcome, ConfidenceLevel, CheckSeverity, CheckGroup,
ScheduleStatus

Enum VALUES must match PostgreSQL enum values exactly.

## G. app/core/exceptions.py

Domain exception classes:
- AISBaseException(Exception) — base for all domain errors
- ClassificationError(AISBaseException) — HS6 not found
- RuleNotFoundError(AISBaseException) — no PSR for this HS6
- TariffNotFoundError(AISBaseException) — no schedule for corridor
- StatusUnknownError(AISBaseException) — no status assertion found
- ExpressionEvaluationError(AISBaseException) — expression eval failed
- InsufficientFactsError(AISBaseException) — required facts missing
- CorridorNotSupportedError(AISBaseException) — country pair not in v0.1

Each accepts a message (str) and optional detail (dict).

## H. app/schemas/common.py

Create from docs/FastAPI_layout.md Section 4:
- Meta (request_id: str, timestamp: datetime)
- ApiResponse (data: Any, meta: Meta)
- ErrorDetail (code: str, message: str, details: Optional[dict])
- ErrorResponse (error: ErrorDetail, meta: Meta)

## I. app/main.py

Minimal FastAPI app:
- Title and version from config
- Include api_router at prefix /api/v1
- Exception handlers for all domain exceptions → proper HTTP responses
  (404 for not-found, 422 for insufficient facts, 500 for eval errors)
- Startup event logging "AfCFTA Intelligence API v0.1.0 starting"

## J. app/api/router.py

Root router that includes the v1 health endpoint.

## K. app/api/v1/health.py

GET /health → {"status": "ok", "version": "0.1.0"}

## L. Alembic setup

Initialize Alembic with async PostgreSQL support:
- alembic.ini pointing to DATABASE_URL
- alembic/env.py that imports our Base.metadata and uses async engine
- env.py must load .env via python-dotenv
- Create an initial empty migration file

IMPORTANT: Do NOT run any alembic commands. Just create the config files
and the empty migration. I will run migrations myself.

## M. tests/conftest.py

Pytest fixtures:
- App fixture providing the FastAPI app
- async_client fixture using httpx.AsyncClient
- test_settings fixture overriding DATABASE_URL for afcfta_test database

## N. tests/unit/test_health.py

One test: hit GET /api/v1/health, assert 200 and body contains status "ok".

## Constraints

- Do NOT run pip install, alembic, pytest, uvicorn, or any shell commands
  that need network or database access. Only create and edit files.
- Do NOT create any ORM models, business logic, or domain-specific endpoints.
  This is the foundation only.
- Do NOT modify any files in app/core/countries.py, app/core/fact_keys.py,
  app/core/entity_keys.py, app/core/failure_codes.py, or tests/fixtures/.
  Those are locked reference data I created by hand.
- Do NOT modify anything in docs/. Those are read-only architecture specs.

## When finished

List every file you created, organized by directory. Then flag any decisions
you made where the architecture docs were ambiguous or contradictory.

---END---

---

## After the Prompt Runs — Verification

```bash
# 1. Install dependencies
pip install -e ".[dev]"
# or: pip install -e . && pip install pytest pytest-asyncio httpx ruff

# 2. Run the health test
pytest tests/unit/test_health.py -v
# Expected: 1 passed

# 3. Start the app
uvicorn app.main:app --reload
# Hit http://localhost:8000/api/v1/health
# Expected: {"status": "ok", "version": "0.1.0"}

# 4. Verify Alembic
alembic upgrade head
# Expected: runs with no errors (empty migration)

# 5. Spot-check enums
python -c "from app.core.enums import RuleStatusEnum; print(list(RuleStatusEnum))"
# Expected: all values printed

# 6. Count files
find app -name "*.py" | wc -l
# Expected: 40+ files

# 7. Verify stubs exist
python -c "import app.services.eligibility_service"
# Expected: imports without error
```

If all checks pass:

```bash
git add -A
git commit -m "scaffold: full project structure, enums, health endpoint, alembic"
```

---

## What Comes Next

Your second prompt should be **Prompt 1.1** from the handbook (hs6_product
backbone table). It's the spine everything joins through, and getting it right
early validates that your Alembic + ORM + repository pattern works end-to-end.

If you want provenance from the start, do **Prompt 1.0** (source_registry +
legal_provision) first instead. Either order works — the hs6_product table
doesn't have a foreign key to source_registry.

If using Codex, after this scaffold prompt runs successfully, run
`bash split_agents.sh` to create the directory-scoped AGENTS.md files before
proceeding to Prompt 1.1.
