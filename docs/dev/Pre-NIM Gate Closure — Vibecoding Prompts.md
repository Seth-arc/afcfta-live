# AfCFTA Live Pre-NIM Gate Closure Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run yourself. Do not skip ahead.
>
> **Purpose**: Close the remaining blockers before starting the next core prompt book.
>
> **Targets covered**:
> 1. Freeze assessment and assistant schemas, rerun the full gate on the March 26 head, publish fresh artifacts, and enforce a 48-hour no-schema-change window
> 2. Remove engine disposal from readiness checks and rerun the load baseline and 100-concurrency comparison
> 3. Add `topic` filters and aliases to provenance APIs and pin them with integration tests
> 4. Reconcile and publish the current HS6 coverage analysis

---

## Goal

Bring the repo from "likely ready" to "provably ready" for the next prompt book by:

- eliminating known operational defects
- locking the public contracts
- refreshing test and load evidence on the current head
- reconciling documented HS6 coverage with the actual locked corpus

## Non-goals

- Do not change deterministic eligibility logic
- Do not expand geography beyond v0.1
- Do not start trader UI or decision-rendering work in this book
- Do not re-open NIM architecture beyond what is needed to lock and verify it

## Working Rules

1. Treat `app/schemas/assessments.py`, `app/schemas/audit.py`, and `app/schemas/nim/` as freeze candidates.
2. Do not change public response shapes unless a prompt explicitly requires it.
3. If a prompt changes a contract, add or tighten tests before moving on.
4. Publish new evidence only from the March 26 head, not from earlier stored artifacts.
5. Keep readiness, provenance, and coverage work separate so failures are easy to isolate.

---

## Prompt 1 - Codify the contract freeze and gate criteria

```text
Read:
- docs/dev/production_runbook.md
- tests/unit/test_contract_freeze.py
- tests/contract_constants.py
- app/schemas/assessments.py
- app/schemas/audit.py
- app/schemas/nim/

Create a short pre-NIM gate-closure document that defines:
1. Which schemas are frozen
2. What counts as a schema change
3. What tests and artifacts must be rerun on the March 26 head
4. The 48-hour no-schema-change rule after a clean gate
5. The exact artifact paths and report names to publish

Work in these files first:
- docs/dev/pre_nim_gate_closure.md
- docs/dev/production_runbook.md if cross-links are needed

Requirements:
1. Freeze at least:
   - assessment request and response contracts
   - audit replay contract
   - assistant request and response envelope
   - clarification and explanation schemas
2. Define the gate command set explicitly:
   - unit
   - integration
   - assistant/NIM
   - load baseline
   - 100-concurrency load
3. State that no schema or response-shape edits are allowed during the 48-hour soak.
4. Link the freeze to the existing contract-freeze tests rather than inventing a new mechanism.
5. Make the doc usable as an operator checklist.

When done, summarize:
- the frozen schema set
- the exact gate suite required
- the freeze window rules
```

**You run:**
```bash
git diff docs/dev/pre_nim_gate_closure.md docs/dev/production_runbook.md
```
## Completed 26 March
---

## Prompt 2 - Fix readiness so health probes stop disposing the engine

```text
Read:
- app/db/base.py
- app/api/v1/health.py
- Dockerfile
- docker-compose.prod.yml
- tests/integration/test_health_api.py
- tests/load/run_load_test.py

Fix the readiness check so it verifies database reachability without disposing the shared engine on every probe.

Work in these files first:
- app/db/base.py
- tests/integration/test_health_api.py
- tests/unit/ if a focused helper test is needed

Requirements:
1. Remove the per-probe engine disposal from the readiness path.
2. Keep the readiness semantics the same: return degraded when the DB is unavailable.
3. Preserve the authenticated pool-stats behavior in /health/ready.
4. Add or tighten tests so this regression cannot return silently.
5. Do not weaken the Docker or compose health checks.

When done, summarize:
- the root cause
- the code path changed
- the test added or strengthened
```

**You run:**
```bash
python -m pytest tests/integration/test_health_api.py -v
python tests/load/run_load_test.py --mode burst --concurrency 10 --requests 50 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-ci.json
python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-100.json
python tests/load/compare_reports.py --baseline tests/load/baseline.json --report artifacts/load-report-ci.json --latency-tolerance-pct 25 --min-success-rate 95
python tests/load/compare_reports.py --baseline tests/load/baseline_100c.json --report artifacts/load-report-100.json --latency-tolerance-pct 50 --min-success-rate 95
```

Note: on the validated Windows/Git Bash local setup, force `--url http://127.0.0.1:8000` and use the active local dev auth key (`dev-local-key`). The default `localhost` target and older long-lived token produced false load failures in the March 26 gate rerun.

---

## Prompt 3 - Add provenance `topic` filters and aliases at the API boundary

```text
Read:
- app/api/v1/sources.py
- app/repositories/sources_repository.py
- tests/integration/test_sources_api.py
- tests/integration/test_audit_api.py

Add the missing provenance-topic traversal contract at the route layer.

Work in these files first:
- app/api/v1/sources.py
- app/repositories/sources_repository.py only if route support needs a small adapter
- tests/integration/test_sources_api.py
- tests/integration/test_audit_api.py if provenance traversal assertions should be extended

Requirements:
1. Support GET /sources?topic=...
2. Support GET /provisions?topic=... as an alias for topic_primary
3. Preserve existing topic_primary behavior for backward compatibility
4. Keep route handlers thin
5. Prefer reusing repository lookup_by_topic() if it fits cleanly
6. Add integration tests that pin:
   - /sources?topic=...
   - /provisions?topic=...
   - backward compatibility for /provisions?topic_primary=...
7. Do not rename existing response fields

When done, summarize:
- the new query parameters supported
- how backward compatibility is preserved
- the integration tests added
```

