# AfCFTA Live Build Gap Closure Prompt Handbook

> How to use: copy-paste each prompt into your coding agent in order.
> Run the commands yourself. Do not skip ahead.
>
> This book expands:
> - `AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md`
> - `Deployment Ready - Prompt Handbook (2026-04-10).md`
> - the earlier backend/NIM/production-gate prompt books
>
> The goal here is not just prioritization. It is implementation closure.
> Each prompt is more explicit about exact files, acceptance criteria, stop
> conditions, and release evidence so the remaining gaps can be closed without
> guesswork.
>
> Your `AGENTS.md` shell restriction still applies: the coding agent creates and
> edits files; you run commands yourself.

## Goal

Convert the 2026-04-10 build-progress gaps into an implementation-grade launch
closure sequence that:

1. freezes replay-grade legal provenance for new evaluations
2. removes browser-visible backend secrets from the trader UI path
3. produces fresh current-head verification evidence under one canonical bundle
4. restores honest 10c/100c release confidence
5. makes operator workflows, dataset promotion, and rollback evidence unambiguous
6. hardens the trader UI into a trustworthy decision surface

This book is deliberately more detailed than the earlier deployment-ready book.
If a gap cannot be honestly closed from the current repo state, the prompt must
surface that blocker explicitly rather than inventing a fake implementation.

## Current Starting Point

Use the 2026-04-10 build-progress handbook as the source of truth for current
status:

- deterministic backend plus NIM foundation: `86%`
- deployment-ready product: `62%`
- world-class public trader product: `48%`

The fastest lift identified there is:

1. immutable audit provenance
2. browser-safe auth
3. fresh current-head verification bundle
4. 100-concurrency recovery
5. deployment and rollback reconciliation

Prompts `1` through `8`, plus `13` and `14`, are the closure path for those
deployment-ready gaps.

Prompts `9` through `12`, plus `14`, close the broader trader-product gaps.

## Non-goals

- Do not expand geography beyond the locked v0.1 countries.
- Do not introduce probabilistic scoring, confidence guessing, or silent
  inference.
- Do not weaken blocker semantics, replay guarantees, or audit requirements to
  make the gate easier to pass.
- Do not call a private-beta browser access pattern "public-user auth" unless
  the repo actually gains a real user identity boundary.
- Do not hide stale artifacts under a new folder name and call them current-head
  evidence.

## Primary References

- `AGENTS.md`
- `docs/dev/prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md`
- `docs/dev/prompts/Deployment Ready - Prompt Handbook (2026-04-10).md`
- `docs/dev/prompts/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md`
- `docs/dev/production_runbook.md`
- `docs/dev/rollback_runbook.md`
- `docs/dev/pre_nim_gate_closure.md`
- `docs/dev/testing.md`
- `docs/dev/parser_promotion_workflow.md`
- `docs/FastAPI_layout.md`
- `docs/Join_Strategy.md`
- `docs/api/`

## Working Rules

Use these rules across every prompt in this book:

1. Read every cited file before editing.
2. Land code, tests, and docs together when a prompt changes runtime behavior,
   a contract, or an operator workflow.
3. Keep deterministic decision ownership in the engine. NIM and UI layers may
   explain, clarify, or proxy, but they do not decide.
4. Never treat a new evaluation as replay-safe unless its persisted record
   contains the snapshot data the prompt requires.
5. Never expose `API_AUTH_KEY`, `NIM_API_KEY`, or any equivalent reusable
   backend secret to the browser bundle, browser devtools, or browser network
   traffic.
6. If a prompt introduces a new configuration surface, update `app/config.py`,
   `.env.example`, relevant runbooks, and CI or verification docs in the same
   change.
7. If a prompt introduces a new launch gate, make it fail closed. Missing
   artifacts or stale evidence must block the gate.
8. Keep prompts sequential unless a prompt explicitly says a task can be done in
   parallel after a prerequisite lands.

## Definition Of Done Per Prompt

A prompt is complete only when all of the following are true:

1. The named gap is closed in code or is converted into an explicit documented
   blocker with a verified gate state.
2. The narrowest useful tests pin the behavior and would fail without the fix.
3. Operator or public docs reflect the new runtime truth.
4. The prompt summary can cite exact files, exact tests, and exact verification
   evidence.

## Gap Coverage Matrix

| Build-progress gap | Prompts that close it |
|---|---|
| Immutable audit provenance for new evaluations | `1`, `2`, `6`, `14` |
| Direct/case/interface replay parity and case-path visibility | `2`, `6`, `14` |
| Browser-safe auth boundary | `3`, `4`, `13`, `14` |
| NIM failure isolation and degraded operation | `5`, `6`, `14` |
| Fresh current-head verification bundle | `7`, `14` |
| 10c/100c performance recovery and SLO clarity | `8`, `14` |
| Dataset manifest and promotion traceability | `9`, `14` |
| Wider live-backed coverage | `10`, `14` |
| Trader trust/provenance UX | `11`, `12`, `14` |
| Deployment and rollback doc reconciliation | `13`, `14` |

## Prompt Status

| Prompt | Status | Completed |
|---|---|---|
| 1 | [ ] Pending | - |
| 2 | [ ] Pending | - |
| 3 | [ ] Pending | - |
| 4 | [ ] Pending | - |
| 5 | [ ] Pending | - |
| 6 | [ ] Pending | - |
| 7 | [ ] Pending | - |
| 8 | [ ] Pending | - |
| 9 | [ ] Pending | - |
| 10 | [ ] Pending | - |
| 11 | [ ] Pending | - |
| 12 | [ ] Pending | - |
| 13 | [ ] Pending | - |
| 14 | [ ] Pending | - |

