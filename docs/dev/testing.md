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

## NIM Evaluation Harness

The mocked NIM regression harness lives in:

- `tests/nim_eval/`

This suite is the lightweight baseline for future NIM prompt tuning, model
rollouts, and parser iterations. It does not require a live NIM endpoint.
Every case uses a mocked `NimClient` response so the harness can run locally,
in CI, or during offline prompt work without network dependencies.

### What it covers now

- parse-shape regression for representative natural-language prompts
- clarification regression for under-specified trade queries
- draft-to-engine mapping invariants, especially stripping NIM-only metadata

### How to run only the NIM eval harness

```bash
python -m pytest tests/nim_eval -v
```

or by marker:

```bash
python -m pytest -m nim_eval -v
```

### How to add a new eval case

1. Start from a supported scenario in `tests/fixtures/golden_cases.py`.
2. Add one dict to `tests/nim_eval/cases.py` with:
   - `name`
   - `user_input`
   - `expected_fields`
   - `expected_clarification`
3. Keep the mocked NIM payload aligned to only the engine-facing draft fields
   the case is asserting.
4. If the case is a clarification case, keep the required trade fields `None`
   so the harness proves the clarification gate still triggers.

### How to use it during model tuning

Use this harness before and after any NIM parser or prompt change.

- If a complete-parse case regresses, the draft schema or prompt behavior drifted.
- If a clarification case stops returning empty required fields, the intake gate
  may be letting ambiguous queries through.
- If NIM-only metadata appears in the mapped request body, the deterministic
  engine boundary has been violated.

This harness is intentionally narrower than the full assistant integration
tests. It is the fast regression baseline for mocked parser behavior, while
`tests/integration/test_assistant_api.py` and
`tests/integration/test_nim_full_flow.py` remain the contract tests for the
live assistant path.

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
4. `load-baseline`
5. `docker-build`

What each stage protects:

- `lint` protects baseline code style and fast static hygiene with `python -m ruff check app tests scripts`
- `unit-tests` protects service logic, helpers, and fast deterministic regressions with `python -m pytest tests/unit -v`
- `integration-tests` protects live API and database behavior by starting PostgreSQL, applying Alembic migrations, seeding deterministic data, and running `python -m pytest tests/integration -v`
- `load-baseline` protects against performance regressions by running a small burst load test and comparing results against a committed baseline
- `docker-build` protects the production container artifact by validating `docker build -t afcfta-intelligence:ci .`

CI artifact and report locations:

- `artifacts/unit-tests.xml`
- `artifacts/integration-tests.xml`
- `artifacts/load-report-ci.json`

Those files are uploaded as workflow artifacts so later coverage or image-validation prompts have stable report paths to extend.

CI assumptions:

- jobs run on `ubuntu-latest`
- integration tests can reach PostgreSQL on `localhost:5432`
- the integration job installs `psycopg2-binary` because `scripts/seed_data.py` uses the sync SQLAlchemy engine path
- no repository secrets are required for the current CI stages

## Load Baseline

The `load-baseline` CI job detects performance regressions on every push and pull request.

### What it does

1. Starts PostgreSQL, applies migrations, and seeds reference data.
2. Starts the FastAPI app with `uvicorn` and `RATE_LIMIT_ENABLED=false`.
3. Runs a small burst: `--concurrency 10 --requests 50`.
4. Compares the resulting `artifacts/load-report-ci.json` against the committed baseline at `tests/load/baseline.json` using `tests/load/compare_reports.py`.

### Comparison metrics and tolerances

| Metric | Check | Default tolerance |
|---|---|---|
| `metrics.latency_s.p95` | Must not exceed `baseline_p95 × 1.25` | 25% increase |
| `metrics.success_rate_pct` | Must be ≥ 95% | fixed floor |

The job fails if either check fails. The CI report is uploaded as the `load-baseline-report` artifact on every run.

### How to update the baseline

Only update the baseline when a deliberate change — new query, schema migration, middleware addition — is expected to shift performance.

**Steps:**

1. Run the CI-scale burst locally against your running stack:

```bash
python tests/load/run_load_test.py \
  --mode burst \
  --concurrency 10 \
  --requests 50 \
  --api-key $AIS_API_KEY \
  --report artifacts/load-report-ci.json
```

2. Verify the new numbers are intentional (not a bug):

```bash
python tests/load/compare_reports.py \
  --baseline tests/load/baseline.json \
  --report artifacts/load-report-ci.json
```

3. Promote the report to the new baseline:

```bash
cp artifacts/load-report-ci.json tests/load/baseline.json
git add tests/load/baseline.json
git commit -m "chore: update load baseline after <reason>"
```

Alternatively, download the `load-baseline-report` artifact from a passing CI run and use that as the new baseline — it reflects GitHub Actions runner performance rather than local performance.

### First-run note

The committed `tests/load/baseline.json` uses a conservative p95 of 2.0 s to avoid false positives on the first CI run. After the first successful CI run, download the `load-baseline-report` artifact and promote it as described above to tighten the baseline to actual measured CI performance.

## Load Testing

The load test harness lives in [`tests/load/`](../../tests/load/).
It is a standalone Python script, not a pytest test, and requires no
special infrastructure beyond a running AIS stack.  No new dependencies
are needed — stdlib `asyncio` and `httpx` are sufficient.

### Modes

The harness supports two modes selected with `--mode`:

| Mode | Behaviour |
|---|---|
| `burst` | All workers launch simultaneously.  Controlled by `--concurrency` and `--requests`. Default. |
| `ramp` | Concurrency increases in discrete steps.  Each step runs for a fixed wall-clock window.  Controlled by `--ramp-stages` and `--ramp-stage-duration`. |

### Scenario: burst (sustained-concurrent)

| Parameter | Default |
|---|---|
| Endpoint | `POST /api/v1/assessments` |
| Payloads | 5 deterministic fixtures (round-robin): GHA→NGA CTH, CMR→NGA VNM pass, CIV→NGA WO, SEN→NGA VNM, CMR→NGA VNM fail |
| Concurrency | 50 simultaneous workers |
| Total requests | 200 |
| Per-request timeout | 30 s |
| Success threshold | 95 % (2xx responses) |

### Scenario: ramp

| Parameter | Default |
|---|---|
| Endpoint | `POST /api/v1/assessments` |
| Payloads | same 5 deterministic fixtures (round-robin) |
| Stage concurrency levels | `10,25,50` |
| Duration per stage | 20 s |
| Per-request timeout | 30 s |
| Success threshold | 95 % overall across all stages |

The ramp scenario increases concurrency across three stages: 10 → 25 → 50
concurrent workers.  Each stage runs for the configured duration, then the
next stage starts immediately.  A single `httpx.AsyncClient` is shared across
stages so the connection pool reflects steady-state server behaviour rather
than cold-start per stage.

All payloads match seeded HS6/corridor combinations in the deterministic
seed slice.  The harness never generates random data.

### Prerequisites

```bash
# Stack must be running with migrations and seed data applied.
docker compose up -d
python -m alembic upgrade head
python scripts/seed_data.py

# Disable the in-process rate limiter — the default is 10 reqs/60 s,
# which would rate-limit most of a 200-request run before it completes.
export RATE_LIMIT_ENABLED=false

# Supply credentials.
export AIS_API_KEY=your-local-dev-api-key
```

### Running

```bash
# Burst defaults: 50 concurrent, 200 total, http://localhost:8000
python tests/load/run_load_test.py

# Burst: explicit scale
python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500

# Ramp defaults: 10→25→50 concurrent, 20 s per stage
python tests/load/run_load_test.py --mode ramp

# Ramp: custom stages and duration
python tests/load/run_load_test.py --mode ramp \
  --ramp-stages 5,10,20,50 --ramp-stage-duration 30

# Against staging with explicit credentials
python tests/load/run_load_test.py --mode ramp \
  --url https://ais-staging.example.com \
  --api-key $STAGING_API_KEY \
  --ramp-stages 10,25,50 --ramp-stage-duration 20
```

### CLI flags

