# AFCFTA-LIVE REPO AUDIT: 2026-03-23

## 🟢 COMPLETE (Production-ready)
- Repeatable-read assessment transaction boundary is implemented for the main assessment path.
- Assessment flow threads a fixed assessment year into core rule and status resolution.
- Direct and case-backed assessments both run through the same deterministic eligibility service.
- Case creation, case retrieval, evaluation persistence, and audit replay endpoints are implemented.
- Evidence readiness is computed inline during assessment and replayed through audit.
- Rule, tariff, source, provision, corridor-profile, and alert APIs are implemented.
- Parser artifact validation and staged-to-operational promotion workflow are documented and enforced before promotion.
- Structured domain error responses with request IDs are implemented.

## 🟡 PARTIAL (Works, needs hardening)
- Assessment determinism is strong on the primary path, but repository and service fallbacks still default to today when callers omit as-of dates; that is safe only because the main orchestrator passes the date explicitly.
- Case workflow is usable, but the “latest replay” contract lives under `/audit/cases/{case_id}/latest`, not `/cases/{id}/latest`, and direct-vs-case parity is pinned at unit-test level more than live API level.
- Evidence integration works, but the public contract uses `existing_documents`, not the `submitted_documents[]` shape expected by the pending NIM design prompt.
- Provenance is exposed in rule, tariff, and audit responses, but audit replay does not hydrate supporting legal provisions as first-class objects.
- Source/provision APIs work, but the expected `/sources?topic=XXX` contract is not implemented; topic filtering exists on provisions via `topic_primary`.
- Intelligence preview works, but the corridor route is `/intelligence/corridors/{exporter}/{importer}`, not the requested hyphenated form.
- Parser promotion is repeatable at content level, but row identities are regenerated each run and there is no immutable promotion manifest pinned for assistant-facing explanations.
- Assessment and audit schemas are tested, but they changed multiple times on 2026-03-23 and are not version-frozen for NIM consumers.

## 🔴 MISSING/BROKEN (Blocks NIM integration)
- `NO_SCHEDULE` is not enforced as a hard blocker; the engine can continue pathway evaluation without tariff coverage, which violates the architecture spec. Estimated fix time: 2-4 hours.
- NIM orchestration layer does not exist yet: no assistant endpoint, no NIM service package, and no `test_assistant_api.py`. Estimated fix time: 1-2 days.
- The pending NIM prompt handbook is already contract-misaligned: it targets `submitted_documents`, while the live API accepts `existing_documents`. Estimated fix time: 1-2 hours to reconcile, longer if public contract renaming is chosen.
- Audit persistence is conditional on `case_id`; direct assessments can succeed without producing a persisted replayable record. That is unsafe for a conversational compliance layer. Estimated fix time: 3-5 hours.
- No authentication or rate limiting exists on the API surface. Estimated fix time: 1 day.
- No production deployment artifacts exist: no Dockerfile, no `docker-compose.prod.yml`, no CI pipeline, no `.env.example`. Estimated fix time: 1-2 days.
- No coverage report, no property-based testing, no load testing, and no chaos testing are present. Estimated fix time: 1-3 days for first-pass hardening.

## 📊 PRODUCTION READINESS SCORES
| Category | Score | Rationale |
|----------|-------|-----------|
| Security | 3/10 | Strong request validation and parameterized DB access exist, but there is no auth, no authorization model, no rate limiting, no API abuse protection, and no PII/data classification posture. |
| Observability | 4/10 | Request IDs, structured error envelopes, and assessment log payloads exist, but there are no latency metrics, no Sentry/New Relic hooks, no alerting on failure rates, and no readiness/dependency health checks. |
| Scalability | 4/10 | Async FastAPI and SQLAlchemy are in place with `pool_pre_ping`, but there is no load evidence, no cache strategy, no explicit pool tuning, and no documented multi-worker deployment model. |
| Config & Secrets | 4/10 | Core env-driven config exists, but there is no `.env.example`, no secret-management story, no readiness health check, and minimal shutdown behavior. |
| Deployment | 1/10 | There is no production Dockerfile, no prod compose, no CI/CD workflow, and no rollback runbook. |
| Testing Coverage | 6/10 | Functional unit and integration coverage is solid for engine behavior, audit, evidence, provenance, and intelligence, but there is no coverage percentage evidence, no property-based tests, no load tests, and no chaos tests. |

## 🚫 CRITICAL BLOCKERS
1. Missing tariff schedules do not halt assessments.
   Repro steps:
   - Submit a valid `POST /api/v1/assessments` request for a supported corridor/product/year with no tariff schedule coverage.
   - The service records `NO_SCHEDULE` as a major issue instead of a blocker, so the hard-blocker short-circuit does not fire and pathway evaluation continues.
2. NIM contract is neither frozen nor implemented.
   Repro steps:
   - Inspect git history for the last 48 hours and note repeated same-day changes to assessment, audit, provenance, and intelligence contracts.
   - Compare the new NIM prompt handbook, which expects `submitted_documents` and `tests/integration/test_assistant_api.py`, with the live API, which exposes `existing_documents` and has no assistant endpoint or assistant integration test.
3. Audit persistence is not guaranteed for conversational runs unless the caller manages cases correctly.
   Repro steps:
   - Call `POST /api/v1/assessments` without `case_id`.
   - The assessment can return successfully, but no persisted evaluation is guaranteed, so there is no legal replay path for that interaction.

## ✅ NIM READY CHECKLIST
- [ ] Assessment contract stable ✗
- [ ] Case workflow complete ✗
- [x] Evidence scoring inline ✓
- [ ] Audit persistence guaranteed ✗

## 🎯 RECOMMENDED FIX ORDER
[Fix `NO_SCHEDULE` blocker semantics and add an integration regression test - 2-4 hours]

[Freeze the assistant-facing request/response contract, reconcile `existing_documents` vs `submitted_documents`, and add contract tests - 4-6 hours]

[Guarantee case creation and persisted evaluation for every assistant-triggered assessment - 4 hours]

[Add auth and rate limiting before any trader-facing UI or NIM exposure - 1 day]

[Add Dockerfile, readiness health check, `.env.example`, and CI pipeline - 1 day]

## 📈 HS6 COVERAGE ANALYSIS
Current: 8 seeded live HS6 products across 4 supported corridors in the deterministic slice, with broader tariff corpus extraction documented separately but not pinned end-to-end for trader-facing use.

Test coverage: 9 locked golden cases, plus live integration suites for golden path, audit replay, provenance APIs, intelligence APIs, rules, tariffs, and quick-slice E2E behavior.

Expansion priority: Chapters 11, 27, and 84 for the next tranche, because they extend existing tested behavior into higher trader-value agro-processing, energy/petrochemical, and machinery flows.
What is needed here.