# AfCFTA Live Production Gate Stabilisation Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Start this book only after completing both the backend hardening book and the
> NIM readiness book**. The backend hardening and NIM readiness books must have
> all exit criteria satisfied before Prompt 1 here.
>
> **Your AGENTS.md shell restriction still applies**: the coding agent creates
> and edits files; you run the commands yourself.
>
> **Primary references**:
> - docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-26.md (audit findings this book resolves)
> - docs/dev/Backend Hardening — Vibecoding Prompts.md (completed prerequisite)
> - docs/dev/NIM Readiness — Vibecoding Prompts.md (completed prerequisite)
> - docs/dev/Decision Renderer — Vibecoding Prompts.md (next book after this one)
> - docs/dev/NIM Integration — Vibecoding Prompts.md (advanced NIM book after Decision Renderer)
> - AGENTS.md for architecture invariants, shell restrictions, and locked scope

---

## Goal

Close every gap identified in the 2026-03-26 production gate audit that would
destabilise the codebase under Decision Renderer or NIM Integration work. This
book does not extend features. It makes the existing engine, its security
boundary, its test corpus, and its deployment artefacts unambiguous and
production-safe before the next phase of interface work begins.

## Non-goals

- Do not add NIM rendering, counterfactual analysis, or trader-UI surface area.
- Do not expand the deterministic engine's legal logic or corridor scope beyond V01.
- Do not introduce new external infrastructure dependencies.
- Do not re-open architecture decisions already settled by the hardening and
  readiness books.

## Working Rules

Use these rules for every prompt in this book:

1. Read every cited file before editing. These prompts are targeted fixes; do not
   rework surrounding code that is not in scope.
2. If a prompt repairs a bug, add a regression test that would fail without the fix
   and passes with it.
3. If a prompt changes configuration, update app/config.py, .env.example, and
   docs/dev/setup.md together.
4. If a prompt changes a contract or schema, update docs and tests in the same
   change.
5. If a prompt touches the NIM boundary, keep NIM metadata (nim_confidence,
   nim_assumptions) out of engine requests and out of audit persistence.

## Definition Of Done Per Prompt

A prompt is only complete when all of the following are true:

1. The specific gap it closes is no longer reproducible.
2. A regression test or CI gate prevents the gap from silently returning.
3. Any affected docs reflect the corrected state.
4. The required summary can cite the exact files changed and tests added.

## Cross-Cutting Implementation Notes

- Preserve all existing request_id correlation, auth, and rate-limiting behaviour
  when editing any middleware, startup, or config path.
- Keep the deterministic assessment engine and its audit persistence path
  completely isolated from any NIM-layer change.
- When adding configuration, always add a corresponding .env.example entry with
  a safe development default and an explicit production note.
- Do not introduce new Python dependencies unless a prompt explicitly justifies one.

---

## Prompt 1 — Eliminate container startup ambiguity and clean up env documentation

```
Read the 2026-03-26 audit findings on Dockerfile worker-count default and .env.example
duplication.
Read Dockerfile (full file).
Read .env.example (full file, note duplicate UVICORN_WORKERS sections at lines ~86 and ~132).
Read docker-compose.prod.yml.

Fix the two configuration clarity gaps so that the container startup path is
unambiguous for both docker-compose and direct docker-run deployments.

Work in these files first:
- Dockerfile
- .env.example
- docker-compose.prod.yml
- docs/dev/setup.md

Requirements:
1. Change the Dockerfile CMD worker-count expansion from ${UVICORN_WORKERS:-2} to
   ${UVICORN_WORKERS:?UVICORN_WORKERS must be set explicitly — do not rely on
   the default. Set 1 for InMemoryRateLimiter deployments, higher only after
   REDIS_URL is configured}. The container must refuse to start rather than
   silently launch two workers without Redis.
2. Remove the duplicate UVICORN_WORKERS block from .env.example. Keep the first
   occurrence (the commented constraint block near REDIS_URL) and delete the
   second. After removal, UVICORN_WORKERS must appear exactly once in .env.example.
3. Verify docker-compose.prod.yml already sets workers=1 explicitly (it does via
   the CMD override). Add a comment explaining why the Dockerfile default is
   intentionally absent and compose is the canonical production entrypoint.
4. Update docs/dev/setup.md to document the exact docker run command for
   non-compose deployments, including the mandatory UVICORN_WORKERS env var.
5. Do not change any runtime behaviour for deployments that already supply
   UVICORN_WORKERS correctly.

When done, summarize:
- the exact Dockerfile line changed
- the .env.example line range removed
- the setup.md addition for non-compose operators
```

