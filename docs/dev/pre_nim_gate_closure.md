# Pre-NIM Gate Closure

Operator checklist for closing the remaining March 26, 2026 blockers before
starting the next primary prompt book.

Use this document together with:

- `docs/dev/production_runbook.md`
- `tests/unit/test_contract_freeze.py`
- `tests/contract_constants.py`

This gate is not complete until the current head has passed the full rerun
suite and the contract freeze window has started.

---

## 1. Frozen Schemas

Treat the following public contracts as frozen for the March 26 gate:

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

The freeze mechanism is the existing contract test suite in
`tests/unit/test_contract_freeze.py`, backed by the field-order and field-set
constants in `tests/contract_constants.py`. Do not create a parallel freeze
policy. If a deliberate contract edit is approved for any frozen schema,
update those existing freeze tests and constants first, then rerun the full
March 26 gate from Section 3.

---

## 2. What Counts As A Schema Change

Any of the following resets the freeze window and requires a fresh full gate rerun:

- adding, removing, or renaming a field on any frozen schema
- changing field order where `tests/contract_constants.py` pins order
- changing required vs optional behavior
- changing accepted aliases or canonical field names
- changing discriminator values such as assistant `response_type`
- changing serialized top-level response shape for assessments, audit replay, or assistant responses
- changing validation rules in a way that alters the public request or response contract

Non-contract internal refactors do not break the freeze if they do not change the
observable schema, serialized field set, or validation semantics.

---

## 3. Gate Rerun Required On The March 26 Head

Run the following suite on the current March 26, 2026 head before starting the
freeze window.

### Unit gate

```bash
python -m pytest tests/unit --cov --cov-report=term-missing --cov-report=xml:artifacts/unit-coverage.xml
```

Publishes:

- `artifacts/unit-coverage.xml`

### Integration gate

```bash
python -m pytest tests/integration --cov --cov-report=term-missing --cov-report=xml:artifacts/integration-coverage.xml
```

Publishes:

- `artifacts/integration-coverage.xml`

### Assistant and NIM gate

```bash
python -m pytest tests/integration/test_assistant_api.py tests/integration/test_nim_full_flow.py -v --junitxml=artifacts/assistant-nim-tests.xml --cov=app.api.v1.assistant --cov=app.services.nim --cov=app.schemas.nim --cov-report=term-missing --cov-report=xml:artifacts/assistant-nim-coverage.xml
```

Publishes:

- `artifacts/assistant-nim-tests.xml`
- `artifacts/assistant-nim-coverage.xml`

### Load baseline gate

```bash
python tests/load/run_load_test.py --mode burst --concurrency 10 --requests 50 --api-key <API_KEY> --report artifacts/load-report-ci.json
python tests/load/compare_reports.py --baseline tests/load/baseline.json --report artifacts/load-report-ci.json --latency-tolerance-pct 25 --min-success-rate 95
```

Publishes:

- `artifacts/load-report-ci.json`

### 100-concurrency load gate

```bash
python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500 --api-key <API_KEY> --report artifacts/load-report-100.json
python tests/load/compare_reports.py --baseline tests/load/baseline_100c.json --report artifacts/load-report-100.json --latency-tolerance-pct 50 --min-success-rate 95
```

Publishes:

- `artifacts/load-report-100.json`

---

## 4. Artifact Set To Publish

Publish or archive this exact set for the March 26 gate cycle:

- `artifacts/unit-coverage.xml`
- `artifacts/integration-coverage.xml`
- `artifacts/assistant-nim-tests.xml`
- `artifacts/assistant-nim-coverage.xml`
- `artifacts/load-report-ci.json`
- `artifacts/load-report-100.json`

If any command writes a JUnit XML or other report to a different path locally,
normalize it back to these filenames before declaring the gate complete.

---

## 5. Current Gate Run Record (March 26, 2026 Head)

Record the fresh March 26 rerun results here before declaring the gate complete.

### Unit results

- Command:
  `python -m pytest tests/unit --cov --cov-report=term-missing --cov-report=xml:artifacts/unit-coverage.xml`
- Result: `544 passed`
- Coverage summary: `90.14%` total coverage
- Attach/archive:
  - `artifacts/unit-coverage.xml`

### Integration results

- Command:
  `python -m pytest tests/integration --cov --cov-report=term-missing --cov-report=xml:artifacts/integration-coverage.xml`
- Result: `215 passed`
- Coverage summary: `85.95%` total coverage
- Attach/archive:
  - `artifacts/integration-coverage.xml`

### Assistant and NIM results

