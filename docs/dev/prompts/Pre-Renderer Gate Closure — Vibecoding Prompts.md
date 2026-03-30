# AfCFTA Live Pre-Renderer Gate Closure Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Start this book only after the Production Gate book is fully complete**
> (all 8 prompts checked off). This book resolves the remaining gaps surfaced by
> the 2026-03-26 deep-dive audit that were not addressed by the Production Gate
> book.
>
> **Your AGENTS.md shell restriction still applies**: the coding agent creates
> and edits files; you run the commands yourself.
>
> **Prompts 1 and 2 require manual .env.prod edits**: the coding agent adds
> tests and verifies enforcement code; you flip the values in .env.prod yourself
> because that file is gitignored and contains live credentials.
>
> **Primary references**:
> - AFCFTA-LIVE_REPO_AUDIT_2026-03-26 (audit that drives this book)
> - docs/dev/Production Gate — Vibecoding Prompts.md (completed prerequisite)
> - docs/dev/Decision Renderer — Vibecoding Prompts (2).md (next book after this one)
> - AGENTS.md for architecture invariants, shell restrictions, and locked scope

---

## Goal

Close the seven remaining production-safety gaps from the 2026-03-26 audit so
that the Decision Renderer and NIM Integration books can start from a stable,
correctly-configured baseline. This book does not extend features. Every change
either enforces an already-designed safeguard, removes a documented workaround
from the evidence service, or adds operational runbooks that the renderer phase
will depend on.

## Non-goals

- Do not add Decision Renderer, counterfactual, or trader-UI surface area.
- Do not change the deterministic assessment engine logic or audit persistence path.
- Do not expand corridor or HS6 coverage beyond what the Production Gate book left.
- Do not introduce new external infrastructure dependencies beyond the Sentry SDK
  (Prompt 4) and the alembic init container pattern (Prompt 5), both of which are
  optional-at-runtime additions.

## Working Rules

Use these rules for every prompt in this book:

1. Read every cited file before editing. These are targeted fixes; do not rework
   surrounding code that is not in scope.
2. If a prompt repairs a bug or workaround, add a regression test that would fail
   without the fix and passes with it.
3. If a prompt changes configuration defaults, update app/config.py, .env.example,
   and docs/dev/setup.md together in the same change.
4. If a prompt changes the evidence service contract, also update any affected
   integration tests that depend on the old workaround behaviour.
5. Prompts 1 and 2 involve .env.prod values you must edit manually. The agent
   verifies enforcement and adds tests; you apply the flag change.

## Definition Of Done Per Prompt

A prompt is only complete when all of the following are true:

1. The specific gap it closes is no longer reproducible.
2. A regression test or CI gate prevents the gap from silently returning.
3. Any affected docs reflect the corrected state.
4. The required summary can cite the exact files changed and tests added.

## Prompt Status

| Prompt | Description | Status | Completed |
|---|---|---|---|
| 1 | Enable rate limiting in production env | [ ] Pending | — |
| 2 | Fix CORS origins for Decision Renderer | [ ] Pending | — |
| 3 | Seed documentary_gap verification questions | [ ] Pending | — |
| 4 | Provision Sentry error tracking | [ ] Pending | — |
| 5 | Add alembic migration step to docker-compose.prod.yml | [ ] Pending | — |
| 6 | Write rollback runbook | [ ] Pending | — |
| 7 | Complete NIM settings in .env.example for production activation | [ ] Pending | — |

## Cross-Cutting Implementation Notes

- Preserve all existing request_id correlation, auth, and rate-limiting behaviour
  when editing any middleware, startup, or config path.
- Keep the deterministic assessment engine and its audit persistence path
  completely isolated from any change in this book.
- When adding configuration, always add a corresponding .env.example entry with
  a safe development default and an explicit production note.
- Do not introduce new Python dependencies unless a prompt explicitly justifies one.
  Sentry SDK (Prompt 4) is the only justified addition; add it to the optional
  extras in pyproject.toml, not to the base install.

---

## Prompt 1 — Enable rate limiting in the production environment