**You run:**
```bash
docker build -t afcfta-live:gate-test .
docker compose -f docker-compose.prod.yml config

Audit item: Dockerfile worker-count default / container startup ambiguity
Status: CLOSED

Evidence:
1. Direct image run without UVICORN_WORKERS failed immediately with the explicit required error:
   "UVICORN_WORKERS must be set explicitly — do not rely on the default. Set 1 for InMemoryRateLimiter deployments, higher only after REDIS_URL is configured"

2. Direct image run with UVICORN_WORKERS=1 no longer failed on worker configuration.
   The container progressed past the worker-count gate and then failed later for a separate reason:
   "ModuleNotFoundError: No module named 'httpx'"

3. docker-compose.prod.yml remains explicit and unchanged in behavior:
   it resolves to `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`, so compose deployments do not rely on any hidden Dockerfile default.

Conclusion:
- The hidden Dockerfile worker default has been removed.
- The image now fails fast when UVICORN_WORKERS is missing.
- Compose remains the canonical production entrypoint with workers pinned explicitly.
- The 2026-03-26 startup-clarity audit item is satisfied.

Audit item: production image missing httpx
Status: CLOSED

Evidence:
1. Rebuilt image successfully with updated runtime dependencies.
2. Direct image run with UVICORN_WORKERS=1 no longer fails with:
   "ModuleNotFoundError: No module named 'httpx'"
3. The application now starts successfully:
   - "Started server process"
   - "Application startup complete"
   - "Uvicorn running on http://0.0.0.0:8000"

Conclusion:
- The production image now includes httpx correctly.
- The previous startup failure was resolved.
- Remaining readiness failure is separate and caused by standalone container database connectivity, not by missing Python dependencies.

```
## Completed 26 March 2026
---

## Prompt 2 — Enable and validate the production static-reference cache

```
Read app/core/cache.py (full file).
Read app/repositories/hs_repository.py and app/repositories/rules_repository.py.
Read app/config.py CACHE_STATIC_LOOKUPS and CACHE_TTL_SECONDS settings.
Read .env.example.
Read docs/dev/parser_promotion_workflow.md.

The TTL cache for static reference lookups is implemented but CACHE_STATIC_LOOKUPS
defaults to false. Enable it for production with clear invalidation semantics and
a regression test that proves correctness is maintained under caching.

Work in these files first:
- app/config.py
- .env.example
- app/repositories/hs_repository.py (review existing cache path)
- tests/integration/test_hs_repository.py (or the nearest equivalent)
- docs/dev/setup.md

Requirements:
1. Change the CACHE_STATIC_LOOKUPS default in app/config.py to true so production
   deployments benefit from caching without needing to set the flag manually.
   Keep the existing development override path (false is still valid in .env).
2. In .env.example, update the CACHE_STATIC_LOOKUPS line to reflect the new
   default and add a comment explaining the TTL (default 5 minutes) and the
   two invalidation approaches:
   a. Restart workers after any parser promotion (zero-downtime: rolling restart).
   b. Set CACHE_STATIC_LOOKUPS=false and restart if a promotion window requires
      strict immediate consistency.
3. Add a single integration test that:
   a. Fetches an HS6 code from the repository twice in sequence.
   b. Asserts both calls return identical results.
   c. Asserts the deterministic assessment using that HS6 code produces an identical
      outcome on both the first (cache-miss) and second (cache-hit) call.
   This test must NOT mock the database. Use the integration test database with
   seeded data.
4. Do not cache eligibility decisions. The comment in app/core/cache.py is correct
   and must remain.
5. Update docs/dev/setup.md with the explicit parser-promotion invalidation steps.

When done, summarize:
- the config.py default change
- the two documented invalidation strategies
- the integration test that proves cache correctness
```

