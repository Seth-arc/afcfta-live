# Delivery Plan By Milestone

## Planning Assumptions

- The current engine, APIs, and persistence base are already in place in [app/services/eligibility_service.py](app/services/eligibility_service.py), [app/api/v1](app/api/v1), and [app/repositories](app/repositories).
- The highest-value next steps are to harden runtime correctness, complete the case workflow, and expose already-built legal traceability and intelligence layers.
- This plan assumes incremental delivery on the existing v0.1 scope, not a continent-wide expansion.

## Milestone 1: Assessment Correctness Hardening

**Goal:** make every assessment legally and technically consistent with the project's architecture rules.

**Scope**
- Enforce repeatable-read transaction semantics for assessments
- Resolve status against the same assessment date as rules and tariffs
- Confirm evidence lookup also runs against the same request-time snapshot contract
- Add regression coverage for snapshot consistency and date-sensitive status behavior

**Primary outcome**
- The engine becomes architecture-compliant for deterministic single-snapshot evaluation

**Definition of done**
- Assessments run under explicit transaction isolation
- Status overlays no longer rely on implicit current-date behavior
- Integration tests prove consistent rule, tariff, and status resolution for a fixed assessment year

**Dependencies**
- Existing DB/session layer in [app/db/base.py](app/db/base.py) and [app/db/session.py](app/db/session.py)
- Existing status logic in [app/repositories/status_repository.py](app/repositories/status_repository.py)

---

## Milestone 2: Complete The Case-Centered Workflow

**Goal:** convert the platform from a stateless calculator into a proper case workflow.

**Scope**
- Add assess-by-case execution
- Load facts directly from stored case_input_fact rows
- Persist evaluations automatically for case-based runs
- Support "latest evaluation for case" as a standard retrieval flow
- Normalize the contract between case storage and assessment execution

**Primary outcome**
- A user can create a case once, run assessments repeatedly, and retrieve historical evaluations without resubmitting facts

**Definition of done**
- There is a first-class API flow from case creation to assessment to audit replay
- Assessment behavior from stored case facts matches direct-payload assessment behavior
- Audit persistence is automatic for case-backed runs

**Dependencies**
- Existing case endpoints in [app/api/v1/cases.py](app/api/v1/cases.py)
- Existing evaluation persistence in [app/repositories/evaluations_repository.py](app/repositories/evaluations_repository.py)
- Existing audit replay in [app/services/audit_service.py](app/services/audit_service.py)

---

## Milestone 3: Integrate Evidence Readiness Into The Main Decision Flow

**Goal:** make evidence a true operational output, not a side calculation.

**Scope**
- Extend assessment input to accept submitted documents
- Run readiness scoring during assessments
- Return required, missing, and completeness data alongside eligibility outcomes
- Align evidence outputs between the standalone endpoint and assessment endpoint

**Primary outcome**
- The engine answers both "is it eligible?" and "are we ready to support that claim?"

**Definition of done**
- Assessment requests can carry document inventories
- Assessment responses include missing evidence and readiness score
- Evidence API and assessment API produce aligned results for the same entity and persona

**Dependencies**
- Existing evidence service in [app/services/evidence_service.py](app/services/evidence_service.py)
- Existing evidence endpoint in [app/api/v1/evidence.py](app/api/v1/evidence.py)

---

## Milestone 4: Expose Provenance And Legal Traceability

**Goal:** promote legal/source traceability from internal infrastructure to a user-visible capability.

**Scope**
- Add source and legal provision API endpoints
- Surface provenance links in rule, tariff, evidence, and audit responses
- Provide a simple trace model showing which sources and provisions supported a decision

**Primary outcome**
- Users can inspect the legal basis of a result directly, not just trust internal storage

**Definition of done**
- Provenance endpoints are live
- Major decision outputs can link back to source/provision records
- Audit responses clearly expose legal traceability

**Dependencies**
- Provenance repository in [app/repositories/sources_repository.py](app/repositories/sources_repository.py)
- Provenance models in [app/db/models/sources.py](app/db/models/sources.py)

---

## Milestone 5: Activate The Intelligence Layer

**Goal:** turn corridor intelligence and alerts into a real product capability.

