**Role**: Senior Staff Engineer conducting pre-production gate review for AfCFTA Live eligibility engine + NIM integration readiness

**Context**: 
- AIS v0.1 delivery complete (Milestones 1-4 fully delivered via 19-prompt execution Mar 23, 2026)
- Engine hardened: transaction-isolated assessments, case workflows, evidence readiness, provenance APIs
- Next phase: NVIDIA NIM conversational layer before trader UI
- Target: Production-grade AfCFTA trader decision engine by Q2 2026 hackathons

**Your Mission**: Deep-dive audit of current repo state. Identify **ALL gaps** blocking safe NIM integration and trader UI. Prioritize by risk/cost.

---

## Phase 1: Architecture Completeness Audit

**Files to systematically review** (in priority order):

```
CRITICAL PATH (must be 100% before NIM):
├── app/services/eligibility_service.py          # Core deterministic logic
├── app/services/evidence_service.py             # Document readiness scoring  
├── app/services/audit_service.py               # Legal replay capability
├── app/repositories/                          # ALL repositories
│   ├── status_repository.py
│   ├── evaluations_repository.py
│   ├── cases_repository.py
│   ├── sources_repository.py
│   └── intelligence_repository.py
├── app/api/v1/                               # ALL endpoints
│   ├── assessments.py
│   ├── cases.py
│   ├── audit.py
│   ├── sources.py
│   └── intelligence.py
├── app/schemas/                              # Response contracts
│   ├── assessments.py
│   ├── audit.py
│   └── intelligence.py
└── tests/integration/                        # E2E coverage
    ├── test_golden_path.py
    ├── test_audit_api.py
    └── test_assistant_api.py (NIM orchestrator)

SUPPORTING LAYERS:
├── app/db/                                   # Transaction guarantees
├── scripts/parsers/                          # Data pipeline reliability
├── docs/dev/delivery_plan_and_backlog.md     # Delivery claims vs reality
└── AGENTS.md                                # Architecture invariants preserved?
```

**Audit Checklist** - Flag **RED** if ANY missing:

```
[ ] ELIGIBILITY ENGINE
    [ ] Snapshot-consistent assessments (REPEATABLE READ verified)
    [ ] assessment_date threaded through ALL subservices  
    [ ] Integration tests cover date-sensitive golden cases
    [ ] Output contract stable: eligible, pathway_used, rule_status, tariff_outcome, evidence_required, confidence_class

[ ] CASE WORKFLOW  
    [ ] POST /cases → assess → auto-persist evaluation
    [ ] GET /cases/{id}/latest → full audit replay
    [ ] Case facts → direct facts produce identical assessment
    [ ] Failed assessments persist correctly

[ ] EVIDENCE INTEGRATION
    [ ] Assessment requests accept submitted_documents[]
    [ ] readiness_score computed inline (not separate call)
    [ ] missing_evidence aligns with standalone evidence API
    [ ] Audit trail includes evidence decisions

[ ] PROVENANCE/TRACEABILITY
    [ ] GET /sources/{id}, GET /sources?topic=XXX
    [ ] GET /provisions?source_id=XXX&topic=XXX  
    [ ] Rule/tariff responses include provenance_ids
    [ ] Audit replay exposes supporting provisions

[ ] INTELLIGENCE PREVIEW
    [ ] GET /intelligence/corridors/{exporter}-{importer}
    [ ] GET /intelligence/alerts?status=open&severity=high
    [ ] Alert generation triggers defined and testable

[ ] DATA PIPELINE
    [ ] Parser validation gate rejects malformed artifacts
    [ ] Staged→operational promotion idempotent
    [ ] HS6 coverage expanding (list current slice size)
```

---

## Phase 2: Production Readiness Gaps

**Score each category 0-10, justify LOW scores (<8)**:

```
SECURITY & ACCESS
[ ] API key auth on ALL endpoints
[ ] Rate limiting (trader + hacker protection)
[ ] Input sanitization (SQLi, prompt injection)
[ ] PII/data classification (HS6 codes, trader facts)

OBSERVABILITY
[ ] Structured logging (request_id, latency percentiles)
[ ] Error tracking (Sentry/New Relic integration ready)
[ ] Circuit breakers (DB timeouts, external API failures)
[ ] Assessment success/failure rates per HS6/corridor

SCALABILITY  
[ ] DB connection pooling verified under load
[ ] Async endpoint performance (p95 < 500ms)
[ ] Cache strategy for static rules/provenance
[ ] Horizontal scaling story (multiple uvicorn workers)

CONFIG & SECRETS
[ ] Environment variable coverage (no hardcoded values)
[ ] .env.example complete
[ ] Docker HEALTHCHECK endpoints
[ ] Graceful shutdown (finish inflight requests)

DEPLOYMENT
[ ] Dockerfile multi-stage build (<500MB final image)
[ ] docker-compose.prod.yml 
[ ] CI pipeline (lint → test → build → scan → deploy)
[ ] Rollback strategy documented

TESTING COVERAGE
[ ] pytest coverage >90% (extract from `pytest --cov`)
[ ] Property-based tests for edge-case rules
[ ] Load tests (100 concurrent assessments)
[ ] Chaos engineering (DB read replica lag simulation)
```

---

## Phase 3: NIM Integration Readiness

**CRITICAL gaps blocking NIM layer**:

```
NIM LAYER DEPENDENCIES (must exist before Prompt 1):
[ ] Stable assessment input contract (no breaking schema changes)
[ ] Stable assessment output contract (NIM explanation validation)
[ ] Audit persistence guaranteed (legal compliance)
[ ] Case workflow complete (conversational state)
[ ] Error responses structured (NIM clarification triggers)

INTERFACE STABILITY:
[ ] No recent schema changes in last 48 hours
[ ] Golden path integration tests pinned to exact data versions
[ ] All repos implement as_of_date parameter correctly
[ ] Evidence readiness scoring deterministic
```

---

## Phase 4: Risk Assessment

**HIGH RISK (>20% failure probability)**:
```
1. Data pipeline reliability - parser promotion failures block new HS6 coverage
2. Transaction isolation under concurrent load  
3. Audit completeness - missing evidence steps break legal traceability
4. Intelligence alert triggers - false positives erode trader trust
```

**BLOCKERS** (stop NIM work immediately):
```
1. Failing integration tests
2. Non-deterministic assessment outputs
3. Missing case workflow (NIM needs assessment state)
4. Incomplete evidence integration (NIM clarification depends on it)
```

---

## Deliverable Format

**Return exactly this structure**:

```markdown
# AFCFTA-LIVE REPO AUDIT: [TIMESTAMP]

## 🟢 COMPLETE (Production-ready)
- [List fully baked components]

## 🟡 PARTIAL (Works, needs hardening)  
- [List + specific gaps]

## 🔴 MISSING/BROKEN (Blocks NIM integration)
- [List + estimated fix time]

## 📊 PRODUCTION READINESS SCORES
| Category | Score | Rationale |
|----------|-------|-----------|
| Security | 6/10  | [Why] |
| Observability | 3/10 | [Why] |
| Scalability | 4/10 | [Why] |

## 🚫 CRITICAL BLOCKERS
1. [BLOCKER #1 with repro steps]
2. [BLOCKER #2 with repro steps]

## ✅ NIM READY CHECKLIST
- [ ] Assessment contract stable ✓/✗
- [ ] Case workflow complete ✓/✗  
- [ ] Evidence scoring inline ✓/✗
- [ ] Audit persistence guaranteed ✓/✗

## 🎯 RECOMMENDED FIX ORDER
```
1. [Highest priority blocker - 2hrs]
2. [Next blocker - 4hrs] 
3. [Hardening task - 1 day]
```

## 📈 HS6 COVERAGE ANALYSIS
```
Current: XXX products across XX corridors
Test coverage: XX golden cases
Expansion priority: [top 3 HS6 chapters]
```
```

---

## Execution Instructions

1. **Clone current repo state** `git checkout -b audit-$(date +%Y%m%d)`
2. **Run full test suite** `pytest tests/unit tests/integration --cov`
3. **Spin up local API** `uvicorn app.main:app --reload`
4. **Test golden path manually** 
   ```bash
   curl -X POST http://localhost:8000/v1/assessments \
   -H "Content-Type: application/json" \
   -d @tests/fixtures/golden_case_001.json | jq .
   ```
5. **Execute audit, return ONLY the exact deliverable format above**

**Timebox**: 45 minutes maximum. If you hit gaps you can't resolve, document them precisely with repro steps.

---
```