**You run:**
```bash
python -m pytest tests/integration/test_hs_repository.py -v
python -m pytest tests/integration -q

Audit item: enable static reference TTL cache by default
Status: CLOSED

Evidence:
1. CACHE_STATIC_LOOKUPS default changed to true in app/config.py.
2. .env.example and docs/dev/setup.md now document:
   - default TTL = 5 minutes
   - rolling restart after parser promotion
   - strict immediate-consistency path using CACHE_STATIC_LOOKUPS=false plus restart
3. New integration regression test passed:
   test_static_lookup_cache_preserves_hs_resolution_and_assessment_outcome
4. Full integration suite passed after the change:
   206 passed

Conclusion:
- Static lookup caching is enabled by default for production.
- Repository lookups and deterministic assessment outcomes remain identical across
  cache-miss and cache-hit paths.
- Eligibility decisions are still not cached.

```
## Completed 26 March 2026
---

## Prompt 3 — Enforce the NIM input boundary: length cap and injection guard

```
Read AGENTS.md section on NIM boundary constraints and maximum input length.
Read app/services/nim/intake_service.py in full (282 lines).
Read app/schemas/nim/intake.py.
Read tests/unit/test_nim_intake_service.py.

The parse_user_input() method sends user_input to the NIM model with no length
guard. AGENTS.md mandates max_length=2000. Add the cap, ensure oversized input
returns a structured clarification rather than an opaque error, and add a
regression test suite for the boundary.

Work in these files first:
- app/services/nim/intake_service.py
- app/schemas/nim/clarification.py (for the oversized-input clarification shape)
- tests/unit/test_nim_intake_service.py

Requirements:
1. Add a constant NIM_MAX_INPUT_CHARS = 2000 at the module level of intake_service.py.
   Keep it derived from AGENTS.md and comment the source.
2. In parse_user_input(), before calling self.nim_client.generate_json(), check
   len(user_input) > NIM_MAX_INPUT_CHARS. If exceeded:
   a. Log a warning with the truncated length (not the content).
   b. Do NOT truncate silently and send a shortened string. Return an empty
      NimAssessmentDraft so the clarification layer handles it. Truncated text
      sent to a legal reasoning model is a silent data quality risk.
   c. Add a flag or metadata to the returned draft so the assistant orchestration
      layer can emit a user-visible clarification asking for a shorter description.
      Use a field name that already exists in NimAssessmentDraft or add a
      nim_rejection_reason field if one does not exist.
3. Verify that no existing method passes nim_confidence, nim_assumptions, or any
   other NIM-only metadata field through to the engine. If to_eligibility_request()
   or the mapping layer does not already strip these, add an explicit assertion
   test that the returned EligibilityRequest never contains those keys.
4. Add unit tests covering:
   - input exactly at the 2000 character boundary → sent to NIM normally
   - input 1 character over → empty draft returned, nim_rejection_reason set
   - mapping from NimAssessmentDraft to EligibilityRequest never includes
     nim_confidence or nim_assumptions keys
   - NIM metadata stripping is tested independently so contract drift is
     detected without needing a live model call

When done, summarize:
- the exact guard added and where in the method it sits
- the rejection path and the field used to communicate it to the orchestration layer
- the four test cases and what each one protects
```

**You run:**
```bash
python -m pytest tests/unit/test_nim_intake_service.py -v
python -m pytest tests/unit/test_nim_mapping.py -v

Audit item: enable static reference TTL cache by default
Status: CLOSED

Evidence:
1. CACHE_STATIC_LOOKUPS default changed to true in app/config.py.
2. .env.example and docs/dev/setup.md now document:
   - default TTL = 5 minutes
   - rolling restart after parser promotion
   - strict immediate-consistency path using CACHE_STATIC_LOOKUPS=false plus restart
3. New integration regression test passed:
   test_static_lookup_cache_preserves_hs_resolution_and_assessment_outcome
4. Full integration suite passed after the change:
   206 passed

Conclusion:
- Static lookup caching is enabled by default for production.
- Repository lookups and deterministic assessment outcomes remain identical across
  cache-miss and cache-hit paths.
- Eligibility decisions are still not cached.
```
## Completed 26 March 2026
---

