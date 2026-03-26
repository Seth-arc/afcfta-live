# AfCFTA Live Post-Audit Hardening Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run yourself. Do not skip ahead.
>
> **Start this book only after completing the Production Gate Stabilisation book**.
> All Production Gate exit criteria must be satisfied before Prompt 1 here.
>
> **Your AGENTS.md shell restriction still applies**: the coding agent creates and
> edits files; you run the commands yourself.
>
> **Primary references**:
> - docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-26.md (audit findings this book closes)
> - docs/dev/Production Gate — Vibecoding Prompts.md (completed prerequisite)
> - docs/dev/Decision Renderer — Vibecoding Prompts (2).md (next book after this one)
> - AGENTS.md for architecture invariants, shell restrictions, and locked scope
>
> **Targets covered**:
> 1. Resolve the inoperative `_CONFIDENCE_TO_RISK` mapping so evidence risk-category
>    filtering works correctly
> 2. Set `CORS_ALLOW_ORIGINS` so browser-based trader UI connections are not blocked
> 3. Add a Prometheus `/metrics` endpoint for production observability
> 4. Add an integration test proving assessments write retrievable alert rows
> 5. Configure Sentry error tracking in the production environment
> 6. Document and validate the Redis multi-worker upgrade path

---

## Goal

Close the remaining code-level and operational gaps identified in the 2026-03-26 repo
audit that were not blocking NIM integration but are required before the Decision
Renderer is delivered to traders or before a multi-worker production deployment is
considered stable.

## Non-goals

- Do not change the deterministic eligibility engine.
- Do not change any frozen assessment, audit, or assistant schema.
- Do not expand corridor or HS6 scope beyond V01.
- Do not start Decision Renderer or NIM Integration work in this book.
- Do not re-open architecture decisions already settled by the Production Gate book.

## Working Rules

1. Read every cited file before editing. These prompts are targeted fixes; do not
   rework surrounding code that is not in scope.
2. Prompts 1 and 4 are code changes. Add a regression test for each fix so the gap
   cannot silently return.
3. Prompt 3 introduces a new Python dependency. Justify it in `pyproject.toml` and
   document it in `.env.example`.
4. Prompts 2, 5, and 6 are operational configuration changes. Do not edit any Python
   source files in those prompts.
5. When adding any configuration key, update `app/config.py`, `.env.example`, and
   `docs/dev/setup.md` in the same change.

## Definition Of Done Per Prompt

A prompt is only complete when all of the following are true:

1. The specific gap it closes is no longer reproducible.
2. A regression test or CI gate prevents the gap from silently returning (code prompts
   only).
3. Any affected docs reflect the corrected state.
4. The required summary can cite the exact files changed and tests added.

## Prompt Status

| Prompt | Status | Completed |
|---|---|---|
| 1 | [ ] Pending | — |
| 2 | [ ] Pending | — |
| 3 | [ ] Pending | — |
| 4 | [ ] Pending | — |
| 5 | [ ] Pending | — |
| 6 | [ ] Pending | — |

## Cross-Cutting Implementation Notes

- Do not change any frozen schema (`app/schemas/assessments.py`, `app/schemas/audit.py`,
  `app/schemas/nim/`) during this book.
- Preserve all existing `request_id` correlation, auth, and rate-limiting behaviour when
  editing any middleware, startup, or config path.
- Keep the deterministic assessment engine and its audit persistence path completely
  isolated from any new infrastructure change.
- Do not introduce new Python dependencies unless a prompt explicitly justifies one.

---

## Prompt 1 — Map confidence classes to evidence risk categories