**Scope**
- Add corridor profile and alert endpoints
- Add an alert generation service for key conditions such as pending-rule exposure, missing schedule coverage, and corridor risk changes
- Decide whether alerts remain advisory or influence response metadata

**Primary outcome**
- The system can describe corridor-level operational risk, not just rule-level legal eligibility

**Definition of done**
- Intelligence endpoints are exposed
- Alerts can be created, listed, and associated with relevant entities or cases
- At least selected intelligence signals are visible in user workflows

**Dependencies**
- Intelligence repository in [app/repositories/intelligence_repository.py](app/repositories/intelligence_repository.py)
- Intelligence schema in [app/db/models/intelligence.py](app/db/models/intelligence.py)

---

## Milestone 6: Data Pipeline Operationalization

**Goal:** make rule and applicability ingestion reliable enough for systematic expansion.

**Scope**
- Standardize parser input/output contracts
- Add validation and promotion checkpoints for parser outputs
- Make ingestion repeatable from staged data into operational rule tables
- Improve diagnostics when parser rows cannot be promoted cleanly

**Primary outcome**
- Data expansion becomes a controlled pipeline rather than a set of one-off scripts

**Definition of done**
- Parser outputs are validated before load
- Promotion path from staged to operational data is documented and reproducible
- Failures are reportable and triageable

**Dependencies**
- Parser scripts in [scripts/parsers](scripts/parsers)
- Existing parser tests in [tests/unit](tests/unit)

---

## Milestone 7: Controlled Data Coverage Expansion

**Goal:** increase real product utility inside the current v0.1 geography.

**Scope**
- Expand HS6 product coverage
- Expand tariff/status/evidence records for existing supported countries
- Add golden cases and integration cases for new product/corridor combinations
- Prioritize operationally meaningful chapters before broad long-tail coverage

**Primary outcome**
- More real-world product/corridor combinations can be assessed without changing platform architecture

**Definition of done**
- Noticeable increase in supported live combinations
- Golden-case set materially expands
- Integration coverage grows with the data footprint

**Dependencies**
- Seed/data workflows in [scripts/seed_data.py](scripts/seed_data.py), [scripts/seed_psr_rules.py](scripts/seed_psr_rules.py), and [tests/fixtures/golden_cases.py](tests/fixtures/golden_cases.py)

---

## Suggested Milestone Sequence

1. Milestone 1: Assessment Correctness Hardening
2. Milestone 2: Complete The Case-Centered Workflow
3. Milestone 3: Integrate Evidence Readiness
4. Milestone 4: Expose Provenance
5. Milestone 5: Activate Intelligence
6. Milestone 6: Data Pipeline Operationalization
7. Milestone 7: Controlled Data Coverage Expansion

# Jira-Style Backlog

## Epic AIS-1: Assessment Correctness Hardening

**Objective:** enforce deterministic, single-snapshot assessment behavior.

### AIS-101 Enforce repeatable-read assessment transactions
**Type:** Story  
**Priority:** Highest  
**Story Points:** 5  
**Dependencies:** None

**Description**
Apply explicit transaction isolation for assessment execution so rules, tariffs, status, and evidence are resolved against one stable database snapshot.

**Acceptance Criteria**
- Assessment execution uses explicit transaction boundaries
- Isolation behavior is documented in the service layer
- Integration coverage proves stable reads across multi-step resolution

### AIS-102 Pass assessment date through status resolution
**Type:** Story  
**Priority:** Highest  
**Story Points:** 3  
**Dependencies:** AIS-101

**Description**
Refactor status lookup so it resolves against the request's assessment date instead of implicit current date.

**Acceptance Criteria**
- Status repository accepts an as-of date
- Eligibility assessment passes assessment_date consistently
- Existing behavior is preserved for non-assessment callers or explicitly updated

### AIS-103 Add snapshot-consistency integration tests
**Type:** Story  
**Priority:** High  
**Story Points:** 3  
**Dependencies:** AIS-101, AIS-102

**Description**
Add integration tests covering date-sensitive rules, tariffs, and statuses under one assessment request.

**Acceptance Criteria**
- Tests fail under inconsistent date behavior
- Tests pass with aligned assessment snapshot handling

### AIS-104 Review evidence lookup for snapshot alignment
**Type:** Task  
**Priority:** Medium  
**Story Points:** 2  
**Dependencies:** AIS-101

