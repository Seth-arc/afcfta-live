# AfCFTA Live Backend Hardening Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Your AGENTS.md shell restriction still applies**: the coding agent creates
> and edits files; you run the commands yourself.
>
> **Primary references**:
> - docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md for prioritized blockers and risks
> - AGENTS.md for architecture invariants, shell restrictions, and locked scope
> - docs/FastAPI_layout.md for route, service, repository, and schema boundaries
> - docs/api/ for public contract expectations that must remain coherent

---

## Goal

Make the backend deterministic, auditable, secure enough for pre-production,
and operationally credible before any NIM or trader-facing UI work depends on it.

## Non-goals

- Do not add NIM model orchestration here.
- Do not merge conversational concerns into the eligibility engine.
- Do not expand country or corridor scope.

## Working Rules

Use these rules for every prompt in this book:

1. Read the cited audit findings, architecture rules, and target code before editing.
2. Keep route handlers thin and push business logic into services.
3. If a prompt changes a public contract, update tests and docs in the same change.
4. If a prompt introduces configuration, update app/config.py, .env.example, README.md, and setup docs together.
5. If a prompt adds operational behavior, prefer explicit, minimal seams over speculative abstractions.

## Definition Of Done Per Prompt

A prompt is only complete when all of the following are true:

1. The code path named by the prompt implements the required behavior.
2. The narrowest relevant tests pin the behavior or contract.
3. Any affected public or operator docs reflect the new reality.
4. The prompt's required summary can cite exact files, route behavior, and tests.

## Cross-Cutting Implementation Notes

- Preserve the existing structured error envelope and request_id behavior when adding auth, rate limiting, health, logging, or timeout controls.
- For contract-freeze prompts, pin both schema shape and required decision fields, not just status codes.
- For persistence prompts, ensure evaluation rows plus check rows remain atomic and replay-safe.
- For deployment prompts, document only commands and runtime settings that the repository actually supports.

---

## Prompt 1 — Convert missing tariff coverage into a true hard blocker

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "CRITICAL BLOCKERS".
Read AGENTS.md section "Deterministic Engine Execution Order", especially the blocker list.
Read app/services/eligibility_service.py and the relevant tests around blocker handling.

Fix the eligibility blocker stage so missing tariff schedule coverage halts the assessment before pathway evaluation.

Work in these files first:
- app/services/eligibility_service.py
- tests/unit/test_eligibility_service.py
- tests/integration/test_golden_path.py
- tests/integration/test_quick_slice_e2e.py

Requirements:
1. `NO_SCHEDULE` must be emitted as a blocker-stage failure, not a warning-only major issue.
2. If tariff resolution fails, the engine must stop before pathway evaluation exactly as the architecture doc requires.
3. Preserve the response contract shape.
4. Persist audit checks exactly enough to explain why execution stopped.
5. Add unit and integration coverage that would fail if pathway evaluation still ran after missing schedule coverage.
6. Do not change unrelated failure-code behavior.
7. Make the skipped-pathway behavior visible in tests through explicit assertions, not only by absence of later failures.

When done, summarize:
- the exact blocker logic change
- which tests prove pathway evaluation is skipped
- whether any existing tests had to be updated for now-correct behavior
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_golden_path.py -v
python -m pytest tests/integration/test_quick_slice_e2e.py -v
```
# Completed 24 March
---

## Prompt 2 — Add regression coverage for every architecture-level hard blocker

```
Read AGENTS.md section "Blocker Checks (Step 4 — run BEFORE pathway evaluation)".
Read the current blocker tests in tests/unit/test_eligibility_service.py and tests/integration/test_quick_slice_e2e.py.

Add exhaustive regression coverage for all hard blockers so future interface work cannot accidentally weaken deterministic stop conditions.

Work in these files first:
- tests/unit/test_eligibility_service.py
- tests/integration/test_quick_slice_e2e.py
- tests/integration/test_golden_path.py

Requirements:
1. Cover all hard blockers listed in AGENTS.md.
2. Assert pathway evaluation is skipped when any hard blocker fires.
3. Assert audit output contains the blocker check and final decision trail.
4. Keep fixtures deterministic and isolated.
5. Do not rewrite broad sections of the existing integration suite.
6. Name each scenario after the architecture rule it protects so future regressions are easy to spot.

