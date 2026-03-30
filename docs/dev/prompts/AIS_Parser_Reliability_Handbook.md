# AIS Parser Reliability Build Handbook

> Goal: harden the Appendix IV parser build so parser-generated data becomes a stable contract for repositories, services, and the assessment API.
>
> Time estimate: 2-4 working days
>
> Prerequisite: the Appendix IV parser pipeline has been built, parser output has been loaded into PostgreSQL, and the existing quick-slice integration tests can run against the live database.

---

## Table of contents

1. [What this phase is](#1-what-this-phase-is)
2. [Why this phase is next](#2-why-this-phase-is-next)
3. [Scope and non-goals](#3-scope-and-non-goals)
4. [Build sequence](#4-build-sequence)
5. [Workstream A - Repository integration coverage](#5-workstream-a---repository-integration-coverage)
6. [Workstream B - Parser acceptance coverage](#6-workstream-b---parser-acceptance-coverage)
7. [Workstream C - End-to-end assessment expansion](#7-workstream-c---end-to-end-assessment-expansion)
8. [Workstream D - Audit trace verification](#8-workstream-d---audit-trace-verification)
9. [Validation checklist](#9-validation-checklist)
10. [Definition of done](#10-definition-of-done)
11. [Suggested commit sequence](#11-suggested-commit-sequence)

---

## 1. What this phase is

The engine, parser modules, and core API surface already exist. The highest-value remaining work is not a new service. It is proving that parser-generated rules resolve, persist, and execute correctly across the full stack.

This phase treats parser output as production data, not a one-off import artifact.

The objective is to make these four layers agree with each other:

1. CSV output from the parser modules in `scripts/parsers/`
2. Loaded rows in `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway`, and `hs6_psr_applicability`
3. Repository resolution behavior in `app/repositories/`
4. Live outcomes from `POST /api/v1/assessments` and the audit endpoints

---

## 2. Why this phase is next

The current repository state already includes:

- Parser modules in `scripts/parsers/`
- Assessment orchestration in `app/services/eligibility_service.py`
- Audit reconstruction in `app/services/audit_service.py`
- Live API routes in `app/api/v1/assessments.py` and `app/api/v1/audit.py`
- Unit coverage for services in `tests/unit/`
- Live integration coverage in `tests/integration/test_quick_slice_e2e.py` and `tests/integration/test_golden_path.py`

What is still thin is the contract between parsed data and runtime behavior.

The main failure modes this phase is meant to catch are:

1. Wrong PSR selected because applicability precedence is wrong
2. Wrong tariff line selected because repository matching is too narrow
3. Parser-generated pathways that look valid in CSVs but are not executable in the engine
4. Persisted audit trails that do not reconstruct the actual decision path
5. Integration tests that only pass for the original quick-slice products and not for parser-era coverage

---

## 3. Scope and non-goals

### In scope

- Repository integration tests
- Parser fixture and acceptance tests
- Expanded parser-era assessment tests
- Audit trace verification for persisted evaluations
- Small bug fixes exposed by the new tests

### Not in scope

- New API endpoints
- New database tables or migrations
- Frontend work
- New countries or corridors outside v0.1
- Rewriting locked architecture documents
- Broad refactors unrelated to parser-backed correctness

---

## 4. Build sequence

Do this phase in the following order. The order matters because each step reduces ambiguity for the next one.

```text
Step 1: Repository integration tests
   ↓
Step 2: Parser fixture tests
   ↓
Step 3: Expanded live assessment integration tests
   ↓
Step 4: Audit endpoint and persistence verification
```

Reasoning:

- If repository precedence is wrong, end-to-end tests are noisy and hard to trust.
- If parser fixture tests are missing, regressions in decomposition and pathway generation will only show up late.
- If assessment tests are expanded before repository behavior is pinned down, failures will be difficult to diagnose.
- Audit tests belong last because they verify the trace of behavior that earlier steps have already stabilized.

---

## 5. Workstream A - Repository integration coverage

### Goal

Prove that data resolution is correct before it reaches the service layer.

### Files to create

- `tests/integration/test_rules_repository.py`
- `tests/integration/test_tariffs_repository.py`
- `tests/integration/test_status_repository.py`
- `tests/integration/test_evaluations_repository.py`
- `tests/integration/test_hs_repository.py`

### A1. Rules repository

Target file: `app/repositories/rules_repository.py`

What to verify:

1. HS6 lookup resolves through `hs6_psr_applicability`, not live inheritance logic
2. Specificity precedence is correct:
   - direct subheading
   - range
   - inherited heading
   - inherited chapter
3. Returned pathways are ordered by `priority_rank`
4. Parser-generated `pending`, `PROCESS`, and `NOTE` cases are returned intact

Minimum assertions:

- returned `psr_id` matches the winning applicability row
- returned pathways include expected `pathway_code` values
- `priority_rank` order is deterministic
- `rule_status` is surfaced exactly as stored

### A2. Tariffs repository

Target file: `app/repositories/tariffs_repository.py`

What to verify:

1. HS6 requests match tariff schedule lines even when stored at 8-digit or 10-digit depth
2. year filtering uses the correct `calendar_year`
3. corridor filtering uses exporter and importer correctly
4. missing tariff schedules fail cleanly

Minimum assertions:

- correct schedule header and rate row selected
- correct base and preferential rate pair returned
- no false positive when the corridor or year does not match

### A3. Status repository

Target file: `app/repositories/status_repository.py`

What to verify:

1. corridor overlays resolve correctly
2. rule overlays resolve correctly
3. effective and expiry date windows are applied correctly
4. no overlay is returned when the assertion is out of date

### A4. Evaluations repository

Target files:

- `app/repositories/evaluations_repository.py`
- `app/repositories/cases_repository.py`

What to verify:

1. evaluation header rows persist correctly
2. atomic check rows persist correctly
3. evaluation plus checks can be retrieved together
4. case evaluation history returns newest first

### A5. HS repository

Target file: `app/repositories/hs_repository.py`

What to verify:

1. HS8 and HS10 inputs truncate to HS6 correctly
2. canonical HS2017 resolution returns the expected product
3. unsupported codes fail cleanly

---

## 6. Workstream B - Parser acceptance coverage

### Goal

Make the parser modules testable without requiring the full PDF or a live database.

### Files to create

- `tests/unit/test_rule_decomposer_parser.py`
- `tests/unit/test_pathway_builder_parser.py`
- `tests/unit/test_applicability_builder_parser.py`

### Supporting fixtures to add

- `tests/fixtures/appendix_iv_decomposer_cases.json`
- `tests/fixtures/appendix_iv_pathway_cases.json`
- `tests/fixtures/appendix_iv_applicability_cases.json`

### B1. Rule decomposer coverage

Target file: `scripts/parsers/rule_decomposer.py`

Must cover:

1. `WO`
2. `CTH`
3. `CTSH`
4. `CC`
5. `VNM`
6. `VA`
7. `PROCESS`
8. `NOTE`
9. compound `AND`
10. compound `OR`
11. `Yet to be agreed` pending handling

Critical assertions:

- correct `component_type`
- correct `operator_type`
- correct threshold extraction
- correct `tariff_shift_level`
- correct confidence buckets

### B2. Pathway builder coverage

Target file: `scripts/parsers/pathway_builder.py`

Must cover:

1. one pathway for standalone components
2. multiple pathways for OR alternatives
3. one `all` expression for AND combinations
4. correct `expression_json` shape for `WO`, `CTH`, `CTSH`, `VNM`, and `VA`
5. non-executable wrapper behavior for `PROCESS` and `NOTE`

Critical assertions:

- `pathway_code`
- `priority_rank`
- `variables`
- exact `expression.op`
- presence or absence of nested executable expressions

### B3. Applicability builder coverage

Target file: `scripts/parsers/applicability_builder.py`

Must cover:

1. direct subheading match
2. range match
3. inherited heading match
4. inherited chapter match
5. most-specific-wins behavior

Critical assertions:

- winning `psr_hs_code`
- `applicability_type`
- `priority_rank`
- no duplicate winner for the same HS6 code

---

## 7. Workstream C - End-to-end assessment expansion

### Goal

Expand live assessment coverage beyond the original quick-slice rules and ensure the parser-era database still drives correct outcomes.

### Primary target

- `tests/integration/test_quick_slice_e2e.py`

### Existing state

This file already includes the original quick-slice cases and parser-era chapter coverage additions. Continue to use dynamic candidate selection instead of hard-coding fragile assumptions when the live dataset may evolve.

### What to strengthen

1. textile case from chapters 50-63
2. chemical case from chapters 28-29
3. machinery case from chapter 84
4. agricultural case from chapters 06-08
5. at least one OR-alternative case where the first pathway fails and a later one passes
6. at least one pending-status case that blocks before pathway evaluation

### Rules for assertions

1. Do not change test intent to fit bad data
2. Prefer asserting behavior, not incidental labels
3. Where parser output may vary, assert membership rather than exact string equality for pathway codes
4. For failures, assert canonical failure codes from `app/core/failure_codes.py`

### Secondary target

- `tests/integration/test_golden_path.py`

What to strengthen:

1. one parser-era OR-alternative scenario
2. one provisional or incomplete confidence scenario
3. continued coverage of core API response shape

---

## 8. Workstream D - Audit trace verification

### Goal

Prove that persisted evaluations accurately reconstruct the decision path seen by the live assessment API.

### Files to expand or create

- expand `tests/unit/test_audit_service.py`
- create `tests/integration/test_audit_api.py`

### D1. Audit service unit coverage

Target file: `app/services/audit_service.py`

Must verify:

1. classification trace reconstruction
2. PSR resolution trace reconstruction
3. pathway grouping under pathway summaries
4. general rules summary reconstruction
5. tariff outcome reconstruction
6. evidence readiness reconstruction
7. final decision reconstruction
8. parser-generated non-executable pathways remain visible in the stored trace model where appropriate

### D2. Audit API integration coverage

Target route file: `app/api/v1/audit.py`

Must verify:

1. `GET /api/v1/audit/evaluations/{evaluation_id}` returns a full trail
2. `GET /api/v1/audit/cases/{case_id}/evaluations` returns ordered evaluation history
3. stored checks include classification, rule, pathway, status, tariff, evidence, and final decision stages

---

## 9. Validation checklist

Use this checklist before considering the phase complete.

### Repository layer

- rules repository precedence is covered
- tariff repository year and corridor filtering is covered
- status repository time-window behavior is covered
- evaluations repository persistence and replay is covered
- HS resolution truncation behavior is covered

### Parser layer

- decomposition test fixtures cover all major component types
- pathway fixture tests cover standalone, AND, OR, and non-executable pathways
- applicability fixture tests cover direct, range, heading, and chapter precedence

### API layer

- quick-slice live integration tests still pass against parser-loaded data
- parser-era chapter coverage exists in live assessment tests
- audit trail API is exercised end to end

### Behavioral invariants

- no test relies on raw HS text joins
- no test assumes missing facts are silently defaulted
- no test bypasses the status-aware output contract
- non-executable parser pathways are skipped by runtime evaluation but remain traceable

---

## 10. Definition of done

This phase is done when all of the following are true:

1. Repository precedence and join behavior are directly tested
2. Parser transformations are tested with fixed fixtures
3. Live integration tests cover parser-era chapters beyond the original quick slice
4. Audit persistence and replay are verified end to end
5. Any defects uncovered by this work are fixed at the repository or parser boundary, not patched only at the endpoint layer

If a test fails because live parser data is malformed, fix the parser or repository logic. Do not weaken the contract to make the suite pass.

---

## 11. Suggested commit sequence

Use small, phase-aligned commits.

```text
test: add repository integration coverage for parser-backed resolution
test: add parser fixture coverage for decomposition and pathway building
test: expand parser-era assessment integration coverage
test: add audit persistence and replay integration coverage
fix: resolve parser or repository defects exposed by reliability tests
```

---

## Execution notes

The human operator runs the test commands locally. This repository's agent instructions explicitly prohibit running `pytest` from the agent environment.

Recommended local validation order:

```bash
python -m pytest tests/integration/test_rules_repository.py -v
python -m pytest tests/unit/test_rule_decomposer_parser.py -v
python -m pytest tests/unit/test_pathway_builder_parser.py -v
python -m pytest tests/unit/test_applicability_builder_parser.py -v
python -m pytest tests/integration/test_quick_slice_e2e.py -v
python -m pytest tests/integration/test_audit_api.py -v
```

If failures appear, fix the lowest layer first:

1. parser fixture logic
2. repository query behavior
3. service orchestration
4. endpoint assertions