---

## Prompt 1 - Persist replay-grade provenance snapshots for new evaluations

```text
Read:
- docs/dev/prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md
- app/services/eligibility_service.py
- app/services/audit_service.py
- app/repositories/evaluations_repository.py
- app/repositories/sources_repository.py
- app/schemas/audit.py
- tests/unit/test_eligibility_service.py
- tests/unit/test_audit_service.py
- tests/integration/test_audit_api.py

Problem:
New evaluations persist a compact decision snapshot, but replay-critical rule and
tariff provenance can still be reconstructed from live source/provision rows when
a persisted snapshot is absent. That allows the legal basis shown during replay to
drift after the original assessment, which is the highest-value launch blocker in
the 2026-04-10 build-progress handbook.

Work in these files first:
- app/services/eligibility_service.py
- app/services/audit_service.py
- app/repositories/evaluations_repository.py
- app/repositories/sources_repository.py
- app/schemas/audit.py
- tests/unit/test_eligibility_service.py
- tests/unit/test_audit_service.py
- tests/integration/test_audit_api.py

Requirements:
1. Capture immutable provenance for rule and tariff summaries at evaluation write
   time, not at replay time.
2. Persist the snapshot inside the same atomic evaluation write as the decision
   snapshot so replay-critical legal support is committed or rejected together.
3. For each rule snapshot include at minimum:
   - source_id
   - short_title
   - version_label
   - publication_date
   - effective_date
   - page_ref
   - table_ref
   - row_ref
   - captured_at
   - supporting_provisions
4. For each tariff snapshot include at minimum:
   - schedule_source_id
   - rate_source_id
   - short_title
   - version_label
   - publication_date
   - effective_date
   - line_page_ref
   - rate_page_ref
   - table_ref
   - row_ref
   - captured_at
   - supporting_provisions
5. Supporting provisions must stay thin and bounded. Persist no more than five per
   source, ordered deterministically, and include only:
   - provision_id
   - source_id
   - article_label
   - clause_label
   - topic_primary
   - text_excerpt or equivalent thin legal text field
6. Do not persist full source bodies, unbounded provision lists, binary artifacts,
   or large mutable source payloads.
7. If the minimum required snapshot cannot be built for a new interface-triggered
   or case-backed evaluation, do not silently treat the evaluation as replay-safe.
   Keep the legal decision correct, but force the persistence path to fail closed
   for replay safety rather than falling back to live provenance.
8. Preserve backward compatibility for legacy evaluations already stored.
9. Keep route, service, repository, and schema layering intact.

Tests to add or update:
1. New evaluations persist rule and tariff provenance snapshots on the write path.
2. A replayed audit trail for a new evaluation remains unchanged after mutating the
   underlying live source/provision rows in the test DB.
3. Snapshot ordering for supporting provisions is deterministic.
4. Snapshot size stays bounded and does not persist more than the allowed thin fields.

User-run verification:
1. Run the targeted unit and audit integration tests.
2. Create a new evaluation through the normal API path.
3. Mutate the referenced source metadata and provision text in the test DB.
4. Replay the new evaluation and confirm the supporting provenance shown to the
   client is byte-for-byte unchanged from before the mutation.

Return summary:
- snapshot fields persisted
- where the snapshot is captured
- what fails closed when replay safety cannot be guaranteed
- tests added
```

---

## Prompt 2 - Distinguish frozen replay from legacy fallback and lock replay parity

```text
Read:
- app/services/audit_service.py
- app/services/eligibility_service.py
- app/api/v1/assessments.py
- app/api/v1/cases.py
- app/api/v1/assistant.py
- app/schemas/audit.py
- tests/integration/test_audit_api.py
- tests/integration/test_assessments_api.py
- tests/integration/test_cases_api.py
- tests/integration/test_assistant_api.py

Problem:
The repo now needs two replay classes to be explicit:
1. new evaluations that are snapshot-frozen and legally replay-safe
2. legacy evaluations that still require a live fallback path

At the moment that distinction is not explicit enough, and direct, case-backed,
prepared/finalized interface, and assistant-triggered flows are not pinned hard
enough as one replay contract family.

Work in these files first:
- app/services/audit_service.py
- app/services/eligibility_service.py
- app/api/v1/assessments.py
- app/api/v1/cases.py
- app/api/v1/assistant.py
- app/schemas/audit.py
- tests/integration/test_audit_api.py
- tests/integration/test_assessments_api.py
- tests/integration/test_cases_api.py
- tests/integration/test_assistant_api.py

Requirements:
1. Expose replay guarantee state explicitly in the audit response using a small,
   machine-readable field such as `replay_mode` or `provenance_mode`.
2. The field must distinguish at least:
   - `snapshot_frozen`
   - `legacy_live_fallback`
3. New evaluations created after Prompt 1 must surface `snapshot_frozen`.
4. Legacy rows without frozen snapshots may still replay through live fallbacks,
   but the response must never imply that the provenance is frozen.
5. Direct assessments, case-backed assessments, prepared-interface assessments,
   finalized-interface assessments, and assistant-triggered assessments must all
   produce the same replay guarantee semantics when they persist a new evaluation.
6. Keep replay identifiers explicit across all interface-facing flows:
   `case_id`, `evaluation_id`, and audit URL/header linkage must remain intact.
7. Update docs and tests together if the audit schema adds the replay-mode field.
8. Do not invent a fake "fully frozen" state for historical rows that do not have
   the persisted snapshot payload.

Tests to add or update:
1. New direct assessment -> replay shows `snapshot_frozen`.
2. New case-backed assessment -> replay shows `snapshot_frozen`.
3. Assistant-triggered assessment -> replay shows `snapshot_frozen`.
4. A seeded legacy evaluation without snapshots -> replay shows `legacy_live_fallback`.
5. Cross-path parity test proving the same replay-mode semantics and replay headers
   are returned for all interface-facing entry points.

User-run verification:
1. Run assessment, case, assistant, and audit integration suites.
2. Create one evaluation through each entry point.
3. Replay each result and confirm the same guarantee semantics are shown.
4. Replay at least one legacy seeded row and confirm it is clearly labeled as fallback.

Return summary:
- replay-mode field chosen
- new-vs-legacy semantics
- interface paths proven to match
- tests added
```

