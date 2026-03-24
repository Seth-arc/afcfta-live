# AfCFTA Live Production Readiness Prompt Books

> **How to use**: This file is now the entry point for two separate prompt books:
> one for backend hardening and one for NIM readiness.
>
> **Why it was split**:
> - backend hardening work must land first to make the service safe, deterministic, and operable
> - NIM readiness work should only begin once those backend guarantees are in place

## Working Rules

Use these rules across both prompt books:

1. Complete prompts in order. If a prompt reveals contract drift or missing prerequisites, fix that before moving on.
2. Read every file named in a prompt before editing. These books assume the implementation follows the existing route, service, repository, and schema layering.
3. Land code, tests, and documentation together when a prompt changes a contract, runtime behavior, or operator workflow.
4. Treat each prompt as finished only when its required summary can be answered with concrete files and tests.
5. Do not start NIM work while any backend exit criterion is still false.

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

---

## Prompt Books

### 1. Backend Hardening

Use this first.

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

Use this second, after backend hardening is complete.

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

---

## Required Execution Order

1. Finish the backend hardening prompt book.
2. Confirm the backend exit criteria are met.
3. Start the NIM readiness prompt book.
4. Only after both are stable should you build the trader-facing UI.

---

## Backend Exit Criteria Before NIM

- missing tariff coverage is a true hard blocker
- assessment and audit contracts are frozen and tested
- assistant-triggered decisions persist replayable audit trails
- auth and rate limits are in place
- liveness and readiness checks exist
- CI and container artifacts exist
- coverage reporting and deterministic edge-case tests exist

Once these are true, the NIM layer can be built on stable backend guarantees instead of moving contracts.

## Handoff Checklist

Before handing work from backend hardening to NIM readiness, verify all of the following in one place:

1. The assessment and audit response examples in the docs match the tested contract.
2. The assistant-facing implementation will be able to rely on the canonical document field name already chosen by the backend.
3. Replay identifiers needed by an assistant flow are returned or derivable from the persisted backend path.
4. Runtime settings required for auth, rate limiting, logging, and readiness are documented in the checked-in environment docs.