## Prompt 4 — Wire the evidence risk-tier filter from assessment context

```
Read app/services/evidence_service.py in full.
Read app/repositories/evidence_repository.py lines 60-110 (get_verification_questions).
Read app/services/eligibility_service.py — find where build_readiness or get_readiness
is called and what context is available at that call site.
Read app/schemas/assessments.py — note the confidence_class field and its possible values.
Read tests/unit/test_evidence_service.py.

app/services/evidence_service.py line 38 passes risk_category=None to
get_verification_questions(). The repository is wired to filter on this column when
a value is present, but the caller never supplies one. Any verification questions
tagged with a risk_category in the database are silently excluded from every evidence
readiness response.

Fix the wiring. Use confidence_class as the risk signal, define the mapping
explicitly, and add regression coverage.

Work in these files first:
- app/services/evidence_service.py
- tests/unit/test_evidence_service.py
- tests/integration/test_golden_path.py (verify existing golden cases still pass)

Requirements:
1. Define a private mapping _CONFIDENCE_TO_RISK: dict[str, str | None] that
   translates confidence_class values to the risk_category strings used in the
   verification_question table. Use the following mapping unless the evidence
   repository's data model says otherwise:
   - "complete" → None (no risk filter — return all active questions)
   - "incomplete" → "MEDIUM"
   - "insufficient" → "HIGH"
   If the mapping cannot be established from the existing table schema without a
   DB migration, define it as a stub that always returns None and file a TODO
   comment explaining what DB data is required to activate it. Either outcome is
   acceptable; silent omission is not.
2. Update build_readiness() and get_readiness() to accept an optional
   confidence_class: str | None parameter.
3. Pass _CONFIDENCE_TO_RISK.get(confidence_class) as risk_category to
   get_verification_questions(). When confidence_class is None, pass None (no filter).
4. At each call site in eligibility_service.py that calls build_readiness or
   get_readiness, pass the current assessment's confidence_class value if it is
   available at that point in execution. If confidence_class is not yet determined
   when evidence is evaluated (because evidence runs before confidence is scored),
   pass None and add a comment explaining the ordering constraint.
5. Add unit tests covering:
   - "complete" confidence → risk_category=None passed to repository
   - "incomplete" confidence → risk_category="MEDIUM" passed (or None if stub)
   - "insufficient" confidence → risk_category="HIGH" passed (or None if stub)
   - missing confidence_class → risk_category=None (safe default)
6. Run the existing golden path tests to confirm no regressions.

When done, summarize:
- the mapping chosen (or the stub rationale if no DB data supports it)
- where confidence_class is passed in the eligibility service
- the regression tests that prevent the None-passthrough from silently returning
```

