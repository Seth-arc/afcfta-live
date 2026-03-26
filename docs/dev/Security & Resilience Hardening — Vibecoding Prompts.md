# AfCFTA Live Security & Resilience Hardening Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run yourself. Do not skip ahead.
>
> **Prerequisite**: The Post-Audit Hardening book must be fully complete (all 6 prompts
> checked off) before starting Prompt 1 here. Prompt 1 is a security action and must
> complete before any other prompt in this book.
>
> **Your AGENTS.md shell restriction still applies**: the coding agent creates and
> edits files; you run the commands yourself.
>
> **Primary references**:
> - docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-26.md (audit findings this book closes)
> - docs/dev/Post-Audit Hardening — Vibecoding Prompts.md (completed prerequisite)
> - docs/dev/Decision Renderer — Vibecoding Prompts (2).md (next book after this one)
> - AGENTS.md for architecture invariants, shell restrictions, and locked scope
>
> **Targets covered**:
> 1. Remove `.env.prod` from git tracking and rotate the exposed credentials
> 2. Fix the enum `None`-crash in `sources.py` that returns 500 instead of 400
> 3. Add year-range validation to `EligibilityRequest` so out-of-range years are
>    rejected before reaching the engine
> 4. Handle orphaned `CaseFile` rows created by a failed one-step create+assess request
> 5. Make evidence snapshot isolation explicit and deterministic (not implicit via
>    REPEATABLE READ)
> 6. Enable Redis-backed rate limiting for multi-worker deployments and record the
>    100-concurrency load baseline
> 7. Add property-based tests for the expression evaluator using Hypothesis
> 8. Commit load test baseline files to unblock the CI `load-baseline` job

---

## Goal

Close the eight security, schema correctness, and operational resilience gaps identified
in the 2026-03-26 deep-dive audit. These gaps do not block NIM integration but must be
resolved before the Decision Renderer is delivered to traders or before a multi-worker
production deployment is considered stable.

## Non-goals

- Do not change the deterministic eligibility engine.
- Do not change any frozen assessment, audit, or assistant schema.
- Do not expand corridor or HS6 scope beyond V01.
- Do not start Decision Renderer work in this book.
- Do not re-open architecture decisions already settled by the Production Gate or
  Post-Audit Hardening books.

## Working Rules

1. Read every cited file before editing. These are targeted fixes; do not rework
   surrounding code that is not in scope.
2. Prompts 2, 3, 4, 5, and 7 are code changes. Each must include a regression test so
   the gap cannot silently return.
3. Prompts 1, 6, and 8 are operational or data changes. Do not edit any Python source
   files in those prompts.
4. Prompt 1 is security-critical. It must complete — including credential rotation in
   the actual infrastructure — before any other prompt begins.
5. Prompt 5 requires a database migration. Run `alembic upgrade head` after the agent
   delivers the migration file and before running the regression tests.
6. When adding any configuration key, update `app/config.py`, `.env.example`, and
   `docs/dev/production_runbook.md` in the same change.

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
| 7 | [ ] Pending | — |
| 8 | [ ] Pending | — |

## Cross-Cutting Implementation Notes

- Do not change any frozen schema (`app/schemas/assessments.py`, `app/schemas/audit.py`,
  `app/schemas/nim/`) during this book.
- Preserve all existing `request_id` correlation, auth, and rate-limiting behaviour when
  editing any middleware, startup, or config path.
- Keep the deterministic assessment engine and its audit persistence path completely
  isolated from any new change.
- Do not introduce new Python dependencies unless a prompt explicitly justifies one.
- The AGENTS.md rule that Alembic revision identifiers must be ≤ 32 characters applies
  to the migration in Prompt 5.

---

## Prompt 1 — Remove .env.prod from git and rotate exposed credentials

