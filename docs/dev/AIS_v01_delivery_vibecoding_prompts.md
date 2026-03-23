# AIS v0.1 Delivery Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Your AGENTS.md shell restriction still applies**: the coding agent creates
> and edits files; you run the commands yourself.
>
> **Primary references**:
> - docs/dev/delivery_plan_and_backlog.md for sequencing, scope, and dependencies
> - AGENTS.md for architecture invariants and shell restrictions
> - docs/FastAPI_layout.md for route/service/repository boundaries
> - docs/Expression_grammar.md when touching expression or evidence-related audit paths

---

## Prompt 1 — Enforce repeatable-read assessment transactions

```
Read AGENTS.md sections "Transaction Isolation", "Deterministic Engine Execution Order", and "Code Organization".
Read docs/dev/delivery_plan_and_backlog.md epic AIS-1 tickets AIS-101 and AIS-103.

Implement explicit REPEATABLE READ transaction handling for assessment execution.

Work in these files first:
- app/db/base.py
- app/db/session.py
- app/api/deps.py
- app/services/eligibility_service.py
- tests/unit/test_eligibility_service.py
- tests/integration/test_golden_path.py

Requirements:
1. Preserve the existing async SQLAlchemy setup.
2. Add a clean way to create an assessment-scoped session/transaction that uses REPEATABLE READ isolation.
3. Keep route handlers thin. Do not move business logic into app/api/v1/assessments.py.
4. Do not break existing non-assessment dependencies that use get_db().
5. Add focused tests that prove the new session/transaction path is used for assessments.
6. If the cleanest solution is a new dependency or helper context manager, add it in the db/session or api/deps layer.
7. Keep the change minimal and architecture-compliant.

When done, summarize:
- what isolation mechanism you implemented
- which code path uses it
- what tests were added or updated
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_golden_path.py -v
```
# Completed 23 March
---

## Prompt 2 — Pass assessment_date through status resolution

```
Read AGENTS.md sections "Transaction Isolation" and "Deterministic Engine Execution Order".
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-102.

Refactor status resolution so it uses the request's assessment date instead of date.today().

Work in these files first:
- app/repositories/status_repository.py
- app/services/status_service.py
- app/services/eligibility_service.py
- tests/unit/test_status_service.py
- tests/unit/test_eligibility_service.py
- tests/integration/test_status_repository.py

Requirements:
1. Add an explicit as_of_date parameter to the repository and service path.
2. Ensure eligibility assessments pass the same assessment_date already derived from request.year.
3. Preserve compatibility for non-assessment callers by making the default behavior explicit and safe.
4. Keep status overlay output shape unchanged unless a testable bug requires a schema update.
5. Add tests that prove status selection changes when the as_of_date changes.

When done, summarize:
- the new call signature
- where the as_of_date is threaded through
- the specific tests that prove the fix
```

**You run:**
```bash
python -m pytest tests/unit/test_status_service.py -v
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_status_repository.py -v
```
# Completed 23 March
---

## Prompt 3 — Add snapshot-consistency integration coverage

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-103.
Read tests/integration/test_golden_path.py and tests/integration/test_quick_slice_e2e.py to follow existing integration patterns.

Add integration tests that verify rules, tariffs, and statuses are resolved consistently for a fixed assessment snapshot.

Work in these files first:
- tests/integration/test_golden_path.py
- tests/integration/test_quick_slice_e2e.py
- tests/conftest.py if helpers are needed

Requirements:
1. Add targeted tests, not broad rewrites.
2. Cover at least one case where status timing matters.
3. Assert the final response still includes rule_status, tariff_outcome.status, and confidence_class.
4. Keep fixtures deterministic.

