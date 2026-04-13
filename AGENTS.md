# AGENTS.md — AfCFTA Live

Custom instructions for Codex (and any coding agent) working in this repo.
Read this file before touching code. It overrides general defaults.

---

## 1. What This Repo Is

AfCFTA Live is a deterministic trade-eligibility engine with an additive NIM
assistant overlay and a trader UI. Decisions are legal artifacts. They must
replay identically months later, regardless of what changes in the underlying
data.

Current build state (as of 2026-04-10):

- deterministic backend + NIM foundation: ~86%
- deployment-ready: ~62%
- world-class public trader product: ~48%

Every change must move one of those numbers up honestly, or explicitly mark a
blocker. Do not invent closure.

---

## 2. Shell And Execution Boundary

- **You create and edit files. The human runs commands.**
- Do not execute `pytest`, `docker`, `npm`, migrations, load harnesses, or any
  deployment action unless the prompt explicitly says to.
- When a change needs verification, emit the exact commands the human should
  run and what "pass" looks like. Do not claim a test passed if you did not run
  it.
- Never fabricate artifact paths, gate results, SHAs, or dataset manifests.

---

## 3. Non-Negotiable Invariants

These are failure-closed rules. A change that violates any of them must be
rejected or converted into an explicit, documented blocker.

1. **Deterministic ownership stays in the engine.** NIM and UI may explain,
   clarify, render, or proxy. They never decide. No probabilistic eligibility.
   No confidence guessing. No silent inference.
2. **Replay safety at write time, not replay time.** New evaluations must
   persist immutable rule/tariff/provision snapshots in the same atomic write
   as the decision snapshot. If you cannot freeze the snapshot, do not persist
   the evaluation.
3. **No browser-visible backend secrets.** `API_AUTH_KEY`, `NIM_API_KEY`, and
   any equivalent reusable credential must never appear in the Vite bundle,
   browser devtools, or browser network traffic. `VITE_API_KEY` is being
   removed; do not reintroduce it.
4. **Two API families, kept distinct:**
   - `/api/v1/` — machine and operator clients. API-key protected.
   - `/web/api/` — browser clients. Session / BFF boundary. No shared secret.
   Never collapse, cross-wire, or re-expose these.
5. **Blocker semantics are sacred.** Do not weaken blocker logic, audit
   requirements, or replay guarantees to make a gate easier to pass.
6. **No geography expansion.** v0.1 countries and corridors are locked. Do not
   widen scope without an explicit prompt.
7. **Fail-closed gates.** Missing artifact, stale artifact, unverifiable
   runbook step → fail. Never pass a gate on historical evidence.
8. **Legacy rows are labeled, not upgraded.** Pre-freeze evaluations replay via
   documented live-fallback and must be clearly marked as such. Do not
   retroactively mint `snapshot_frozen` for them.

---

## 4. Repo Layout You Should Know

```
app/
  api/v1/            # machine/operator routes (API-key)
  api/web/           # browser routes (session/BFF)
  services/          # eligibility_service, audit_service, nim orchestration
  repositories/      # evaluations, sources, provisions, tariffs
  schemas/           # pydantic contracts (audit.py, assessment.py, ...)
  config.py          # all new config surfaces land here
frontend/
  src/api/client.ts  # browser API client — no shared secret
tests/
  unit/
  integration/
  load/              # 10c and 100c harnesses
docs/
  dev/
    production_runbook.md
    rollback_runbook.md
    testing.md
    parser_promotion_workflow.md
    prompts/         # progress + gap-closure handbooks (source of truth)
  api/
  FastAPI_layout.md
.github/workflows/ci.yml
docker-compose.prod.yml
.env.example
```

Read the relevant files before editing. Do not guess at shapes.

---

## 5. Change Hygiene

Every behavior-changing PR must land **code + tests + docs together**. A change
is not done until all three are aligned.

- **Code:** minimal diff to the cited files. Do not drive-by refactor.
- **Tests:** the narrowest test that would fail without the fix. Prefer pinning
  the exact contract (schema field present, snapshot frozen, secret absent)
  over broad behavioral tests.
- **Docs:** if you change a config, route, header, artifact name, or operator
  workflow, update `.env.example`, `app/config.py`, the relevant runbook, and
  any doc that references the old shape. Stale docs are a gate failure.

When adding a new config surface, update all four in the same change:
`app/config.py`, `.env.example`, the runbook, and CI/verification docs.