```
This is a security-critical prompt. Do not start any other prompt until this one is
complete, including the credential rotation step that you (not the agent) must perform
in your actual infrastructure.

Read:
- .env.prod (full file)
- .env.example (full file)
- .gitignore

The file .env.prod is tracked by git (shown by `git status`). It contains real
production credentials: a database password and an API auth key. Both must be treated
as compromised from the moment this fact was discovered. The file also has
RATE_LIMIT_ENABLED=false, which means the production API is accepting unlimited
requests.

This is an operational prompt. Do not change any Python source files.

Work in these files:
- .gitignore
- .env.example

Requirements:
1. In .gitignore, add .env.prod on its own line if it is not already present. Verify
   that .env, .env.prod, .env.local, and .env.*.local are all covered. Do not remove
   any existing entries.
2. In .env.example, locate the API Authentication and Database sections. Strengthen
   both comment blocks to include an explicit warning:
   "These values must be generated outside this repository and must never be committed
   to git. If .env.prod is currently tracked by git, run:
     git rm --cached .env.prod
     git commit -m 'chore: stop tracking .env.prod'
   then rotate both DATABASE_URL credentials and API_AUTH_KEY immediately."
3. In .env.example, set RATE_LIMIT_ENABLED=true as the documented production default
   and add a comment: "Must be true in all non-local environments. Setting this to
   false disables all rate limiting globally."
4. Do not edit .env.prod itself. The agent must not read or write production secrets.

When done, summarize:
- the lines added to .gitignore
- the warning text added to .env.example and which sections it appears in
- confirmation that RATE_LIMIT_ENABLED is documented as true in .env.example
```

**You run** (in this exact order, after the agent finishes):
```bash
# 1. Stop tracking the file without deleting it
git rm --cached .env.prod

# 2. Verify it is now untracked
git status .env.prod

# 3. Commit the .gitignore and .env.example changes
git add .gitignore .env.example
git commit -m "chore: stop tracking .env.prod and document credential rotation"

# 4. MANUALLY rotate credentials in your infrastructure:
#    - Generate a new POSTGRES_PASSWORD and update it in the database + .env.prod
#    - Generate a new API_AUTH_KEY (min 32 random bytes) and update .env.prod
#    - Set RATE_LIMIT_ENABLED=true in .env.prod
#    - Restart the API service

# 5. Confirm .env.prod is absent from the next push
git log --oneline -3
```

---

## Prompt 2 — Fix enum None-crash in sources.py

```
Read:
- app/api/v1/sources.py (full file)
- app/schemas/assessments.py (TopicEnum or equivalent enum import used in sources.py)
- tests/unit/test_sources_api.py (full file)

The topic filter in GET /sources and the source_id filter in GET /provisions extract
`.value` from enum parameters without guarding against None. When a caller passes a
query parameter value that does not match a valid enum member, FastAPI raises a
ValidationError before the handler is reached — but if a None value reaches the
`.value` call inside the handler, the result is an unhandled AttributeError that
returns a 500 instead of a structured 400.

Audit finding: sources.py lines 27-29.

Work in these files:
- app/api/v1/sources.py
- tests/unit/test_sources_api.py

Requirements:
1. Read sources.py carefully. Identify every location where `.value` is extracted from
   an optional enum parameter without a None guard. There may be more than the two
   lines flagged in the audit.
2. For each location, replace the bare `.value` call with a pattern that:
   - returns None (passes no filter) when the enum parameter is None
   - returns the string value when the enum parameter is present
   A one-line expression is preferred: `param.value if param is not None else None`.
3. Do not change the function signatures, route paths, or response schemas.
4. Do not change any other file.
5. Add or strengthen tests in test_sources_api.py:
   - assert that GET /sources with no topic parameter returns HTTP 200 (no crash)
   - assert that GET /sources with a valid topic parameter returns HTTP 200
   - assert that GET /provisions with no source_id returns HTTP 200
   - assert that GET /provisions with a valid source_id returns HTTP 200
   These tests do not require a live database; use the existing fake/mock session
   pattern already established in that test file.

When done, summarize:
- every location in sources.py where the None guard was added
- the tests added or strengthened
```

**You run:**
```bash
python -m pytest tests/unit/test_sources_api.py -v
```

---

## Prompt 3 — Year-range validation in EligibilityRequest