```
Read:
- app/services/evidence_service.py (full file — focus on _CONFIDENCE_TO_RISK at line 13)
- app/repositories/evidence_repository.py
- app/db/models/evidence.py
- scripts/sql/seed_evidence_requirements.sql
- tests/unit/test_evidence_service.py

The _CONFIDENCE_TO_RISK dict maps all four confidence classes to None. This means
verification question filtering by risk_category is silently inoperative: all
questions are returned regardless of the confidence class supplied by the caller.
The TODO comment at line 8 of evidence_service.py acknowledges this and describes
exactly what is needed.

Fix the mapping so verification questions are filtered against the actual
risk_category values stored in the verification_question table.

Work in these files first:
- app/services/evidence_service.py
- tests/unit/test_evidence_service.py

Requirements:
1. Inspect the verification_question rows in the seed SQL (scripts/sql/seed_evidence_requirements.sql)
   to discover the distinct risk_category values in use.
2. Map each confidence_class to the appropriate DB value:
   - "complete"      → None  (all questions apply; no category filtering)
   - "incomplete"    → the category covering documentary gap scenarios
   - "insufficient"  → the category covering origin claim scenarios
   - "provisional"   → None  (provisional is a rule-level flag, not a risk severity)
   If the seeded categories differ from the above description, use what is actually in
   the seed SQL and document the mapping in a comment directly above the dict.
3. Remove the TODO comment once the mapping is populated.
4. Do not change the signature of build_readiness() or get_readiness().
5. Do not change any other service, schema, or repository file.
6. Add or strengthen unit tests in test_evidence_service.py:
   - assert that "complete" produces no risk_category filter (get_verification_questions
     called with risk_category=None)
   - assert that "incomplete" and "insufficient" each produce the correct non-None
     risk_category value
   - assert that questions whose risk_category does not match the resolved category
     are excluded from the returned verification_questions list

When done, summarize:
- the actual risk_category values found in the seed SQL
- the mapping applied for each confidence_class
- the test cases added
```

**You run:**
```bash
python -m pytest tests/unit/test_evidence_service.py -v
```
## Completed 26 March
---

## Prompt 2 — Set CORS_ALLOW_ORIGINS for the trader UI

```
Read:
- app/main.py (CORS middleware block in create_app)
- app/config.py (CORS_ALLOW_ORIGINS setting)
- .env.example (CORS section near the bottom)
- .env.prod
- docs/dev/setup.md

CORS_ALLOW_ORIGINS defaults to empty (disabled). This is intentionally correct for
pure server-to-server access (NIM integration, audit replays), but the Decision
Renderer and any browser-based trader UI require the header to be present before a
single cross-origin browser request will succeed. Configure the production CORS policy
now so it is not an ops surprise when the Decision Renderer team connects.

This is an operational configuration prompt. Do not change any Python source files.

Work in these files first:
- .env.prod
- .env.example (strengthen the comment in the CORS section)
- docs/dev/setup.md

Requirements:
1. In .env.prod, set CORS_ALLOW_ORIGINS to the staging and production Decision
   Renderer origins as a comma-separated list. If the exact origins are not yet known,
   add a clearly-marked placeholder comment and set the value to the local dev origin
   (http://localhost:3000) so the config key is explicit and not overlooked before
   the Decision Renderer work begins.
2. In .env.example, add a concrete example in the CORS comment block that:
   - shows the Decision Renderer origin format
   - explicitly forbids the use of * in production (the existing text already says
     this; keep it and add the example beneath)
3. In docs/dev/setup.md, add a short "CORS and browser clients" section that names
   the origins that must be added before Decision Renderer development begins and
   references app/config.py and .env.example for the full documentation.
4. Do not change app/main.py or app/config.py — the middleware is already correctly
   wired and needs no modification.

When done, summarize:
- the origins set in .env.prod (real or placeholder)
- the .env.example example line added
- the setup.md section title and location
```

**You run:**
```bash
grep -n "CORS_ALLOW_ORIGINS" .env.prod .env.example docs/dev/setup.md
```
## Completed 26 March
---

## Prompt 3 — Add a Prometheus /metrics endpoint