**You run:**
```bash
python -m pytest tests/unit/test_evidence_service.py -v
python -m pytest tests/integration/test_golden_path.py -v

Audit item: Evidence verification-question risk filter wiring
Date: 2026-03-26
Status: CLOSED

Issue:
`app/services/evidence_service.py` always passed `risk_category=None` into
`get_verification_questions()`. The repository supports filtering by
`verification_question.risk_category` when a value is supplied, but the caller
never supplied one. That meant the confidence/risk wiring was absent and the
behavior depended on an implicit no-filter path.

Fix:
1. Added an explicit `_CONFIDENCE_TO_RISK` mapping in `app/services/evidence_service.py`.
2. Threaded `confidence_class` through `build_readiness()` and `get_readiness()`.
3. Passed the mapped value into `get_verification_questions()`.
4. Threaded `confidence_class` from `EligibilityService` into the evidence call site.

Mapping decision:
A safe stub was implemented:
- `complete` -> `None`
- `incomplete` -> `None`
- `insufficient` -> `None`
- `provisional` -> `None`

Rationale:
The current database model does not use severity values like `MEDIUM` or `HIGH`
for `verification_question.risk_category`. The actual enum is domain-specific
(`origin_claim`, `documentary_gap`, `valuation_risk`, etc.). Activating a real
confidence-based filter would require explicit DB-backed mapping data. The code
now documents that requirement with a TODO instead of silently hardcoding
`None` with no explanation.

Evidence:
- Unit tests passed:
  `python -m pytest tests/unit/test_evidence_service.py -v`
  Result: 15 passed
- Golden-path integration tests passed:
  `python -m pytest tests/integration/test_golden_path.py -v`
  Result: 18 passed

Regression coverage added:
1. Evidence-service unit tests now verify the repository receives the explicit
   `risk_category` argument for:
   - `complete`
   - `incomplete`
   - `insufficient`
   - missing `confidence_class`
2. Eligibility-service unit tests now verify `confidence_class` is forwarded
   into evidence readiness calls.
3. Golden-path integration coverage confirms no live assessment regressions.

Conclusion:
The silent `None` passthrough has been removed as an undocumented behavior.
The confidence-to-risk decision is now explicit, wired, and tested. A future
DB/data-model change can activate real filtering without reintroducing ambiguity.
```
## Completed 26 March 2026
---

## Prompt 5 — Expand the golden-case corridor corpus for hackathon readiness

```
Read tests/fixtures/golden_cases.py in full.
Read tests/integration/test_golden_path.py — focus on how GOLDEN_CASES fixtures are
seeded and how _prepared_case_facts and _assert_response_shape are structured.
Read AGENTS.md section "V01 Scope" to confirm the five supported countries.
Read docs/dev/delivery_plan_and_backlog.md for any planned corridor priorities.

The current golden-case corpus covers only 2 of the 20 possible V01 directed corridors
(GHA→NGA groats, CMR→NGA petroleum). Q2 2026 hackathon demos require corridor
coverage across at least three additional country pairs and at least two additional
HS6 chapters.

Add three new golden-case scenarios with complete fixture data.

Work in these files first:
- tests/fixtures/golden_cases.py
- tests/integration/test_golden_path.py

Scenarios to add (one per target corridor and HS6 chapter):

1. CIV→NGA — apparel, Chapter 62 (e.g. HS6 620910 infant garments)
   - Pathway: WO (wholly obtained or produced entirely in CIV)
   - Facts: direct_transport=True, cumulation_claimed=False
   - Expected: eligible=True, pathway_used="WO", rule_status="agreed"
   - Add a companion fail case: same HS6 but direct_transport=False
     (expected: eligible=False, failure_codes include FAIL_DIRECT_TRANSPORT)

2. CMR→SEN — coffee/cocoa, Chapter 09 (e.g. HS6 090111 coffee not roasted)
   - Pathway: CTH (change in tariff heading)
   - Facts: tariff_heading_input="2101" (coffee extracts → heading 21),
     tariff_heading_output="0901" (coffee → heading 09)
   - Expected: eligible=True, pathway_used="CTH", rule_status="agreed"
   - Add a companion fail case: same tariff headings with no change
     (expected: eligible=False)

3. NGA→GHA — iron or steel, Chapter 72 (e.g. HS6 720211 ferro-manganese)
   - Pathway: VNM (value of non-originating materials ≤ 40% ex-works)
   - Facts: ex_works=50000, non_originating=18000 (36%, pass)
   - Expected: eligible=True, pathway_used="VNM", rule_status="agreed"
   - Add a companion fail case: non_originating=22000 (44%, over threshold)
     (expected: eligible=False, failure_codes include FAIL_VNM_EXCEEDED)

Requirements:
1. Each scenario must seed its own deterministic HS6 product, PSR rule, tariff
   schedule, rate, and status rows in the test fixture. Do not share fixture data
   between existing and new cases — isolation is required for parallel test runs.
2. Seed PSR rules with agreed rule_status unless the scenario specifically tests a
   provisional or draft rule.
3. Keep fixture data minimal: seed only what the test asserts, nothing more.
4. Wrap each new scenario in a parametrized test in test_golden_path.py following
   the same pattern as the existing parametrized expanded_live_slice test.
5. Assert eligible, pathway_used, rule_status, and at least one failure_code per
   fail case. Do not assert fields not seeded (e.g. do not assert tariff rates if
   the scenario does not seed a specific rate value).
6. After adding the cases, update the HS6 coverage comment at the top of
   tests/fixtures/golden_cases.py to reflect the new corridor and chapter count.

When done, summarize:
- the three new corridor pairs and their HS6 chapters
- the six new test cases (three pass, three fail)
- the total corridor and HS6 chapter counts in the corpus after the change
```