```
Read:
- app/schemas/assessments.py (full file — focus on EligibilityRequest)
- app/core/countries.py (V01_CORRIDORS definition)
- tests/unit/test_assessments_api.py (full file)
- tests/unit/test_contract_freeze.py (to understand what is frozen)

EligibilityRequest accepts any integer value for the `year` field. The engine
converts it to `date(request.year, 1, 1)` and uses it as the assessment snapshot
date. A year of 2019, 2030, or 0 would silently resolve against whatever data
snapshot exists, producing a misleading result rather than a rejected request.

Audit finding: no validation that year is within a supported range.

Work in these files:
- app/schemas/assessments.py
- tests/unit/test_assessments_api.py

Requirements:
1. In EligibilityRequest, add a Pydantic `field_validator` for `year` that:
   - rejects any year below 2020 (the earliest plausible AfCFTA operative year)
   - rejects any year more than 1 above the current calendar year, to prevent
     far-future speculative assessments from reaching the engine
   - raises a clear ValueError with the message:
     "year must be between 2020 and {current_year + 1}; got {value}"
   Compute the upper bound dynamically using `datetime.date.today().year + 1` so the
   validator does not require updating each year.
2. The validator must be a `@field_validator('year', mode='before')` so it fires on
   the raw input value before Pydantic coerces it.
3. Do not change any other field in EligibilityRequest or CaseAssessmentRequest.
4. Verify that test_contract_freeze.py still passes after the change — the frozen
   field list must not change, only the validation behaviour.
5. Add tests to test_assessments_api.py:
   - assert that year=2019 returns HTTP 422 with a structured error body
   - assert that year=2025 (a known valid year) is accepted (HTTP 200 or no
     validation error at schema level)
   - assert that year=(current_year + 2) returns HTTP 422
   These tests should use the TestClient or schema-level instantiation; a live
   database is not required.

When done, summarize:
- the exact validator added (file and line range)
- the lower and upper bounds applied
- the tests added
- confirmation that test_contract_freeze.py still passes
```

**You run:**
```bash
python -m pytest tests/unit/test_assessments_api.py tests/unit/test_contract_freeze.py -v
```

---

## Prompt 4 — Handle orphaned cases on one-step create+assess failure

```
Read:
- app/api/v1/cases.py (full file — focus on create_case, lines 60-110)
- app/repositories/cases_repository.py (full file)
- app/repositories/evaluations_repository.py (get_evaluations_for_case)
- app/api/v1/audit.py (get_latest_case_audit_trail)
- app/schemas/cases.py (CaseCreateResponse and related models)
- tests/integration/test_audit_api.py (test_create_case_with_assess_true_* tests)

When POST /cases is called with assess=true, the handler:
  1. Creates and commits the CaseFile and CaseInputFact rows (line ~92: explicit commit)
  2. Opens a new REPEATABLE READ session to run the engine

If step 2 raises any exception (EvaluationPersistenceError, engine blocker, DB
timeout), the CaseFile committed in step 1 is left with no EligibilityEvaluation. A
subsequent GET /cases/{id}/latest on this case returns a 404 because
get_latest_decision_trace() finds no evaluation row. NIM treats any non-200 on that
path as a broken conversation state.

The correct resolution is Option B: accept the orphaned state as a valid, named state
("assessment_pending") and surface it clearly so callers — including NIM — can detect
and act on it.

Work in these files:
- app/api/v1/cases.py
- app/api/v1/audit.py (add a new route — see below)
- app/schemas/cases.py (add CaseStatusResponse — see below)
- tests/integration/test_audit_api.py

Requirements:
1. In app/schemas/cases.py, add a CaseStatusResponse model with these fields only:
     case_id: UUID
     has_evaluation: bool
     latest_evaluation_id: UUID | None
   Use `model_config = ConfigDict(from_attributes=True)`.
2. In app/api/v1/audit.py, add a new route:
     GET /audit/cases/{case_id}/status → CaseStatusResponse
   The handler must:
   - Fetch the case (404 if not found) via cases_repository
   - Fetch evaluations_for_case (empty list is not an error)
   - Return CaseStatusResponse with has_evaluation=False and
     latest_evaluation_id=None when the list is empty
   - Return CaseStatusResponse with has_evaluation=True and
     latest_evaluation_id set to the newest evaluation's ID otherwise
   Apply the same rate limit dependency as the other audit routes.
3. Do not change the POST /cases handler or the commit behaviour. The orphaned state
   is now handled at read time, not write time. Do not add cascade-delete logic.
4. Do not change any frozen schema.
5. Add integration tests to test_audit_api.py:
   - assert that GET /audit/cases/{id}/status returns 200 with has_evaluation=False
     immediately after a case is created but before any assessment runs
   - assert that GET /audit/cases/{id}/status returns 200 with has_evaluation=True
     and the correct latest_evaluation_id after a successful assessment
   - assert that GET /audit/cases/{unknown_id}/status returns 404

When done, summarize:
- the CaseStatusResponse fields added
- the new route path and handler location
- the tests added
- confirmation that existing create_case tests still pass
```