**Description**
Confirm evidence resolution does not drift from the assessment-time contract and adjust if required.

**Acceptance Criteria**
- Evidence lookup behavior is explicitly defined for assessment date handling
- Any necessary refactor is covered by tests

---

## Epic AIS-2: Case-Centered Workflow Completion

**Objective:** make case storage and assessment execution one coherent workflow.

### AIS-201 Add assess-by-case API
**Type:** Story  
**Priority:** Highest  
**Story Points:** 5  
**Dependencies:** AIS-101, AIS-102

**Description**
Create an API path that runs an assessment directly from a stored case and its facts.

**Acceptance Criteria**
- Endpoint accepts case identifier
- Stored case facts are loaded automatically
- Response matches direct-assessment response shape where applicable

### AIS-202 Auto-persist evaluations for case-backed assessments
**Type:** Story  
**Priority:** High  
**Story Points:** 3  
**Dependencies:** AIS-201

**Description**
Ensure case-backed assessments always persist evaluation and audit records without requiring extra caller coordination.

**Acceptance Criteria**
- Persisted evaluation exists for successful and failed case-backed assessments
- Audit replay works immediately after execution

### AIS-203 Add latest-evaluation-for-case retrieval flow
**Type:** Story  
**Priority:** High  
**Story Points:** 3  
**Dependencies:** AIS-202

**Description**
Support retrieving the latest evaluation summary and full audit trail for a case without requiring users to know the evaluation identifier first.

**Acceptance Criteria**
- Latest evaluation can be queried by case
- Audit replay can be resolved by case in a standard way

### AIS-204 Align case fact normalization with direct assessment inputs
**Type:** Task  
**Priority:** Medium  
**Story Points:** 2  
**Dependencies:** AIS-201

**Description**
Ensure stored case facts and direct request payload facts are normalized identically before evaluation.

**Acceptance Criteria**
- Same logical inputs produce same result in both flows
- Regression tests cover equivalence

---

## Epic AIS-3: Evidence In The Decision Flow

**Objective:** make evidence readiness part of the main assessment experience.

### AIS-301 Extend assessment request to include submitted documents
**Type:** Story  
**Priority:** High  
**Story Points:** 3  
**Dependencies:** AIS-201

**Description**
Add a document inventory to the assessment request contract.

**Acceptance Criteria**
- Request schema supports submitted documents
- Backward compatibility is preserved or clearly versioned

### AIS-302 Compute readiness in assessments
**Type:** Story  
**Priority:** High  
**Story Points:** 5  
**Dependencies:** AIS-301, AIS-104

**Description**
Use submitted documents to calculate missing evidence and readiness score during eligibility assessment.

**Acceptance Criteria**
- Assessment response includes required evidence, missing evidence, and readiness score
- Results align with standalone evidence endpoint behavior

### AIS-303 Add readiness-related audit checks
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3  
**Dependencies:** AIS-302, AIS-202

**Description**
Persist evidence-readiness steps in the audit trail so evidence-related decisions are replayable.

**Acceptance Criteria**
- Evidence completeness decisions appear in audit replay
- Atomic checks or summary checks are persisted consistently

### AIS-304 Update evidence integration coverage
**Type:** Task  
**Priority:** Medium  
**Story Points:** 2  
**Dependencies:** AIS-302, AIS-303

**Description**
Add integration cases for assessments with complete and incomplete document inventories.

**Acceptance Criteria**
- Tests cover both passing and failing readiness scenarios

---

## Epic AIS-4: Provenance Exposure

**Objective:** expose legal/source traceability as a first-class API capability.

### AIS-401 Add source registry API endpoints
**Type:** Story  
**Priority:** High  
**Story Points:** 3  
**Dependencies:** None

**Description**
Expose source lookup/list operations for ingested legal and operational sources.

**Acceptance Criteria**
- Source list and source detail endpoints exist
- Returned shape aligns with provenance schemas

### AIS-402 Add legal provision API endpoints
**Type:** Story  
**Priority:** High  
**Story Points:** 3  
**Dependencies:** AIS-401

**Description**
Expose legal provision lookup/list operations by topic and source.

**Acceptance Criteria**
- Provision detail and filtered listing exist
- Topic/source queries are supported