```
Read:
- app/main.py (full file — create_app and _lifespan)
- app/config.py
- app/api/router.py
- app/api/v1/health.py
- .env.example
- pyproject.toml
- .github/workflows/ci.yml

There is no /metrics endpoint. Assessment throughput, latency distributions, and
error rates are only visible through log aggregation. Add a Prometheus-compatible
metrics endpoint so production operators can scrape directly into Grafana without
requiring a log pipeline.

Work in these files first:
- pyproject.toml
- app/config.py
- app/main.py
- app/api/router.py (only if route exclusion from auth is needed at the router level)
- .env.example
- docs/dev/setup.md

Requirements:
1. Add prometheus-fastapi-instrumentator to the dependencies list in pyproject.toml.
2. Add a METRICS_ENABLED setting (bool, default False) to app/config.py. Keep it off
   by default so existing deployments are unaffected.
3. In create_app(), when METRICS_ENABLED is True, initialise the instrumentator and
   expose /metrics. The endpoint must NOT require API key authentication — Prometheus
   scrapers do not send auth headers. Register it before the protected_router so auth
   middleware does not intercept it.
4. When METRICS_ENABLED is False, the /metrics path must return 404. Do not mount the
   instrumentator at all in this case so the endpoint is not silently reachable.
5. The instrumentator must expose at minimum:
   - http_request_duration_seconds (latency histogram by route and status code)
   - http_requests_total (counter by method, route, and status code)
6. Add a unit test (no DB required) that:
   - confirms GET /metrics returns 404 when METRICS_ENABLED=false
   - confirms GET /metrics returns 200 with Content-Type starting with "text/plain"
     when METRICS_ENABLED=true
7. Add METRICS_ENABLED to .env.example with a comment that explains the scraper model
   and references the /metrics path.
8. Add a "Metrics and observability" section to docs/dev/setup.md that documents the
   endpoint path, how to enable it, and the recommended Prometheus scrape config.

When done, summarize:
- the dependency added and its version constraint
- the config key, default, and the create_app registration logic
- the route registration approach and how auth bypass is achieved
- the tests added
```

**You run:**
```bash
python -m pytest tests/unit/ -v -k "metrics"
# With the stack running:
METRICS_ENABLED=true uvicorn app.main:app --reload &
curl -s http://localhost:8000/metrics | head -30
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/ready
```
## Completed 26 March
---

## Prompt 4 — Add an integration test for intelligence alert generation

```
Read:
- app/services/eligibility_service.py (_emit_alerts_if_possible and the call site
  at the end of assess())
- app/services/intelligence_service.py
- app/repositories/intelligence_repository.py
- app/api/v1/intelligence.py
- app/schemas/intelligence.py (AlertEventOut)
- tests/integration/test_intelligence_api.py
- tests/integration/test_golden_path.py (fixture seeding pattern)
- tests/integration/conftest.py

_emit_alerts_if_possible is called at the end of every completed assessment. There
is no integration test that proves a completed assessment writes an alert row that is
then retrievable via GET /intelligence/alerts. This gap means the alert emission path
could silently break without any test failing.

Add an integration test that closes this gap.

Work in these files first:
- tests/integration/test_intelligence_api.py

Requirements:
1. Add one integration test function that:
   a. Seeds the minimum reference data (HS6 product, PSR rule, tariff schedule, source
      registry row) needed to run a complete assessment for one supported corridor.
      Use the fixture seeding helpers from test_golden_path.py where they exist.
   b. Posts a direct assessment to POST /api/v1/assessments and asserts HTTP 200.
   c. Calls GET /api/v1/intelligence/alerts and asserts that at least one alert row
      is present for the entity_key that corresponds to the assessed corridor.
   d. Asserts that the returned alert row contains at minimum the fields: entity_type,
      entity_key, severity, and status, matching the AlertEventOut schema.
2. If _emit_alerts_if_possible only writes alert rows under specific trigger conditions
   (e.g. rule_status is "provisional", tariff is missing, or corridor overlay is
   active), seed the fixture to trigger that condition and document the exact trigger
   in the test docstring so future maintainers understand why the fixture is structured
   as it is.
3. If the service does not currently write any alert rows for the seeded scenario after
   inspection, document the gap in the test as a skipped test with a clear skip reason
   rather than asserting on an empty list — do not silently pass on an empty result.
4. Do not modify intelligence_service.py, eligibility_service.py, or any repository.
5. Mark the test with pytest.mark.integration.
6. Follow the ORM seeding pattern from test_golden_path.py (session.add / await
   session.flush) rather than raw SQL inserts.

When done, summarize:
- the trigger condition used (what causes _emit_alerts_if_possible to write a row)
- the fixture corridor and HS6 code used
- the assertion made on the returned alert row shape
- whether the test passes, skips, or reveals a genuine gap in the emission path
```