**You run:**
```bash
python -m pytest tests/integration/test_audit_api.py -v
```

---

## Prompt 5 — Make evidence snapshot isolation explicit and deterministic

```
Read:
- app/services/evidence_service.py (full file — focus on lines 8-60)
- app/repositories/evidence_repository.py (full file)
- app/db/models/evidence.py (full file — EvidenceRequirement and related tables)
- app/db/session.py (assessment_session_context and assessment_eligibility_service_context)
- app/services/eligibility_service.py (lines 330-345 — the call site for evidence)
- tests/unit/test_evidence_service.py (full file)
- alembic/versions/ (list the most recent revision file to find the correct `down_revision`)

The evidence_service does not receive `assessment_date` and does not pass it to the
repository. Snapshot isolation for evidence lookups is maintained only because the
caller runs within an open REPEATABLE READ transaction — correct by coincidence, not
by design. If evidence_service were ever called outside that transaction boundary (e.g.
from a background task or a direct API handler that does not go through
`assessment_eligibility_service_context`), it would silently read current data rather
than the snapshot at assessment time.

The fix has two parts: (a) add a runtime guard that asserts the service is always
called within an assessment session, and (b) formally pass `assessment_date` through
to the repository so date-windowed queries become possible without a second migration.

Work in these files:
- app/services/evidence_service.py
- app/repositories/evidence_repository.py
- app/db/models/evidence.py (add columns — see below)
- a new Alembic migration file
- tests/unit/test_evidence_service.py

Requirements:
1. In app/db/models/evidence.py, add two nullable columns to EvidenceRequirement:
     effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
     effective_to:   Mapped[date | None] = mapped_column(Date, nullable=True)
   Both default to NULL (meaning unbounded — the existing rows remain valid).
   Add a composite index on (effective_from, effective_to) to support future
   date-windowed queries.
2. Create an Alembic migration that adds these two columns and the index. The revision
   identifier must be ≤ 32 characters (AGENTS.md constraint). Use a descriptive slug
   such as "evidence_effective_dates".
3. In app/repositories/evidence_repository.py, update get_requirements() and
   get_verification_questions() to accept an optional `as_of_date: date | None = None`
   parameter. When as_of_date is provided, filter:
     effective_from IS NULL OR effective_from <= :as_of_date
     effective_to   IS NULL OR effective_to   >= :as_of_date
   When as_of_date is None, apply no date filter (existing behaviour preserved).
4. In app/services/evidence_service.py:
   a. Add `assessment_date: date | None = None` to the signature of build_readiness()
      (and get_readiness() if it exists as a separate method).
   b. Pass assessment_date through to the repository calls added in step 3.
   c. Add a guard at the top of build_readiness(): if assessment_date is None, emit a
      WARNING-level structured log with message "evidence_service called without
      assessment_date — snapshot isolation relies on caller transaction boundary".
      Do not raise an exception; the existing behaviour must be preserved for callers
      that do not yet pass the date.
5. In app/services/eligibility_service.py, update the call site (lines ~335-341) to
   pass `assessment_date=assessment_date` to build_readiness(). Do not change
   anything else in eligibility_service.py.
6. Add tests to test_evidence_service.py:
   - assert that build_readiness() called with assessment_date=None emits the WARNING
     log (use caplog or monkeypatch the logger)
   - assert that build_readiness() called with a valid assessment_date passes it
     through to get_requirements() and get_verification_questions()
   - assert that rows with effective_to before assessment_date are excluded from the
     result (use a fake/mock repository)
   - assert that rows with effective_from after assessment_date are excluded
   - assert that rows with NULL effective_from and NULL effective_to are always included

When done, summarize:
- the migration revision id and slug
- the columns added and the NULL-means-unbounded semantics
- the updated repository method signatures
- the WARNING log added and when it fires
- the call site change in eligibility_service.py (file and line)
- the tests added
```