---

## Prompt 3 - Introduce a browser-safe trader boundary and remove browser-visible backend secrets

```text
Read:
- frontend/src/api/client.ts
- frontend/src/hooks/useAssessment.ts
- frontend/src/App.tsx
- frontend/src/pages/AssessPage.tsx
- frontend/package.json
- frontend/vite.config.ts
- app/api/router.py
- app/api/deps.py
- app/main.py
- docs/dev/production_runbook.md
- docs/dev/prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md

Problem:
The current frontend sends `X-API-Key` from browser code. That is acceptable for
local-only experimentation, but it is not launch-safe. Any user can extract the
shared secret from the bundle or browser network traffic and replay it outside the UI.

Implement one explicit browser-safe boundary for the trader UI.

Work in these files first:
- frontend/src/api/client.ts
- frontend/src/hooks/useAssessment.ts
- frontend/src/App.tsx
- frontend/vite.config.ts
- app/api/router.py
- app/api/deps.py
- app/main.py
- any new backend-for-frontend files needed for a browser route family
- docs/dev/production_runbook.md
- .env.example

Requirements:
1. Introduce a same-origin browser-facing route family under `/web/api/`.
2. Keep the existing `/api/v1/` family API-key protected for machine and operator clients.
3. The browser route family must never require the browser to know `API_AUTH_KEY`
   or any equivalent reusable backend secret.
4. The `/web/api/` boundary must proxy only the trader-safe operations needed by
   the UI, rather than exposing the full internal API surface by default.
5. Preserve and forward:
   - `X-Request-ID`
   - `X-AIS-Case-Id`
   - `X-AIS-Evaluation-Id`
   - `X-AIS-Audit-URL`
6. Scrub internal-only auth headers from all browser responses.
7. Remove all browser runtime dependency on `VITE_API_KEY` or any fallback value
   like `dev-local-key` in shipped frontend code.
8. Keep local development workable through a same-origin dev proxy or backend
   static serving path, but do not restore browser secret exposure to do it.

Tests to add or update:
1. Frontend/client tests proving browser requests no longer attach `X-API-Key`.
2. Backend tests proving `/web/api/` can call the internal service layer without
   exposing the internal key to the browser.
3. Tests proving replay headers still reach the browser path.
4. Tests proving `/api/v1/` still requires API-key auth for machine clients.

User-run verification:
1. Build the frontend and inspect the bundle for `X-API-Key`, `API_AUTH_KEY`,
   `VITE_API_KEY`, and `dev-local-key`.
2. Open the trader UI and inspect browser network requests.
3. Confirm no shared backend key appears in request headers, local storage, or
   the browser bundle.
4. Confirm the UI can still assess and replay a decision through `/web/api/`.

Return summary:
- browser route family added
- browser secret exposure removed
- machine-client path preserved
- tests added
```

---

## Prompt 4 - Harden the browser boundary with session, CSRF, origin, and rotation controls

```text
Read:
- app/main.py
- app/config.py
- app/api/deps.py
- app/api/router.py
- docs/dev/production_runbook.md
- docs/dev/rollback_runbook.md
- .env.example
- frontend/src/App.tsx
- frontend/src/api/client.ts

Problem:
Removing the browser-visible API key is necessary but not sufficient. The browser
boundary still needs explicit access control, session handling, cross-site request
protection, and operator procedures. The build-progress handbook is clear that this
repo does not yet have a completed public-launch auth story, so the implementation
must be honest about what is and is not now secure.

Work in these files first:
- app/main.py
- app/config.py
- app/api/router.py
- app/api/deps.py
- frontend/src/App.tsx
- frontend/src/api/client.ts
- docs/dev/production_runbook.md
- docs/dev/rollback_runbook.md
- .env.example
- any new threat-model or browser-auth doc you need

Requirements:
1. Implement one explicit browser session boundary for `/web/api/`.
2. Use a named session cookie such as `ais_trader_session`.
3. The cookie must be:
   - `HttpOnly`
   - `Secure` outside local development
   - `SameSite=Lax` or stricter
   - explicitly expired with idle and absolute session lifetimes
4. Protect mutating browser requests with one of:
   - CSRF token + header validation
   - strict same-origin + origin validation
   Choose one and document it precisely.
5. Add browser-route allowlisting so only the intended trader UI origins may use
   the browser boundary.
6. Keep `API_AUTH_KEY` rotation procedures separate from trader-session procedures.
7. Do not pretend this repo now has full public-user identity if it only has a
   private-beta or invite-gated session flow. Document the exact security posture.
8. Add one concise threat-model document covering:
   - browser secret exposure
   - CSRF
   - stolen session cookie risk
   - origin spoofing
   - operator secret rotation
   - what still blocks true public launch if no real user-identity layer exists

Tests to add or update:
1. Invalid or missing browser session -> request rejected.
2. Invalid or missing CSRF/origin protection -> request rejected.
3. Expired session -> request rejected cleanly.
4. Logout or session revocation clears browser access.
5. Internal `/api/v1/` machine-client path remains unchanged.

User-run verification:
1. Exercise login/session creation for the browser boundary.
2. Attempt a mutating request without the required browser protection and confirm rejection.
3. Attempt the same call from an unapproved origin and confirm rejection.
4. Rotate the relevant browser/session secret in staging and confirm the runbook matches reality.

Return summary:
- browser session model implemented
- CSRF/origin strategy chosen
- private-beta vs public-launch posture documented honestly
- tests and docs added
```

