# AfCFTA Live NIM Readiness Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Start this book only after finishing the backend hardening book**.
>
> **Primary references**:
> - docs/dev/Backend Hardening — Vibecoding Prompts.md for required prerequisites
> - docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md for NIM blockers and contract drift findings
> - docs/dev/NIM Integration — Vibecoding Prompts.md for the earlier integration direction
> - AGENTS.md for deterministic boundary rules
> - docs/FastAPI_layout.md for route, service, repository, and schema boundaries

---

## Goal

Prepare and implement a NIM-facing orchestration layer that sits safely on top of
the deterministic engine, never changes legal logic, and always preserves replayable audit behavior.

## Non-goals

- Do not change the eligibility engine’s legal decision logic.
- Do not let NIM bypass case or audit persistence requirements.
- Do not introduce freeform explanation output that can contradict deterministic results.

## Working Rules

Use these rules for every prompt in this book:

1. NIM may parse, clarify, and explain. It may not decide eligibility, fabricate legal facts, or weaken persistence guarantees.
2. Keep assistant routes thin and keep NIM business logic inside app/services/nim/.
3. If a prompt touches response shape, pin it with tests before layering on more behavior.
4. Use the frozen backend field names exactly, including the canonical document field name chosen during backend hardening.
5. Prefer explicit fallbacks and explicit validation errors over opaque retries or magical defaults.

## Assistant Response Invariants

Unless a prompt explicitly narrows scope further, the assistant flow should preserve these invariants:

1. The assistant response must make it clear whether the flow ended in clarification, input rejection, or a completed assessment.
2. Any completed assessment must include or reference the persisted identifiers needed for audit replay.
3. Explanation content is additive only. It must never overwrite or reinterpret deterministic decision fields.
4. NIM-only metadata, such as confidence scores or prompt assumptions, must not leak into live engine requests unless the backend contract explicitly accepts them.
5. Use `existing_documents` rather than the older `submitted_documents` wording unless backend hardening deliberately introduced a documented alias.

## Definition Of Done Per Prompt

A prompt is only complete when all of the following are true:

1. The named NIM schema, service, or route exists and follows the intended boundary.
2. The relevant unit or integration tests pin the contract or failure mode.
3. Any newly required settings or operational behavior are documented.
4. The prompt summary can name the exact replay, validation, and fallback guarantees now in place.

---

## Required Preconditions

Before Prompt 1, verify all of these are already true:

- missing tariff coverage is a hard blocker
- assessment and audit contracts are frozen
- replay-safe persistence exists for interface-triggered decisions
- auth and rate limiting exist on non-health endpoints
- liveness and readiness checks exist

If any of these are false, stop and finish the backend hardening book first.

---

## Prompt 1 — Validate backend prerequisites and codify the NIM boundary

```
Read docs/dev/AFCFTA-LIVE_REPO_AUDIT_2026-03-23.md sections on NIM blockers.
Read AGENTS.md sections on deterministic execution order, audit requirements, and code organization.
Read docs/dev/NIM Integration — Vibecoding Prompts.md.

Before adding NIM services, codify the architectural boundary between NIM orchestration and the deterministic engine.

Work in these files first:
- docs/dev/NIM Integration — Vibecoding Prompts.md
- README.md
- docs/api/endpoints.md if assistant path documentation is needed

Requirements:
1. Remove or rewrite stale assumptions from the older NIM prompt book.
2. Make backend prerequisites explicit.
3. State clearly that NIM may normalize, clarify, and explain, but never decide eligibility.
4. State clearly that assistant-triggered decisions must be replayable through the audit layer.
5. Align terminology with the frozen backend contracts.
6. Explicitly call out any field-name migrations that the older NIM file still assumes.

When done, summarize:
- the stale assumptions you removed
- the new prerequisite gate
- the codified NIM boundary
```

**You run:**
```bash
git diff docs/dev/NIM\ Integration\ —\ Vibecoding\ Prompts.md
```

---

## Prompt 2 — Build a thin assistant-facing contract harness

```
Read the frozen contracts in app/schemas/assessments.py and app/schemas/audit.py.
Read the backend persistence strategy that guarantees replayable interface-triggered decisions.

Create a thin assistant-facing contract harness before adding live NIM model calls.

Work in these files first:
- app/api/v1/assistant.py
- app/api/router.py
- app/schemas/nim/
- tests/integration/test_assistant_api.py

Requirements:
1. Do NOT add actual model-calling logic yet.
2. Define the minimum combined response shape for an assistant flow.
3. Include explicit linkage to the persisted case or evaluation identifiers needed for replay.
4. Keep the route thin.
5. Add integration tests that pin the assistant-facing response contract.
6. Align all field names with the frozen backend contracts.
7. Make the response envelope explicit about whether it contains clarification, assessment, explanation, or structured error content.

When done, summarize:
- the assistant endpoint shape
- the persisted identifiers it returns
- the contract tests that now exist as a guardrail
```

**You run:**
```bash
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Prompt 3 — Create NIM module structure with strict dependency boundaries

```
Read AGENTS.md section "Code Organization".
Read docs/FastAPI_layout.md.
Read the assistant harness from Prompt 2.