When done, summarize the new scenarios and the bug they would have caught before the refactor.
```

**You run:**
```bash
python -m pytest tests/integration/test_golden_path.py -v
python -m pytest tests/integration/test_quick_slice_e2e.py -v
```

---

## Prompt 4 — Review evidence lookup for assessment snapshot alignment

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-104.
Read app/services/evidence_service.py, app/repositories/evidence_repository.py, and app/services/eligibility_service.py.

Determine whether evidence lookup needs explicit assessment-date awareness to stay aligned with the assessment snapshot contract. If it does, implement the smallest correct refactor. If it does not, document the reasoning in code comments or tests where appropriate.

Requirements:
1. Do not invent date filtering unless the schema or logic justifies it.
2. If no code change is needed, add a test or explicit guard that captures the intended behavior.
3. Keep the output contract stable.

When done, summarize whether a code change was required and why.
```

**You run:**
```bash
python -m pytest tests/unit/test_evidence_service.py -v
python -m pytest tests/unit/test_eligibility_service.py -v
```

---

## Prompt 5 — Add a first-class assess-by-case API

```
Read docs/dev/delivery_plan_and_backlog.md epic AIS-2 tickets AIS-201 and AIS-204.
Read AGENTS.md section "Code Organization" and docs/FastAPI_layout.md.

Implement a case-centered assessment flow that loads facts from an existing case instead of requiring the caller to resubmit production_facts.

Work in these files first:
- app/api/v1/cases.py
- app/api/v1/assessments.py
- app/api/deps.py
- app/repositories/cases_repository.py
- app/services/eligibility_service.py
- app/schemas/cases.py
- app/schemas/assessments.py
- tests/unit/test_eligibility_service.py
- tests/integration/test_audit_api.py

Requirements:
1. Add a clean API shape for "assess this case".
2. Keep route handlers thin.
3. Reuse the existing normalization and orchestrator logic rather than duplicating assessment behavior.
4. Make sure stored case facts and direct request facts converge through the same normalization path.
5. Preserve the current direct assessment API.
6. Add tests for parity between direct-input and case-backed execution.

When done, summarize:
- the new endpoint or request mode
- how facts are loaded
- how parity is enforced
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_audit_api.py -v
```

---

## Prompt 6 — Auto-persist case-backed evaluations and add latest-evaluation retrieval

```
Read docs/dev/delivery_plan_and_backlog.md tickets AIS-202 and AIS-203.
Read app/repositories/evaluations_repository.py, app/services/audit_service.py, and app/api/v1/audit.py.

Complete the case workflow by ensuring case-backed assessments always persist evaluations and by adding a straightforward "latest evaluation for case" retrieval path.

Work in these files first:
- app/services/eligibility_service.py
- app/services/audit_service.py
- app/api/v1/audit.py
- app/repositories/evaluations_repository.py
- tests/integration/test_audit_api.py
- tests/integration/test_evaluations_repository.py

Requirements:
1. Persist successful and failed case-backed runs.
2. Add a case-oriented retrieval path that does not require the client to know evaluation_id in advance.
3. Do not break the existing audit endpoints.
4. Keep persistence atomic.

When done, summarize the persistence rules and the new retrieval flow.
```

**You run:**
```bash
python -m pytest tests/integration/test_evaluations_repository.py -v
python -m pytest tests/integration/test_audit_api.py -v
```

---

## Prompt 7 — Extend assessment inputs for submitted documents

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-301.
Read app/schemas/assessments.py, app/schemas/evidence.py, and app/services/evidence_service.py.

Extend the assessment request schema so callers can provide submitted document inventories as part of an assessment.

Work in these files first:
- app/schemas/assessments.py
- app/api/v1/assessments.py
- tests/unit/test_evidence_service.py
- tests/unit/test_eligibility_service.py

Requirements:
1. Add a backward-compatible request field for submitted documents.
2. Keep existing callers valid if they do not send the new field.
3. Choose a simple contract, for example a list of document type strings, unless the existing evidence model requires a richer shape.
4. Keep the field naming consistent with the current evidence service vocabulary.

