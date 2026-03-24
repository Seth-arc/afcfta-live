# Testing

AIS uses two main test layers:

- unit tests
- integration tests

Run the full suite with:

```bash
python -m pytest tests/ -v
```

## Test Layout

```text
tests/
├── fixtures/
│   └── golden_cases.py
├── integration/
│   └── test_golden_path.py
└── unit/
```

## Unit Tests

Unit tests are the fast layer.

They usually:

- mock repositories
- mock collaborating services where needed
- test one service or helper in isolation

Examples:

- classification logic
- rule resolution orchestration
- tariff resolution behavior
- fact normalization
- expression evaluation
- audit reconstruction

## Integration Tests

Integration tests exercise the live FastAPI app and seeded database together.

They do not mock the full stack.

Examples:

- `tests/integration/test_golden_path.py`

Those tests send real HTTP requests to the application through the test client and verify end-to-end outcomes.

## Golden Test Cases

The canonical golden assessment fixtures live in:

- `tests/fixtures/golden_cases.py`

These are the acceptance-style cases used to validate real business outcomes.

They represent realistic:

- products
- corridors
- facts
- expected outcomes

Because `golden_cases.py` is a locked reference file, do not edit it casually.
If you truly need a new golden acceptance case, get explicit review before changing that file.

## How To Add A New Test Case

For normal feature work:

1. add or update a unit test in `tests/unit/`
2. add an integration test in `tests/integration/` if the behavior crosses service or HTTP boundaries
3. if the change needs a new acceptance-style scenario, coordinate before touching `tests/fixtures/golden_cases.py`

When adding a new failure path:

- assert the specific machine-readable failure code
- do not only assert `eligible is False`

## What `@pytest.mark.integration` Means

`@pytest.mark.integration` marks tests that require the integrated application stack and seeded database state.

These tests are slower and more environment-dependent than unit tests.

In AIS, that generally means:

- live FastAPI app
- real database connection
- seeded reference dataset

## Expression Evaluator Safety Test

The expression evaluator includes a safety-focused unit test that checks the source file for disallowed dynamic execution.

It is there to guard against:

- `eval()`
- `exec()`
- standalone `compile()`

This matters because AIS executes rule logic from stored expressions and must do so through a safe parser rather than arbitrary Python execution.

## Coverage Tooling

Coverage is measured with `pytest-cov` against the `app` source tree.
It is not measured against `tests/`, `scripts/`, or Alembic migration files.

Install the dependency (included in the `dev` group):

```bash
python -m pip install -e ".[dev]"
```

### Coverage Commands

**Unit tests with terminal and XML report (no database required):**

```bash
python -m pytest tests/unit -v \
  --cov --cov-report=term-missing --cov-report=xml
```

**Integration tests with terminal and XML report (requires live database and seed data):**

```bash
python -m pytest tests/integration -v \
  --cov --cov-report=term-missing --cov-report=xml
```

**Integration tests with enforced minimum threshold:**

```bash
python -m pytest tests/integration -v \
  --cov --cov-report=term-missing --cov-report=xml --cov-fail-under=60
```

**HTML report for local review:**

```bash
python -m pytest tests/integration -v \
  --cov --cov-report=term-missing --cov-report=html
# report written to artifacts/coverage-html/index.html
```

Report output locations are configured in `pyproject.toml` under `[tool.coverage.xml]`
and `[tool.coverage.html]`.

### Minimum Coverage Threshold

| Scope | Threshold | Applies to |
|---|---|---|
| `app` source tree | **75 %** | Full suite (unit + integration combined) |

The 75 % floor is the measured first-pass baseline for this codebase.
Unit tests alone reach 84 %; 75 % leaves headroom for DB-dependent repository
lines that are only reachable with a live stack.
It is enforced in CI on the integration test job, which is the only job that
runs the complete application stack (live database, migrations, seeded data).

The threshold is **not** enforced on the unit-only job because unit tests
intentionally mock repositories and cannot reach connection-pool,
startup-lifespan, or full-route code paths.

Structural gaps that prevent a higher threshold at this stage:

- `app/main.py` lifespan events and middleware wiring
- `app/db/session.py` async connection-pool setup and teardown
- `app/config.py` pydantic-settings fields not exercised in CI environments
- Repository methods for which no dedicated integration test exists yet
  (for example `sources_repository`, `cases_repository` edge cases,
  `evidence_repository`, and `intelligence_repository` write paths)

Do not raise `fail_under` in `pyproject.toml` until a measured run confirms
the new baseline is sustainable.

### Tracking Coverage Over Time

The XML report at `artifacts/coverage.xml` is uploaded as a GitHub Actions
artifact (`integration-coverage-report`) on every CI run. Use successive
artifact downloads to track whether coverage is trending up or down before
committing to a higher threshold.

## Current Coverage

The suite includes both unit and integration coverage across the assessment engine,
case workflow, evidence readiness, provenance, intelligence, parser tooling, and
the expanded deterministic live slice.

Do not rely on a hard-coded test count in this document. Use the current pytest
output as the source of truth when validating the repository state.

## Continuous Integration

GitHub Actions validates the repository continuously through [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

Current CI stages:

1. `lint`
2. `unit-tests`
3. `integration-tests`
4. `docker-build`

What each stage protects:

- `lint` protects baseline code style and fast static hygiene with `python -m ruff check app tests scripts`
- `unit-tests` protects service logic, helpers, and fast deterministic regressions with `python -m pytest tests/unit -v`
- `integration-tests` protects live API and database behavior by starting PostgreSQL, applying Alembic migrations, seeding deterministic data, and running `python -m pytest tests/integration -v`
- `docker-build` protects the production container artifact by validating `docker build -t afcfta-intelligence:ci .`

CI artifact and report locations:

- `artifacts/unit-tests.xml`
- `artifacts/integration-tests.xml`

Those files are uploaded as workflow artifacts so later coverage or image-validation prompts have stable report paths to extend.

CI assumptions:

- jobs run on `ubuntu-latest`
- integration tests can reach PostgreSQL on `localhost:5432`
- the integration job installs `psycopg2-binary` because `scripts/seed_data.py` uses the sync SQLAlchemy engine path
- no repository secrets are required for the current CI stages

## What New Code Must Be Tested

At minimum:

- every new service method
- every new failure code path
- every schema edge case that can break route validation
- any change to expression evaluation behavior
- any change to audit persistence or replay

If your change affects the deterministic engine output, it should almost always have:

- a focused unit test
- and, when appropriate, a golden-path integration test