Create a NIM integration module with strict separation from the deterministic engine.

Create this structure if it does not already exist:

app/services/nim/
  - __init__.py
  - intake_service.py
  - clarification_service.py
  - explanation_service.py
  - client.py

app/schemas/nim/
  - intake.py
  - clarification.py
  - explanation.py

Requirements:
1. Do NOT move business logic out of eligibility_service, evidence_service, or audit_service.
2. Keep NIM as a thin orchestration layer.
3. Prepare services for dependency injection.
4. Stub out only the service methods needed by the assistant harness.
5. Keep file names and service boundaries aligned with the assistant contract.
6. Add minimal module-level docstrings or comments only where they clarify responsibility boundaries.

When done, summarize:
- files created
- service boundaries
- what intentionally remains outside the NIM module
```

**You run:**
```bash
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Prompt 4 — Implement the NIM client wrapper with safe failure semantics

```
Read app/services/nim/client.py.
Read app/config.py.

Implement a generic NIM client wrapper.

Requirements:
1. Use async HTTP client behavior appropriate to the existing stack.
2. Accept model name, system prompt, and user input.
3. Return raw JSON string response.
4. Add timeout and retry behavior.
5. Do NOT parse or validate here.
6. Make failures easy for the orchestration layer to handle deterministically.

Add:
- class NimClient
- method: async generate_json(prompt: str, input_text: str)

Environment:
- NIM_BASE_URL
- NIM_API_KEY
- NIM_MODEL
- NIM_ENABLED
- NIM_TIMEOUT_SECONDS
- NIM_MAX_RETRIES

When done, summarize:
- request format
- timeout and retry behavior
- how failures surface to callers
```

**You run:**
```bash
python -m pytest tests/unit -q
```

---

## Prompt 5 — Define and validate the intake schema against live backend contracts

```
Read app/schemas/assessments.py.
Read the current NIM design notes.

Implement the Pydantic intake schema for NIM-assisted request normalization.

Work in these files first:
- app/schemas/nim/intake.py
- tests/unit/

Create:
- HS6Candidate
- TradeFlow
- AssessmentContext
- MaterialInput
- ProductionFacts
- NimConfidence
- NimAssessmentDraft

Requirements:
1. Enforce strict typing.
2. Validate HS6 shape and confidence ranges.
3. Disallow extra fields.
4. Use field names that map cleanly to the frozen backend contracts.
5. Do not invent backend-only fields that are not actually accepted by the live service.
6. Separate user-stated facts from NIM-generated confidence or parsing metadata so the mapping layer can drop metadata cleanly.

When done, summarize:
- key validation constraints
- how the schema maps to live assessment inputs
```

**You run:**
```bash
python -m pytest tests/unit -q
```

---

## Prompt 6 — Implement intake parsing and mapping to the live assessment request

```
Read app/services/nim/intake_service.py.
Read the frozen assessment request contract.

Implement parse_user_input() and the mapping from NIM draft to live assessment request.

Work in these files first:
- app/services/nim/intake_service.py
- tests/unit/test_nim_intake_service.py
- tests/unit/test_nim_mapping.py

Requirements:
1. Build a system prompt.
2. Send user input to NimClient.
3. Parse JSON strictly.
4. Validate against NimAssessmentDraft.
5. Map only supported backend fields.
6. Drop NIM-only metadata such as confidence or assumptions before calling the engine.
7. Do not fill missing legal facts artificially.
8. Keep the mapping aligned with the canonical document field name chosen in backend hardening.
9. Make the mapping function independently testable so contract drift shows up without needing a live model call.

When done, summarize:
- the validation flow
- the mapping rules
- the dropped NIM-only fields
```

**You run:**
```bash
python -m pytest tests/unit/test_nim_intake_service.py -v
python -m pytest tests/unit/test_nim_mapping.py -v
```

---

## Prompt 7 — Implement clarification schema and service tied to real missing facts

```
Read app/services/nim/clarification_service.py.
Read the engine response fields for `missing_facts`, `missing_evidence`, and structured failures.

Implement the clarification schema and service.

Work in these files first:
- app/schemas/nim/clarification.py
- app/services/nim/clarification_service.py
- tests/unit/test_nim_clarification_service.py

Requirements:
1. Clarification must target actual missing backend facts or evidence gaps.
2. It must produce one focused follow-up question at a time.
3. It must not infer eligibility or promise outcomes.
4. Validation should reject empty or structurally weak clarification payloads.
5. The service should be deterministic in how it prioritizes missing items before asking NIM to phrase the question.
6. Prefer core legal facts needed to unblock assessment before supporting evidence questions when both are missing.

When done, summarize:
- schema constraints
- priority logic for missing facts
- the guardrails against speculative guidance
```

**You run:**
```bash
python -m pytest tests/unit/test_nim_clarification_service.py -v
```

---

## Prompt 8 — Implement explanation schema and hallucination-safe explanation service