**You run:**
```bash
python -m pytest tests/integration/test_intelligence_api.py -v
```
## Completed 26 March
---

## Prompt 5 — Configure Sentry error tracking for production

```
Read:
- app/main.py (_configure_error_tracker — full function)
- app/config.py (ERROR_TRACKING_BACKEND, SENTRY_DSN, SENTRY_TRACES_SAMPLE_RATE)
- .env.example (Optional External Error Tracking section)
- .env.prod
- docs/dev/production_runbook.md

The Sentry integration seam is fully wired: _configure_error_tracker in app/main.py
initialises the SDK and attaches capture_exception to the unhandled-exception handler.
In production today ERROR_TRACKING_BACKEND=none means every 500 is only visible in
structured logs. Configure the production environment so that unhandled exceptions are
captured automatically.

This is an operational configuration prompt. Do not change any Python source files.

Work in these files first:
- .env.prod
- docs/dev/production_runbook.md

Requirements:
1. In .env.prod, set:
   - ERROR_TRACKING_BACKEND=sentry
   - SENTRY_DSN=<your-project-dsn>
   - SENTRY_TRACES_SAMPLE_RATE=0.05  (5% trace sampling; adjust for cost and volume)
   If the DSN is not yet provisioned, add a clearly-marked TODO placeholder and set
   ERROR_TRACKING_BACKEND=none with a comment so the gap is visible and not lost.
2. In docs/dev/production_runbook.md, add a section "Error Tracking" that:
   - names the backend (Sentry)
   - states which environment the DSN applies to
   - states the traces sample rate and how to adjust it
   - notes that sentry-sdk must be installed separately (it is an optional import
     via importlib; it is not in pyproject.toml dependencies)
   - links to _configure_error_tracker in app/main.py as the implementation reference
3. Do not add sentry-sdk to pyproject.toml. The integration uses importlib.import_module
   so the SDK is an optional runtime dependency, not a build-time one.
4. Do not change app/main.py or app/config.py.

When done, summarize:
- whether a real DSN or a documented placeholder was written to .env.prod
- the SENTRY_TRACES_SAMPLE_RATE configured
- the production_runbook.md section title and content summary
```

**You run:**
```bash
grep -n "SENTRY\|ERROR_TRACKING" .env.prod docs/dev/production_runbook.md
```

---

## Prompt 6 — Document and validate the Redis multi-worker upgrade path