```
Read app/config.py — locate RATE_LIMIT_ENABLED and its default value.
Read app/api/deps.py — find require_assessment_rate_limit and the rate-limit
  enforcement path including the short-circuit when RATE_LIMIT_ENABLED is false.
Read tests/integration/test_rate_limit_api.py in full.
Read .env.example — locate the RATE_LIMIT_ENABLED entry.

The production environment file currently has RATE_LIMIT_ENABLED=false, which
disables all rate limiting. This prompt verifies enforcement is correctly wired
and adds a regression test so CI will catch any future config drift that silently
removes rate limiting.

Work in these files:
- tests/integration/test_rate_limit_api.py (add regression test)
- .env.example (verify and update comment if needed — do NOT edit .env.prod)

Requirements:
1. Verify that app/config.py RATE_LIMIT_ENABLED defaults to true (not false). If
   the default is currently false, change it to true in app/config.py.
   Production environments that want the correct default should not need to set
   an explicit override.
2. In .env.example, ensure RATE_LIMIT_ENABLED=true is present and that the
   comment above it explicitly states: "Must be true in all non-local
   environments. Setting this to false disables all rate limiting globally."
3. Add a single integration test named
   test_rate_limit_is_enforced_when_enabled that:
   a. Starts with RATE_LIMIT_ENABLED=true and RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS
      set to 2 (via dependency override, not by editing the real config).
   b. Sends 3 consecutive POST /api/v1/assessments requests.
   c. Asserts the third request returns HTTP 429 with a Retry-After header.
   d. Does NOT require a live database or a working assessment payload — use
      the existing mock/override pattern in the test file.
4. Verify no existing test overrides RATE_LIMIT_ENABLED=false as a permanent
   test fixture. If any do, add a comment explaining the override is test-only
   and must not be copied to production config.
5. Do not edit .env.prod directly. After this prompt is done, you will manually
   change RATE_LIMIT_ENABLED=false to RATE_LIMIT_ENABLED=true in .env.prod.

When done, summarize:
- whether app/config.py default was changed and from what value to what
- the exact .env.example change made (line content before/after)
- the test name, what it sends, and what it asserts
```

**You run:**
```bash
python -m pytest tests/integration/test_rate_limit_api.py -v
python -m pytest tests/integration -q --ignore=tests/integration/test_golden_path.py
```

After tests pass, manually open .env.prod and change:
```
RATE_LIMIT_ENABLED=false
```
to:
```
RATE_LIMIT_ENABLED=true
```
## Completed 26 March
---

## Prompt 2 — Set correct CORS origins for the Decision Renderer

```
Read app/main.py — locate the CORSMiddleware setup and how CORS_ALLOW_ORIGINS
  is consumed (split on comma, passed to allow_origins).
Read app/config.py — locate the CORS_ALLOW_ORIGINS setting and its default.
Read .env.example — locate the CORS section and its current comment.

The production environment file currently has CORS_ALLOW_ORIGINS=http://localhost:3000.
This is a placeholder. When the Decision Renderer browser client connects from
its real domain, the browser will block every preflight with a CORS rejection.

Work in these files:
- .env.example (update the CORS section — do NOT edit .env.prod yet)
- tests/integration/test_public_contracts_api.py or the nearest CORS test file
  (add a preflight regression test)

Requirements:
1. In .env.example, update the CORS section to:
   a. Change the active value to CORS_ALLOW_ORIGINS= (empty, safe default for
      pure API access in local dev where no browser client exists).
   b. Add a commented production example line directly below it:
      # Production (Decision Renderer):
      # CORS_ALLOW_ORIGINS=https://decision-renderer-staging.afcfta.example,https://decision-renderer.afcfta.example
   c. Add a constraint comment: "Do not use * in production — enumerate origins
      explicitly. The localhost placeholder in .env.prod must be replaced with
      the real Decision Renderer origin before browser integration begins."
2. Add one integration test named test_cors_preflight_rejects_unlisted_origin that:
   a. Sends an OPTIONS preflight request with Origin: https://untrusted.example
      and Access-Control-Request-Method: POST to /api/v1/assessments.
   b. Asserts the response does NOT include
      Access-Control-Allow-Origin: https://untrusted.example in its headers.
   This test must use the real CORS middleware path — do not mock CORSMiddleware.
3. Add one integration test named test_cors_preflight_allows_configured_origin that:
   a. Overrides CORS_ALLOW_ORIGINS to https://renderer.test.example for the
      test only (via app override or env patch at test scope).
   b. Sends an OPTIONS preflight from that origin.
   c. Asserts Access-Control-Allow-Origin matches.
4. Do not edit .env.prod in this prompt. After tests pass, you will manually
   update .env.prod CORS_ALLOW_ORIGINS to the real Decision Renderer staging
   and production origins once those domains are provisioned.

When done, summarize:
- the exact .env.example CORS section changes (before/after)
- the two test names and what each one asserts
- the origin values used in each test
```