| Flag | Mode | Default | Description |
|---|---|---|---|
| `--mode` | both | `burst` | `burst` or `ramp` |
| `--url` | both | `$AIS_BASE_URL` or `http://localhost:8000` | Base URL |
| `--api-key` | both | `$AIS_API_KEY` | API key |
| `--auth-header` | both | `X-API-Key` | Header name for the key |
| `--timeout` | both | `30` | Per-request timeout in seconds |
| `--report` | both | `artifacts/load-report.json` | Output path |
| `--fail-under` | both | `95` | Minimum overall success-rate % to exit 0 |
| `--concurrency` | burst | `50` | Max simultaneous workers |
| `--requests` | burst | `200` | Total request count |
| `--ramp-stages` | ramp | `10,25,50` | Comma-separated concurrency levels |
| `--ramp-stage-duration` | ramp | `20` | Seconds per stage |

### Metrics captured

#### Burst and aggregate (both modes)

| Metric | Description |
|---|---|
| `successful_2xx` | Count and percentage of HTTP 200 responses |
| `rate_limited_429` | Count of HTTP 429 responses |
| `network_errors` | Count of connection/timeout failures |
| `wall_elapsed_s` | Total wall-clock duration |
| `throughput_rps` | Effective requests per second |
| `latency_s.min/p50/p75/p95/p99/max` | Latency distribution for successful requests only |

#### Per stage (ramp mode only)

Each entry in the `stages` array of the JSON report adds:

| Field | Description |
|---|---|
| `stage` | 1-based stage number |
| `concurrency` | Target concurrency for this stage |
| `duration_target_s` | Configured stage window |
| All metrics above | Computed from requests that completed during this stage |

The `stages` key is absent from burst-mode reports.

### JSON report structure

Burst:
```json
{
  "config": { "mode": "burst", "concurrency": 50, "total_requests": 200, ... },
  "mode": "burst",
  "metrics": { "successful_2xx": ..., "latency_s": { "p95": ... }, ... }
}
```

Ramp:
```json
{
  "config": { "mode": "ramp", "ramp_stages": [10, 25, 50], "ramp_stage_duration_s": 20, ... },
  "mode": "ramp",
  "metrics": { "scenario": "ramp-aggregate", "successful_2xx": ..., "latency_s": { ... }, ... },
  "stages": [
    { "stage": 1, "concurrency": 10, "duration_target_s": 20, "successful_2xx": ..., "latency_s": { "p95": ... }, ... },
    { "stage": 2, "concurrency": 25, "duration_target_s": 20, "successful_2xx": ..., "latency_s": { "p95": ... }, ... },
    { "stage": 3, "concurrency": 50, "duration_target_s": 20, "successful_2xx": ..., "latency_s": { "p95": ... }, ... }
  ]
}
```

### Interpreting results

- A 429-heavy run means `RATE_LIMIT_ENABLED=false` was not set, or the
  `RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS` limit was too low.  This is not a
  capacity signal — it is a configuration signal.  The harness warns loudly
  when more than 10 % of requests are rate-limited.
- p95 latency above 500 ms at 50 concurrent workers suggests the connection
  pool or worker count needs tuning.
- In ramp mode, compare `p95` and `success_rate_pct` across stages to identify
  the concurrency level where latency degrades or errors begin.  A clean ramp
  should show roughly constant p95 until pool or process limits are reached.
- If `success_rate_pct` falls below `--fail-under` (default 95) the script
  exits with code 1, making it usable as a staging gate.

### Watching pool saturation during a load run

Poll `GET /api/v1/health/ready` with your API key during or after a load run
to read the `pool_stats` block:

```bash
curl -s -H "X-API-Key: $AIS_API_KEY" http://localhost:8000/api/v1/health/ready \
  | python -m json.tool
```

Key fields in `pool_stats`:

| Field | What it tells you |
|---|---|
| `checked_out` | Connections currently in use by active requests |
| `pool_size` | Configured steady-state pool capacity (`DB_POOL_SIZE`) |
| `overflow` | Connections using the overflow buffer beyond `pool_size` |
| `checked_in` | Idle connections currently sitting in the pool |
| `pool_pressure` | `"ok"` / `"elevated"` / `"saturated"` (see below) |