---

## Prompt 5 - Add NIM circuit breaker and deterministic degraded mode

```text
Read:
- app/api/v1/assistant.py
- app/services/nim/client.py
- app/services/nim/explanation_service.py
- app/services/nim/clarification_service.py
- app/services/nim/rendering_service.py
- app/services/nim/logging.py
- tests/unit/test_nim_client.py
- tests/unit/test_nim_explanation_service.py
- tests/unit/test_nim_clarification_service.py
- tests/integration/test_assistant_api.py
- tests/integration/test_nim_full_flow.py

Problem:
NIM retries and fallbacks exist, but the build-progress handbook still calls out
missing breaker-grade failure isolation and incomplete operator visibility. Repeated
downstream failure must not create retry storms, unpredictable latency, or silent
loss of deterministic fallback behavior.

Work in these files first:
- app/services/nim/client.py
- app/api/v1/assistant.py
- app/services/nim/explanation_service.py
- app/services/nim/clarification_service.py
- app/services/nim/rendering_service.py
- app/services/nim/logging.py
- app/config.py
- tests/unit/test_nim_client.py
- tests/unit/test_nim_explanation_service.py
- tests/unit/test_nim_clarification_service.py
- tests/integration/test_assistant_api.py
- tests/integration/test_nim_full_flow.py

Requirements:
1. Add an explicit circuit-breaker or failure-throttling mechanism around NIM calls.
2. The breaker must expose at least `closed`, `open`, and `half_open` semantics.
3. When the breaker is open:
   - do not keep sending normal NIM traffic
   - fall back to deterministic clarification/explanation/rendering behavior
   - preserve deterministic assessment correctness
4. Keep retry behavior bounded and subordinate to the breaker state.
5. Ensure no NIM failure path can mutate engine-owned decision fields.
6. Add observable fields for:
   - breaker state
   - retry count
   - timeout count
   - fallback type used
7. Document the operator-visible behavior of the breaker so degraded mode is not
   mistaken for a silent success path.

Tests to add or update:
1. Unit tests for breaker transition rules.
2. Unit tests proving repeated retryable failures open the breaker.
3. Unit tests proving half-open recovery closes the breaker only after a success.
4. Integration tests proving assistant responses still return safe deterministic
   output when the breaker is open.
5. Tests proving no engine-owned response fields change under degraded NIM mode.

User-run verification:
1. Force repeated NIM timeouts or 5xx responses in a controlled environment.
2. Confirm the breaker opens and the assistant still returns deterministic output.
3. Restore the downstream and confirm half-open -> closed recovery works.

Return summary:
- breaker design
- degraded-mode behavior
- observable signals added
- tests added
```

---

## Prompt 6 - Add launch-grade observability for assessments, persistence, replay, NIM, and pool pressure

```text
Read:
- app/main.py
- app/config.py
- app/core/logging.py
- app/api/v1/health.py
- app/services/audit_service.py
- app/services/eligibility_service.py
- app/services/nim/logging.py
- app/db/base.py
- docs/dev/production_runbook.md
- docs/dev/testing.md
- tests/unit/test_health.py
- tests/integration/test_health_api.py

Problem:
The repo has logging seams, health endpoints, and some NIM logging, but it still
lacks the operator picture needed to detect:
- persistence failures
- frozen-vs-legacy replay mix
- NIM degradation
- pool pressure
- rate-limit abuse
- corridor/HS6 outcome anomalies

Close that gap with bounded-cardinality metrics and explicit operator documentation.

Work in these files first:
- app/main.py
- app/config.py
- app/core/logging.py
- app/api/v1/health.py
- app/services/audit_service.py
- app/services/eligibility_service.py
- app/services/nim/logging.py
- app/db/base.py
- docs/dev/production_runbook.md
- docs/dev/testing.md
- tests/unit/test_health.py
- tests/integration/test_health_api.py

Requirements:
1. Add metrics and/or structured log events for:
   - assessments by eligible/not_eligible/blocker outcome
   - confidence_class
   - exporter/importer corridor
   - hs6_code
   - pathway_used
   - audit persistence success/failure
   - replay_mode (`snapshot_frozen` vs `legacy_live_fallback`)
   - assistant clarification vs assessment vs error response type
   - NIM retry/fallback/breaker state
   - auth failures
   - rate-limit rejections
2. Keep cardinality bounded. The fixed v0.1 corridor set and HS6 slice are small
   enough to be explicit, but do not add free-form user text or request IDs as
   metric labels.
3. Extend readiness or adjacent operator output with pool statistics and a simple
   pressure classification if that is not already present on the current head.
4. Make evaluation-persistence failure and replay-fallback behavior visible enough
   that operators can answer:
   - are new interface evaluations actually frozen?
   - are failures increasing?
   - are we unintentionally falling back to legacy behavior?
5. Update operator docs with a short "what to monitor" section covering:
   - key counters
   - key log events
   - what a degraded NIM state looks like
   - what a persistence/replay problem looks like

Tests to add or update:
1. Unit tests for any new pool-pressure or metric-classification helpers.
2. Tests proving persistence failures emit the expected signal.
3. Tests proving replay-mode signals are emitted correctly for frozen vs legacy rows.
4. Integration or focused tests for readiness output structure if it changes.

User-run verification:
1. Trigger at least one persistence failure in a controlled path.
2. Trigger NIM degradation.
3. Hit readiness during a small load run.
4. Confirm logs/metrics make all three situations obvious without code inspection.

Return summary:
- new operator signals
- bounded dimensions chosen
- production docs updated
- tests added
```