**You run:**
```bash
# Apply the migration first
python -m alembic upgrade head

# Then run the tests
python -m pytest tests/unit/test_evidence_service.py -v
python -m pytest tests/integration/test_audit_api.py -v -k "evidence"
```

---

## Prompt 6 — Enable Redis rate limiting and promote to multi-worker

```
Read:
- docker-compose.prod.yml (full file)
- .env.prod (full file)
- .env.example (Redis section)
- docs/dev/production_runbook.md (Scaling to multiple workers section)
- app/main.py (_lifespan — startup guard for multi-worker without Redis)
- tests/integration/test_app_bootstrap_helpers.py (Redis lifespan tests)

The Post-Audit Hardening book documented the Redis upgrade path. This prompt
activates it. The docker-compose.prod.yml already contains a commented-out Redis
service block and a commented-out depends_on reference from the API service. The
.env.prod already contains a commented-out REDIS_URL entry.

This is an operational prompt. Do not change any Python source files.

Work in these files:
- docker-compose.prod.yml
- .env.prod
- docs/dev/production_runbook.md

Requirements:
1. In docker-compose.prod.yml:
   a. Uncomment the Redis service block (redis:7-alpine).
   b. Uncomment the depends_on redis reference in the api service.
   c. Change the api service `command` worker count from `"1"` to `"2"`. Add a
      comment on the same line: "# Requires REDIS_URL — see .env.prod".
2. In .env.prod:
   a. Uncomment REDIS_URL=redis://redis:6379/0.
   b. Set RATE_LIMIT_ENABLED=true (it is currently false — this was flagged in
      Prompt 1 but must be confirmed here after the Redis service is available).
   c. Do not change any other value.
3. In docs/dev/production_runbook.md, update the "Scaling to multiple workers"
   section. Add a "Current state" line at the top of the section that reads:
   "Current state (as of 2026-03-26): Redis enabled, UVICORN_WORKERS=2, rate
   limiting active."
4. Do not add UVICORN_WORKERS to docker-compose.prod.yml — the worker count is
   controlled by the compose command override (step 1c above).

When done, summarize:
- the exact docker-compose.prod.yml lines changed
- the .env.prod lines changed
- the production_runbook.md line added
```

**You run:**
```bash
# Validate the compose config parses correctly
docker compose -f docker-compose.prod.yml config

# Confirm Redis and rate-limit settings
grep -n "REDIS\|RATE_LIMIT\|workers" docker-compose.prod.yml .env.prod

# Start the stack and confirm Redis handshake in logs
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs api | grep -i "redis\|rate.limit\|workers"

# Health check
curl -sf http://localhost:8000/api/v1/health/ready | python -m json.tool
```

---

## Prompt 7 — Property-based tests for the expression evaluator