- Command:
  `python -m pytest tests/integration/test_assistant_api.py tests/integration/test_nim_full_flow.py -v --junitxml=artifacts/assistant-nim-tests.xml --cov=app.api.v1.assistant --cov=app.services.nim --cov=app.schemas.nim --cov-report=term-missing --cov-report=xml:artifacts/assistant-nim-coverage.xml`
- Result: `50 passed`
- Coverage summary: `79.46%` total coverage
- Attach/archive:
  - `artifacts/assistant-nim-tests.xml`
  - `artifacts/assistant-nim-coverage.xml`

### Load baseline result

- Command:
  `python tests/load/run_load_test.py --mode burst --concurrency 10 --requests 50 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-ci.json`
- Comparison:
  `python tests/load/compare_reports.py --baseline tests/load/baseline.json --report artifacts/load-report-ci.json --latency-tolerance-pct 25 --min-success-rate 95`
- Result: `PASS` — `50 / 50` successful, `0` rate-limited, `0` network errors, `p95 = 0.5930 s`, baseline comparison `PASS` (`+3.2%` vs `+25%` ceiling)
- Attach/archive:
  - `artifacts/load-report-ci.json`

### 100-concurrency load result

- Command:
  `python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-100.json`
- Comparison:
  `python tests/load/compare_reports.py --baseline tests/load/baseline_100c.json --report artifacts/load-report-100.json --latency-tolerance-pct 50 --min-success-rate 95`
- Result: `PASS` — `500 / 500` successful, `0` rate-limited, `0` network errors, `p95 = 2.1710 s`, baseline comparison `PASS` (`-63.8%` vs `+50%` ceiling)
- Attach/archive:
  - `artifacts/load-report-100.json`

### Go / No-Go checklist

- [x] Schema freeze is active for the frozen contracts in Section 1
- [x] Readiness regression is fixed
- [x] Provenance topic filters and aliases are live
- [x] Current locked coverage statement is published
- [x] All five gate result blocks above are marked passed on the March 26 head

The 48-hour soak does not start from partial progress. It starts only after every
gate result block above is marked passed and this checklist is fully green.

---

## 6. Current Locked Coverage Slice

The canonical March 26, 2026 acceptance slice is derived from
`tests/fixtures/golden_cases.py` and currently covers:

- 9 distinct HS6 products
- 6 directed corridors
- 15 golden cases
- 9 HS chapters

Use these figures in the README, runbook, and gate log. Do not restate older
coverage claims from the pre-expansion slice.

---

## 7. 48-Hour No-Schema-Change Rule

The 48-hour freeze window starts only when all of the following are true:

- the full gate suite above passed on the March 26 head
- the readiness probe regression is fixed
- provenance topic filters and aliases are live and test-pinned
- the current HS6 coverage statement has been reconciled and published

During the 48-hour soak:

- no edits are allowed to the frozen schema files listed in Section 1
- no assessment, audit, or assistant response-shape changes are allowed
- no alias changes are allowed for canonical public fields
- any contract change immediately invalidates the soak and requires a fresh full gate rerun

Record the freeze start timestamp explicitly in the production runbook or gate log.

---

## 8. Operator Checklist

- [x] Confirm the frozen schema set has not changed since the gate rerun started
- [x] Run the unit gate and publish `artifacts/unit-coverage.xml`
- [x] Run the integration gate and publish `artifacts/integration-coverage.xml`
- [x] Run the assistant/NIM gate and publish `artifacts/assistant-nim-tests.xml`
- [x] Publish `artifacts/assistant-nim-coverage.xml`
- [x] Run the load baseline gate and publish `artifacts/load-report-ci.json`
- [x] Run the 100-concurrency load gate and publish `artifacts/load-report-100.json`
- [x] Publish the locked coverage statement: 9 HS6 products, 6 directed corridors, 15 golden cases, 9 HS chapters
- [x] Confirm all gate checks passed on the March 26 head
- [x] Record the freeze start timestamp
- [x] Enforce a 48-hour no-schema-change window before starting the next primary prompt book

Once every item above is complete, the repo is cleared for the next gate-dependent handoff.

---

## 9. Final Gate-Closure Summary

Status for the March 26, 2026 head: **PASSED / FORMALLY CLEARED**.

Reason:

- the March 26 rerun ledger in Section 5 is fully populated with passing unit,
  integration, assistant/NIM, and load evidence
- the Go / No-Go checklist is fully green
- the locked coverage statement is published and the readiness/provenance fixes are live

Schema freeze start timestamp:

- `2026-03-26T10:32:57.1600046-04:00`

Next prompt-book handoff:

- the next allowed primary prompt book is **Decision Renderer**
- **NIM Readiness** is already complete and the freeze is now in effect
- **NIM Integration** is post-readiness follow-on work only, not the next primary
  build step