When done, summarize the new blocker scenarios and which architecture rule each one protects.
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_quick_slice_e2e.py -v
python -m pytest tests/integration/test_golden_path.py -v
```
# Completed 24 March
---

## Prompt 3 — Freeze the assessment and audit contracts

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md sections "MISSING/BROKEN" and "NIM READY CHECKLIST".
Read app/schemas/assessments.py, app/schemas/audit.py, app/schemas/evidence.py, docs/api/endpoints.md, and README.md.

Stabilize and document the current request or response contracts that downstream interface layers will consume.

Work in these files first:
- app/schemas/assessments.py
- app/schemas/audit.py
- app/schemas/evidence.py
- docs/api/endpoints.md
- docs/api/eligibility-api.md
- README.md
- tests/integration/test_golden_path.py
- tests/integration/test_audit_api.py

Requirements:
1. Pick one canonical document-inventory field name for assessments and document it consistently.
2. If backward compatibility is needed, add an explicit alias strategy rather than ambiguous parallel semantics.
3. Ensure the assessment response contract is documented and pinned in tests.
4. Ensure the audit replay contract is documented and pinned in tests.
5. Do not introduce breaking schema changes unless absolutely necessary; if you do, update all docs and tests in the same change.
6. Add or tighten contract assertions for all required decision fields.
7. Add at least one documentation example that matches the tested payload exactly.

When done, summarize:
- the canonical request field names
- any aliases retained for compatibility
- the tests that now freeze the contract for downstream consumers
```

**You run:**
```bash
python -m pytest tests/integration/test_golden_path.py -v
python -m pytest tests/integration/test_audit_api.py -v
```
# Completed 24 March
---

## Prompt 4 — Guarantee replay-safe persistence for interface-triggered assessments

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "CRITICAL BLOCKERS" item 3.
Read app/services/eligibility_service.py, app/api/v1/cases.py, app/api/v1/assessments.py, app/services/audit_service.py, and app/repositories/evaluations_repository.py.

Design and implement a safe persistence rule so interface-triggered assessments are guaranteed to produce a replayable evaluation trail.

Work in these files first:
- app/services/eligibility_service.py
- app/api/v1/assessments.py
- app/api/v1/cases.py
- app/services/audit_service.py
- app/repositories/cases_repository.py
- app/repositories/evaluations_repository.py
- tests/unit/test_eligibility_service.py
- tests/integration/test_audit_api.py

Requirements:
1. Define one explicit persistence strategy.
2. Do not allow interface-facing flows to return an unreplayable legal decision.
3. Keep direct deterministic engine execution reusable.
4. Preserve atomic persistence of evaluation plus checks.
5. Add tests for successful and failed interface-style runs.
6. Make the case or evaluation identifier handoff explicit so the later assistant layer can reuse it without guessing.

When done, summarize:
- the persistence strategy you chose
- why it is legally replay-safe
- the tests that prove failed and successful runs both persist
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_audit_api.py -v
```
# Completed 24 March
---

## Prompt 5 — Add API authentication to every non-health endpoint

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "PRODUCTION READINESS SCORES" for Security.
Read app/main.py, app/api/router.py, and all routes under app/api/v1/.

Implement a simple, production-sane authentication layer for all non-health API routes.

Work in these files first:
- app/main.py
- app/config.py
- app/api/deps.py
- app/api/router.py
- app/api/v1/assessments.py
- app/api/v1/cases.py
- app/api/v1/audit.py
- app/api/v1/sources.py
- app/api/v1/intelligence.py
- tests/integration/

Requirements:
1. Leave `/api/v1/health` unauthenticated.
2. Choose one simple mechanism appropriate for the current scope, such as API key authentication.
3. Apply it uniformly to all non-health routes.
4. Return structured error responses consistent with the existing error envelope.
5. Add integration tests that verify authenticated and unauthenticated behavior.
6. Do not hard-code secrets.
7. Document where the authenticated principal is sourced from so later logging work can reuse it.

When done, summarize:
- the auth mechanism
- where it is enforced
- the test matrix that proves route coverage
```

**You run:**
```bash
python -m pytest tests/integration/test_auth_api.py -v
python -m pytest tests/unit/test_eligibility_service.py -v
```
# Completed 24 March
---

## Prompt 6 — Add rate limiting suitable for trader UI ingress

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Security".
Read the authenticated routes and any middleware added in Prompt 5.

Add rate limiting for the API surface with stricter limits on high-cost routes.

Work in these files first:
- app/main.py
- app/config.py
- app/api/v1/assessments.py
- tests/integration/