---

## 6. Provenance And Audit Rules

When touching `eligibility_service`, `audit_service`, `evaluations_repository`,
or `schemas/audit.py`:

- Persist provenance **inline with the evaluation write**, atomically.
- Rule snapshots must include: `source_id`, `short_title`, `version_label`,
  `publication_date`, `effective_date`, `page_ref`, `table_ref`, `row_ref`,
  `captured_at`, `supporting_provisions`.
- Tariff snapshots must include: `schedule_source_id`, `rate_source_id`,
  `short_title`, `version_label`, `publication_date`, `effective_date`,
  `line_page_ref`, `rate_page_ref`, `table_ref`, `row_ref`, `captured_at`,
  `supporting_provisions`.
- Supporting provisions: max 5 per source, deterministically ordered, thin
  fields only (`provision_id`, `source_id`, `article_label`, `clause_label`,
  `topic_primary`, `text_excerpt`). No full bodies. No unbounded lists. No
  binaries.
- Replay must read from the persisted snapshot for frozen evaluations and from
  live sources only for explicitly labeled legacy rows.

---

## 7. NIM Assistant Rules

- Contracts are in `app/api/v1/assistant.py` and `app/schemas/`. Respect them.
- `user_input` is capped at 2000 characters. Do not raise silently.
- NIM is additive. It never writes deterministic decision fields.
- Failures must route through the circuit breaker / degraded path. Log
  breaker state, retry count, timeout, and fallback reason with safe
  cardinality metrics.
- Never let a NIM outage block or corrupt a deterministic assessment.

---

## 8. Frontend Rules

- Vanilla-preserving: follow the existing stack. Do not introduce new
  frameworks, CSS preprocessors, or build tools.
- All browser API calls go through `/web/api/` via the session-aware client.
- No `import.meta.env.VITE_API_KEY`. No backend secrets in bundle.
- Every new UI state needs explicit error, empty, retry, and degraded-mode
  rendering. Trust cues (citations, provenance, replay linkage) must be
  visible on any decision surface.
- Accessibility and mobile are gate items, not polish.

---

## 9. Performance And SLOs

- 10c and 100c gates are the committed bars. Do not silently relax them.
- Hot-path changes must be justified by a fresh measurement, not intuition.
- Worker, Redis, and pool sizing live in `app/config.py` and the production
  runbook. Keep them in sync.

---

## 10. Observability

New failure modes must be observable. When adding behavior that can fail,
emit:

- a structured log with `request_id`
- a Prometheus counter or histogram with bounded labels
- a runbook entry describing what operators do when it fires

Specifically track: replay freeze failures, legacy-fallback usage, NIM
degraded mode, browser auth/session failures, persistence failures, pool
pressure.

---

## 11. How To Respond To A Prompt From The Handbook

The `docs/dev/prompts/` handbooks are the canonical task queue. When handed a
numbered prompt:

1. Read every file the prompt cites before editing anything.
2. Work only in the files the prompt names first, unless a dependency forces a
   wider change — in which case flag it.
3. Produce code + tests + docs in the same change.
4. Return a summary citing: exact files changed, exact tests added, exact
   verification commands for the human to run, and any honest blocker you
   hit.
5. Do not mark the prompt done. The human marks status in the Prompt Status
   table after running the gate.

---

## 12. What Not To Do

- Do not call a private-beta access pattern "public-user auth".
- Do not hide stale artifacts under a new folder name and call them
  current-head evidence.
- Do not mint `snapshot_frozen = true` on legacy rows to pass a gate.
- Do not introduce probabilistic scoring or confidence heuristics anywhere in
  the decision path.
- Do not expand geography, HS chapter coverage, or corridor set without an
  explicit prompt.
- Do not collapse `deployment_ready` and `public_launch_ready` into a single
  verdict.
- Do not edit the handbooks in `docs/dev/prompts/` as part of closure work —
  they are the spec, not the output.

---

## 13. Definition Of Done

A task is done only when all of these are true:

1. The named gap is closed in code, or converted into an explicit documented
   blocker with verified gate state.
2. The narrowest useful tests pin the behavior and would fail without the fix.
3. Operator and public docs reflect the new runtime truth.
4. The change summary cites exact files, exact tests, and exact verification
   evidence the human can reproduce.

If any of those four are missing, the task is not done — regardless of how
clean the diff looks.