```
Read app/services/nim/explanation_service.py.
Read the assessment response contract and audit replay contract.

Implement the explanation schema and service.

Work in these files first:
- app/schemas/nim/explanation.py
- app/services/nim/explanation_service.py
- tests/unit/test_nim_explanation_service.py

Requirements:
1. Explanation output must be structured.
2. It must not alter deterministic engine fields.
3. Reject explanation payloads that contradict:
   - eligible
   - pathway_used
   - rule_status
   - tariff_outcome
   - confidence_class
4. Keep next steps and warning notes tied to real engine outputs.
5. Add explicit tests for hallucination or contradiction rejection.
6. Provide a minimal deterministic fallback explanation shape that can be returned without a model.

When done, summarize:
- response guarantees
- contradiction checks
- fallback behavior when explanation validation fails
```

**You run:**
```bash
python -m pytest tests/unit/test_nim_explanation_service.py -v
```

---

## Prompt 9 — Wire the assistant endpoint to the live engine, persistence path, and NIM services

```
Read app/api/v1/assistant.py, app/api/deps.py, and the NIM services.
Read the replay-safe persistence strategy from backend hardening.

Implement the real assistant orchestration flow.

Flow:
1. Parse natural-language input with intake_service.
2. If confidence or completeness is insufficient, return a clarification response.
3. Map to the live assessment request.
4. Ensure a replayable persistence path exists.
5. Call the deterministic eligibility service.
6. Call the explanation service.
7. Return the combined response.

Requirements:
1. Keep the route thin.
2. Do not allow the assistant path to bypass persistence guarantees.
3. Do not let NIM alter deterministic outputs.
4. Preserve authenticated and rate-limited behavior from backend hardening.
5. Add integration tests that cover:
   - happy path
   - clarification path
   - replay linkage
6. Make the early-exit conditions explicit, such as invalid HS, missing corridor parties, or insufficient draft completeness.

When done, summarize:
- orchestration flow
- early exit rules
- how replay-safe persistence is preserved
```

**You run:**
```bash
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Prompt 10 — Add NIM fallback behavior that never blocks deterministic assessments

```
Read all NIM services and the assistant integration tests.

Add robust fallback behavior for NIM failure modes.

Requirements:
1. If NIM intake fails, return a structured clarification or input error rather than an opaque crash.
2. If the deterministic engine can still run, NIM explanation failure must not block the assessment result.
3. If explanation fails, return a minimal deterministic summary envelope.
4. Add tests for timeout, invalid JSON, and validation rejection.
5. Keep fallback behavior explicit and easy to reason about.
6. Never fabricate clarification or explanation text from partial model output that failed validation.

When done, summarize:
- fallback behavior per failure stage
- which user-visible responses are preserved
- how deterministic outputs remain authoritative
```

**You run:**
```bash
python -m pytest tests/unit -q
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Prompt 11 — Add NIM-specific logging and audit correlation without polluting legal audit trails

```
Read app/core/logging.py and app/services/audit_service.py.
Read the assistant orchestration path.

Add NIM-specific logging that is operationally useful but distinct from the legal audit trail.

Work in these files first:
- app/services/nim/logging.py
- app/api/v1/assistant.py
- app/services/nim/
- tests/unit/

Requirements:
1. Track request_id, latency, model name, and validation outcomes.
2. Keep model I or O logging safe and configurable.
3. Do not mix NIM logs into deterministic eligibility check persistence.
4. Add enough correlation metadata to connect assistant traffic to persisted cases and evaluations.
5. Exclude raw freeform user text by default unless there is an explicit redaction-safe need.

When done, summarize:
- what is logged
- what is intentionally not logged
- how to correlate assistant events to replayable decisions
```

**You run:**
```bash
python -m pytest tests/unit -q
```

---

## Prompt 12 — Add end-to-end NIM full-flow validation

```
Read the complete assistant orchestration path and all NIM service tests.

Add a full end-to-end validation scenario for the NIM-assisted flow.

Work in these files first:
- tests/integration/test_nim_full_flow.py
- tests/integration/test_assistant_api.py if helpers are needed

Scenario:
- user asks a natural-language trade question
- NIM intake parses it
- the engine runs deterministically
- audit-safe persistence occurs
- explanation is generated or a deterministic fallback is returned

Assertions:
1. No deterministic engine fields are altered by NIM.
2. The result can be replayed through the audit layer.
3. No hallucinated fields appear.
4. The assistant response shape remains stable.

When done, summarize:
- the full flow covered
- the deterministic invariants protected
- any remaining gaps before trader UI work
```

**You run:**
```bash
python -m pytest tests/integration/test_nim_full_flow.py -v
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Recommended Execution Groups

### Group 1 — Contract and boundary alignment

Prompts 1-2

### Group 2 — Core NIM module and schemas

Prompts 3-8

### Group 3 — Assistant orchestration and hardening

Prompts 9-12

---

## Exit Criteria

- assistant-facing contracts are pinned in integration tests
- NIM input maps cleanly to the frozen backend request contract
- clarification targets real engine gaps
- explanations cannot contradict deterministic results
- every assistant-triggered decision is replayable through audit
- NIM failures degrade gracefully without corrupting legal decision behavior

Once these are true, the backend is ready for a trader-facing UI on top of a stable assistant layer.