---

## Prompt 7 - Publish a canonical current-head verification bundle under the git SHA

```text
Read:
- scripts/local_gate_runner.py
- scripts/run_verification.py
- .github/workflows/ci.yml
- docs/dev/pre_nim_gate_closure.md
- docs/dev/testing.md
- README.md
- docs/dev/production_runbook.md

Problem:
The repo has historical reports and partial artifact paths, but the build-progress
handbook still treats fresh current-head proof as missing. Release evidence needs
one canonical bundle format, one manifest, one SHA-based location, and one rule
for rejecting stale or mixed-head artifacts.

Work in these files first:
- scripts/local_gate_runner.py
- scripts/run_verification.py
- .github/workflows/ci.yml
- docs/dev/testing.md
- docs/dev/production_runbook.md
- README.md

Requirements:
1. Emit one canonical bundle path:
   `artifacts/verification/<git-sha>/`
2. The manifest must include at minimum:
   - git_sha
   - generated_at
   - dirty_worktree flag
   - command set actually run
   - pass/fail summary by suite
   - coverage summaries
   - load summaries
   - browser/UI build summary if the UI is in scope
   - dataset manifest reference from Prompt 9
3. Include or reference the following artifacts when applicable:
   - unit JUnit XML
   - integration JUnit XML
   - assistant/NIM JUnit XML
   - coverage XML files
   - load warmup report
   - 10c report
   - 100c report
   - frontend build output summary
4. Make it impossible to confuse stale artifacts with the current release candidate.
5. Keep local and CI naming aligned so operators see the same model in both places.
6. If the worktree is dirty, fail closed by default and mark the manifest clearly.
7. Do not run the full suite from the coding agent; prepare the harness only.

Tests to add or update:
1. Script-level tests for manifest generation and path selection where practical.
2. CI guards that fail when the expected artifact set is incomplete.
3. If frontend build artifacts are added, verify the manifest includes them.

User-run verification:
1. Run the local verification harness on the current head.
2. Confirm the bundle lands under the current git SHA.
3. Confirm the manifest references every expected artifact and the dataset manifest id.
4. Confirm stale artifacts outside the current SHA path are not treated as gate evidence.

Return summary:
- canonical bundle path
- manifest fields
- CI/local alignment
- next operator commands
```

---

## Prompt 8 - Recover 10c/100c performance honestly and freeze the release SLOs

```text
Read:
- tests/load/run_load_test.py
- tests/load/compare_reports.py
- tests/load/baseline.json
- tests/load/baseline_100c.json
- app/db/base.py
- app/api/deps.py
- app/main.py
- app/repositories/hs_repository.py
- app/repositories/rules_repository.py
- app/repositories/tariffs_repository.py
- app/repositories/evidence_repository.py
- docs/dev/testing.md
- docs/dev/production_runbook.md
- .github/workflows/ci.yml

Problem:
The build-progress handbook still treats performance and scalability as under-closed.
The system needs current-head 10c and 100c evidence, explicit release SLOs, and
documented runtime settings. Threshold changes alone do not close this gap.

Work in these files first:
- tests/load/run_load_test.py
- tests/load/compare_reports.py
- app/db/base.py
- app/api/deps.py
- app/main.py
- hot-path repositories touched by the measurement results
- docs/dev/testing.md
- docs/dev/production_runbook.md
- .github/workflows/ci.yml

Requirements:
1. Freeze the release SLOs in one authoritative place. At minimum document:
   - warmup expectation
   - 10c success-rate floor
   - 10c latency threshold
   - 100c success-rate floor
   - 100c latency threshold
   - max allowed network errors
2. Remove obvious hot-path waste before changing thresholds.
3. Keep deterministic semantics unchanged.
4. Any cache change must be justified, documented, and bounded to static or low-churn reads.
5. Record the worker count, Redis usage, pool size, overflow, and cache settings
   alongside each accepted load report.
6. If a threshold changes, document:
   - previous value
   - new value
   - why the change is honest
   - who approved it
7. Update the verification bundle so accepted 10c and 100c reports are always attached.

Tests to add or update:
1. Load-harness checks or comparison-script guards for the frozen SLOs.
2. Unit tests for any new tuning helper or cache-selection logic.
3. CI checks or docs guards that keep the load thresholds aligned with the docs.

User-run verification:
1. Run warmup, 10c, and 100c on the tuned branch.
2. Capture success rate, p50, p95, network errors, worker count, Redis mode, and
   pool settings in the bundle.
3. Do not mark this prompt complete until the accepted reports are attached.

Return summary:
- hotspots removed
- runtime settings changed
- frozen SLOs
- measured before/after deltas
```

---

## Prompt 9 - Make parser and tariff promotions operator-verifiable with dataset manifests

