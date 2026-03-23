## v0.1.0 — 2026-03-21

### Added

- Deterministic eligibility engine with 8-step pipeline
- Rule lookup API (`GET /api/v1/rules/{hs6}`)
- Tariff lookup API (`GET /api/v1/tariffs`)
- Eligibility assessment API (`POST /api/v1/assessments`)
- Case-backed assessment API (`POST /api/v1/assessments/cases/{case_id}`)
- Evidence readiness API (`POST /api/v1/evidence/readiness`)
- Decision audit trail APIs (`GET /api/v1/audit/...`), including latest evaluation retrieval by case
- Provenance APIs for sources and legal provisions (`GET /api/v1/sources...`, `GET /api/v1/provisions...`)
- Intelligence APIs for corridor profiles and alert listing (`GET /api/v1/intelligence/...`)
- Structured error handling with request tracing
- Safe expression evaluator (no dynamic execution, whitelist-only parser)
- Repeatable Appendix IV parser promotion workflow with staged validation and dry-run support
- Seed data for 8 deterministic HS6 products across 4 supported corridors
- Full documentation: API reference, user guides, concept docs, developer guide
- Completed the AIS parser reliability phase.

Added repository integration coverage for rules, tariffs, status, evaluations, and HS resolution.
Added fixed-fixture parser tests for rule decomposition, pathway generation, and applicability precedence.
Expanded live assessment integration coverage across parser-era product chapters and OR-alternative behavior.
Added audit service unit coverage and audit API integration coverage for persisted evaluation replay.
Added targeted integration coverage for deterministic agricultural, chemical, and machinery live-slice cases on newly seeded corridors.

Fixed repository and persistence defects uncovered by the new suites:
- HS6 prefix tariff matching for deeper tariff lines
- applicability range-boundary preservation
- mixed typed case-fact batch persistence
- mixed audit-check batch persistence
- request-scoped DB commit behavior for persisted evaluations
- persisted audit `check_type` schema alignment for full logical audit stages via Alembic revision `0011_expand_checktype`
- Alembic migration environment fallback to async `DATABASE_URL` when sync PostgreSQL drivers are unavailable
- first-class fact contract hardening for `non_originating_inputs` and `output_hs6_code`, including typed normalization, executable-pathway required-fact inference, and audit replay coverage
- deterministic integration fixtures for repository precedence, tariff status precedence, status windows, HS version scoping, and pending-rule blocker coverage
- sync seed-data idempotency against an existing HS6 backbone and consistent resolver precedence for test helpers

Validation is maintained through the current unit and integration suites rather than a hard-coded static test count in this changelog.

### Scope

- Countries: Nigeria, Ghana, Côte d'Ivoire, Senegal, Cameroon
- Seeded corridor coverage: Ghana -> Nigeria, Cameroon -> Nigeria, Côte d'Ivoire -> Nigeria, and Senegal -> Nigeria
- Product resolution at HS6 level
- Supported capabilities: rule lookup, tariff lookup, direct assessment, case-backed assessment, evidence readiness, audit replay, provenance lookup, and corridor intelligence lookup
- Status-aware outputs with `rule_status`, `tariff_status`, and `confidence_class`
- Full-stack API surface for health, rules, tariffs, cases, assessments, evidence, audit, provenance, and intelligence

### Not Yet Included

- Frontend user interface
- HS8 or HS10 computation as a decision layer
- Real-time legal update feeds
- Full Africa-wide country and corridor coverage
- Machine-learning or probabilistic scoring

### Notes

- This release is a scoped prototype focused on deterministic correctness, auditability, and legal traceability
- The engine is designed to show its work rather than act as a black-box recommendation system