**You run:**
```bash
python -m pytest tests/integration/test_sources_api.py -v
python -m pytest tests/integration/test_audit_api.py -v
```

---

## Prompt 4 - Reconcile and publish the current HS6 coverage analysis

```text
Read:
- tests/fixtures/golden_cases.py
- README.md
- docs/dev/production_runbook.md

Reconcile the documented coverage analysis with the locked corpus and current gate expectations.

Work in these files first:
- README.md
- docs/dev/production_runbook.md
- docs/dev/pre_nim_gate_closure.md if it needs a coverage section

Requirements:
1. Derive the current coverage from the locked golden corpus and current acceptance slice.
2. Publish at minimum:
   - number of distinct HS6 products
   - number of directed corridors
   - number of golden cases
   - HS chapter count
3. Fix drift where docs still claim the older smaller slice.
4. Keep the wording factual and traceable to the locked corpus.
5. Do not modify tests/fixtures/golden_cases.py.

When done, summarize:
- the current HS6 coverage numbers
- which stale claims were corrected
- where the canonical coverage statement now lives
```

**You run:**
```bash
git diff README.md docs/dev/production_runbook.md docs/dev/pre_nim_gate_closure.md
```

---

## Prompt 5 - Rerun and publish the full March 26 gate

```text
Read:
- docs/dev/pre_nim_gate_closure.md
- .github/workflows/ci.yml
- docs/dev/testing.md
- docs/dev/production_runbook.md

Prepare the repository docs for a fresh March 26 gate run and artifact publication.

Work in these files first:
- docs/dev/production_runbook.md
- docs/dev/pre_nim_gate_closure.md

Requirements:
1. Add a section for the current gate run with placeholders for:
   - unit results
   - integration results
   - assistant/NIM results
   - load baseline result
   - 100c load result
2. Record the exact artifact paths to attach or archive.
3. Add a short "go/no-go" checklist tied to:
   - schema freeze active
   - readiness regression fixed
   - provenance topic filters live
   - current coverage statement published
4. Make it explicit that the 48-hour soak starts only after all gate checks pass on the March 26 head.

When done, summarize:
- the gate evidence structure
- the publishable artifact list
- the soak start condition
```

**You run:**
```bash
python -m pytest tests/unit --cov --cov-report=term-missing --cov-report=xml:artifacts/unit-coverage.xml
python -m pytest tests/integration --cov --cov-report=term-missing --cov-report=xml:artifacts/integration-coverage.xml
python -m pytest tests/integration/test_assistant_api.py tests/integration/test_nim_full_flow.py -v --junitxml=artifacts/assistant-nim-tests.xml --cov=app.api.v1.assistant --cov=app.services.nim --cov=app.schemas.nim --cov-report=term-missing --cov-report=xml:artifacts/assistant-nim-coverage.xml
python tests/load/run_load_test.py --mode burst --concurrency 10 --requests 50 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-ci.json
python tests/load/run_load_test.py --mode burst --concurrency 100 --requests 500 --url http://127.0.0.1:8000 --api-key dev-local-key --report artifacts/load-report-100.json
python tests/load/compare_reports.py --baseline tests/load/baseline.json --report artifacts/load-report-ci.json --latency-tolerance-pct 25 --min-success-rate 95
python tests/load/compare_reports.py --baseline tests/load/baseline_100c.json --report artifacts/load-report-100.json --latency-tolerance-pct 50 --min-success-rate 95
```

---

## Prompt 6 - Declare the freeze and hand off to the next book

```text
Read:
- docs/dev/pre_nim_gate_closure.md
- docs/dev/production_runbook.md
- docs/dev/NIM Readiness — Vibecoding Prompts.md
- docs/dev/Decision Renderer — Vibecoding Prompts.md
- docs/dev/NIM Integration — Vibecoding Prompts.md

Write the final gate-closure summary and state which prompt book is allowed next.

Work in these files first:
- docs/dev/pre_nim_gate_closure.md
- docs/dev/production_runbook.md

Requirements:
1. State whether the March 26 head passed or failed the gate.
2. Record the exact schema freeze start timestamp if the gate passed.
3. State the exact next prompt book:
   - NIM Readiness if prerequisites are still not formally cleared
   - Decision Renderer if NIM readiness is already complete and the freeze is in effect
4. State explicitly that NIM Integration is post-readiness follow-on work, not the next primary build step.
5. Keep the handoff short and operational.

When done, summarize:
- pass/fail
- freeze start
- next allowed prompt book
```

**You run:**
```bash
git diff docs/dev/pre_nim_gate_closure.md docs/dev/production_runbook.md
```

---

## Recommended Execution Groups

### Group 1 - Freeze and readiness fix

Prompts 1-2

### Group 2 - Provenance contract closure

Prompt 3

### Group 3 - Coverage reconciliation and gate publication

Prompts 4-6

---

## Exit Criteria

This prompt book is complete only when all of these are true:

- assessment, audit, and assistant contracts are explicitly frozen
- `/health/ready` no longer disposes the shared engine
- load baseline and 100-concurrency comparisons have been rerun on the fixed March 26 head
- `/sources?topic=...` and `/provisions?topic=...` are live and pinned by integration tests
- the documented HS6 coverage matches the locked corpus
- fresh March 26 test and load artifacts are published
- a 48-hour no-schema-change window is declared with a recorded start time

Once these are true, the repo is cleared for the next primary prompt book.