**You run:**
```bash
python -m pytest tests/integration/test_public_contracts_api.py -v
python -m pytest tests/integration -q -k "cors"
```

After tests pass, manually open .env.prod and replace:
```
CORS_ALLOW_ORIGINS=http://localhost:3000
```
with the real Decision Renderer origins when they are provisioned:
```
CORS_ALLOW_ORIGINS=https://decision-renderer-staging.afcfta.example,https://decision-renderer.afcfta.example
```
## Completed 26 March
---

## Prompt 3 — Seed documentary_gap verification questions and remove the evidence service workaround

```
Read app/services/evidence_service.py lines 1–30 in full (the _CONFIDENCE_TO_RISK
  mapping and the comment describing the workaround).
Read app/repositories/evidence_repository.py — get_verification_questions() method
  (lines 65–115 approximately) — confirm the risk_category SQL filter is wired.
Read scripts/seed_data.py — find the verification_questions list and the
  question_risk_category() helper.
Read scripts/sql/seed_evidence_requirements.sql — understand the existing
  INSERT patterns for evidence_requirement rows.
Read tests/integration/test_golden_path.py — find any test that exercises the
  evidence readiness path so you know what to regression-test.
Read tests/unit/test_evidence_service.py.

The evidence service has a documented workaround at lines 13–25:
- 'incomplete' maps to 'general' (stand-in for a missing 'documentary_gap' bucket)
- 'insufficient' maps to 'origin_claim' (stand-in)
This workaround exists because no verification_question rows with
risk_category='documentary_gap' were seeded.

This prompt seeds proper documentary_gap question rows and removes the workaround.

Work in these files:
- scripts/seed_data.py
- app/services/evidence_service.py
- tests/unit/test_evidence_service.py
- tests/integration/test_golden_path.py (or nearest evidence integration test)

Requirements:
1. In scripts/seed_data.py, inside the verification_questions list, add
   documentary_gap question rows for each rule type that already has seeded
   questions (WO, CTH, VNM). Each documentary_gap question must:
   a. Use entity_type matching the existing pattern for that rule type.
   b. Use risk_category='documentary_gap'.
   c. Use persona_mode='officer' (the customs verification persona).
   d. Have question_text that asks the customs officer to verify the
      documentary evidence package is complete and consistent.
   e. Use seed_uuid() with a stable key like
      'question/documentary_gap/{rule_type}/officer' so reruns are idempotent.
   f. Set priority_level=2 and question_order=1.
2. In app/services/evidence_service.py:
   a. Update _CONFIDENCE_TO_RISK so that 'incomplete' maps to 'documentary_gap'
      instead of 'general'.
   b. Keep 'insufficient' mapped to 'origin_claim' — that mapping is correct.
   c. Remove the workaround comment at lines 13–19. Replace it with a single
      line: '# Maps confidence class to verification question risk tier.'
3. Add a unit test named test_incomplete_confidence_routes_to_documentary_gap
   that calls EvidenceService.build_readiness() with confidence_class='incomplete'
   and asserts that the returned verification_questions list is non-empty and
   that get_verification_questions() was called with risk_category='documentary_gap'.
   Mock the evidence_repository to isolate the unit test.
4. Add a unit test named test_complete_confidence_skips_risk_filter that calls
   build_readiness() with confidence_class='complete' and asserts
   get_verification_questions() was called with risk_category=None.
5. Run the full integration suite after reseeding. The golden path tests must
   still pass — the documentary_gap questions are additive, not replacing.

When done, summarize:
- the rule types for which documentary_gap rows were added
- the exact _CONFIDENCE_TO_RISK change
- the two new unit tests and what each one asserts
- golden path integration test outcome (passed/count)
```

**You run:**
```bash
python scripts/seed_data.py - ## passed
python -m pytest tests/unit/test_evidence_service.py -v ## passed
python -m pytest tests/integration/test_golden_path.py -v ## passed
python -m pytest tests/integration -q ## passed
```
## Completed 29 March
---