### AIS-403 Surface provenance in rule responses
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5  
**Dependencies:** AIS-401, AIS-402

**Description**
Enrich rule and tariff responses with source/provision references where available.

**Acceptance Criteria**
- Rule response includes clear provenance identifiers or embedded provenance objects
- Traceability is discoverable without separate DB inspection

### AIS-404 Surface provenance in audit replay
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5  
**Dependencies:** AIS-402, AIS-202

**Description**
Include supporting source/provision context in audit traces where the decision layer already carries those links.

**Acceptance Criteria**
- Audit response exposes provenance references for relevant checks or summaries

---

## Epic AIS-5: Intelligence And Alerts

**Objective:** activate corridor intelligence and alerting as usable capabilities.

### AIS-501 Add corridor profile API
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3  
**Dependencies:** None

**Description**
Expose corridor profile retrieval for supported exporter-importer pairs.

**Acceptance Criteria**
- Endpoint returns active corridor profile
- Missing profile behavior is defined clearly

### AIS-502 Add alert listing API
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3  
**Dependencies:** None

**Description**
Expose open and acknowledged alerts by entity, severity, and status.

**Acceptance Criteria**
- API supports basic alert filtering
- Response aligns with intelligence schemas

### AIS-503 Build alert generation service
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5  
**Dependencies:** AIS-501, AIS-502

**Description**
Create a service that emits alerts for operationally significant conditions such as pending-rule exposure or schedule gaps.

**Acceptance Criteria**
- Alerts can be generated from defined trigger conditions
- Trigger logic is covered by tests

### AIS-504 Decide alert impact on assessment outputs
**Type:** Task  
**Priority:** Medium  
**Story Points:** 2  
**Dependencies:** AIS-503

**Description**
Define whether alerts are informational only or should influence confidence or warning outputs.

**Acceptance Criteria**
- Product rule is documented
- Implementation reflects the chosen policy

---

## Epic AIS-6: Parser And Ingestion Operationalization

**Objective:** make data promotion reliable and repeatable.

### AIS-601 Standardize parser artifact contracts
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3  
**Dependencies:** None

**Description**
Define stable contracts for decomposed components, pathways, and applicability artifacts.

**Acceptance Criteria**
- Contracts are documented
- Validation rules are explicit

### AIS-602 Add parser output validation gate
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5  
**Dependencies:** AIS-601

**Description**
Prevent malformed parser outputs from being promoted into operational tables without clear diagnostics.

**Acceptance Criteria**
- Invalid rows are reported with actionable diagnostics
- Promotion fails cleanly when validation thresholds are exceeded

### AIS-603 Build repeatable staged-to-operational promotion workflow
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5  
**Dependencies:** AIS-601, AIS-602

**Description**
Turn the current script sequence into a reproducible ingestion workflow with clear steps and expected outputs.

**Acceptance Criteria**
- End-to-end flow from staged artifacts to operational data is documented and testable
- Operators can repeat the workflow consistently

### AIS-604 Expand parser regression fixtures
**Type:** Task  
**Priority:** Medium  
**Story Points:** 3  
**Dependencies:** AIS-601

**Description**
Add more fixed fixtures for parser edge cases, especially OR-pathway alternation and pending/manual-review constructs.

**Acceptance Criteria**
- Fixture coverage expands for known tricky rule patterns

---

## Epic AIS-7: Data Coverage Expansion

**Objective:** expand practical utility within the locked v0.1 geography.

### AIS-701 Prioritize next HS6 product set
**Type:** Task  
**Priority:** Medium  
**Story Points:** 2  
**Dependencies:** None

**Description**
Select the next tranche of HS6 products based on operational importance and current corridor coverage gaps.

**Acceptance Criteria**
- Prioritized product list exists
- Coverage criteria are explicit

### AIS-702 Expand rule/tariff/status/evidence records for selected tranche
**Type:** Story  
**Priority:** Medium  
**Story Points:** 8  
**Dependencies:** AIS-701, AIS-603

**Description**
Load the next set of product/corridor combinations across the core decision layers.

**Acceptance Criteria**
- Selected combinations are resolvable end-to-end
- Data can support rule lookup, tariff lookup, assessment, and evidence output

