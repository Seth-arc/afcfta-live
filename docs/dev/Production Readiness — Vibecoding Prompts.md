# AfCFTA Live Production Readiness Prompt Books

> **How to use**: This file is the entry point for four sequential prompt books.
> Complete each book in full before starting the next. Do not skip ahead.
>
> **Current status (2026-03-26)**:
> - Backend Hardening ✓ completed 24 March
> - NIM Readiness ✓ completed 24 March
> - Production Gate Stabilisation — in progress (start here)
> - Decision Renderer and NIM Integration (advanced) — blocked until gate is complete

## Working Rules

Use these rules across all prompt books:

1. Complete prompts in order. If a prompt reveals contract drift or missing prerequisites, fix that before moving on.
2. Read every file named in a prompt before editing. These books assume the implementation follows the existing route, service, repository, and schema layering.
3. Land code, tests, and documentation together when a prompt changes a contract, runtime behavior, or operator workflow.
4. Treat each prompt as finished only when its required summary can be answered with concrete files and tests.
5. Do not start NIM work while any backend exit criterion is still false.
6. Do not start Decision Renderer or NIM Integration (advanced) while any Production Gate exit criterion is still false.

## Expected Outputs

Backend hardening should leave you with:

- blocker-safe deterministic assessment behavior
- pinned assessment and audit contracts
- replay-safe persistence for interface-triggered decisions
- auth, rate limiting, health checks, logging, environment docs, and deploy artifacts

NIM readiness should leave you with:

- a thin assistant contract on top of the frozen backend contracts
- a strict NIM module that parses, clarifies, and explains but never decides
- graceful fallback behavior that preserves deterministic outputs and replayable audit records

Production gate stabilisation should leave you with:

- unambiguous container startup (no hidden worker-count defaults)
- NIM input boundary enforced at the service layer (max 2000 chars, no truncation)
- evidence risk-tier filter wired to confidence_class
- golden-case corpus covering at least 5 corridors and 3 HS6 chapters
- audit trail provision linkage validated against source_id mismatches
- static-reference cache enabled by default with documented invalidation
- nim_eval scaffold in place for future model tuning regression testing
- verified gate checklist recorded in production_runbook.md

---

## Prompt Books

### 1. Backend Hardening

**Status: ✓ Completed 24 March 2026**

File:
- [docs/dev/Backend Hardening — Vibecoding Prompts.md](docs/dev/Backend%20Hardening%20%E2%80%94%20Vibecoding%20Prompts.md)

This book covers:
- deterministic blocker correctness
- contract freeze for assessment and audit APIs
- audit-safe persistence strategy
- authentication and rate limiting
- liveness and readiness checks
- structured logging and timeout safety
- environment completeness
- Docker and CI
- coverage, property-based testing, and load scaffolding
- provenance hardening and production runbooks

### 2. NIM Readiness

**Status: ✓ Completed 24 March 2026**

File:
- [docs/dev/NIM Readiness — Vibecoding Prompts.md](docs/dev/NIM%20Readiness%20%E2%80%94%20Vibecoding%20Prompts.md)

This book covers:
- backend prerequisite validation for NIM
- assistant-facing contract harness
- contract-safe case and audit integration
- NIM schema and service boundaries
- clarification and explanation orchestration
- hallucination guards and fallback behavior
- final assistant integration and full-flow validation

### 3. Production Gate Stabilisation

**Status: START HERE — resolves 2026-03-26 audit gaps**

File:
- [docs/dev/Production Gate — Vibecoding Prompts.md](docs/dev/Production%20Gate%20%E2%80%94%20Vibecoding%20Prompts.md)

This book covers:
- container startup ambiguity and env documentation cleanup
- production cache activation with invalidation semantics
- NIM input length cap and injection guard
- evidence risk-tier filter wiring
- golden-case corridor corpus expansion (2 → 5+ corridors)
- NIM evaluation scaffold for regression protection
- audit trail provision linkage integrity
- full gate validation with Decision Renderer and NIM Integration handoff checklist

### 4. Decision Renderer

**Status: Blocked — start only after Production Gate exit criteria are met**

File:
- [docs/dev/Decision Renderer — Vibecoding Prompts.md](docs/dev/Decision%20Renderer%20%E2%80%94%20Vibecoding%20Prompts.md)

This book covers:
- deterministic decision renderer
- counterfactual engine for quantified gap analysis
- NIM rendering service with contradiction guardrails
- assistant orchestration wiring
- end-to-end rendering validation

### 5. NIM Integration (Advanced)

**Status: Blocked — start only after Decision Renderer exit criteria are met**

File:
- [docs/dev/NIM Integration — Vibecoding Prompts.md](docs/dev/NIM%20Integration%20%E2%80%94%20Vibecoding%20Prompts.md)

This book covers:
- explanation style refinement
- model rollout controls
- NIM interaction analytics
- session-aware follow-up support
- NIM evaluation set for regression testing

---

## Required Execution Order

1. ✓ Finish the backend hardening prompt book.
2. ✓ Confirm the backend exit criteria are met.
3. ✓ Start and finish the NIM readiness prompt book.
4. **Close all Production Gate exit criteria (start here).**
5. Start the Decision Renderer prompt book.
6. Start the NIM Integration (advanced) prompt book.
7. Only after all five books are stable should you build the trader-facing UI.

---

## Backend Exit Criteria Before NIM

**All satisfied as of 24 March 2026:**

- missing tariff coverage is a true hard blocker ✓
- assessment and audit contracts are frozen and tested ✓
- assistant-triggered decisions persist replayable audit trails ✓
- auth and rate limits are in place ✓
- liveness and readiness checks exist ✓
- CI and container artifacts exist ✓
- coverage reporting and deterministic edge-case tests exist ✓

## Production Gate Exit Criteria Before Decision Renderer

These must all be true before starting Decision Renderer Prompt 1:

- Dockerfile refuses to start without an explicit UVICORN_WORKERS value
- .env.example has no duplicate configuration blocks
- NIM input is capped at 2000 characters with structured handling for oversized input
- NIM metadata never enters EligibilityRequest after mapping
- Evidence risk_category is wired to confidence_class (or documented as a stub)
- Golden-case corpus covers at least 5 directed corridors and 3 HS6 chapters
- Provision source_id mismatches are detected, logged, and excluded
- CACHE_STATIC_LOOKUPS defaults to true with documented invalidation procedure
- tests/nim_eval/ scaffold exists, runs with mocked NimClient, is documented
- Full test suite passes: ≥90% unit coverage, ≥80% integration coverage
- production_runbook.md contains a verified gate section for the 2026-03-26 audit

## Handoff Checklist

Before handing work from backend hardening to NIM readiness (already complete):

1. The assessment and audit response examples in the docs match the tested contract.
2. The assistant-facing implementation will be able to rely on the canonical document field name already chosen by the backend.
3. Replay identifiers needed by an assistant flow are returned or derivable from the persisted backend path.
4. Runtime settings required for auth, rate limiting, logging, and readiness are documented in the checked-in environment docs.

Before handing work from Production Gate to Decision Renderer:

1. All 11 Production Gate exit criteria above are true.
2. tests/nim_eval/ cases reference the same HS6 codes and corridors as the expanded golden corpus.
3. The production_runbook.md gate section has been written and reviewed.
4. The Dockerfile and .env.example changes have been smoke-tested with docker compose -f docker-compose.prod.yml config.