**You run:**
```bash
python -m pytest tests/integration/test_golden_path.py -v
python -m pytest tests/integration/test_quick_slice_e2e.py -v
```

---

## Prompt 6 — Add a NIM evaluation scaffold for regression protection

```
Read tests/integration/test_nim_full_flow.py in full.
Read tests/integration/test_assistant_api.py in full.
Read AGENTS.md section on NIM boundary and what NIM may not do.
Read docs/dev/NIM Integration — Vibecoding Prompts.md section "Prompt 5 — Build a NIM
evaluation set for regression testing" to understand the expected structure.

The tests/nim_eval/ directory does not exist. NIM Integration (advanced) Prompt 5
requires it as a pre-condition. Without it, any future NIM tuning, model rollout, or
prompt iteration has no regression baseline.

Create a minimal nim_eval scaffold now so it is ready to be extended during NIM
Integration work without blocking that phase.

Work in these files first:
- tests/nim_eval/__init__.py
- tests/nim_eval/cases.py
- tests/nim_eval/test_nim_eval.py
- docs/dev/testing.md

Requirements:
1. Create tests/nim_eval/ as a proper Python test package with __init__.py.
2. Create tests/nim_eval/cases.py containing a NIM_EVAL_CASES list of at least
   three evaluation cases. Each case must be a dict with these keys:
   - "name": str — human-readable scenario name
   - "user_input": str — natural-language trade query
   - "expected_fields": dict — keys and expected values the NIM draft should
     produce (e.g. hs6_code, exporter, importer, year)
   - "expected_clarification": bool — True if intake is expected to return an
     empty draft requiring clarification (e.g. too vague to parse)
   Use the golden-case scenarios from tests/fixtures/golden_cases.py as the
   basis for the natural-language inputs. Do not invent HS6 codes or corridors
   that are not in the V01 golden corpus.
3. Create tests/nim_eval/test_nim_eval.py with a parametrized test class that:
   a. Marks all tests with @pytest.mark.nim_eval so they can be run in isolation
      or excluded from CI until NIM_ENABLED is true.
   b. For each case in NIM_EVAL_CASES: calls parse_user_input with a mocked
      NimClient whose generate_json returns a pre-canned JSON string matching the
      expected_fields. Asserts the returned NimAssessmentDraft contains the
      expected field values.
   c. For clarification cases: asserts the returned draft is empty (all required
      trade fields are None).
   d. Deterministic invariant assertion: after mapping to EligibilityRequest,
      asserts nim_confidence and nim_assumptions are absent from the request body.
4. Add nim_eval to the pytest markers in pyproject.toml with a description:
   "NIM evaluation harness — requires NIM_ENABLED or mocked NimClient".
5. Update docs/dev/testing.md with a section "NIM Evaluation Harness" that
   explains how to run the eval suite, how to add new cases, and how to use it
   during future model tuning.
6. Do not require a live NIM endpoint. All test cases must pass with the mocked
   client.

When done, summarize:
- the three evaluation cases defined
- what each test case asserts
- how to run only nim_eval tests in isolation
```

**You run:**
```bash
python -m pytest tests/nim_eval/ -v -m nim_eval
python -m pytest tests/unit -q
```

---

## Prompt 7 — Validate audit trail provision linkage integrity

