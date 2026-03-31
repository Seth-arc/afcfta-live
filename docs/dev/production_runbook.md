# AIS Production Runbook

Operator reference for deploying, verifying, and rolling back the AfCFTA Intelligence Service.

This document covers what the repository currently supports. It does not document
future infrastructure (external load balancers, Kubernetes, Prometheus exporters) that
does not yet exist.

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Required environment variables](#2-required-environment-variables)
- [Error Tracking](#error-tracking)
- [Scaling to multiple workers](#scaling-to-multiple-workers)
3. [Deployment path](#3-deployment-path)
4. [Post-deploy acceptance checks](#4-post-deploy-acceptance-checks)
5. [Rollback triggers](#5-rollback-triggers)
6. [Rollback steps](#6-rollback-steps)
7. [Parser and tariff-schedule promotion](#7-parser-and-tariff-schedule-promotion)
8. [Before enabling NIM integration](#8-before-enabling-nim-integration)
9. [Before enabling a trader-facing UI](#9-before-enabling-a-trader-facing-ui)
10. [March 30 Gate Status](#10-march-30-gate-status)
11. [Tuning UVICORN_WORKERS](#11-tuning-uvicorn_workers)

---

## 1. Prerequisites

Before you begin:

- CI is green on the commit you are deploying: lint, unit tests, integration tests, and
  docker build all pass on `main`.
- You have SSH or console access to the target host.
- You have taken a manual database backup or confirmed your managed database has a
  recent automated snapshot.
- You have noted the current Alembic migration head **before** starting:

```bash
python -m alembic current
```

Record that revision. You will need it if migration rollback is required.

---

## 2. Required environment variables

The container will exit immediately if any of these three are absent:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy DSN (`postgresql+asyncpg://...`) |
| `API_AUTH_KEY` | Pre-shared API key for all protected endpoints |
| `ENV` | Runtime environment label (`production`, `staging`) |

Additional variables that must be set when using the bundled `db` service from
`docker-compose.prod.yml`:

| Variable | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL superuser password for the `db` container |

If `POSTGRES_PASSWORD` contains reserved URL characters (`%`, `@`, `:`, `/`, `;`),
keep the raw value in `POSTGRES_PASSWORD` and URL-encode that same password inside
`DATABASE_URL`.

Recommended production overrides (all optional, but review each before first deploy):

| Variable | Safe default | Notes |
|---|---|---|
| `DB_POOL_SIZE` | `5` | Connections held open per worker |
| `DB_POOL_MAX_OVERFLOW` | `10` | Burst capacity above pool size |
| `DB_CONNECT_TIMEOUT_SECONDS` | `10` | Tighten to 5 in low-latency environments |
| `DB_COMMAND_TIMEOUT_SECONDS` | `15` | Per-query driver timeout |
| `DB_STATEMENT_TIMEOUT_MS` | `15000` | Server-side statement timeout |
| `DB_LOCK_TIMEOUT_MS` | `5000` | Server-side lock wait timeout |
| `RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS` | `10` | Per-principal, per-60s window; raise for known clients |
| `RATE_LIMIT_DEFAULT_MAX_REQUESTS` | `120` | All other routes |
| `UVICORN_WORKERS` | `1` | Safe baseline until Redis-backed rate limiting is enabled; raise only after `REDIS_URL` is live |
| `CACHE_STATIC_LOOKUPS` | `false` | Enable only after establishing a no-cache baseline |
| `CACHE_STATUS_LOOKUPS` | `false` | Keep disabled in production unless the status dataset is frozen for a controlled perf run |
| `ALLOWED_HOSTS` | _(required)_ | Comma-separated hostnames accepted by `TrustedHostMiddleware`; must be set outside development/test/ci |
| `LOG_LEVEL` | `INFO` | Do not ship `DEBUG` to production |
| `LOG_FORMAT` | `json` | Keep `json` for log aggregation pipelines |

---

## Error Tracking

The supported production error-tracking backend is **Sentry**. The `SENTRY_DSN`
in `.env.prod` applies to the production API deployment and is consumed by
`_configure_error_tracker()` in [app/main.py](../../app/main.py).

Set:

- `ERROR_TRACKING_BACKEND=sentry`
- `SENTRY_DSN=<production-project-dsn>`
- `SENTRY_TRACES_SAMPLE_RATE=0.05`

`SENTRY_TRACES_SAMPLE_RATE=0.05` means 5% transaction trace sampling. Raise it if
you need more distributed-tracing coverage and can absorb the additional event
volume and cost; lower it if trace volume is too high. Exception capture still
depends on the backend being enabled and the DSN being valid.

`sentry-sdk` must be installed separately in the runtime environment. The app
loads it via `importlib.import_module("sentry_sdk")`, so it is an optional runtime
dependency and is intentionally not pinned in `pyproject.toml`.

If the DSN is not yet provisioned, keep `ERROR_TRACKING_BACKEND=none` and leave
the TODO placeholder visible in `.env.prod` until the production Sentry project
is ready.

---

## Scaling to multiple workers

Production default remains `UVICORN_WORKERS=1` until Redis-backed rate limiting
is live and the higher worker count has been validated on the target dataset.

For the March 30, 2026 load/gate harness only, the local rerun target is:

- `REDIS_URL=redis://localhost:6379/0`
- `UVICORN_WORKERS=4`
- `DB_POOL_SIZE=8`
- `DB_POOL_MAX_OVERFLOW=8`
- `CACHE_STATIC_LOOKUPS=true`
- `CACHE_STATUS_LOOKUPS=true`
- `RATE_LIMIT_ENABLED=false`
- `LOG_REQUESTS_ENABLED=false`

The API must stay on a single Uvicorn worker until Redis-backed rate limiting is
active. `_lifespan()` in [app/main.py](../../app/main.py) raises `RuntimeError`
when `UVICORN_WORKERS > 1` and `REDIS_URL` is empty, because `InMemoryRateLimiter`
is per-process and would otherwise multiply the effective request ceiling.

Promotion sequence:

1. Provision a Redis instance for the deployment, or uncomment the `redis` service
   block and the commented `depends_on` entry in [docker-compose.prod.yml](../../docker-compose.prod.yml).
2. Set `REDIS_URL` in `.env.prod`. For the bundled compose service, use
   `redis://redis:6379/0`.
3. Before changing worker count, ensure database pool sizing is adequate:
   `DB_POOL_SIZE + DB_POOL_MAX_OVERFLOW` must accommodate
   `UVICORN_WORKERS × peak concurrent REPEATABLE READ sessions`.
   The March 30 CI/local gate harness uses `DB_POOL_SIZE=8` and
   `DB_POOL_MAX_OVERFLOW=8`.
4. Raise `UVICORN_WORKERS` in `.env.prod` for direct image/runtime parity, and
   raise the `--workers` value in [docker-compose.prod.yml](../../docker-compose.prod.yml)
   from `1` to the tested target.
5. Restart all API workers so the new Redis-backed limiter and worker count take effect.
6. Confirm the startup log line
   `Redis-backed sliding-window rate limiter active`
   appears before declaring the promotion complete.

After step 6, re-run the health and assessment acceptance checks from section 4
before routing higher traffic volume through the multi-worker deployment.

---

## 3. Deployment path

### 3.1 Prepare the env file

```bash
cp ./.env.example ./.env.prod
```

Edit `.env.prod`. Populate all required variables and review the optional ones.
Never commit `.env.prod`.

### 3.2 Run CI locally (optional but recommended for first deploys)

```bash
python -m ruff check app tests scripts
python -m pytest tests/unit -q
python -m pytest tests/integration -q   # requires a live database
```

### 3.3 Build the production image

```bash
docker build -t afcfta-intelligence:prod .
```

The image uses a multi-stage build. The runtime stage runs as a non-root `appuser`.
If the build fails the image is not tagged and the deploy stops here.

### 3.4 Apply database migrations

Migrations must run **before** starting new API workers, not after.

If your database is managed externally (not via `docker-compose.prod.yml`):

```bash
DATABASE_URL_SYNC=postgresql://afcfta:<password>@<host>:5432/afcfta \
  python -m alembic upgrade head
```

If you are using the bundled `db` service, start it first and let it reach healthy,
then run migrations:

```bash
docker compose -f ./docker-compose.prod.yml up -d db
# Wait for db to be healthy:
docker compose -f ./docker-compose.prod.yml ps
DATABASE_URL_SYNC=postgresql://afcfta:<password>@localhost:5432/afcfta \
  python -m alembic upgrade head
```

### 3.5 Seed reference data (first-time deployment only)

On a fresh database, seed the v0.1 reference slice:

```bash
DATABASE_URL_SYNC=postgresql://afcfta:<password>@<host>:5432/afcfta \
  python scripts/seed_data.py
```

Do not re-run seed on an existing populated database. The seed script is idempotent
at the row level for most tables, but running it against a live dataset that has had
parser promotions applied will overwrite those promotion results.

### 3.6 Start the API service

```bash
docker compose -f ./docker-compose.prod.yml up -d api
```

The container will exit immediately if `DATABASE_URL`, `API_AUTH_KEY`, or `ENV` are
missing. Check logs with:

```bash
docker compose -f ./docker-compose.prod.yml logs api
```

### 3.7 Wait for the health check to pass

The container is not marked ready until `GET /api/v1/health/ready` returns 200.
The health check polls every 30 seconds with a 20-second start period:

```bash
docker compose -f ./docker-compose.prod.yml ps
```

Wait until `api` shows `healthy`. If it stays `starting` beyond 90 seconds, check
the logs. Most startup failures are a missing env var or a database connectivity
problem.

---

## 4. Post-deploy acceptance checks

Run these manually after every deploy before routing production traffic.

### 4.1 Liveness

```bash
curl http://localhost:8000/api/v1/health
```

Expected:

```json
{"status": "ok", "version": "0.1.0"}
```

### 4.2 Readiness

```bash
curl http://localhost:8000/api/v1/health/ready
```

Expected: HTTP 200. A non-200 response means the database connection is not working.

### 4.3 Authentication rejection

Requests without a valid key must be rejected:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/rules/110311
```

Expected: `401`. If you receive `200`, authentication is not working.

### 4.4 Authentication acceptance

```bash
curl -H "X-API-Key: <your-api-key>" http://localhost:8000/api/v1/rules/110311?hs_version=HS2017
```

Expected: HTTP 200 with a JSON rule bundle. If you receive `404`, the seeded HS6/PSR
data is missing or the migration did not complete.

### 4.5 Assessment with replay headers

```bash
curl -s -X POST http://localhost:8000/api/v1/assessments \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "hs6_code": "110311",
    "hs_version": "HS2017",
    "exporter": "GHA",
    "importer": "NGA",
    "year": 2025,
    "persona_mode": "exporter",
    "existing_documents": ["certificate_of_origin","bill_of_materials","invoice"],
    "production_facts": [
      {"fact_type":"tariff_heading_input","fact_key":"tariff_heading_input",
       "fact_value_type":"text","fact_value_text":"1001"},
      {"fact_type":"tariff_heading_output","fact_key":"tariff_heading_output",
       "fact_value_type":"text","fact_value_text":"1103"},
      {"fact_type":"direct_transport","fact_key":"direct_transport",
       "fact_value_type":"boolean","fact_value_boolean":true}
    ]
  }' -v 2>&1 | grep -E "eligible|X-AIS"
```

Expected:
- Response body contains `"eligible": true`
- Response headers contain `X-AIS-Case-Id`, `X-AIS-Evaluation-Id`, `X-AIS-Audit-URL`

If `eligible` is false and you supplied the CTH-pass facts above, the seeded rule
or tariff data is missing or incorrectly promoted.

### 4.6 Audit replay

Using the `X-AIS-Evaluation-Id` from step 4.5:

```bash
curl -H "X-API-Key: <your-api-key>" \
  http://localhost:8000/api/v1/audit/evaluations/<evaluation-id>
```

Expected: HTTP 200. The response body must contain `final_decision.eligible`,
`final_decision.provenance`, and `final_decision.provenance.rule.source_id`.

If this returns 404, evaluation persistence is not working.

### 4.7 Rate limiter active

The assessment endpoint defaults to 10 requests per 60-second window per principal.
Send 11 rapid requests and confirm the 11th returns HTTP 429.

```bash
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/v1/assessments \
    -H "X-API-Key: <your-api-key>" \
    -H "Content-Type: application/json" \
    -d '{"hs6_code":"110311","hs_version":"HS2017","exporter":"GHA","importer":"NGA",
         "year":2025,"persona_mode":"exporter","production_facts":[]}'
done
```

Expected: the first 10 return 200 (or 422 for incomplete facts), the 11th returns 429.

### Operator checklist (one-page summary)

```
[ ] GET /api/v1/health                         → 200, {"status":"ok"}
[ ] GET /api/v1/health/ready                   → 200
[ ] GET /rules/110311 without key              → 401
[ ] GET /rules/110311 with key                 → 200, psr_rule present
[ ] POST /assessments (CTH-pass facts)         → 200, eligible=true
[ ] Response headers: X-AIS-Case-Id present    → yes
[ ] Response headers: X-AIS-Evaluation-Id      → yes
[ ] GET /audit/evaluations/{id}                → 200, final_decision.provenance present
[ ] 11th rapid assessment                      → 429
```

All nine checks must pass before routing any traffic.

---

## 5. Rollback triggers

Roll back immediately if any of the following is observed after a deploy:

- `GET /api/v1/health/ready` returns non-200 and does not recover within 2 minutes
- Authenticated requests return 500 on any read endpoint
- `POST /assessments` returns incorrect `eligible` values for a known-good case
  (use the GHA→NGA, HS 110311, CTH-pass smoke test as the reference)
- `GET /audit/evaluations/{id}` returns 404 for an evaluation that was just created
- Database connection errors appear in the API logs
- The migration produced an error and left the schema in a partial state

Do not roll back for:
- A single 429 (rate limiter is working correctly)
- Slow response on first request after startup (pool pre-warming)
- A missing optional env var that does not affect correctness (e.g. `SENTRY_DSN`)

---

## 6. Rollback steps

### 6.1 Stop the new API container

```bash
docker compose -f ./docker-compose.prod.yml stop api
```

Do not remove the container yet. Keep it available for log inspection.

### 6.2 Roll back the migration (if migrations ran)

Check whether the new deploy advanced the migration head:

```bash
python -m alembic current
```

If the head is ahead of the revision you noted in step 1 of the prerequisites,
downgrade one step at a time until you are back to the prior revision:

```bash
DATABASE_URL_SYNC=postgresql://afcfta:<password>@<host>:5432/afcfta \
  python -m alembic downgrade -1
```

Repeat until `alembic current` matches your recorded pre-deploy head.

If the migration failed mid-way and left the schema in an inconsistent state,
restore from the database backup taken before deployment instead of attempting
a partial downgrade.

### 6.3 Restore the previous image

Re-tag the previous known-good image and restart:

```bash
docker tag afcfta-intelligence:<previous-tag> afcfta-intelligence:prod
docker compose -f ./docker-compose.prod.yml up -d api
```

If you do not have the previous image locally, pull it from your registry:

```bash
docker pull <registry>/afcfta-intelligence:<previous-tag>
docker tag <registry>/afcfta-intelligence:<previous-tag> afcfta-intelligence:prod
docker compose -f ./docker-compose.prod.yml up -d api
```

### 6.4 Verify rollback

Run the full operator checklist from section 4 against the restored service.
If the readiness check still fails after rollback, the problem is the database,
not the image. Check the database directly and consider restoring from backup.

### 6.5 Capture diagnostics before cleaning up

Before removing the failed container:

```bash
docker compose -f ./docker-compose.prod.yml logs api > /tmp/ais-failed-deploy.log
```

### 6.6 Migrations with data changes

Some Alembic revisions are schema-only (add/drop a column); these are safe to downgrade with
`alembic downgrade -1` as described above.  Revisions that also **move or transform data** (e.g.
backfilling a column, renaming a foreign key, splitting a table) require extra care:

**Before deploying any data-migration revision:**

1. Review the migration file under `alembic/versions/` for `op.execute(...)` or `INSERT/UPDATE`
   calls in the `upgrade()` function.
2. Confirm that the `downgrade()` function reverses the data change, not just the schema change.
   If it does not, mark the revision as non-reversible in its docstring:
   ```python
   # NOTE: This migration is NOT safely reversible. Downgrade requires restoring from backup.
   ```
3. Take a manual database snapshot **immediately** before running `alembic upgrade head`.

**During rollback of a data-migration revision:**

```bash
# Check what the current head is
python -m alembic current

# Inspect the downgrade() function before running it
python -m alembic show <revision-id>

# If downgrade() is safe, proceed
DATABASE_URL_SYNC=postgresql://afcfta:<password>@<host>:5432/afcfta \
  python -m alembic downgrade -1

# If downgrade() is NOT safe (marked non-reversible above), restore from backup instead:
# 1. Stop the API container (step 6.1)
# 2. Drop and recreate the database from the pre-deploy snapshot
# 3. Restart with the previous image (step 6.3)
```

**After a data-migration rollback, re-run the seeder if reference data was affected:**

```bash
DATABASE_URL_SYNC=postgresql://afcfta:<password>@<host>:5432/afcfta \
  python scripts/seed_data.py
```

Then re-run all acceptance checks in section 4.

---

## 7. Parser and tariff-schedule promotion

A parser or tariff-schedule promotion changes the PSR rule and pathway data that the
engine reads at assessment time. This is a separate operational event from a code
deploy and has its own verification steps.

Full procedure: [docs/dev/parser_promotion_workflow.md](parser_promotion_workflow.md)

Key points for production:

1. Always run a dry-run before promoting:
   ```bash
   python scripts/parsers/psr_db_inserter.py --dry-run
   ```

2. Validate database state after promotion:
   ```bash
   python scripts/parsers/validation_runner.py --scope db
   ```

3. If `CACHE_STATIC_LOOKUPS=true`, restart API workers after promotion so stale cached
   PSR and tariff rows are evicted. The TTL (default 5 minutes) limits the window but
   an explicit restart eliminates it immediately.

4. Re-run the acceptance checks in section 4 after promotion completes.

---

## 8. Before enabling NIM integration

Do not connect a NIM (Natural Intelligence Module) layer to the API until all of the
following are true.

### 8.1 Audit persistence is guaranteed for every assessment

Every `POST /assessments` call — with or without `case_id` in the request body —
must produce a persisted evaluation record and return `X-AIS-Evaluation-Id` in the
response headers. Verify with the smoke test in section 4.5 and confirm the evaluation
is retrievable via step 4.6.

This is currently working: direct assessments auto-create a case and persist the
evaluation.

### 8.2 Assessment contract is stable

The NIM layer will depend on these fields in `POST /assessments` responses:
`eligible`, `pathway_used`, `rule_status`, `tariff_outcome`, `evidence_required`,
`missing_evidence`, `readiness_score`, and `confidence_class`.

Do not rename, remove, or reorder these fields without coordinating with the NIM
prompt set and updating the NIM integration tests.

Use `existing_documents` (not `submitted_documents`) as the document-inventory field.
`submitted_documents` is accepted as an alias but is not the canonical field name.

### 8.3 The `NO_SCHEDULE` gap is closed

Currently, an assessment on a corridor/product/year with no tariff schedule coverage
records `NO_SCHEDULE` as a major issue but does not hard-block pathway evaluation.
The engine should never declare a product eligible when tariff coverage is absent.
Verify the gap is closed before NIM exposure by running an assessment for a supported
corridor with a year that has no seeded tariff data and confirming `eligible: false`.

### 8.4 Rate limits are tuned for the NIM caller volume

The default `RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS=10` per 60-second window is correct
for controlled access but will block any NIM that issues more than 10 assessments per
minute per principal. Set the limit to match the expected NIM throughput or assign a
separate principal with a higher limit.

### 8.5 Assistant input boundary is enforced at the API layer

`AssistantRequest.user_input` is capped at 2000 characters. Requests above that
boundary now fail with HTTP 422 before any NIM call is attempted.

---

## 9. Before enabling a trader-facing UI

Do not route public or trader-facing traffic until all section 8 conditions are met,
plus:

### 9.1 API key rotation is operational

The API key is a single shared secret (`API_AUTH_KEY`). Before public exposure,
confirm you have a process to rotate it without downtime (update `.env.prod` and
restart workers).

### 9.2 Assessment rate limits match expected trader volume

`RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS=10` per 60-second window is the default. Measure
actual peak per-user request rates from any pilot or staging observation and set the
limit explicitly before public launch.

### 9.3 Log aggregation is capturing structured request logs

The API emits JSON-structured request logs with `request_id`,
`authenticated_principal`, `method`, `route`, `status_code`, and `latency_ms`.
Confirm the log pipeline is ingesting those fields before public traffic arrives
so you have a baseline for latency and error-rate alerting.

### 9.4 Assessment responses are verified against golden cases

Run the locked golden corpus through the live API and confirm all 15 cases pass.
The current acceptance slice in `tests/fixtures/golden_cases.py` covers 9 distinct
HS6 products across 6 directed corridors and 9 HS chapters.

```bash
python -m pytest tests/integration/test_golden_path.py -v
```

All 15 must return the expected `eligible` value and `pathway_used`.

### 9.5 Database backup confirmed

Confirm a database backup was taken and the restore procedure has been tested at
least once in staging before accepting trader submissions.

### 9.6 Coverage gaps noted in testing.md are not on the critical path

Review [docs/dev/testing.md](testing.md) for the list of repository paths only
reachable with a live stack that are not yet covered by integration tests.
Confirm none of those paths are exercised by the first trader-facing flows
before enabling public access.

---

## Historical Appendix - Production Gate Stabilisation (2026-03-26)

This section records the verified closure state of the 2026-03-26 production-gate
audit cycle. `docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-26.md` was not present in the
repository, so verification was performed against the audit prompt outputs plus the
final repository state after Prompts 1–7 of the production-gate prompt book.

Historical only. Do not use this appendix as the current March 30 go/no-go
control; use Section 10 and `docs/dev/pre_nim_gate_closure.md` instead.

Use [pre_nim_gate_closure.md](/c:/Users/ssnguna/Local%20Sites/afcfta-live/docs/dev/pre_nim_gate_closure.md)
as the operator checklist for the frozen schema set, required March 26 rerun
commands, published artifact names, and the 48-hour no-schema-change rule.

### 10.1 Gaps closed and prompt ownership

- Prompt 1 — Container startup ambiguity closed.
  Docker now refuses to start without an explicit `UVICORN_WORKERS` value, `.env.example`
  has one `UVICORN_WORKERS` block, and `docker-compose.prod.yml` keeps `--workers 1`
  explicit for the canonical compose entrypoint.
- Prompt 2 — Static-reference cache default closed.
  `CACHE_STATIC_LOOKUPS` now defaults to `true`, the cache correctness integration
  test passed, and parser-promotion invalidation steps are documented.
- Prompt 3 — NIM input boundary closed.
  `parse_user_input()` now rejects oversized input at 2000 characters without
  truncation, returns a structured draft rejection reason to orchestration, and
  keeps NIM-only metadata out of engine requests. On the March 30 head, public
  assistant API calls now fail earlier at schema validation with HTTP 422.
- Prompt 4 — Evidence risk-filter wiring closed.
  `confidence_class` is now threaded into evidence readiness. Because the current
  `verification_question.risk_category` data model is domain-specific rather than
  severity-based, the mapping is an explicit safe stub with a TODO instead of an
  undocumented `None` passthrough.
- Prompt 5 — Golden-case corpus expansion closed.
  The locked corpus now covers 9 distinct HS6 products across 6 directed V01
  corridors, pinned by 15 golden cases spanning 9 HS6 chapters, including the
  added Chapter 62, 09, and 72 scenarios with pass/fail companion cases.
- Prompt 6 — NIM evaluation scaffold closed.
  `tests/nim_eval/` exists, is marked with `@pytest.mark.nim_eval`, passes with a
  mocked client, and is documented for future model-tuning work.
- Prompt 7 — Audit-trail provenance hardening closed.
  Provision summaries with mismatched `source_id` values are logged at `WARNING`
  and omitted from decision traces instead of being silently attached.
- Prompt 8 — Gate validation and reproducibility closed.
  The full gate suite passed, and two seeded integration helpers were hardened to
  allocate unused HS6 fixture codes so repeated gate runs do not fail on unique-key
  collisions.

### 10.2 Gate validation commands and recorded results

Run these commands to reproduce the gate validation:

```bash
python -m pytest tests/unit --cov --cov-report=term-missing
python -m pytest tests/integration --cov --cov-report=term-missing
python -m pytest tests/unit tests/integration --cov --cov-report=term-missing
python -m pytest tests/nim_eval -v -m nim_eval
```

Recorded results for this audit cycle:

- `python -m pytest tests/unit --cov --cov-report=term-missing`
  Result: `538 passed`, `90.28%` total coverage
- `python -m pytest tests/integration --cov --cov-report=term-missing`
  Result: `211 passed`, `86.24%` total coverage
- `python -m pytest tests/unit tests/integration --cov --cov-report=term-missing`
  Result: `749 passed`, `96.72%` total coverage
- `python -m pytest tests/nim_eval -v -m nim_eval`
  Result: `5 passed`

### 10.2A Current March 26 rerun evidence ledger

Record the fresh March 26 rerun here before enabling the next prompt book.

| Gate | Command / comparison | Result | Artifact paths |
|---|---|---|---|
| Unit | `python -m pytest tests/unit --cov --cov-report=term-missing --cov-report=xml:artifacts/unit-coverage.xml` | `544 passed`, `90.14%` total coverage | `artifacts/unit-coverage.xml` |
| Integration | `python -m pytest tests/integration --cov --cov-report=term-missing --cov-report=xml:artifacts/integration-coverage.xml` | `215 passed`, `85.95%` total coverage | `artifacts/integration-coverage.xml` |
| Assistant/NIM | `python -m pytest tests/integration/test_assistant_api.py tests/integration/test_nim_full_flow.py -v --junitxml=artifacts/assistant-nim-tests.xml --cov=app.api.v1.assistant --cov=app.services.nim --cov=app.schemas.nim --cov-report=term-missing --cov-report=xml:artifacts/assistant-nim-coverage.xml` | `50 passed`, `79.46%` total coverage | `artifacts/assistant-nim-tests.xml`, `artifacts/assistant-nim-coverage.xml` |
| Load baseline | `python tests/load/run_load_test.py --mode burst --concurrency 10 --requests 50 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-ci.json` plus `python tests/load/compare_reports.py --baseline tests/load/baseline.json --report artifacts/load-report-ci.json --latency-tolerance-pct 25 --min-success-rate 95` | `PASS` — `50 / 50` successful, `p95 = 0.5930 s`, baseline comparison pass | `artifacts/load-report-ci.json` |
| 100c load | `python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-100.json` plus `python tests/load/compare_reports.py --baseline tests/load/baseline_100c.json --report artifacts/load-report-100.json --latency-tolerance-pct 50 --min-success-rate 95` | `PASS` — `500 / 500` successful, `p95 = 2.1710 s`, baseline comparison pass | `artifacts/load-report-100.json` |

Note: the historical 100c result above predates the current March 30 gate
configuration. It is retained for appendix accuracy only and does not qualify
as current release-gate evidence.

### 10.2B Go / No-Go for the March 26 gate

- `[x]` Schema freeze is active for the contracts listed in `docs/dev/pre_nim_gate_closure.md`
- `[x]` Readiness regression is fixed
- `[x]` Provenance topic filters and aliases are live and test-pinned
- `[x]` Current locked coverage statement is published
- `[x]` All five entries in section 10.2A are marked passed on the March 26 head

The 48-hour no-schema-change soak starts only after every item above is green.
Do not start the soak from partial completion, stale artifacts, or a mixed-head rerun.

### 10.2C Final gate-closure handoff

Status for the March 26, 2026 head: **PASSED / FORMALLY CLEARED**.

Current formal status:

- section 10.2A is fully populated with passing unit, integration, assistant/NIM,
  and load evidence for the March 26 head
- the March 26 gate is now recorded as complete and publishable

Schema freeze start timestamp:

- `2026-03-26T10:32:57.1600046-04:00`

Next allowed prompt book:

- **Decision Renderer** is the next allowed primary prompt book
- **NIM Readiness** is already complete and the freeze is in effect
- **NIM Integration** remains post-readiness follow-on work, not the next primary
  build step

### 10.3 Verified gate checklist

- `[x]` Dockerfile refuses to start when `UVICORN_WORKERS` is not set explicitly
- `[x]` `.env.example` contains exactly one `UVICORN_WORKERS` entry
- `[x]` `docker-compose.prod.yml` overrides `--workers 1` explicitly
- `[x]` Evidence `risk_category` wiring is explicit and documented as a safe stub/TODO
- `[x]` Golden-path tests passed with the evidence change in place
- `[x]` `parse_user_input()` handles input longer than 2000 characters without truncation on internal/direct-call paths
- `[x]` NIM metadata never appears in `EligibilityRequest` after mapping
- `[x]` `nim_rejection_reason` reaches the orchestration layer through the draft
- `[x]` Golden cases cover 6 directed corridors
- `[x]` The locked corpus covers 9 distinct HS6 products
- `[x]` The locked corpus contains 15 golden cases
- `[x]` The corpus includes at least three added HS6 chapters (62, 09, 72)
- `[x]` Provision `source_id` mismatches are logged and excluded from the audit trail
- `[x]` No provision with the wrong `source_id` appears in decision traces
- `[x]` `CACHE_STATIC_LOOKUPS` defaults to `true`
- `[x]` Cached and uncached static lookup paths return identical integration outcomes
- `[x]` Cache invalidation after parser promotion is documented
- `[x]` `tests/nim_eval/` exists and is a valid Python package
- `[x]` `@pytest.mark.nim_eval` tests pass with a mocked `NimClient`
- `[x]` `docs/dev/testing.md` documents the harness

### 10.4 Decision Renderer prerequisite confirmation

Decision Renderer Prompt 1 prerequisites are verified as met:

- NIM readiness book complete
- Assistant-facing contracts pinned by passing integration tests
- NIM input maps to the frozen backend contract and is now length-capped
- Clarification targets real engine gaps
- Explanations cannot contradict deterministic results
- Every assistant-triggered decision is replayable
- NIM failures degrade gracefully

### 10.5 NIM Integration (advanced) prerequisite confirmation

NIM Integration (advanced) Prompt 1 prerequisites are verified as met:

- All 8 backend prerequisite gate items are satisfied by the passing integration suite
- `tests/nim_eval/` is present and ready for Prompt 5 extension
`method`, `route`, `status_code`, and `latency_ms`. Confirm your log pipeline is
ingesting these fields before public traffic arrives so you have a baseline for latency
and error-rate alerting.

### 9.4 Assessment responses are verified against golden cases

Run the locked golden corpus through the live API and confirm all 15 cases pass.
The current acceptance slice in `tests/fixtures/golden_cases.py` covers 9 distinct
HS6 products across 6 directed corridors and 9 HS chapters.

```bash
python -m pytest tests/integration/test_golden_path.py -v
```

All 15 must return the expected `eligible` value and `pathway_used`.

### 9.5 Database backup confirmed

Confirm a database backup was taken and the restore procedure has been tested at least
once in staging before accepting trader submissions.

### 9.6 Coverage gaps noted in testing.md are not on the critical path

Review [docs/dev/testing.md](testing.md) for the list of repository paths only
reachable with a live stack that are not yet covered by integration tests. Confirm
none of those paths are exercised by the first trader-facing flows before enabling
public access.

---

## 10. March 30 Gate Status

This is the current go/no-go control for the March 30, 2026 head.

Use [docs/dev/pre_nim_gate_closure.md](pre_nim_gate_closure.md) as the source of
truth for:

- the frozen schema set
- the canonical rerun command
- the artifact bundle that must be published
- the 48-hour no-schema-change rule

Current March 30 repo state:

- `AGENTS.md` is restored and published at the repo root
- the parser confidence gate is tightened and test-pinned
- published intelligence corridor profiles are explicitly narrowed to the seeded active pairs
- the local/CI gate harness now warms caches and emits `load-report-warmup.json`, `load-report-ci.json`, and `load-report-100.json`
- the 100c gate enforces baseline-relative latency comparison (`+50%` tolerance) and minimum success rate (`>=95%`) without an additional absolute p95 cap
- dirty-worktree verification runs are rejected by default; only clean reruns can start the freeze window
- status-overlay caching is available but remains opt-in and is enabled only for the frozen load/gate harness

What is still pending on March 30:

- a fresh full verification rerun on the current head
- publication of `artifacts/verification/<git-sha>/manifest.json` and the associated XML/JSON reports
- deliberate refresh of `tests/load/baseline.json` and `tests/load/baseline_100c.json` if the accepted rerun becomes the new baseline

Until those three items are complete, do not declare the repo formally cleared
for trader UI work.

---

## 11. Tuning UVICORN_WORKERS

The default production baseline is `UVICORN_WORKERS=1`. Do not raise this value
until the Redis-backed rate-limiter path in [Scaling to multiple workers](#scaling-to-multiple-workers)
is complete. After Redis is active, use this section to validate and tune a higher
worker count with a measured comparison rather than treating `2` as a default.

### 11.1 Run the comparison harness

Before changing `UVICORN_WORKERS` in `.env.prod`, first complete the Redis
enablement steps in [Scaling to multiple workers](#scaling-to-multiple-workers).
Then validate on staging or on the production host before routing live traffic:

1. Start a single-worker instance on port 8001 and a multi-worker instance on
   port 8002 pointing at the same database (see testing.md for exact commands).
2. Run:

```bash
python tests/load/run_multi_worker_comparison.py \
    --single-url http://localhost:8001 \
    --multi-url  http://localhost:8002 \
    --api-key    $AIS_API_KEY \
    --concurrency 50 \
    --requests 200
```

3. Confirm all four acceptance checks pass before promoting the new worker count:

| Check | Required |
|---|---|
| Multi-worker `success_rate_pct` | ≥ 95 % |
| Multi-worker `throughput_rps` | > single-worker |
| Multi-worker p95 latency | ≤ single-worker p95 |
| `pool_pressure` on both instances | not `saturated` |

### 11.2 Pool sizing when raising workers

Each Uvicorn worker holds its own connection pool.  With `UVICORN_WORKERS=4`
and `DB_POOL_SIZE=5`, the API can hold up to 20 simultaneous database
connections.  Confirm your PostgreSQL `max_connections` setting can accommodate
`UVICORN_WORKERS × (DB_POOL_SIZE + DB_POOL_MAX_OVERFLOW)` before deploying.

### 11.3 Apply the change

Once Redis is active and the comparison run passes:

```bash
# Update .env.prod
UVICORN_WORKERS=4   # or whichever value was tested

# Ensure REDIS_URL is set in .env.prod, update docker-compose.prod.yml
# --workers from 1 to the tested value, then restart the API service.
docker compose -f ./docker-compose.prod.yml up -d api
```

Verify the readiness endpoint returns healthy, confirm the startup log line
`Redis-backed sliding-window rate limiter active` appears, and re-run the
operator checklist from section 4.