```text
Read:
- scripts/parsers/psr_db_inserter.py
- scripts/parsers/validation_runner.py
- scripts/sql/load_tariff_data.sql
- docs/dev/parser_promotion_workflow.md
- docs/dev/production_runbook.md
- data/staged/tariffs/
- data/staged/raw_csv/

Problem:
The build-progress handbook says promotion is dataset-repeatable but still lacks a
formal manifest proving exactly what legal and tariff dataset is live. That weakens
release traceability and makes it harder to tie runtime behavior back to a specific
promoted corpus.

Work in these files first:
- scripts/parsers/psr_db_inserter.py
- scripts/parsers/validation_runner.py
- docs/dev/parser_promotion_workflow.md
- docs/dev/production_runbook.md
- any new manifest helper files you need

Requirements:
1. Emit a machine-readable dataset manifest for each promotion.
2. The manifest must include at minimum:
   - manifest_id
   - generated_at
   - promoted_at
   - git_sha
   - operator-visible source identifiers
   - input file paths and checksums
   - row counts per target table
   - validation summary
   - warning/failure summary
   - effective scope summary (corridors, HS6 counts, chapters if known)
3. Make the manifest comparable across repeated identical promotions.
4. Keep promotions atomic and repeatable at the dataset level.
5. Link the accepted manifest into the verification bundle and release docs so the
   operator can say exactly which dataset a release candidate used.
6. Do not invent a mutable row-id guarantee if rows are regenerated each promotion.
   Document that limitation honestly and make the dataset fingerprint the stable anchor.

Tests to add or update:
1. Script tests for manifest generation.
2. Validation tests proving repeat runs over identical inputs produce equivalent
   manifest content except for allowed timestamps/ids.
3. Docs examples showing how the manifest path is referenced by the release bundle.

User-run verification:
1. Run one promotion in a controlled environment.
2. Capture the manifest.
3. Repeat the same promotion and compare the manifests.
4. Confirm the release bundle references the accepted manifest id/path.

Return summary:
- manifest shape
- dataset identity anchor chosen
- release linkage added
- tests/docs updated
```

---

## Prompt 10 - Expand live-backed regression coverage across priority chapters and corridors

```text
Read:
- tests/fixtures/golden_cases.py
- tests/integration/test_golden_path.py
- tests/integration/test_quick_slice_e2e.py
- data/staged/hs6_product.csv
- docs/dev/testing.md
- docs/dev/prompts/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md
- docs/dev/prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md

Problem:
Coverage is still thin relative to a trader-facing product. The earlier audit and
the build-progress handbook both call for wider live-backed product coverage,
especially in commercially meaningful chapters.

Work in these files first:
- tests/fixtures/golden_cases.py
- tests/integration/test_golden_path.py
- tests/integration/test_quick_slice_e2e.py
- tests/integration/seed_helpers.py
- docs/dev/testing.md

Requirements:
1. Expand the locked acceptance slice without leaving the v0.1 corridor set.
2. Add at least:
   - two additional directed corridors not already covered in the original slice
   - three additional commercially meaningful HS chapters
3. Use the earlier repo-audit expansion priority as the floor:
   - Chapter 11
   - Chapter 27
   - Chapter 84
   Add more if the live data already supports them cleanly.
4. For each new corridor/chapter scenario add:
   - one eligible case
   - one ineligible or blocked companion case
5. Include at least one scenario each for:
   - status/provisional behavior
   - blocker behavior
   - evidence/document gap behavior
   - replay-safe persisted evaluation behavior
6. Update the locked coverage statements in docs and comments so totals stay accurate.
7. Do not invent unsupported countries or non-seeded legal/tariff slices.

Tests to add or update:
1. Golden-path integration coverage for all new scenarios.
2. Quick-slice or API-level regression coverage for representative new cases.
3. Any helper updates needed to keep seeded fixture identities deterministic.

User-run verification:
1. Run the golden-path and quick-slice integration suites.
2. Confirm the new totals for corridors, HS6 products, and chapters.
3. Confirm the accepted coverage statement in docs matches the actual fixture corpus.

Return summary:
- new corridors and chapters added
- pass/fail or blocker scenarios added
- updated corpus totals
- docs/tests updated
```

---

## Prompt 11 - Build a launch-grade trader decision trust surface

```text
Read:
- frontend/src/pages/AssessPage.tsx
- frontend/src/components/AssessmentForm.tsx
- frontend/src/components/AssessmentResult.tsx
- frontend/src/components/StatusIndicator.tsx
- frontend/src/components/TariffCard.tsx
- frontend/src/components/AuditLink.tsx
- frontend/src/components/RenderingPanel.tsx
- frontend/src/api/types.ts
- frontend/src/api/client.ts
- docs/concepts/status-and-confidence.md
- docs/api/examples.md
- docs/user-guide/understanding-results.md

Problem:
The build-progress handbook calls out that the UI is not yet trustworthy enough
for launch. Traders need to see not just an answer, but the legal status, replay
linkage, evidence posture, and confidence limitations in a way that is hard to
misread.

Work in these files first:
- frontend/src/pages/AssessPage.tsx
- frontend/src/components/AssessmentResult.tsx
- frontend/src/components/StatusIndicator.tsx
- frontend/src/components/TariffCard.tsx
- frontend/src/components/AuditLink.tsx
- frontend/src/components/RenderingPanel.tsx
- frontend/src/api/types.ts
- docs/user-guide/understanding-results.md
- any new frontend components you need

Requirements:
1. Surface the deterministic decision fields prominently:
   - eligible
   - pathway_used
   - rule_status
   - tariff_status
   - confidence_class
   - failures
   - missing_facts
   - evidence_required
   - missing_evidence
2. Make provisional, incomplete, and legacy-fallback states visually and textually explicit.
3. Show the replay/audit linkage in a first-class way, not as a hidden debug detail.
4. Present provenance/citation affordances so a user can understand where the rule
   and tariff support came from before leaving the page.
5. Keep assistant explanation content clearly subordinate to deterministic engine truth.
6. Do not collapse blocker, not-eligible, and incomplete states into one generic red banner.
7. Add trust copy or labels that explain status without legal overstatement.
8. Update user-facing docs/examples to match the UI state model.

Tests to add or update:
1. Add or extend a frontend rendering test harness suitable for this Vite app if one
   does not already exist.
2. Add component tests for:
   - agreed/complete success
   - provisional status
   - incomplete/missing facts
   - legacy replay fallback label
   - audit link rendering
3. If a minimal frontend test harness is introduced, document and wire it into CI.

User-run verification:
1. Build the frontend.
2. Exercise at least one eligible, one blocked, one provisional, and one legacy
   replay scenario.
3. Confirm a trader can identify the legal status, evidence needs, and replay link
   without opening devtools.

Return summary:
- trust signals added to the UI
- deterministic-vs-assistant separation preserved
- frontend test coverage added
- docs updated
```