Requirements:
1. Add configurable rate limits through settings.
2. Apply tighter limits to high-cost routes such as assessments.
3. Return deterministic, structured error responses when limits are exceeded.
4. Keep the implementation minimal and testable.
5. Add at least one integration test for a throttled route.
6. Keep route-level overrides explicit so later assistant endpoints can opt into stricter limits without reworking middleware.

When done, summarize:
- default limits
- high-cost route policy
- what remains for future distributed rate limiting
```

**You run:**
```bash
python -m pytest tests/integration/test_rate_limit_api.py -v
python -m pytest tests/integration/test_auth_api.py -v
python -m pytest tests/integration/test_audit_api.py -v
```
# Completed 24 March
---

## Prompt 7 — Upgrade health to true liveness and readiness checks

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md sections on Observability and Deployment.
Read app/api/v1/health.py, app/main.py, app/db/base.py, and app/config.py.

Extend the health surface so operators can distinguish process liveness from dependency readiness.

Work in these files first:
- app/api/v1/health.py
- app/api/router.py
- app/config.py
- app/db/base.py
- tests/unit/test_health.py
- tests/integration/

Requirements:
1. Keep a lightweight liveness endpoint.
2. Add a readiness endpoint that checks database connectivity safely.
3. Return status information in the existing structured style where appropriate.
4. Do not add heavyweight startup logic.
5. Add tests for both healthy and failing readiness scenarios if practical.
6. Document the exact endpoint names so container and CI work can depend on them later without guesswork.

When done, summarize:
- the liveness or readiness split
- what the readiness check validates
- any caveats for production deployment
```

**You run:**
```bash
python -m pytest tests/unit/test_health.py -v
python -m pytest tests/integration -q
```
# Completed 24 March
---

## Prompt 8 — Add structured request logging, latency capture, and audit correlation

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Observability".
Read app/main.py, app/core/logging.py, and app/services/audit_service.py.

Implement a minimal but production-credible structured logging layer.

Work in these files first:
- app/core/logging.py
- app/main.py
- app/services/audit_service.py
- app/config.py
- tests/unit/

Requirements:
1. Keep request_id propagation intact.
2. Log route, method, status_code, latency_ms, and authenticated principal if available.
3. Keep assessment audit logs distinct from generic HTTP request logs.
4. Make logging configuration environment-driven.
5. Do not introduce noisy duplicated logs.
6. Add focused tests where practical for formatter or helper behavior.
7. Make correlation fields stable enough that later NIM logging can reuse them instead of inventing a parallel scheme.

When done, summarize:
- what is logged per request
- what is logged per assessment
- how operators can correlate API traffic to legal audit trails
```

**You run:**
```bash
python -m pytest ./tests/unit/test_logging.py -v
python -m pytest ./tests/unit/test_audit_service.py -v
python -m pytest ./tests/unit/test_audit_service.py -v
python -m pytest ./tests/integration/test_auth_api.py -v
python -m pytest ./tests/integration/test_health_api.py -v
```
# Completed 24 March
---

## Prompt 9 — Add failure instrumentation, DB timeout safety, and external-hook seams

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Observability".
Read app/main.py, app/db/base.py, and app/config.py.

Prepare the application for production error tracking and timeout safety without overengineering it.

Work in these files first:
- app/main.py
- app/db/base.py
- app/config.py
- README.md

Requirements:
1. Add configurable DB statement or connection timeout settings where the current stack allows it safely.
2. Add clear extension points for external error tracking such as Sentry without making it mandatory.
3. Ensure unhandled exceptions still flow through the existing structured error response.
4. Document the configuration surface.
5. Keep the changes minimal and production-focused.
6. Distinguish between required in-process safeguards and optional external integrations in the docs.

When done, summarize:
- the timeout controls added
- the error-tracking seam you created
- what still requires external infrastructure
```

**You run:**
```bash
python -m pytest ./tests/unit/test_health.py -v
python -m pytest ./tests/unit/test_logging.py -v
python -m pytest ./tests/unit/test_audit_service.py -v
python -m pytest ./tests/integration/test_auth_api.py -v
python -m pytest ./tests/integration/test_health_api.py -v
```
# Completed 24 March
---

## Prompt 10 — Add environment completeness and a checked-in `.env.example`