## Prompt 4 — Provision Sentry error tracking

```
Read app/main.py — _configure_error_tracker() function in full.
Read app/config.py — ERROR_TRACKING_BACKEND, SENTRY_DSN, and
  SENTRY_TRACES_SAMPLE_RATE settings.
Read .env.example — the Optional External Error Tracking section.
Read pyproject.toml — the [project.optional-dependencies] or [tool.poetry.extras]
  section if it exists.

The Sentry seam is fully implemented in main.py but currently inactive:
- ERROR_TRACKING_BACKEND=none in .env.prod
- SENTRY_DSN=<your-project-dsn> is a literal placeholder

This prompt documents the activation steps, adds the sentry-sdk as an optional
dependency, and adds a unit test that proves the seam behaves correctly when
the backend is configured.

Work in these files:
- pyproject.toml (add sentry-sdk as optional extra)
- .env.example (expand the Sentry section with activation instructions)
- tests/unit/test_error_tracker.py (create this file)
- docs/dev/setup.md (add Sentry activation steps)

Requirements:
1. In pyproject.toml, add a new optional extras group named 'sentry' with
   sentry-sdk>=1.40.0 as its sole dependency. Keep it out of the base install
   so deployments without Sentry do not pull the SDK. Add an installation
   note comment.
2. In .env.example, replace the current Sentry section with:
   a. ERROR_TRACKING_BACKEND=none (unchanged safe default)
   b. SENTRY_DSN= (empty, not a placeholder string)
   c. SENTRY_TRACES_SAMPLE_RATE=0.05
   d. A multi-line comment block explaining:
      - Install: pip install -e ".[sentry]" (or add sentry to Dockerfile extras)
      - After installing, set ERROR_TRACKING_BACKEND=sentry and SENTRY_DSN=<dsn>
      - Restart the API; startup log will confirm "External error tracking
        initialized with backend sentry"
      - Set SENTRY_TRACES_SAMPLE_RATE=0.0 if performance tracing is not needed
3. Create tests/unit/test_error_tracker.py with three unit tests:
   a. test_error_tracker_noop_when_backend_is_none: constructs an ErrorTracker
      with capture_exception=None and calls capture_exception(Exception('test'));
      asserts it does not raise.
   b. test_error_tracker_calls_capture_when_wired: constructs an ErrorTracker
      with a mock capture function and calls capture_exception(Exception('x'));
      asserts the mock was called once with the exception.
   c. test_configure_error_tracker_returns_noop_for_unsupported_backend: calls
      _configure_error_tracker() with a settings mock that has
      ERROR_TRACKING_BACKEND='datadog'; asserts the returned tracker's
      _capture_exception is None.
   Import ErrorTracker and _configure_error_tracker from app.main. Do not start
   the real FastAPI app in these tests.
4. In docs/dev/setup.md, add a section titled "Enabling Sentry Error Tracking"
   with: install command, the three env vars to set, the startup log line to
   look for, and a note that SENTRY_DSN must be obtained from the Sentry
   project settings (never committed to git).
5. Do not edit .env.prod — after this prompt you will manually set
   ERROR_TRACKING_BACKEND=sentry and SENTRY_DSN=<real-dsn> once the Sentry
   project is provisioned.

When done, summarize:
- the pyproject.toml extras entry added
- the .env.example Sentry section changes
- the three test names and what each one asserts
- the docs/dev/setup.md section added
```

**You run:**
```bash
python -m pytest tests/unit/test_error_tracker.py -v
python -m pytest tests/unit -q
```

After the Sentry project is provisioned, manually update .env.prod:
```
ERROR_TRACKING_BACKEND=sentry
SENTRY_DSN=<your-real-project-dsn>
```
and install the extras in the runtime image by adding `.[sentry]` to the
Dockerfile pip install line.

## Completed 29 March
---

## Prompt 5 — Add database migration step to docker-compose.prod.yml