---

## Prompt 12 - Harden the trader UI for accessibility, mobile quality, and degraded states

```text
Read:
- frontend/src/App.tsx
- frontend/src/index.css
- frontend/src/pages/AssessPage.tsx
- frontend/src/components/AssessmentForm.tsx
- frontend/src/components/CountrySelector.tsx
- frontend/src/components/HsCodeInput.tsx
- frontend/src/components/AssessmentResult.tsx
- frontend/src/components/RenderingPanel.tsx
- frontend/src/hooks/useAssessment.ts
- frontend/package.json
- .github/workflows/ci.yml
- docs/user-guide/quickstart.md

Problem:
The current UI is basic. The build-progress handbook specifically calls out mobile,
accessibility, empty/error/retry handling, and degraded-mode states as unfinished.
This prompt closes those quality gaps and makes the frontend testable in CI.

Work in these files first:
- frontend/src/App.tsx
- frontend/src/index.css
- frontend/src/pages/AssessPage.tsx
- frontend/src/components/AssessmentForm.tsx
- frontend/src/components/CountrySelector.tsx
- frontend/src/components/HsCodeInput.tsx
- frontend/src/components/AssessmentResult.tsx
- frontend/src/components/RenderingPanel.tsx
- frontend/src/hooks/useAssessment.ts
- frontend/package.json
- .github/workflows/ci.yml
- docs/user-guide/quickstart.md

Requirements:
1. Ensure the core assessment flow works cleanly on desktop and mobile breakpoints.
2. Add explicit states for:
   - loading
   - empty
   - validation error
   - auth/session failure
   - rate limited
   - replay unavailable
   - degraded NIM/rendering path
   - generic retryable network failure
3. Make forms keyboard-complete and screen-reader sensible.
4. Do not rely on color alone to communicate outcome or risk.
5. Respect reduced-motion expectations where animations or transitions exist.
6. Because the frontend currently has no test script, add a minimal Vite-native
   test harness if needed and wire it into `frontend/package.json`.
7. Update CI to run the frontend build and any newly added frontend tests.
8. Document the frontend verification commands in the repo docs.

Tests to add or update:
1. Component or UI tests for the degraded/error states above.
2. Responsive layout verification for at least one narrow mobile viewport.
3. Keyboard navigation and focus-state checks where practical.
4. CI coverage for `npm --prefix frontend run build` and the new frontend tests.

User-run verification:
1. Run the frontend build.
2. Run the frontend test suite if added.
3. Check the core flow at a mobile-width viewport and a desktop viewport.
4. Simulate rate limit, session expiry, and degraded assistant rendering states.

Return summary:
- accessibility/mobile changes
- degraded/error states added
- frontend test harness and CI changes
- docs updated
```

---

## Prompt 13 - Reconcile deployment and rollback docs with runtime reality

```text
Read:
- docs/dev/production_runbook.md
- docs/dev/rollback_runbook.md
- docs/dev/pre_nim_gate_closure.md
- docs/dev/testing.md
- README.md
- .env.example
- docker-compose.prod.yml
- Dockerfile
- .github/workflows/ci.yml
- frontend/package.json

Problem:
The build-progress handbook still treats deployment and rollback operations as under-closed.
The docs contain historical gate sections, current gate expectations, and runtime
details that are partly correct but not yet one clean operator story.

Bring the operator documentation into exact alignment with the implementation after
Prompts 1 through 12.

Work in these files first:
- docs/dev/production_runbook.md
- docs/dev/rollback_runbook.md
- docs/dev/testing.md
- README.md
- .env.example
- docker-compose.prod.yml
- Dockerfile
- .github/workflows/ci.yml

Requirements:
1. Reconcile auth docs so the difference between:
   - `/api/v1/` machine/operator clients
   - `/web/api/` browser clients
   is explicit and unambiguous.
2. Document the real session/auth posture for trader UI access, including any
   remaining blocker to true public launch.
3. Document the canonical verification bundle and dataset manifest requirements.
4. Document the real 10c/100c gate and the exact commands or scripts that produce it.
5. Document the real worker/Redis/pool constraints without ambiguity.
6. Document what operators monitor for:
   - replay freeze failures
   - legacy fallback usage
   - NIM degraded mode
   - browser auth/session failures
7. Separate historical appendix material from the current go/no-go path so an
   operator under time pressure cannot accidentally use stale evidence.
8. Make rollback guidance match the real image, migration, and artifact model.

Tests / validation:
1. No code test harness required, but every referenced command, file path, header,
   route, and artifact name must match the real implementation.
2. If CI or scripts changed, cross-check the docs against those exact paths and names.

User-run verification:
1. Perform a tabletop deploy and rollback walkthrough using only the runbooks.
2. Confirm every header, route family, bundle path, manifest path, and threshold
   referenced in the docs exists in the codebase.
3. Confirm the docs distinguish deployment-ready vs public-launch-ready honestly.

Return summary:
- operator docs corrected
- stale or ambiguous guidance removed
- current go/no-go docs aligned to runtime
```

