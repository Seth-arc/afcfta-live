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

## Working Rules

Use these prompts only for improvements that preserve the already-shipped assistant contract.

1. Do not re-open first-build architecture decisions that belong in the NIM readiness book.
2. Keep deterministic engine fields and replay identifiers stable unless a prompt explicitly says otherwise.
3. If a change affects response shape, add or tighten regression tests before changing prompt wording or UX phrasing.
4. Keep legal audit persistence separate from assistant analytics, session state, or prompt-tuning artifacts.

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