```
Read docker-compose.prod.yml in full.
Read alembic.ini — note the script_location and the database URL variable name.
Read Dockerfile — confirm alembic is present in the runtime image
  (alembic/ directory and alembic.ini are copied in).
Read docs/dev/setup.md — find the existing migration instructions.

The production compose file starts the API without running alembic upgrade head.
Any deployment to a fresh database or after a schema-changing migration requires
a manual alembic step before the container is useful. This prompt adds a
migration init container so compose deployments are self-contained.

Work in these files:
- docker-compose.prod.yml
- docs/dev/setup.md
- docs/dev/rollback_runbook.md (will be created in Prompt 6; add a forward
  reference comment only in this prompt if the file does not yet exist)

Requirements:
1. In docker-compose.prod.yml, add a new service named migrate with:
   a. The same image reference as the api service (afcfta-intelligence:prod).
   b. env_file: [./.env.prod] so it shares the same DATABASE_URL.
   c. command: ["python", "-m", "alembic", "upgrade", "head"]
   d. restart: "no" — it should run once and exit.
   e. depends_on: db with condition: service_healthy.
   f. No ports exposed.
2. Update the api service depends_on block to add:
     migrate:
       condition: service_completed_successfully
   This ensures the API container does not start until migrations are confirmed
   applied. The migrate service must exit 0 for this condition to be satisfied.
3. In docs/dev/setup.md, update the production deployment section to document:
   a. The migrate service runs automatically on every docker compose up.
   b. Alembic's idempotency guarantee: upgrade head is safe to run on an
      already-current schema (it is a no-op).
   c. How to run a migration manually against a running stack:
      docker compose -f docker-compose.prod.yml run --rm migrate
4. Do not change the development docker-compose.yml — the migrate service is
   production-only.
5. Verify the compose file is syntactically valid by running docker compose config.
   Fix any syntax errors before marking this prompt complete.

When done, summarize:
- the migrate service definition added (key fields)
- the api depends_on change
- the three docs/dev/setup.md additions
```

**You run:**
```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
```
## Completed 29 March
---

## Prompt 6 — Write the production rollback runbook

```
Read docker-compose.prod.yml (updated in Prompt 5).
Read alembic.ini.
Read docs/dev/setup.md — find references to migrations and deployment.
Read the alembic/versions/ directory — list the migration files to understand
  the version naming convention.

There is no documented rollback procedure. This prompt creates a concrete runbook
so operators can safely roll back a failing deployment: revert the image, reverse
the migration, restore service.

Work in these files:
- docs/dev/rollback_runbook.md (create this file)
- docs/dev/setup.md (add a reference link to the runbook)

Requirements:
1. Create docs/dev/rollback_runbook.md with the following sections:

   ## When to use this runbook
   Criteria: API container fails health checks after deployment, assessment
   endpoint returns 500, or migration applied but previous image is needed.

   ## Step 1 — Pin the last known-good image
   Document: how to identify the previous image tag from the CI docker-build
   job artifact (GitHub Actions: afcfta-intelligence:ci-<sha>). Show the
   docker-compose.prod.yml image line to edit.

   ## Step 2 — Reverse the migration
   Show the exact command:
     docker compose -f docker-compose.prod.yml run --rm \
       -e "$(cat .env.prod | grep DATABASE_URL)" \
       migrate python -m alembic downgrade -1
   Explain: downgrade -1 reverses only the last applied revision. For multiple
   revisions, repeat or supply the target revision id explicitly.
   Warning: downgrade destroys data for any destructive migration (DROP COLUMN,
   DROP TABLE). Always take a pg_dump backup before downgrading:
     docker compose -f docker-compose.prod.yml exec db \
       pg_dump -U afcfta afcfta > backup-$(date +%Y%m%d-%H%M).sql

   ## Step 3 — Restart with the pinned image
   docker compose -f docker-compose.prod.yml up -d api

   ## Step 4 — Verify rollback
   Curl the health endpoint and one golden assessment to confirm the previous
   version is serving correctly.

   ## Re-deploy after root cause fix
   Note that a new migration may be needed to re-apply the failed schema change
   after the bug is fixed. Never re-apply a reversed migration without a code fix.

   ## Alembic revision reference
   List all current revision IDs and their descriptions (derive from alembic/
   versions/ filenames). Update this table after every new migration is merged.

2. In docs/dev/setup.md, under the production deployment section, add:
   "For rollback procedures see docs/dev/rollback_runbook.md."

When done, summarize:
- the five sections in the runbook
- the exact downgrade command documented
- the backup command documented
- the setup.md reference line added
```

**You run:**
```bash
ls alembic/versions/
python -m pytest tests/integration -q --co -q 2>/dev/null | tail -5
```