---

## Prompt 14 - Run the final launch-candidate gate and record deployment-ready vs public-launch-ready

```text
Read:
- docs/dev/prompts/AFCFTA-LIVE_BUILD_PROGRESS_HANDBOOK_2026-04-10.md
- docs/dev/prompts/AFCFTA-LIVE_BUILD_GAP_CLOSURE_PROMPT_HANDBOOK_2026-04-11.md
- docs/dev/production_runbook.md
- docs/dev/rollback_runbook.md
- docs/dev/testing.md
- README.md
- .github/workflows/ci.yml
- app/api/v1/assistant.py
- app/services/eligibility_service.py
- frontend/src/api/client.ts

Problem:
After Prompts 1 through 13, the repo still needs one explicit final gate that
records what is actually true on the chosen commit and distinguishes:
1. deployment-ready candidate
2. public-launch-ready trader product

Do not collapse those into one label unless the evidence honestly supports it.

Work in these files first:
- docs/dev/production_runbook.md
- README.md
- any new launch-candidate checklist or manifest files you need

Requirements:
1. Add one final launch-candidate checklist section or dedicated file that records:
   - git SHA
   - verification bundle path
   - dataset manifest id/path
   - replay-mode result for new evaluations
   - browser auth mode in force
   - 10c result
   - 100c result
   - rollback drill result
   - frontend build/test result
   - deployment_ready verdict
   - public_launch_ready verdict
2. The gate must fail closed:
   - missing artifact -> fail
   - stale artifact -> fail
   - unverifiable runbook step -> fail
   - browser-visible secret -> fail
   - new evaluations not frozen -> fail
3. If the repo still lacks real-user public auth, mark:
   - `deployment_ready = true` only if the rest of the gate passes
   - `public_launch_ready = false`
   and explain why in one explicit blocker field.
4. Require explicit signoff fields for:
   - engineering
   - security
   - operations
5. Record the exact user-run commands needed to reproduce the gate on the chosen SHA.
6. Do not mark the release ready from historical March 26/March 30 artifacts.

Minimum gate items to verify:
1. New evaluations replay with `snapshot_frozen`.
2. Legacy rows are labeled clearly.
3. `/web/api/` does not expose a shared backend secret.
4. `/api/v1/` still protects machine/operator routes.
5. NIM degraded mode is observable and safe.
6. Verification bundle exists under the current SHA.
7. Dataset manifest is linked.
8. 10c and 100c reports pass the accepted gate.
9. Frontend build passes and UI verification is recorded.
10. Runbook rollback drill succeeds.

User-run verification:
1. Run the full current-head verification suite and publish the bundle.
2. Run at least one direct, case-backed, and assistant-triggered assessment.
3. Replay those evaluations and verify frozen provenance.
4. Smoke-test the trader UI through the browser-safe route family.
5. Perform the documented rollback drill or tabletop exercise.
6. Mark the final verdict only after all evidence is attached.

Return summary:
- final checklist location
- deployment_ready verdict
- public_launch_ready verdict
- exact remaining blocker if public launch is still not honest
```

---

## Recommended Execution Order

### Group 1 - Replay-safe legal core

1. Prompt 1 - replay-grade provenance snapshots
2. Prompt 2 - frozen vs legacy replay semantics

### Group 2 - Browser and assistant boundary hardening

3. Prompt 3 - browser-safe trader boundary
4. Prompt 4 - session/CSRF/origin hardening
5. Prompt 5 - NIM circuit breaker
6. Prompt 6 - observability and pool pressure

### Group 3 - Evidence and release proof

7. Prompt 7 - canonical verification bundle
8. Prompt 8 - 10c/100c recovery and SLO freeze
9. Prompt 9 - dataset manifest and promotion traceability
10. Prompt 10 - live-backed coverage expansion

### Group 4 - Trader product quality

11. Prompt 11 - trust/provenance UX
12. Prompt 12 - accessibility/mobile/degraded states

### Group 5 - Operator closure

13. Prompt 13 - deployment/rollback doc reconciliation
14. Prompt 14 - final launch-candidate gate

## Exit Criteria

This handbook is complete only when all of the following are true:

- new evaluations replay with immutable rule/tariff/provision snapshots
- legacy evaluations are clearly labeled as live-fallback and not overclaimed
- no browser request path exposes a reusable backend secret
- the browser session boundary and origin protections are explicit and documented
- NIM failures are isolated behind a breaker-grade degraded path
- operators can see persistence failures, replay mode, NIM degradation, and pool pressure
- the current head has one canonical verification bundle under its git SHA
- accepted 10c and 100c reports are attached to that bundle
- each promoted dataset has a manifest linked into release evidence
- the golden/live-backed coverage slice is widened and documented accurately
- the trader UI exposes legal status, evidence posture, and replay linkage clearly
- the frontend is build-verified and has launch-grade error/degraded states
- deployment and rollback docs match runtime reality
- the final gate records separate `deployment_ready` and `public_launch_ready` verdicts

If `public_launch_ready` remains false because the repo still lacks a true public
user-identity boundary, that is an acceptable honest outcome. It is not acceptable
to mark it true without the implementation and evidence to support it.
