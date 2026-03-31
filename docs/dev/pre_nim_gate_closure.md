# Pre-NIM Gate Closure

Operator checklist for the March 30, 2026 contract-freeze and gate rerun.

Use this document together with:

- `AGENTS.md`
- `docs/dev/production_runbook.md`
- `tests/unit/test_contract_freeze.py`
- `tests/contract_constants.py`

This gate is not complete until the current head has passed the full rerun suite
and the resulting artifact bundle has been published from the current commit.

---

## 1. Frozen Public Surface

Treat the following public contracts as frozen on the March 30, 2026 head:

### Assessment request and response

- `app/schemas/assessments.py`
  - `EligibilityRequest`
  - `CaseAssessmentRequest`
  - `TariffOutcomeResponse`
  - `EligibilityAssessmentResponse`
- `app/schemas/cases.py`
  - `CaseCreateAssessmentOptions`
  - `CaseCreateRequest`
  - `CaseCreateResponse`

### Audit replay contract

- `app/schemas/audit.py`
  - `AuditTrail`
  - `FinalDecisionTrace`
  - `AuditTariffOutcomeTrace`
  - provenance trace models exposed through audit replay

### Assistant request and response envelope

- `app/schemas/nim/assistant.py`
  - `AssistantContext`
  - `AssistantRequest`
  - `ClarificationResponse`
  - `AssistantError`
  - `AssistantResponseEnvelope`

### Clarification and explanation schemas

- `app/schemas/nim/clarification.py`
  - `ClarificationContext`
- `app/schemas/nim/explanation.py`
  - `ExplanationContext`
  - `ExplanationResult`

### Intake schema set

- `app/schemas/nim/intake.py`
  - `HS6Candidate`
  - `TradeFlow`
  - `AssessmentContext`
  - `MaterialInput`
  - `ProductionFacts`
  - `NimConfidence`
  - `NimAssessmentDraft`

The freeze mechanism remains the existing contract suite in
`tests/unit/test_contract_freeze.py`, backed by
`tests/contract_constants.py`. Do not create a parallel freeze policy.

`AGENTS.md` is now restored and published again at the repo root. Treat it as
part of the operator-facing contract during this freeze window.

---

## 2. What Resets The Freeze

Any of the following requires a fresh full gate rerun:

- adding, removing, or renaming a field on any frozen schema
- changing field order where `tests/contract_constants.py` pins order
- changing required vs optional behavior
- changing accepted aliases or canonical field names
- changing discriminator values such as assistant `response_type`
- changing the serialized top-level response shape for assessments, audit replay, or assistant responses
- changing validation rules in a way that alters the public request or response contract

Internal refactors do not reset the freeze if they leave the observable schema,
serialized field set, and validation semantics unchanged.

---

## 3. Canonical March 30 Rerun Path

Recommended local rerun command:

```bash
python scripts/local_gate_runner.py --host 127.0.0.1 --port 8002 --api-key <API_KEY>
```

Run it only from a clean commit. `scripts/run_verification.py` now refuses a
dirty worktree unless `--allow-dirty` is passed for a diagnostic-only run that
cannot start the freeze window.

What it does:

- seeds deterministic fixture data unless `--skip-seed` is passed
- starts a local API with the March 30 gate defaults
- delegates to `scripts/run_verification.py`
- writes the canonical manual artifact bundle to `artifacts/verification/<git-sha>/`

The March 30 gate defaults for load runs are:

- `RATE_LIMIT_ENABLED=false`
- `LOG_REQUESTS_ENABLED=false`
- `CACHE_STATIC_LOOKUPS=true`
- `CACHE_STATUS_LOOKUPS=true`
- `UVICORN_WORKERS=4`
- `DB_POOL_SIZE=8`
- `DB_POOL_MAX_OVERFLOW=8`

Raw verification entry point when the API is already running:

```bash
python scripts/run_verification.py --base-url http://127.0.0.1:8002 --api-key <API_KEY>
```

---

## 4. Artifact Bundle To Publish

Publish the entire `artifacts/verification/<git-sha>/` directory produced by the
rerun. At minimum, review and retain:

- `manifest.json`
- `database-preflight.log`
- `unit-tests.xml`
- `unit-coverage.xml`
- `integration-tests.xml`
- `integration-coverage.xml`
- `assistant-nim-tests.xml`
- `assistant-nim-coverage.xml`
- `load-report-warmup.json`
- `load-report-ci.json`
- `load-report-ci-compare.log`
- `load-report-100.json`
- `load-report-100-compare.log`

If a March 30 rerun is accepted as the new load baseline, deliberately refresh:

- `tests/load/baseline.json`
- `tests/load/baseline_100c.json`

Do not update either baseline file from a failing or partial run.

---

## 5. Current March 30 Ledger

Populate this ledger only after executing the rerun on the current head.

| Gate | Status | Evidence |
|---|---|---|
| Contract freeze test suite | `PENDING LOCAL RERUN` | `tests/unit/test_contract_freeze.py` |
| Unit suite | `PENDING LOCAL RERUN` | `artifacts/verification/<git-sha>/unit-tests.xml` and `unit-coverage.xml` |
| Integration suite | `PENDING LOCAL RERUN` | `artifacts/verification/<git-sha>/integration-tests.xml` and `integration-coverage.xml` |
| Assistant/NIM suite | `PENDING LOCAL RERUN` | `artifacts/verification/<git-sha>/assistant-nim-tests.xml` and `assistant-nim-coverage.xml` |
| 10c load gate | `PENDING LOCAL RERUN` | `artifacts/verification/<git-sha>/load-report-ci.json` and `load-report-ci-compare.log` |
| 100c load gate | `PENDING LOCAL RERUN` | `artifacts/verification/<git-sha>/load-report-100.json` and `load-report-100-compare.log` |
| Artifact publication | `PENDING LOCAL RERUN` | `artifacts/verification/<git-sha>/manifest.json` |

Do not mark this ledger passed from the older March 25 or March 26 evidence.

---

## 6. Current Repo Truth On March 30, 2026

These statements are true on the current repo head and do not require the rerun
to infer:

- public contract freeze tests remain the canonical freeze mechanism
- `AGENTS.md` is restored and published at the repo root
- the parser confidence gate was tightened in `scripts/parsers/validation_runner.py`
- the published intelligence corridor profile surface is explicitly narrowed to the seeded active pairs
- the load harness now emits `load-report-warmup.json`, `load-report-ci.json`, and `load-report-100.json`
- the 100c gate now enforces baseline-relative latency comparison (`+50%` tolerance) and minimum success rate (`>=95%`) without an additional absolute p95 cap
- static reference, case bundle, provenance snapshot, and opt-in status overlay caching are available to support the March 30 load rerun

The following still require local execution before trader UI work can be
declared unblocked:

- a full passing March 30 verification manifest on the current head
- refreshed 10c and 100c committed baselines from that accepted rerun

---

## 7. 48-Hour No-Schema-Change Rule

The 48-hour freeze window starts only when all of the following are true:

- the full rerun suite above passes on the March 30, 2026 head
- the artifact bundle is published from the current commit
- the load baselines are refreshed only if the accepted rerun is intended to become the new baseline

During the 48-hour soak:

- no edits are allowed to the frozen schema files listed in Section 1
- no assessment, audit, or assistant response-shape changes are allowed
- no alias changes are allowed for canonical public fields
- any contract change immediately invalidates the soak and requires a fresh full gate rerun

Record the freeze start timestamp in `docs/dev/production_runbook.md` only after
the current head passes.

---

## 8. Operator Checklist

- [ ] Confirm the frozen schema set has not changed since the March 30 rerun started
- [ ] Confirm `git status --short` is empty before starting the rerun
- [ ] Run `python scripts/local_gate_runner.py --host 127.0.0.1 --port 8002 --api-key <API_KEY>`
- [ ] Review `artifacts/verification/<git-sha>/manifest.json`
- [ ] Confirm unit, integration, assistant/NIM, 10c, and 100c entries all passed
- [ ] Publish the full `artifacts/verification/<git-sha>/` directory
- [ ] Refresh `tests/load/baseline.json` only if the accepted 10c report becomes the new baseline
- [ ] Refresh `tests/load/baseline_100c.json` only if the accepted 100c report becomes the new baseline
- [ ] Record the freeze start timestamp in `docs/dev/production_runbook.md`
- [ ] Enforce the 48-hour no-schema-change window before trader UI work

Until every item above is checked, the repo is not formally cleared for a
trader-facing UI release.