When done, summarize the new request field and its compatibility behavior.
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/unit/test_evidence_service.py -v
```

---

## Prompt 8 — Compute readiness inside eligibility assessments

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-302.
Read AGENTS.md section "API Output Contract".
Read app/services/eligibility_service.py, app/services/evidence_service.py, app/schemas/assessments.py, and app/schemas/evidence.py.

Integrate evidence readiness into the main assessment flow using the submitted documents from the request.

Requirements:
1. Reuse EvidenceService rather than duplicating readiness logic.
2. Preserve the required v0.1 output fields: hs6_code, eligible, pathway_used, rule_status, tariff_outcome, failures, missing_facts, evidence_required, confidence_class.
3. Add readiness data in a backward-compatible way.
4. Keep evidence_required meaningful and derived from the actual evidence target selected by the rule/pathway logic.
5. Ensure missing evidence and readiness score are auditable or at least available for later audit integration.

Work in these files first:
- app/services/eligibility_service.py
- app/schemas/assessments.py
- app/services/evidence_service.py
- tests/unit/test_eligibility_service.py

When done, summarize the response changes and the exact evidence path used in assessments.
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
```

---

## Prompt 9 — Add evidence-readiness audit checks and integration coverage

```
Read docs/dev/delivery_plan_and_backlog.md tickets AIS-303 and AIS-304.
Read app/services/audit_service.py and tests/integration/test_audit_api.py.

Persist and replay evidence-readiness details as part of the audit trail, then add integration tests for complete and incomplete document packs.

Requirements:
1. Keep audit output structured and consistent with the existing replay model.
2. Do not overload existing check types with unrelated semantics.
3. Add focused integration coverage rather than broad fixture rewrites.

Work in these files first:
- app/services/eligibility_service.py
- app/services/audit_service.py
- app/schemas/audit.py if needed
- tests/integration/test_audit_api.py
- tests/integration/test_golden_path.py

When done, summarize the new audit evidence fields/checks and the new integration scenarios.
```

**You run:**
```bash
python -m pytest tests/integration/test_audit_api.py -v
python -m pytest tests/integration/test_golden_path.py -v
```

---

## Prompt 10 — Add source registry API endpoints

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-401.
Read docs/FastAPI_layout.md and app/repositories/sources_repository.py.

Add thin API endpoints for source registry lookup and listing.

Work in these files first:
- app/api/deps.py
- app/api/router.py
- app/api/v1/sources.py
- app/repositories/sources_repository.py
- app/schemas/sources.py
- tests/integration/test_sources_api.py (create if needed)

Requirements:
1. Keep route handlers thin and push logic into a dedicated service only if needed.
2. Support at least source detail by source_id and filtered list queries.
3. Reuse existing schemas where possible.
4. Wire the new router into the main API router.

When done, summarize the new endpoints and supported query filters.
```

**You run:**
```bash
python -m pytest tests/integration/test_sources_api.py -v
```

---

## Prompt 11 — Add legal provision API endpoints

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-402.
Read app/repositories/sources_repository.py and app/schemas/sources.py.

Add API endpoints for legal provision detail and filtered listing.

Work in these files first:
- app/api/v1/sources.py
- app/api/deps.py
- app/repositories/sources_repository.py
- app/schemas/sources.py
- tests/integration/test_sources_api.py

Requirements:
1. Support filtering by at least topic_primary and source_id.
2. Keep source and provision routes coherent under one API module unless there is a strong reason to split them.
3. Use the existing Pydantic response models.

When done, summarize the new provision endpoints and filters.
```

**You run:**
```bash
python -m pytest tests/integration/test_sources_api.py -v
```

---

## Prompt 12 — Surface provenance in rule and tariff responses

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-403.
Read app/api/v1/rules.py, app/api/v1/tariffs.py, app/schemas/rules.py, and app/schemas/tariffs.py.

Enrich rule and tariff responses with provenance references that already exist in the data layer.

Requirements:
1. Prefer adding explicit provenance identifiers or embedded source/provision summaries rather than opaque text.
2. Keep the existing response shape backward-compatible where practical.
3. Do not fake provenance where the underlying repository does not provide it; add repository columns cleanly if needed.
4. Preserve thin route handlers.

Work in these files first:
- app/repositories/rules_repository.py
- app/repositories/tariffs_repository.py
- app/schemas/rules.py
- app/schemas/tariffs.py
- app/api/v1/rules.py
- app/api/v1/tariffs.py
- tests/integration/test_rules_repository.py
- tests/integration/test_tariffs_repository.py

