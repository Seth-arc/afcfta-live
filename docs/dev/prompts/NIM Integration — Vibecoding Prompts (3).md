# NIM Integration — Advanced Follow-On Prompts

> **Status**: This file is no longer the primary NIM execution plan.
>
> **Use this only after**:
> - [docs/dev/Backend Hardening — Vibecoding Prompts.md](docs/dev/Backend%20Hardening%20%E2%80%94%20Vibecoding%20Prompts.md)
> - [docs/dev/NIM Readiness — Vibecoding Prompts.md](docs/dev/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md)
>
> **What changed**:
> - the primary NIM execution sequence now lives in the dedicated NIM readiness book
> - this file is now reserved for post-readiness NIM enhancements
> - stale overlapping prompts were removed so there is only one canonical path for initial NIM delivery
>
> **Stale assumptions removed from earlier versions of this file**:
> - `submitted_documents` was used as the document-inventory field name throughout earlier NIM prompt wording. The canonical backend field is `existing_documents`. `submitted_documents` is accepted by the live API as an input-only alias for backward compatibility only; it must not appear in new NIM schemas, response contracts, or test fixtures.
> - Earlier prompts assumed that direct assessments (no `case_id`) were sufficient for conversational compliance flows. They are not. Every assistant-triggered assessment must produce a persisted replayable record. `POST /api/v1/assessments` auto-creates a submitted case when `case_id` is omitted, so callers should not bypass case creation.
> - Earlier prompts treated audit persistence as optional or caller-managed. Audit persistence is now a hard pre-condition for NIM integration, not an optional capability.
> - Earlier prompts did not gate NIM work on tariff-schedule blocker enforcement. Missing tariff coverage must be a hard blocker (engine halts, pathway evaluation skipped) before any assistant layer is built on top.

---

## Purpose

Use this companion prompt book only after the core assistant layer already exists and is stable.

It is for advanced NIM enhancements such as:
- prompt and response quality tuning
- explanation style refinement
- model rollout controls
- session memory and follow-up UX improvements
- NIM analytics and evaluation loops

It is not for first-time NIM implementation.

---

## Codified NIM Architectural Boundary

This boundary is non-negotiable. Every prompt in this file and in the NIM readiness book must preserve it.

**What NIM may do:**
- Parse and normalize natural-language trade queries into structured intake facts
- Ask clarifying questions when required backend facts are absent
- Explain deterministic engine outputs in plain language
- Summarize evidence requirements and next steps based on engine results

**What NIM must never do:**
- Decide eligibility. Eligibility is decided by the deterministic engine only.
- Override, reinterpret, or contradict any of these engine output fields: `eligible`, `pathway_used`, `rule_status`, `tariff_outcome`, `confidence_class`, `failures`, `missing_facts`
- Fabricate legal facts, provision text, tariff rates, or corridor status
- Bypass or weaken audit persistence — every assessment the assistant triggers must produce a persisted, replayable record
- Pass NIM-only metadata (confidence scores, parse assumptions, session state) into the deterministic engine unless the backend contract explicitly accepts them

**Replayability rule:**
Every assessment triggered through the assistant path must be replayable through the audit layer. The response must include or reference `evaluation_id`, `case_id`, and the `X-AIS-Audit-URL` header. If `audit_persisted` is `false` in the assessment response, the assistant must not claim audit compliance or present the result as legally recorded.

**Field-name migration notice:**
The canonical document-inventory field is `existing_documents`. The older field name `submitted_documents` must not appear in any NIM schema, assistant response shape, or new test fixture. The live API accepts `submitted_documents` as an input-only alias for backward compatibility, but responses and all new contracts use `existing_documents` exclusively.

---

## Backend Prerequisites Gate

Do not use any prompt in this file unless ALL of the following are already true in the live codebase:

1. Missing tariff coverage is a hard blocker — the engine halts and skips pathway evaluation when `tariff_schedule_line` is absent for the requested corridor
2. Assessment and audit response contracts are frozen — no same-day field changes since the last NIM readiness book completion
3. `POST /api/v1/assessments` auto-creates a submitted case when `case_id` is omitted, so every interface-triggered assessment produces a persisted replayable record
4. `audit_persisted: bool` is present in assessment responses and the assistant layer checks it
5. Auth and rate limiting are active on all non-health endpoints
6. Liveness (`/api/v1/health`) and readiness (`/api/v1/health/ready`) endpoints exist
7. The assistant endpoint, NIM module (`app/services/nim/`), and `tests/integration/test_assistant_api.py` all exist and are covered by tests
8. The NIM readiness book (Prompts 1–12) has been completed

If any of these are false, do not use this file. Return to [docs/dev/NIM Readiness — Vibecoding Prompts.md](docs/dev/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md).

---

## Working Rules

Use these prompts only for improvements that preserve the already-shipped assistant contract.

1. Do not re-open first-build architecture decisions that belong in the NIM readiness book.
2. Keep deterministic engine fields and replay identifiers stable unless a prompt explicitly says otherwise.
3. If a change affects response shape, add or tighten regression tests before changing prompt wording or UX phrasing.
4. Keep legal audit persistence separate from assistant analytics, session state, or prompt-tuning artifacts.
5. Use `existing_documents` exclusively in any schema, mapping, or test you write. Never introduce `submitted_documents` in new code.