```
Read app/config.py, README.md, docs/dev/setup.md, and the audit findings on Config & Secrets.

Create a complete, documented environment-variable surface for local, staging, and production usage.

Work in these files first:
- app/config.py
- .env.example
- README.md
- docs/dev/setup.md

Requirements:
1. Add every currently required runtime setting to `.env.example` with safe placeholders.
2. Keep secrets out of the repository.
3. Expand settings only where production controls introduced in earlier prompts require them.
4. Document which settings are mandatory versus optional.
5. Do not break the current local developer flow.
6. Group variables by concern, such as API, database, auth, rate limiting, logging, and deployment.

When done, summarize:
- the new environment variables
- which are required in production
- any defaults that are intentionally development-only
```

**You run:**
```bash
python -m pytest tests/unit -q
```
# Completed 24 March
---

## Prompt 11 — Add a production Dockerfile and a minimal prod compose entrypoint

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Deployment".
Read pyproject.toml, README.md, docker-compose.yml, and app/main.py.

Create production-oriented container artifacts.

Work in these files first:
- Dockerfile
- docker-compose.prod.yml
- README.md
- docs/dev/setup.md

Requirements:
1. Use a multi-stage Docker build.
2. Keep the runtime image as small as practical.
3. Add a healthcheck that uses the new readiness endpoint where appropriate.
4. Do not assume development-only mounted volumes.
5. Document the production startup command and required environment variables.
6. Preserve the existing local docker-compose setup unless a small compatibility improvement is clearly needed.
7. Make the runtime container fail fast when mandatory production settings are missing.

When done, summarize:
- the image stages
- the runtime command
- how the prod compose file differs from local development
```

**You run:**
```bash
docker build -t afcfta-live:prod .
docker compose -f docker-compose.prod.yml config
```
# Completed 24 March
---

## Prompt 12 — Add CI for lint, unit tests, integration tests, and image build validation

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Deployment" and "Testing Coverage".
Read pyproject.toml and the existing test docs.

Create a CI workflow that validates production readiness changes continuously.

Work in these files first:
- .github/workflows/ci.yml
- README.md
- docs/dev/testing.md

Requirements:
1. Run lint.
2. Run unit tests.
3. Run integration tests with the required database service.
4. Validate the Docker build.
5. Keep the workflow readable and incremental.
6. Do not add deployment automation yet unless the pipeline already has a natural place for it.
7. Surface artifact or report locations clearly enough that coverage and image-validation prompts can build on them.

When done, summarize:
- the CI stages
- what each stage protects
- any assumptions about secrets or runners
```

**You run:**
```bash
git diff .github/workflows/ci.yml
```
# Completed 24 March
---

## Prompt 13 — Add coverage reporting and enforce a first production-readiness floor

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Testing Coverage".
Read pyproject.toml and docs/dev/testing.md.

Add coverage tooling and document a realistic first-pass coverage floor.

Work in these files first:
- pyproject.toml
- docs/dev/testing.md
- README.md

Requirements:
1. Add pytest coverage configuration.
2. Emit a machine-readable and human-readable coverage report.
3. Set an initial minimum threshold that is honest for the current codebase.
4. Do not fake a 90 percent claim if the repository cannot currently sustain it.
5. Update documentation so coverage commands are explicit.
6. State whether the threshold applies to all tests or to the production-relevant test paths only.

When done, summarize:
- the new coverage commands
- the minimum threshold chosen
- which code areas likely need the next wave of tests
```

**You run:**
```bash
python -m pytest tests/unit tests/integration --cov
```

---

## Prompt 14 — Add property-based tests around deterministic edge cases

```
Read docs/Expression_grammar.md and the audit recommendation on property-based testing.
Read the current unit tests for expression evaluation, tariff resolution, and evidence readiness.

Add property-based or generative tests to the most failure-prone deterministic calculations.

Work in these files first:
- tests/unit/test_expression_evaluator.py
- tests/unit/test_tariff_resolution_service.py
- tests/unit/test_evidence_service.py
- pyproject.toml if a new dev dependency is required

Requirements:
1. Focus on deterministic invariants, not random smoke tests.
2. Prioritize derived-variable math, missing-fact handling, and threshold boundaries.
3. Keep tests readable and domain-relevant.
4. Do not use property-based testing to compensate for unclear business rules.
5. Seed or bound generators so failures are reproducible and easy to diagnose.