When done, summarize which provenance fields were added to which responses.
```

**You run:**
```bash
python -m pytest tests/integration/test_rules_repository.py -v
python -m pytest tests/integration/test_tariffs_repository.py -v
```

---

## Prompt 13 — Surface provenance in audit replay

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-404.
Read app/services/audit_service.py, app/schemas/audit.py, and the existing persisted check payload shapes.

Extend audit replay so relevant rule, tariff, evidence, or decision summaries expose provenance references where those references are already available.

Requirements:
1. Keep audit replay additive and backward-compatible where possible.
2. Avoid stuffing large unrelated payloads into atomic checks if a summary-level field is cleaner.
3. Add tests that prove provenance survives replay.

Work in these files first:
- app/services/audit_service.py
- app/schemas/audit.py
- tests/integration/test_audit_api.py

When done, summarize where provenance now appears in the audit trail.
```

**You run:**
```bash
python -m pytest tests/integration/test_audit_api.py -v
```

---

## Prompt 14 — Add corridor profile and alert listing APIs

```
Read docs/dev/delivery_plan_and_backlog.md tickets AIS-501 and AIS-502.
Read app/repositories/intelligence_repository.py and app/schemas/intelligence.py.

Add read-only intelligence APIs for corridor profiles and alert listing.

Work in these files first:
- app/api/deps.py
- app/api/router.py
- app/api/v1/intelligence.py
- app/repositories/intelligence_repository.py
- app/schemas/intelligence.py
- tests/integration/test_intelligence_api.py (create if needed)

Requirements:
1. Support corridor profile lookup by exporter/importer.
2. Support alert listing by status and severity at minimum.
3. Keep endpoints thin and repository-backed.

When done, summarize the new intelligence endpoints.
```

**You run:**
```bash
python -m pytest tests/integration/test_intelligence_api.py -v
```

---

## Prompt 15 — Build alert generation service

```
Read docs/dev/delivery_plan_and_backlog.md tickets AIS-503 and AIS-504.
Read app/db/models/intelligence.py, app/repositories/intelligence_repository.py, and app/services/eligibility_service.py.

Implement a minimal alert generation service for operationally significant conditions and decide how alerts should affect assessment outputs.

Requirements:
1. Add the smallest repository write surface needed to create alerts.
2. Trigger alerts only for clearly defined conditions such as pending-rule exposure, missing schedule coverage, or not-yet-operational corridor status.
3. Document in code whether alerts are advisory-only or affect confidence/warnings.
4. Keep the initial implementation narrow and testable.

Work in these files first:
- app/repositories/intelligence_repository.py
- app/services/intelligence_service.py (create if needed)
- app/services/eligibility_service.py
- tests/unit/test_eligibility_service.py
- tests/integration/test_intelligence_api.py

When done, summarize the trigger rules and how alerts interact with assessments.
```

**You run:**
```bash
python -m pytest tests/unit/test_eligibility_service.py -v
python -m pytest tests/integration/test_intelligence_api.py -v
```

---

## Prompt 16 — Standardize parser artifact contracts and validation gate

```
Read docs/dev/delivery_plan_and_backlog.md tickets AIS-601 and AIS-602.
Read the parser scripts and tests under scripts/parsers and tests/unit/test_*parser*.py.

Define and enforce stable contracts for decomposed rule components, pathway artifacts, and applicability artifacts. Then add a validation gate that prevents malformed parser outputs from being promoted.

Work in these files first:
- scripts/parsers/rule_decomposer.py
- scripts/parsers/pathway_builder.py
- scripts/parsers/applicability_builder.py
- scripts/parsers/validation_runner.py
- tests/unit/test_rule_decomposer_parser.py
- tests/unit/test_pathway_builder_parser.py
- tests/unit/test_applicability_builder_parser.py

Requirements:
1. Keep parser outputs aligned with the runtime schema and expression grammar.
2. Fail loudly and informatively on malformed artifacts.
3. Preserve verbatim legal text.
4. Do not introduce silent normalization that violates AGENTS.md invariants.

When done, summarize the artifact contracts and the validation failure behavior.
```