No automated test gates this prompt — the deliverable is the runbook document.
Verify it renders correctly in your editor before marking complete.

## Completed 29 March
---

## Prompt 7 — Complete NIM configuration for production activation

```
Read app/config.py — locate all NIM_* settings (NIM_ENABLED, NIM_BASE_URL,
  NIM_API_KEY, NIM_MODEL, NIM_TIMEOUT_SECONDS, NIM_MAX_RETRIES).
Read .env.example — locate the NIM Assistant Integration section.
Read app/services/nim/client.py — confirm which settings are required when
  NIM_ENABLED=true.
Read tests/integration/test_nim_full_flow.py lines 1–52 (the module docstring)
  to understand the NIM_ENABLED=false fallback contract.

NIM_ENABLED, NIM_BASE_URL, NIM_API_KEY, and NIM_MODEL are absent from .env.prod.
When the NIM endpoint is provisioned, an operator cannot activate NIM without
knowing which values to set or what constraints apply. This prompt makes the
activation path unambiguous.

Work in these files:
- .env.example (expand the NIM section)
- app/config.py (add validator if NIM_ENABLED=true requires non-empty companions)
- tests/unit/test_nim_config_validation.py (create this file)

Requirements:
1. In .env.example, expand the NIM section to include every required var with
   a clear activation checklist comment:
   ```
   # =========================
   # NIM Assistant Integration
   # NIM_ENABLED=false is safe in all environments — assistant path returns
   # deterministic fallback explanation without calling the model endpoint.
   #
   # To activate NIM in production:
   #   1. Provision an NVIDIA NIM endpoint and obtain the base URL and API key.
   #   2. Set NIM_ENABLED=true.
   #   3. Set NIM_BASE_URL to the endpoint base URL (no trailing slash).
   #   4. Set NIM_API_KEY to the provisioned key (never commit to git).
   #   5. Set NIM_MODEL to the deployed model name (e.g. meta/llama-3.1-70b-instruct).
   #   6. Restart the API. The startup log will not confirm NIM — NIM is lazy-init.
   #   7. Send one assistant request and check the response explanation field is
   #      non-empty and does not say "deterministic fallback".
   # =========================
   NIM_ENABLED=false
   NIM_BASE_URL=
   NIM_API_KEY=
   NIM_MODEL=
   NIM_TIMEOUT_SECONDS=30
   NIM_MAX_RETRIES=2
   ```
2. In app/config.py, add a model_validator (Pydantic v2) on the Settings model
   that runs when NIM_ENABLED=true and raises ValueError if any of NIM_BASE_URL,
   NIM_API_KEY, or NIM_MODEL is empty or None. The error message must name the
   missing field explicitly. This prevents silent NIM misconfiguration from
   reaching the first real request.
3. Create tests/unit/test_nim_config_validation.py with three unit tests:
   a. test_nim_disabled_requires_no_companions: constructs Settings with
      NIM_ENABLED=false and empty NIM_BASE_URL/NIM_API_KEY/NIM_MODEL; asserts
      no ValidationError is raised.
   b. test_nim_enabled_with_all_fields_valid: constructs Settings with
      NIM_ENABLED=true and all three companion fields set to non-empty strings;
      asserts no ValidationError is raised.
   c. test_nim_enabled_without_base_url_raises: constructs Settings with
      NIM_ENABLED=true, NIM_BASE_URL='', NIM_MODEL='test', NIM_API_KEY='key';
      asserts ValidationError is raised and the error message names NIM_BASE_URL.
   Override DATABASE_URL, API_AUTH_KEY, and ENV in each test via Settings
   constructor kwargs so the tests do not require a real environment.
4. Do not edit .env.prod. After the NIM endpoint is provisioned, manually add
   these lines to .env.prod:
     NIM_ENABLED=true
     NIM_BASE_URL=<endpoint-url>
     NIM_API_KEY=<provisioned-key>
     NIM_MODEL=<deployed-model-name>

When done, summarize:
- the .env.example NIM section rewritten (activation checklist)
- the model_validator added to Settings and which fields it guards
- the three test names and what each one asserts
```

**You run:**
```bash
python -m pytest tests/unit/test_nim_config_validation.py -v
python -m pytest tests/unit -q
python -m pytest tests/integration/test_nim_full_flow.py -v
```