```
Read:
- app/main.py (_lifespan — Redis startup guard and fallback warning)
- app/config.py (REDIS_URL, UVICORN_WORKERS)
- app/api/deps.py (InMemoryRateLimiter, RedisRateLimiter)
- .env.example (Redis section)
- .env.prod
- docker-compose.prod.yml
- docs/dev/production_runbook.md
- docs/dev/setup.md

The Redis multi-worker path is fully implemented and guarded. The startup guard in
_lifespan raises RuntimeError if UVICORN_WORKERS > 1 and REDIS_URL is empty. There
is no Redis service definition in docker-compose.prod.yml and the production runbook
does not document the exact steps to promote from single-worker to multi-worker.

Make the upgrade path explicit and operator-safe.

This is an operational configuration prompt. Do not change any Python source files.

Work in these files first:
- docker-compose.prod.yml
- .env.prod
- .env.example (confirm the Redis constraint comment is clear; edit only if unclear)
- docs/dev/production_runbook.md

Requirements:
1. In docker-compose.prod.yml, add a commented-out Redis service block using the
   official redis:7-alpine image. The block must be clearly labelled as the service
   to uncomment when promoting to multiple workers. Add a commented-out depends_on
   reference from the API service to the Redis service so the dependency is obvious.
2. In .env.prod, add a commented-out REDIS_URL entry pointing at the compose service
   hostname (redis://redis:6379/0) with a note that it must be uncommented together
   with the redis service block in docker-compose.prod.yml and UVICORN_WORKERS
   raised from 1.
3. In .env.example, verify the Redis section already explains the InMemoryRateLimiter
   constraint and the per-process bucket risk. If it is already correct, record in
   the summary that no change was needed.
4. In docs/dev/production_runbook.md, add a section "Scaling to multiple workers"
   that documents the exact promotion steps:
   a. Provision a Redis instance or uncomment the compose service.
   b. Set REDIS_URL in .env.prod.
   c. Raise UVICORN_WORKERS in .env.prod and docker-compose.prod.yml.
   d. Restart all workers.
   e. Confirm the startup log line "Redis-backed sliding-window rate limiter active"
      appears before declaring the promotion complete.
   f. Note the DB connection pool sizing requirement: DB_POOL_SIZE + DB_POOL_MAX_OVERFLOW
      must accommodate UVICORN_WORKERS × peak concurrent REPEATABLE READ sessions
      (the CI load baseline uses DB_POOL_SIZE=20 / MAX_OVERFLOW=80 for 100c).
5. Do not change any Python source files.

When done, summarize:
- the docker-compose.prod.yml Redis block added
- the .env.prod entry added or confirmed as already present
- whether .env.example needed changes
- the production_runbook.md section title and the six-step promotion sequence
```

**You run:**
```bash
docker compose -f docker-compose.prod.yml config
grep -n "REDIS\|UVICORN_WORKERS" .env.prod .env.example docs/dev/production_runbook.md
```

---

## Recommended Execution Groups

### Group 1 — Code fixes with regression tests

Prompts 1 and 4

These are the only prompts that change source code or tests. Run both test suites
together before moving to configuration work. Neither prompt depends on the other.

### Group 2 — Observability

Prompt 3

Run after Group 1 is clean. Introduces the only new Python dependency in this book.
Verify the unit test passes before moving to operational prompts.

### Group 3 — Operational configuration

Prompts 2, 5, and 6

No code changes. All three edit `.env.prod` and docs. Work through them in order or
in parallel — they are independent of each other. All require `.env.prod` to be
accessible.

---

## Exit Criteria

This prompt book is complete only when all of the following are true:

- `_CONFIDENCE_TO_RISK` maps `incomplete` and `insufficient` to real DB `risk_category`
  values; `test_evidence_service.py` passes and covers the new mapping
- `CORS_ALLOW_ORIGINS` is set in `.env.prod` with at least the Decision Renderer
  staging origin (real value or documented placeholder)
- `GET /metrics` returns 200 with Prometheus text when `METRICS_ENABLED=true`; returns
  404 when false; unit test covers both states
- At least one integration test verifies that a completed assessment writes a
  retrievable alert row via `GET /intelligence/alerts`
- `ERROR_TRACKING_BACKEND=sentry` (or a documented placeholder) is set in `.env.prod`;
  the production runbook has an Error Tracking section
- The Redis multi-worker upgrade path is documented in the production runbook and a
  commented-out Redis compose service exists in `docker-compose.prod.yml`
- All existing unit and integration test suites still pass after all changes in this
  book

Once these are true, the repo is cleared for Decision Renderer work.