**You run:**
```bash
python -m pytest tests/unit/test_rule_decomposer_parser.py -v
python -m pytest tests/unit/test_pathway_builder_parser.py -v
python -m pytest tests/unit/test_applicability_builder_parser.py -v
```

---

## Prompt 17 — Build a repeatable staged-to-operational promotion workflow

```
Read docs/dev/delivery_plan_and_backlog.md ticket AIS-603.
Read scripts/parsers/psr_db_inserter.py and the current seed/parser workflow docs.

Turn the current parser promotion path into a more repeatable staged-to-operational workflow with clear validation and promotion steps.

Requirements:
1. Prefer improving the existing scripts and workflow documentation over introducing a large new framework.
2. Make failure points explicit.
3. Preserve idempotency where possible.
4. Document the expected input files, validation step, and promotion step.

Work in these files first:
- scripts/parsers/psr_db_inserter.py
- scripts/parsers/validation_runner.py
- docs/dev/delivery_plan_and_backlog.md only if a brief cross-reference is useful
- create a focused developer runbook under docs/dev if needed

When done, summarize the promotion workflow and the operator steps.
```

**You run:**
```bash
python -m pytest tests/unit/test_rule_decomposer_parser.py -v
python -m pytest tests/unit/test_pathway_builder_parser.py -v
python -m pytest tests/unit/test_applicability_builder_parser.py -v
```

---

## Prompt 18 — Prioritize the next HS6 tranche and expand live-backed coverage

```
Read docs/dev/delivery_plan_and_backlog.md epic AIS-7 tickets AIS-701 through AIS-704.
Read tests/fixtures/golden_cases.py, scripts/seed_data.py, and the existing integration tests.

Expand the live-backed product/corridor slice inside the locked v0.1 geography.

Requirements:
1. Start by selecting a small next tranche of HS6 products with meaningful corridor coverage.
2. Update the data/seed path needed to support them.
3. Add or expand golden cases.
4. Add integration scenarios for the expanded live slice.
5. Keep the work bounded; do not attempt broad country-scope expansion.

Work in these files first:
- scripts/seed_data.py
- scripts/seed_psr_rules.py if needed
- tests/fixtures/golden_cases.py
- tests/integration/test_golden_path.py
- tests/integration/test_quick_slice_e2e.py

When done, summarize:
- which HS6 products were added
- which corridors they cover
- which new golden/integration cases were added
```

**You run:**
```bash
python -m pytest tests/integration/test_golden_path.py -v
python -m pytest tests/integration/test_quick_slice_e2e.py -v
```

---

## Prompt 19 — Reconcile documentation with delivered behavior

```
Read docs/dev/delivery_plan_and_backlog.md epic AIS-8 tickets AIS-801 through AIS-803.
Read README.md, CHANGELOG.md, and the API/developer docs touched by the earlier prompts.

Update documentation so it matches the delivered runtime behavior.

Requirements:
1. Reconcile test-count and feature claims.
2. Document which layers are user-facing versus internal infrastructure.
3. Document the case-backed assessment workflow and any new provenance/intelligence endpoints.
4. Keep architecture docs unchanged unless a direct inconsistency must be corrected and the change is explicitly justified.

When done, summarize the documentation files updated and the specific mismatches corrected.
```

**You run:**
```bash
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

---

## Suggested Execution Groups

### Group 1 — Correctness Foundation
1. Prompt 1
2. Prompt 2
3. Prompt 3
4. Prompt 4

### Group 2 — Case Workflow
5. Prompt 5
6. Prompt 6

### Group 3 — Evidence In Decision Flow
7. Prompt 7
8. Prompt 8
9. Prompt 9

### Group 4 — Provenance Exposure
10. Prompt 10
11. Prompt 11
12. Prompt 12
13. Prompt 13

### Group 5 — Intelligence Activation
14. Prompt 14
15. Prompt 15

### Group 6 — Parser Operationalization
16. Prompt 16
17. Prompt 17

### Group 7 — Data Expansion And Docs
18. Prompt 18
19. Prompt 19