```
Read app/services/audit_service.py — focus on _build_decision_provenance() and the
section that fetches provision summaries via sources_repository.
Read app/repositories/sources_repository.py in full.
Read app/schemas/audit.py — ProvisionSummary, RuleProvenanceTrace, TariffProvenanceTrace.
Read tests/integration/test_audit_api.py.

The 2026-03-26 audit flagged that audit_service.py allows silent source_id mismatches:
provision summaries are fetched and attached to audit trails without verifying that
the returned provision's source_id matches the one requested. A mismatched provision
could attach a legally wrong source document to a decision trace.

Harden the provision attachment logic and add a regression test.

Work in these files first:
- app/services/audit_service.py
- app/repositories/sources_repository.py
- tests/integration/test_audit_api.py

Requirements:
1. In audit_service.py, after fetching provision summaries from sources_repository,
   add an explicit check: for each returned provision, if its source_id does not
   match the requested source_id, log a warning and exclude it from the audit trail
   rather than silently attaching it.
2. Do not raise an exception when a mismatch occurs. Log it at WARNING level with
   the evaluation_id, expected source_id, and actual source_id. The audit trail
   should continue building with the mismatch omitted — a partial trail is legally
   safer than a corrupted one.
3. Add a targeted integration test that:
   a. Seeds a provision with source_id A and a different source_id B in the DB.
   b. Calls get_decision_trace() on an evaluation whose provenance references source_id A.
   c. Asserts the audit trail contains a provision with source_id A.
   d. Asserts no provision with source_id B appears in the trail (no cross-contamination).
4. Do not change the public AuditTrail schema shape — this is an internal filtering
   change only.

When done, summarize:
- the exact check added and where in the code it sits
- the log message format
- the integration test that prevents silent cross-contamination
```

**You run:**
```bash
python -m pytest tests/integration/test_audit_api.py -v
python -m pytest tests/integration/test_sources_api.py -v
```

---

## Prompt 8 — Final gate validation and handoff to Decision Renderer

```
Read the 2026-03-26 audit in full (docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-26.md
if it exists, otherwise use the audit prompt output).
Read docs/dev/Decision Renderer — Vibecoding Prompts.md section "Required Preconditions".
Read docs/dev/NIM Integration — Vibecoding Prompts.md section "Backend Prerequisites Gate".
Read docs/dev/production_runbook.md.
Read the final state of the repository after Prompts 1-7 of this book.

Run the full test suite and produce a verified gate checklist that proves all
audit gaps are closed and both the Decision Renderer book and the NIM Integration
(advanced) book can be safely started.

Work in these files first:
- docs/dev/production_runbook.md (add a "Production Gate Stabilisation — 2026-03-26"
  section)
- docs/dev/Production Gate — Vibecoding Prompts.md (update this file: add a
  completion timestamp and tick-off status for each prompt)

Gate checklist to verify (assert each item is true before writing the section):

CONTAINER AND CONFIGURATION
[ ] Dockerfile refuses to start when UVICORN_WORKERS is not set explicitly
[ ] .env.example has exactly one UVICORN_WORKERS entry
[ ] docker-compose.prod.yml CMD overrides workers=1 explicitly

ENGINE CORRECTNESS
[ ] Evidence risk_category filter is wired (or documented as stub with TODO)
[ ] All existing golden-path tests pass with risk_category change in place

NIM BOUNDARY
[ ] parse_user_input() rejects or handles input > 2000 characters without truncating
[ ] NIM metadata fields never appear in EligibilityRequest after mapping
[ ] nim_rejection_reason or equivalent is returned to the orchestration layer

CORPUS COVERAGE
[ ] Golden cases cover at least 5 corridors (up from 2)
[ ] At least three HS6 chapters are represented (Chapter 62, 09, 72 or equivalent)

AUDIT TRAIL INTEGRITY
[ ] Provision source_id mismatch is logged and excluded (not silently attached)
[ ] No provision with a wrong source_id appears in decision traces

STATIC CACHE
[ ] CACHE_STATIC_LOOKUPS defaults to true in app/config.py
[ ] Cache correctness integration test passes (same result cached vs uncached)
[ ] Invalidation procedure documented in docs/dev/setup.md

NIM EVAL SCAFFOLD
[ ] tests/nim_eval/ exists and is a valid Python package
[ ] @pytest.mark.nim_eval tests pass with mocked NimClient
[ ] docs/dev/testing.md documents the harness

DECISION RENDERER PRECONDITIONS (from Decision Renderer book)
[ ] NIM readiness book complete ✓ (already true before this book)
[ ] Assistant-facing contracts pinned in integration tests ✓
[ ] NIM input maps to frozen backend contract ✓ (and now length-capped)
[ ] Clarification targets real engine gaps ✓ (and now risk-tier-aware)
[ ] Explanations cannot contradict deterministic results ✓
[ ] Every assistant-triggered decision is replayable ✓
[ ] NIM failures degrade gracefully ✓

NIM INTEGRATION ADVANCED PRECONDITIONS (from NIM Integration book)
[ ] All 8 backend prerequisite gate items satisfied ✓
[ ] tests/nim_eval/ scaffold ready for Prompt 5 extension ✓

Requirements:
1. Run pytest tests/unit tests/integration --cov and record the output.
2. If coverage drops below 90% for unit or below 80% for integration, do not proceed
   — identify and fix the gap before writing the handoff section.
3. Write a "Production Gate Stabilisation — 2026-03-26" section in
   docs/dev/production_runbook.md that lists:
   a. Every gap from the audit and the prompt that closed it.
   b. The full test command to reproduce the gate validation.
   c. Explicit confirmation that Decision Renderer Prompt 1 prerequisites are met.
   d. Explicit confirmation that NIM Integration (advanced) Prompt 1 prerequisites
      are met.
4. Do not write aspirational claims. Only record what the test run actually confirmed.

When done, summarize:
- the coverage numbers from the test run
- which audit gaps are confirmed closed
- any item that could not be verified and why
```