Pressure thresholds (based on `checked_out / pool_size`):

| Value | Threshold | Action |
|---|---|---|
| `ok` | < 75 % | Normal — no action needed |
| `elevated` | ≥ 75 % | Consider increasing `DB_POOL_SIZE` or `UVICORN_WORKERS` |
| `saturated` | ≥ 95 % | Pool is at capacity — requests are queuing for connections |

If `pool_pressure` is `saturated` and p95 latency is high, the bottleneck
is the connection pool, not the application logic.  Increase `DB_POOL_SIZE`
(and `DB_POOL_MAX_OVERFLOW`) or add Uvicorn workers before scaling load further.

### Multi-worker comparison

`tests/load/run_multi_worker_comparison.py` measures the throughput difference
between a single-worker and a multi-worker server by running the burst scenario
against two separately started instances and printing a side-by-side report.

**The script does not start or stop server processes.**
Start both servers before running it.

#### Step 1 — start the two servers (two terminal windows, same database)

**Terminal A — single worker (port 8001):**

```bash
# Copy your prod env and override worker count and port
cp .env.prod .env.single
# Edit .env.single: set RATE_LIMIT_ENABLED=false
UVICORN_WORKERS=1 DATABASE_URL="postgresql+asyncpg://afcfta:<password>@localhost:5432/afcfta" \
  ENV=development API_AUTH_KEY=$AIS_API_KEY \
  uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1
```

**Terminal B — multi-worker (port 8002):**

```bash
UVICORN_WORKERS=4 DATABASE_URL="postgresql+asyncpg://afcfta:<password>@localhost:5432/afcfta" \
  ENV=development API_AUTH_KEY=$AIS_API_KEY \
  RATE_LIMIT_ENABLED=false \
  uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 4
```

Both servers share the same database.  The DB connection pool is per-worker,
so 4 workers × `DB_POOL_SIZE=5` = up to 20 simultaneous DB connections.
Set `DB_POOL_SIZE` and `DB_POOL_MAX_OVERFLOW` accordingly before running.

#### Step 2 — run the comparison

```bash
python tests/load/run_multi_worker_comparison.py \
    --single-url http://localhost:8001 \
    --multi-url  http://localhost:8002 \
    --api-key    $AIS_API_KEY \
    --concurrency 50 \
    --requests 200
```

Report is written to `artifacts/multi-worker-comparison.json`.

#### Expected outcome and acceptance bar

Linear throughput scaling (2× workers → 2× RPS) is unlikely because:

- The database connection pool is the shared bottleneck.  Each worker holds
  its own pool, but all pools share the same PostgreSQL instance.
- Uvicorn's async workers handle I/O concurrency well within a single process;
  adding workers mainly helps CPU-bound work and independent event-loop tasks.
- At low concurrency levels the single worker may already be mostly idle,
  leaving little headroom for multi-worker gains.

**Acceptance bar before raising `UVICORN_WORKERS` in production:**

| Check | Required result |
|---|---|
| Multi-worker `success_rate_pct` | ≥ 95 % |
| Multi-worker throughput (`throughput_rps`) | > single-worker throughput |
| Multi-worker p95 latency | ≤ single-worker p95 (multi-worker should not be slower) |
| `pool_pressure` on both servers | not `saturated` during the run |

If multi-worker throughput is not meaningfully higher than single-worker,
the bottleneck is the database or network, not worker count.  Address pool
tuning (`DB_POOL_SIZE`, `DB_POOL_MAX_OVERFLOW`) or query performance first.

Do not raise `UVICORN_WORKERS` in production without a comparison run that
passes all four checks above.

### What still needs true performance infrastructure

The harness is intentionally minimal — stdlib `asyncio` + `httpx`.
Before a trader-facing deployment, supplement it with:

| Gap | Tooling to add |
|---|---|
| Latency percentile tracking across multiple runs | Grafana + Prometheus or Datadog |
| DB pool saturation signal | `pg_stat_activity` metrics exported via Postgres exporter |
| Multi-worker concurrency | Run from separate machines or use a distributed load tool |
| Baseline comparison | Store `load-report.json` as a CI artifact and diff p95 between runs |

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