```
Read:
- app/services/expression_evaluator.py (full file)
- tests/unit/test_expression_evaluator.py (full file)
- pyproject.toml (dependencies and dev extras)
- AGENTS.md (expression evaluator constraints — lines 68-71)

The expression evaluator parses and evaluates boolean rule expressions against
trader-supplied facts. It is the most security-sensitive component in the engine:
a parsing bug here could silently allow an ineligible shipment to pass or block a
legitimate one. The existing tests are hand-written cases. Property-based tests using
Hypothesis will find boundary conditions that manual tests miss.

Work in these files:
- pyproject.toml (add hypothesis to the dev extras)
- tests/unit/test_expression_evaluator.py

Requirements:
1. Add `hypothesis>=6.100` to the `[project.optional-dependencies] dev` list in
   pyproject.toml. Do not add it to the main dependencies.
2. Add property-based tests in test_expression_evaluator.py using
   `from hypothesis import given, settings, strategies as st`.
   Add the following test strategies:

   a. AND/OR identity laws:
      For any boolean fact value b, assert:
        evaluate("A AND TRUE", {A: b})  == b
        evaluate("A OR FALSE", {A: b})  == b
        evaluate("A AND FALSE", {A: b}) == False
        evaluate("A OR TRUE", {A: b})   == True

   b. Idempotency:
      For any boolean fact value b, assert:
        evaluate("A AND A", {A: b}) == b
        evaluate("A OR A",  {A: b}) == b

   c. Negation:
      For any boolean fact value b, assert:
        evaluate("NOT A", {A: b}) == (not b)
        evaluate("NOT (NOT A)", {A: b}) == b

   d. Fact name fuzz:
      Generate random short ASCII identifiers (letters only, 1-8 chars) as fact
      names. Assert that evaluate(expr, facts) either returns a bool or raises
      exactly the documented exception type (do not allow AttributeError,
      KeyError, or any unlisted exception to escape).

   e. Missing fact handling:
      For any expression referencing fact A, if A is absent from the facts dict,
      assert that evaluate() raises the documented missing-fact exception (not
      KeyError or AttributeError).

3. Each property test must have a `@settings(max_examples=200)` decorator so the
   CI run is bounded. Do not use `@settings(deadline=None)` — keep the default
   deadline so slow evaluations are caught.
4. Do not change app/services/expression_evaluator.py or any other source file.
5. Do not add hypothesis to the main `[project.dependencies]` list — it is a dev
   dependency only.

When done, summarize:
- the version constraint added to pyproject.toml
- each property test added and the law it verifies
- any evaluator behaviour discovered by Hypothesis that the existing tests did not
  cover (edge cases, unexpected exception types, etc.)
```

**You run:**
```bash
pip install -e ".[dev]"
python -m pytest tests/unit/test_expression_evaluator.py -v --hypothesis-show-statistics
```

---

## Prompt 8 — Commit load test baseline files to unblock CI

```
Read:
- .github/workflows/ci.yml (load-baseline job — lines 209-315)
- tests/load/run_load_test.py (--report flag and output format)
- tests/load/compare_reports.py (--baseline flag and expected schema)
- tests/load/ (list all files present)

The CI load-baseline job runs two load scenarios and compares them against committed
baseline files:
  tests/load/baseline.json      (10c / 50 requests — CI smoke baseline)
  tests/load/baseline_100c.json (100c / 500 requests — 100-concurrency baseline)

If either baseline file is absent, the compare_reports.py step fails and the job
is permanently blocked. These files must be committed to the repository.

This is a data/operational prompt. Do not change any Python source files or CI
configuration.

Work: generate and commit the two baseline files by running the load tests against a
local stack with the same pool settings as CI.

You (not the agent) will run the commands below. The agent's role in this prompt is
only to document the accepted p95 thresholds in docs/dev/production_runbook.md.

After you have generated the files, paste the key metrics (p50, p95, p99, success_rate)
from each run into the chat so the agent can update the runbook.

Agent work in these files:
- docs/dev/production_runbook.md (add a "Load Baselines" section)

Runbook requirements:
1. Add a section "Load Baselines" to docs/dev/production_runbook.md. The agent must
   leave placeholders for the metric values (p50, p95, p99, success_rate for both
   scenarios) — you will fill them in after the runs complete.
2. The section must note:
   - the pool settings required to match CI (DB_POOL_SIZE=20, DB_POOL_MAX_OVERFLOW=80)
   - the latency tolerance in the CI comparison gate (25% for 10c, 50% for 100c)
   - the minimum success rate gate (95%)
   - the command to regenerate a baseline after intentional performance changes:
       python tests/load/run_load_test.py --mode burst --concurrency 10 --requests 50 \
         --api-key <key> --report tests/load/baseline.json
       python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500 \
         --api-key <key> --report tests/load/baseline_100c.json
3. Do not change ci.yml, run_load_test.py, or compare_reports.py.
```