---

## Canonical Execution Order

1. Run the backend hardening book.
2. Run the NIM readiness book.
3. Only then use this file for iterative improvement work.

---

## What Moved Out Of This File

The following now belong in [docs/dev/NIM Readiness — Vibecoding Prompts.md](docs/dev/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md):

- assistant contract harness
- NIM module creation
- intake schemas and services
- clarification and explanation services
- assistant endpoint orchestration
- fallback behavior needed for first safe production use
- full-flow NIM integration testing

---

## Prompt 1 — Tune explanation style without changing factual outputs

```
Read the live explanation service and its tests.
Read the stable assistant response contract.

Improve explanation phrasing quality while preserving strict factual alignment to deterministic outputs.

Work in these files first:
- app/services/nim/explanation_service.py
- tests/unit/test_nim_explanation_service.py
- tests/integration/test_nim_full_flow.py

Requirements:
1. Do not change any deterministic decision fields.
2. Keep all contradiction guards intact.
3. Improve only phrasing, summary structure, and next-step usefulness.
4. Add tests if needed for any new explanation formatting rules.
5. Preserve the existing explanation schema so downstream UI code does not need to rebind fields.

When done, summarize:
- what explanation quality improved
- what invariants remain protected
```

**You run:**
```bash
python -m pytest tests/unit/test_nim_explanation_service.py -v
python -m pytest tests/integration/test_nim_full_flow.py -v
```

---

## Prompt 2 — Add model rollout controls and safe configuration switches

```
Read app/config.py and the NIM client implementation.

Add configuration controls for model rollout and safe disablement.

Work in these files first:
- app/config.py
- app/services/nim/client.py
- .env.example
- README.md

Requirements:
1. Add explicit enable or disable controls for NIM features.
2. Support model version switching through configuration.
3. Keep deterministic fallback behavior available when NIM is disabled.
4. Document the runtime flags clearly.
5. Make the disabled path easy to exercise in tests and staging.

When done, summarize:
- the rollout controls added
- how to disable NIM safely in production
```

**You run:**
```bash
python -m pytest tests/unit -q
```

---

## Prompt 3 — Add NIM interaction analytics without polluting legal audit data

```
Read the NIM logging layer and the existing structured logging configuration.

Add lightweight analytics for assistant usage patterns.

Work in these files first:
- app/services/nim/logging.py
- app/core/logging.py
- README.md

Requirements:
1. Capture model latency, clarification frequency, and fallback frequency.
2. Keep legal audit persistence separate.
3. Make logging safe and configurable.
4. Do not log sensitive freeform user content unless explicitly redacted and justified.
5. Prefer aggregate counters and structured metadata over raw payload capture.

When done, summarize:
- the analytics signals added
- what data is intentionally excluded
```

**You run:**
```bash
python -m pytest tests/unit -q
```

---

## Prompt 4 — Add session-aware follow-up support only after core stability

```
Read the assistant endpoint, the case or evaluation persistence strategy, and the current NIM readiness tests.

Add lightweight session-aware follow-up support for assistant conversations.

Work in these files first:
- app/api/v1/assistant.py
- app/services/nim/
- tests/integration/test_assistant_api.py

Requirements:
1. Do not replace case-backed or evaluation-backed persistence with chat-only state.
2. Keep follow-up state minimal and explicit.
3. Support what-if and clarification continuation flows without weakening replayability.
4. Add tests for incremental fact completion across turns.
5. Document TTL or invalidation expectations if any ephemeral session state is introduced.

When done, summarize:
- the session model used
- what persists versus what stays ephemeral
```

**You run:**
```bash
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Prompt 5 — Build a NIM evaluation set for regression testing

```
Read the assistant full-flow tests and the locked golden cases.

Create a small NIM-specific evaluation harness so future prompt or model changes can be checked for regressions.

Work in these files first:
- tests/nim_eval/
- README.md
- docs/dev/testing.md

Requirements:
1. Include representative natural-language prompts.
2. Check parse quality, clarification quality, explanation consistency, and fallback behavior.
3. Keep deterministic backend invariants as the pass or fail baseline.
4. Make the evaluation harness easy to extend.
5. Separate golden expectations for deterministic outputs from softer expectations about explanation phrasing.

When done, summarize:
- the evaluation dimensions covered
- how to use the harness during future NIM tuning
```

**You run:**
```bash
python -m pytest tests/nim_eval -q
```

---

## Exit Criteria For Using This File

Only use these prompts once:

- the assistant path already exists
- the NIM readiness book has been completed
- contracts are stable enough that you are improving quality rather than defining the initial architecture

If those conditions are not true, go back to [docs/dev/NIM Readiness — Vibecoding Prompts.md](docs/dev/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md).

## Post-Readiness Handoff

Once this file becomes active, the team should already have:

1. a stable assistant endpoint and response contract
2. replayable persistence for assistant-triggered decisions
3. explanation, clarification, and fallback behavior already covered by tests

If any of those are still moving, go back to the NIM readiness book instead of extending from here.