**You run:**
```bash
python -m pytest tests/unit tests/integration --cov --cov-report=term-missing
python -m pytest tests/nim_eval/ -v -m nim_eval
python -m pytest tests/integration/test_nim_full_flow.py -v
python -m pytest tests/integration/test_golden_path.py -v
```

---

## Recommended Execution Groups

### Group 1 — Infrastructure and configuration stability

Prompts 1–2

These must land first. Container and cache issues affect every subsequent test run.

### Group 2 — Engine correctness and security boundary

Prompts 3–4

Fix the NIM input boundary and the evidence risk-tier wiring before expanding
coverage. New tests in Group 3 must run against the corrected engine behaviour.

### Group 3 — Corpus and scaffold expansion

Prompts 5–6

Add corridor coverage and nim_eval now so both are available to the Decision
Renderer and NIM Integration (advanced) books from their first prompt.

### Group 4 — Audit integrity and gate validation

Prompts 7–8

Close the provision linkage gap and validate the complete gate before handing off.

---

## Exit Criteria

All of the following must be true before starting the Decision Renderer book or the
NIM Integration (advanced) book:

- Dockerfile refuses to start without an explicit UVICORN_WORKERS value
- .env.example has no duplicate configuration blocks
- NIM input is capped at 2000 characters with structured handling for oversized input
- NIM metadata (nim_confidence, nim_assumptions) never enters EligibilityRequest
- Evidence risk_category is wired to confidence_class (or documented as a stub)
- Golden-case corpus covers at least 5 directed corridors and 3 HS6 chapters
- Provision source_id mismatches are detected, logged, and excluded from audit trails
- CACHE_STATIC_LOOKUPS defaults to true with documented invalidation procedure
- tests/nim_eval/ scaffold exists, runs with mocked NimClient, is documented
- Full test suite passes: ≥90% unit coverage, ≥80% integration coverage
- production_runbook.md contains a verified gate section for this audit cycle

Once these are true, the system has a stable, unambiguous foundation for the
Decision Renderer rendering layer and for advanced NIM enhancements.