**You run** (stack must be running with Redis enabled from Prompt 6):
```bash
export AIS_BASE_URL=http://localhost:8000
export AIS_API_KEY=<your-api-key>
export RATE_LIMIT_ENABLED=false   # disable limiter for the load run only
export DB_POOL_SIZE=20
export DB_POOL_MAX_OVERFLOW=80

# 10c baseline
python tests/load/run_load_test.py \
  --mode burst --concurrency 10 --requests 50 \
  --api-key "$AIS_API_KEY" \
  --report tests/load/baseline.json

# 100c baseline
python tests/load/run_load_test.py \
  --mode burst --concurrency 100 --requests 500 \
  --api-key "$AIS_API_KEY" \
  --report tests/load/baseline_100c.json

# Commit both files
git add tests/load/baseline.json tests/load/baseline_100c.json
git commit -m "chore: commit load test baselines for CI comparison gate"
```

---

## Recommended Execution Groups

### Group 1 — Security (must be first)

Prompt 1

Remove .env.prod from git and rotate credentials before any other work begins. The
CI pipeline, load tests, and Docker stack all use separate CI-scoped keys and are
unaffected, but the production API key and database password visible in the tracked
file must be rotated before this branch is merged.

### Group 2 — Defensive code fixes (no migration, no new dependency)

Prompts 2 and 3

These are independent of each other and require no schema migration or new package.
Run both test suites before moving to Group 3. Either can be skipped to unblock the
other.

### Group 3 — Workflow correctness (no migration)

Prompt 4

Adds a new read-only route. Does not change any write path or existing schema. Can
run in parallel with Group 2.

### Group 4 — Assessment date formal threading (migration required)

Prompt 5

The only prompt that requires a database schema change. Run `alembic upgrade head`
after the agent delivers the migration and before running the regression tests. Do not
run this group against a shared staging database unless a maintenance window is
scheduled.

### Group 5 — Infrastructure and load baseline

Prompts 6 and 8 (in order)

Prompt 6 enables Redis and promotes to two workers. Prompt 8 records the baselines
against the running stack. Run Prompt 8 only after Prompt 6's stack is healthy and
producing consistent response times.

### Group 6 — Testing resilience (independent)

Prompt 7

No infrastructure dependency. Can run in parallel with any other group after Group 1
is complete.

---

## Exit Criteria

This prompt book is complete only when all of the following are true:

- `.env.prod` is absent from `git status` and both the database password and API auth
  key have been rotated in the actual infrastructure; `RATE_LIMIT_ENABLED=true` is set
  in `.env.prod`
- `GET /sources` and `GET /provisions` with no optional parameters return HTTP 200, not
  500; `test_sources_api.py` passes and covers the None-guard paths
- `EligibilityRequest` with `year=2019` returns HTTP 422 with a structured error body;
  `test_contract_freeze.py` still passes unchanged
- `GET /audit/cases/{id}/status` returns 200 with `has_evaluation=false` for a newly
  created case and `has_evaluation=true` after a completed assessment
- `EvidenceRequirement` has `effective_from` and `effective_to` columns; `alembic
  upgrade head` applies cleanly; `build_readiness()` accepts and threads
  `assessment_date`; the WARNING log fires when `assessment_date` is None
- `docker compose -f docker-compose.prod.yml config` validates without error; startup
  logs show "Redis-backed sliding-window rate limiter active"; API responds under two
  workers
- Hypothesis property tests for the expression evaluator pass with 200 examples each;
  no undocumented exception types escape the evaluator
- `tests/load/baseline.json` and `tests/load/baseline_100c.json` exist in the
  repository and the CI `load-baseline` job passes on the next push to main
- All existing unit and integration test suites still pass after all changes in this
  book

Once these are true, the repo is cleared for Decision Renderer integration work.
