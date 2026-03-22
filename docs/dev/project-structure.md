# Project Structure

This document is the orientation guide for a new contributor.

AIS uses a strict layered architecture:

```text
routes -> services -> repositories -> database
```

Business logic belongs in services.
Route handlers stay thin.
Repositories contain SQL and data access only.

## Repository Layout

```text
afcfta-live/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── assessments.py
│   │       ├── audit.py
│   │       ├── cases.py
│   │       ├── evidence.py
│   │       ├── health.py
│   │       ├── rules.py
│   │       └── tariffs.py
│   ├── core/
│   │   ├── countries.py
│   │   ├── entity_keys.py
│   │   ├── enums.py
│   │   ├── exceptions.py
│   │   ├── fact_keys.py
│   │   └── failure_codes.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   │       ├── cases.py
│   │       ├── evaluations.py
│   │       ├── evidence.py
│   │       ├── hs.py
│   │       ├── intelligence.py
│   │       ├── rules.py
│   │       ├── sources.py
│   │       ├── status.py
│   │       └── tariffs.py
│   ├── repositories/
│   │   ├── cases_repository.py
│   │   ├── evaluations_repository.py
│   │   ├── evidence_repository.py
│   │   ├── hs_repository.py
│   │   ├── intelligence_repository.py
│   │   ├── rules_repository.py
│   │   ├── sources_repository.py
│   │   ├── status_repository.py
│   │   └── tariffs_repository.py
│   ├── schemas/
│   │   ├── assessments.py
│   │   ├── audit.py
│   │   ├── cases.py
│   │   ├── common.py
│   │   ├── evaluations.py
│   │   ├── evidence.py
│   │   ├── hs.py
│   │   ├── intelligence.py
│   │   ├── rules.py
│   │   ├── sources.py
│   │   ├── status.py
│   │   └── tariffs.py
│   ├── services/
│   │   ├── audit_service.py
│   │   ├── classification_service.py
│   │   ├── eligibility_service.py
│   │   ├── evidence_service.py
│   │   ├── expression_evaluator.py
│   │   ├── fact_normalization_service.py
│   │   ├── general_origin_rules_service.py
│   │   ├── rule_resolution_service.py
│   │   ├── status_service.py
│   │   └── tariff_resolution_service.py
│   ├── config.py
│   └── main.py
├── alembic/
│   ├── env.py
│   └── versions/
├── docs/
│   ├── api/
│   ├── concepts/
│   ├── dev/
│   └── user-guide/
├── scripts/
│   └── seed_data.py
├── tests/
│   ├── fixtures/
│   │   └── golden_cases.py
│   ├── integration/
│   └── unit/
├── AGENTS.md
├── CONTRIBUTING.md
├── alembic.ini
└── pyproject.toml
```

## What Each Area Contains

## `app/api/v1/`

Versioned HTTP route handlers.

Rules:

- validate input
- call a service or repository dependency
- return the response

Do not put business logic here.

## `app/services/`

All business logic lives here.

This is where you should expect to find:

- rule orchestration
- fact normalization
- expression evaluation
- status overlay logic
- evidence readiness logic
- audit-trail reconstruction

If a route or repository starts accumulating domain logic, move it into a service.

## `app/repositories/`

Repositories own database access.

This is where SQL belongs.

Rules:

- SQL queries only
- no business policy decisions
- no HTTP behavior

Repository SQL should follow the patterns defined in `docs/Join_Strategy.md`.

## `app/db/models/`

SQLAlchemy ORM models matching the database DDL.

These files should stay aligned with:

- `docs/Concrete_Contract.md`
- parser-derived schema definitions where applicable
- Alembic migrations

## `app/schemas/`

Pydantic models for:

- request payloads
- response payloads
- internal typed service outputs

Use `app/schemas/` for runtime models.
Use `docs/` for the architecture and contract specs that those models implement.

## `app/core/`

Core enums, exceptions, and reference data.

Important locked reference files:

- `app/core/countries.py`
  Supported countries and corridor scope for v0.1
- `app/core/fact_keys.py`
  Canonical production fact names and derived-variable relationships
- `app/core/entity_keys.py`
  Polymorphic key formats such as `HS6_RULE:{psr_id}` and `CORRIDOR:{exporter}:{importer}:{hs6_code}`
- `app/core/failure_codes.py`
  Canonical machine-readable failure codes

Treat those files as reference data, not ordinary code.

## `alembic/`

Database migration environment and revision history.

Use this when changing:

- tables
- columns
- enums
- constraints
- indexes

## `scripts/`

Project utility scripts.

Right now the important script is:

- `scripts/seed_data.py`

That script loads the v0.1 seed dataset used by local development and integration testing.

## `tests/`

Automated test suite.

- `tests/unit/`
  Fast tests with mocking, focused on service and utility logic
- `tests/integration/`
  Full-stack tests hitting the live FastAPI app against a seeded database
- `tests/fixtures/`
  Shared fixture data, including the golden assessment cases

## Where Business Logic Lives

Business logic belongs in `app/services/`.

Examples:

- `classification_service.py`
- `rule_resolution_service.py`
- `eligibility_service.py`
- `status_service.py`
- `evidence_service.py`

Never put core decision logic in:

- route handlers
- repositories

## Where SQL Lives

SQL belongs in `app/repositories/`.

Examples:

- `rules_repository.py`
- `tariffs_repository.py`
- `status_repository.py`

Use `docs/Join_Strategy.md` as the source for query patterns and joins.

## Deterministic Engine Execution Order

The architecture contract in `AGENTS.md` defines the conceptual execution order:

1. Resolve HS6 -> `ClassificationService`
2. Fetch PSR(s) -> `RuleResolutionService`
3. Expand pathways -> `RuleResolutionService`
4. Run blocker checks -> `EligibilityService`
5. Evaluate expressions -> `ExpressionEvaluator`
6. Apply general rules -> `GeneralOriginRulesService`
7. Apply status constraints -> `StatusService`
8. Compute tariff -> `TariffResolutionService`
9. Generate evidence requirements -> `EvidenceService`

The orchestration entry point is:

- `app/services/eligibility_service.py`

That is the place to start if you want to understand how a full assessment is assembled.

## Where Specs Live

Use `docs/` for architecture and contract references.

Important files:

- `docs/FastAPI_layout.md`
- `docs/Concrete_Contract.md`
- `docs/Join_Strategy.md`
- `docs/v1_scope.md`
- `docs/expression_grammar.md`

These are not optional reading when you are making schema or engine changes.

## Where To Start As A New Contributor

If you are brand new:

1. read `AGENTS.md`
2. read `docs/FastAPI_layout.md`
3. read `docs/Join_Strategy.md` if your change touches SQL
4. read `docs/expression_grammar.md` if your change touches rule evaluation
5. open the service that owns the behavior you want to change
