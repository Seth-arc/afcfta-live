## v0.1.0 — 2026-03-21

### Added

- Deterministic eligibility engine with 8-step pipeline
- Rule lookup API (`GET /api/v1/rules/{hs6}`)
- Tariff lookup API (`GET /api/v1/tariffs`)
- Eligibility assessment API (`POST /api/v1/assessments`)
- Evidence readiness API (`POST /api/v1/evidence/readiness`)
- Decision audit trail API (`GET /api/v1/audit/...`)
- Structured error handling with request tracing
- Safe expression evaluator (no dynamic execution, whitelist-only parser)
- Seed data for 5 HS6 products across 2 corridors
- 67 passing tests (61 unit + 6 integration)
- Full documentation: API reference, user guides, concept docs, developer guide

### Scope

- Countries: Nigeria, Ghana, Côte d'Ivoire, Senegal, Cameroon
- Seeded corridor coverage: Ghana -> Nigeria and Cameroon -> Nigeria
- Product resolution at HS6 level
- Supported capabilities: rule lookup, tariff lookup, eligibility assessment, evidence readiness, audit replay
- Status-aware outputs with `rule_status`, `tariff_status`, and `confidence_class`
- Full-stack API surface for health, rules, tariffs, cases, assessments, evidence, and audit

### Not Yet Included

- Frontend user interface
- HS8 or HS10 computation as a decision layer
- Real-time legal update feeds
- Full Africa-wide country and corridor coverage
- Machine-learning or probabilistic scoring

### Notes

- This release is a scoped prototype focused on deterministic correctness, auditability, and legal traceability
- The engine is designed to show its work rather than act as a black-box recommendation system