When done, summarize:
- the invariants covered
- the bugs these tests would catch
- any new dependency added
```

**You run:**
```bash
python -m pytest tests/unit/test_expression_evaluator.py -v
python -m pytest tests/unit/test_tariff_resolution_service.py -v
python -m pytest tests/unit/test_evidence_service.py -v
```

---

## Prompt 15 — Add load-test scaffolding for concurrent assessment traffic

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "Scalability".
Read the assessment API contract and current integration patterns.

Create a lightweight load-test scaffold for concurrent assessment execution.

Work in these files first:
- tests/load/
- README.md
- docs/dev/testing.md

Requirements:
1. Do not couple load tests to flaky random data.
2. Use a small, deterministic set of supported HS6 or corridor payloads.
3. Measure latency and success or failure rates.
4. Keep the harness simple enough to run in staging without special infrastructure.
5. Document the target scenario, for example 100 concurrent assessments.
6. Reuse authenticated request patterns if auth has already been introduced.

When done, summarize:
- the load scenario
- the metrics captured
- what still needs true performance infrastructure
```

**You run:**
```bash
python -m pytest tests/load -q
```

---

## Prompt 16 — Add cache and connection-pool tuning only where it is justified

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md sections "Scalability" and "Observability".
Read app/db/base.py, tariff or rule or source repositories, and the new load-test scaffold.

Add conservative performance tuning for clearly static or low-churn reads.

Work in these files first:
- app/db/base.py
- app/repositories/
- app/config.py
- README.md

Requirements:
1. Tune the DB engine or session configuration only with explicit settings.
2. Add in-process caching only for clearly safe, mostly static lookups.
3. Do not cache eligibility decisions.
4. Document invalidation assumptions.
5. Keep the implementation reversible and easy to reason about.
6. Make tuning opt-in or clearly configurable so load findings can validate impact before rollout.

When done, summarize:
- what was tuned
- what was cached
- what was intentionally left uncached and why
```

**You run:**
```bash
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

---

## Prompt 17 — Close the provenance gap for audit replay

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md section "PARTIAL" on provenance.
Read app/services/audit_service.py, app/api/v1/sources.py, app/repositories/sources_repository.py, and app/schemas/audit.py.

Strengthen audit replay so users can traverse from a persisted decision to the exact supporting source and provision records more directly.

Work in these files first:
- app/services/audit_service.py
- app/schemas/audit.py
- app/repositories/sources_repository.py
- app/api/v1/sources.py
- tests/integration/test_audit_api.py
- tests/integration/test_sources_api.py

Requirements:
1. Do not duplicate the entire provenance database inside audit responses.
2. Add enough linkage that a client can traverse from decision replay to supporting provisions cleanly.
3. Keep the response size reasonable.
4. Preserve existing provenance fields unless a carefully reasoned schema improvement is necessary.
5. Prefer stable identifiers and thin summaries over duplicating mutable source payloads.

When done, summarize:
- the new provenance linkage
- how clients traverse it
- the tests that now pin it
```

**You run:**
```bash
python -m pytest tests/integration/test_audit_api.py -v
python -m pytest tests/integration/test_sources_api.py -v
```

---

## Prompt 18 — Write the rollback and production operations runbook

```
Read the final state of the repository after Prompts 1 through 17.
Read docs/dev/setup.md, docs/dev/testing.md, README.md, and the production audit.

Write the operator runbook needed to deploy and safely roll back this service.

Work in these files first:
- docs/dev/production_runbook.md
- README.md

Requirements:
1. Cover startup checks, readiness checks, required env vars, migrations, and smoke tests.
2. Cover rollback triggers and rollback steps.
3. Cover what to verify before enabling NIM and before enabling a trader-facing UI.
4. Keep the runbook concrete, not aspirational.
5. Do not document commands that the repository still does not support.
6. Include a short operator checklist for verifying auth, readiness, and replay-safe assessment behavior after deploy.

When done, summarize:
- the deployment path
- the rollback path
- the minimum acceptance gate before public exposure
```

**You run:**
```bash
python -m pytest tests/unit tests/integration --cov
```

---

## Recommended Execution Groups

### Group 1 — Deterministic correctness and contract freeze

Prompts 1-4

### Group 2 — Security and ingress controls

Prompts 5-6

### Group 3 — Observability and runtime safety

Prompts 7-10

### Group 4 — Deployment and quality gates

Prompts 11-14

### Group 5 — Performance, provenance, and operations

Prompts 15-18

---

## Exit Criteria

- missing tariff coverage is a real hard blocker
- assessment and audit contracts are frozen and tested
- interface-triggered decisions persist replayable audit trails
- auth and rate limits are enforced
- liveness and readiness checks exist
- CI runs lint, tests, and build validation
- a production Docker path exists
- coverage reporting and deterministic edge-case tests are in place

Once these are true, the backend is ready to support a NIM layer and a trader-facing UI.