### AIS-703 Expand golden cases
**Type:** Story  
**Priority:** Medium  
**Story Points:** 3  
**Dependencies:** AIS-702

**Description**
Increase acceptance fixtures to cover newly onboarded products and corridors.

**Acceptance Criteria**
- Golden cases reflect the expanded live slice
- Expected outputs are explicit and stable

### AIS-704 Expand integration coverage with live-backed assessments
**Type:** Story  
**Priority:** Medium  
**Story Points:** 5  
**Dependencies:** AIS-702, AIS-703

**Description**
Add integration scenarios for newly supported combinations.

**Acceptance Criteria**
- New live-backed end-to-end tests exist for the expanded data slice

---

## Epic AIS-8: Documentation And Developer Alignment

**Objective:** keep implementation, tests, and documentation synchronized.

### AIS-801 Reconcile README and changelog claims
**Type:** Task  
**Priority:** Low  
**Story Points:** 1  
**Dependencies:** None

**Description**
Align test-count and feature claims across project-facing documentation.

**Acceptance Criteria**
- Top-level docs no longer contradict each other

### AIS-802 Document exposed vs internal-only layers
**Type:** Task  
**Priority:** Low  
**Story Points:** 2  
**Dependencies:** AIS-401, AIS-501

**Description**
Clarify which schema/repository layers are already product features and which are internal foundations.

**Acceptance Criteria**
- Docs distinguish runtime-exposed capabilities from internal infrastructure

### AIS-803 Document case-backed assessment workflow
**Type:** Task  
**Priority:** Low  
**Story Points:** 2  
**Dependencies:** AIS-201, AIS-202, AIS-203

**Description**
Document the intended case lifecycle once the case-centered flow is implemented.

**Acceptance Criteria**
- Developer and API docs reflect the actual case workflow

# Recommended Sprint Grouping

## Sprint 1
- AIS-101
- AIS-102
- AIS-103
- AIS-201

## Sprint 2
- AIS-202
- AIS-203
- AIS-204
- AIS-301
- AIS-302

## Sprint 3
- AIS-303
- AIS-401
- AIS-402
- AIS-403
- AIS-404

## Sprint 4
- AIS-501
- AIS-502
- AIS-503
- AIS-601
- AIS-602

## Sprint 5
- AIS-603
- AIS-604
- AIS-701
- AIS-702
- AIS-703
- AIS-704

## Sprint 6
- AIS-504
- AIS-801
- AIS-802
- AIS-803

# Dependency Summary

## Critical Path

1. AIS-101
2. AIS-102
3. AIS-201
4. AIS-202
5. AIS-301
6. AIS-302
7. AIS-303

## Major Dependency Chains

- Assessment correctness chain: AIS-101 -> AIS-102 -> AIS-103
- Case workflow chain: AIS-101 -> AIS-102 -> AIS-201 -> AIS-202 -> AIS-203
- Evidence-in-decision chain: AIS-104 -> AIS-301 -> AIS-302 -> AIS-303 -> AIS-304
- Provenance exposure chain: AIS-401 -> AIS-402 -> AIS-403 and AIS-404
- Intelligence activation chain: AIS-501 and AIS-502 -> AIS-503 -> AIS-504
- Parser operationalization chain: AIS-601 -> AIS-602 -> AIS-603
- Data expansion chain: AIS-701 and AIS-603 -> AIS-702 -> AIS-703 -> AIS-704

## Estimated Epic Totals

| Epic | Total Story Points |
|---|---:|
| AIS-1 Assessment Correctness Hardening | 13 |
| AIS-2 Case-Centered Workflow Completion | 13 |
| AIS-3 Evidence In The Decision Flow | 13 |
| AIS-4 Provenance Exposure | 16 |
| AIS-5 Intelligence And Alerts | 13 |
| AIS-6 Parser And Ingestion Operationalization | 16 |
| AIS-7 Data Coverage Expansion | 18 |
| AIS-8 Documentation And Developer Alignment | 5 |
| **Total** | **107** |

# Suggested Delivery Logic

1. First harden correctness.
2. Then complete the case workflow.
3. Then enrich the decision with evidence.
4. Then expose provenance.
5. Then activate intelligence.
6. Then industrialize ingestion.
7. Then expand data breadth.