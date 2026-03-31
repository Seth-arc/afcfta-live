# AfCFTA Live Decision Renderer Prompt Book

> **How to use**: Copy-paste each prompt into your coding agent in order. Run the
> commands it tells you to run. Do not skip ahead. Each prompt depends on the
> one before it.
>
> **Start this book only after completing the NIM Readiness prompt book**.
>
> **Primary references**:
> - docs/dev/NIM Readiness — Vibecoding Prompts.md for required prerequisites
> - docs/dev/post_readiness_decision_renderer_reference.md for exact implementation contracts
> - AGENTS.md for deterministic boundary rules
> - docs/FastAPI_layout.md for route, service, repository, and schema boundaries

---

## Goal

Add a post-engine rendering layer that turns safe, structured assessment results
into decision-support language — with quantified gaps, fix strategies, and next
steps — while never altering the deterministic legal outcome.

## Non-goals

- Do not change the eligibility engine's legal decision logic.
- Do not let the renderer override `eligible`, `pathway_used`, `rule_status`, `tariff_outcome`, or `confidence_class`.
- Do not allow NIM-generated rendering to fabricate facts, thresholds, or pathway outcomes.
- Do not let rendering failures block or corrupt deterministic assessment results.

## Working Rules

Use these rules for every prompt in this book:

1. The rendering layer is additive only. Deterministic fields are never rewritten by it.
2. The counterfactual engine is deterministic. It reads real pathway failures and quantifies real gaps.
3. The NIM rendering service must validate its structured output and reject contradictions before use.
4. If NIM rendering fails validation, fall back to the deterministic `DecisionRenderer` output. Never fabricate fallback text.
5. Keep `assistant_rendering` and `assessment` as separate, non-overlapping sections in the response envelope.

## Rendering Invariants

Unless a prompt explicitly narrows scope further, the rendering layer must preserve these invariants:

1. `headline` must not claim qualification when `eligible == false` or failure when `eligible == true`.
2. `summary` must not introduce pathways not present in `pathway_analysis`.
3. `gap_analysis` must not invent a delta not present in `counterfactuals`.
4. `fix_strategy` must not propose unsupported legal pathways.
5. `warnings` must only reference pending rule status, incomplete facts, or real deterministic caveats.
6. The response envelope must keep `assessment` fields identical to what the deterministic engine produced.

## Definition Of Done Per Prompt

A prompt is only complete when all of the following are true:

1. The named service or schema exists and follows the intended boundary.
2. The relevant unit or integration tests pin the contract or failure mode.
3. Contradiction rejection and fallback behavior are tested explicitly.
4. The prompt summary can name the exact rendering guarantees now in place.

---

## Required Preconditions
Before Prompt 1, verify all of these are already true:

- NIM readiness book is complete (Prompts 1–12 done)
- Assistant-facing contracts are pinned in integration tests
- NIM input maps cleanly to the frozen backend request contract
- Clarification targets real engine gaps
- Explanations cannot contradict deterministic results
- Every assistant-triggered decision is replayable through audit
- NIM failures degrade gracefully without corrupting legal decision behavior

If any of these are false, stop and complete the NIM Readiness book first.

---

## Prompt 1 — Implement the deterministic decision renderer

```
Read docs/dev/post_readiness_decision_renderer_reference.md Part I.
Read app/services/nim/explanation_service.py.
Read app/schemas/assessments.py.

Implement the production-grade deterministic decision renderer.

Work in these files:
- app/services/nim/decision_renderer.py
- tests/unit/test_decision_renderer.py

Create:
- RenderedDecision dataclass with fields: headline, summary, gap_analysis, fix_strategy, next_steps, warnings
- DecisionRendererError exception
- DecisionRenderer class with a render() method

The render() method accepts:
- engine_payload: the full structured assessment output
- counterfactuals: an optional list of counterfactual result mappings

Requirements:
1. Validate that engine_payload contains all required top-level keys before rendering.
2. Validate that decision contains eligible, confidence_class, and rule_status before rendering.
3. Build headline, summary, gap_analysis, fix_strategy, next_steps, and warnings purely from deterministic inputs.
4. Never alter any deterministic field.
5. Return a minimal deterministic narrative even when counterfactuals are absent.
6. Humanize missing fact names using a known mapping.

Add tests covering:
- eligible result → clean qualifying narrative with pathway reason
- failed VNM → quantified gap if counterfactual delta is present
- failed CTH → tariff-shift narrative without inventing a gap
- missing facts → incomplete narrative with no fake certainty
- pending rule status → warning appears in warnings list
- malformed payload → DecisionRendererError raised

When done, summarize:
- the rendering logic for each output field
- which inputs drive each field
- the validation rules that guard against bad payloads
```

**You run:**
```bash
python -m pytest tests/unit/test_decision_renderer.py -v
```
# Completed 31 March
---

## Prompt 2 — Implement the counterfactual engine

```
Read docs/dev/post_readiness_decision_renderer_reference.md Part III.
Read app/services/nim/decision_renderer.py from Prompt 1.
Read app/schemas/assessments.py for the pathway_analysis contract.

Implement the deterministic counterfactual engine.

Work in these files:
- app/services/nim/counterfactual_engine.py
- tests/unit/test_counterfactual_engine.py

Create:
- CounterfactualResult dataclass with fields: kind, message, delta, pathway_code, fact_key
- CounterfactualEngine class with a generate() method

The generate() method accepts:
- normalized_facts: the parsed and validated user-stated facts
- pathway_analysis: the list of pathway results from the deterministic engine
- selected_pathway: optional pathway code

Pathway cases to handle:
- VNM: compute delta between actual vnom_percent and threshold_percent; emit value_reduction result if actual exceeds threshold
- VA: compute delta between threshold_percent and actual va_percent; emit value_add_increase result if actual is below threshold
- CTH: emit tariff_shift_fix with message about non-originating input reclassification
- CTSH: emit tariff_shift_fix with message about subheading-level reclassification
- WO: emit origin_fix with message about wholly obtained confirmation
- PROCESS: emit process_fix with message about performing the required manufacturing process

Requirements:
1. Skip pathways where passed is not False.
2. Only emit quantified deltas when both actual and threshold values are available.
3. Deduplicate results by kind, message, and pathway_code.
4. Never speculate unsupported fixes or invent legal alternatives.
5. Use Decimal arithmetic for all percentage comparisons to avoid float drift.

Add tests covering:
- VNM failure with known actual and threshold → correct delta and message
- VA failure with known actual and threshold → correct delta and message
- CTH failure → correct fix message, no delta
- passed pathways → not included in results
- missing threshold value → no quantified result emitted, no crash
- deduplication across repeated pathway codes

When done, summarize:
- the pathway codes handled
- how deltas are computed and formatted
- the deduplication strategy
```

**You run:**
```bash
python -m pytest tests/unit/test_counterfactual_engine.py -v
```
# Completed 31 March
---

## Prompt 3 — Implement the NIM rendering service

```
Read docs/dev/post_readiness_decision_renderer_reference.md Part II.
Read app/services/nim/client.py.
Read app/services/nim/decision_renderer.py from Prompt 1.
Read app/services/nim/counterfactual_engine.py from Prompt 2.

Implement the NIM rendering service that submits the truth payload to NIM,
validates the structured response, and falls back to DecisionRenderer on failure.

Work in these files:
- app/services/nim/rendering_service.py
- app/schemas/nim/rendering.py
- tests/unit/test_rendering_service.py

Create:
- NimRendering schema (strict Pydantic model) with fields:
  - headline: str
  - summary: str
  - gap_analysis: str | None
  - fix_strategy: str | None
  - next_steps: list[str] with minItems=2, maxItems=4
  - warnings: list[str] with maxItems=3
- RenderingService class

The RenderingService.render() method should:
1. Build the system prompt from the reference document.
2. Build the user prompt from the truth payload (decision, product, pathway_analysis, counterfactuals, missing_facts, evidence_required, tariff_outcome).
3. Call NimClient.generate_json().
4. Parse and validate the response against NimRendering.
5. Run contradiction guardrails:
   - headline must not claim qualification when eligible == false
   - headline must not claim failure when eligible == true
   - summary must not introduce pathways absent from pathway_analysis
   - gap_analysis must not invent a delta absent from counterfactuals
   - fix_strategy must not propose pathways absent from the rule set
   - warnings must only reference pending status, incomplete facts, or real caveats
6. If any validation or guardrail fails, discard NIM output and return DecisionRenderer output instead.
7. If NIM is disabled or times out, return DecisionRenderer output without raising.

Requirements:
1. Never let a NIM failure block the assessment result.
2. Never return partial or unvalidated NIM output.
3. Keep fallback behavior explicit and logged.
4. Do not mix NIM rendering logs into the deterministic audit trail.

Add tests covering:
- valid NIM response → returned as NimRendering
- contradictory headline → rejected and fallback returned
- invented pathway in summary → rejected and fallback returned
- invented delta in gap_analysis → rejected and fallback returned
- NIM timeout → fallback returned without crash
- invalid JSON → fallback returned without crash
- NIM disabled → fallback returned immediately

When done, summarize:
- the prompt contract submitted to NIM
- the contradiction guardrails applied
- the fallback behavior per failure mode
```

**You run:**
```bash
python -m pytest tests/unit/test_rendering_service.py -v
```
# Completed 31 March
---

## Prompt 4 — Wire the rendering layer into the assistant orchestration

```
Read app/api/v1/assistant.py.
Read app/services/nim/rendering_service.py from Prompt 3.
Read app/services/nim/counterfactual_engine.py from Prompt 2.
Read the existing assistant integration tests.

Wire the rendering layer into the assistant orchestration flow.

Extend the flow in app/api/v1/assistant.py to:
1. Run the deterministic assessment (already in place).
2. Generate structured explanation (already in place).
3. Generate counterfactuals using CounterfactualEngine from the engine output.
4. Run NIM rendering over the truth payload using RenderingService.
5. Attach assistant_rendering to the response.
6. Keep assessment fields separate and unchanged.

Response envelope must follow this shape:

{
  "assessment": {
    "eligible": ...,
    "pathway_used": ...,
    "rule_status": ...,
    "tariff_outcome": { ... }
  },
  "assistant_rendering": {
    "headline": "...",
    "summary": "...",
    "gap_analysis": "...",
    "fix_strategy": "...",
    "next_steps": ["..."],
    "warnings": []
  }
}

Requirements:
1. Keep the route thin. Move rendering logic into RenderingService.
2. Do not allow rendering failure to block the assessment result.
3. If rendering fails, include a minimal deterministic rendering in assistant_rendering.
4. Do not alter any assessment field as part of rendering.
5. Preserve audit linkage from the existing persistence path.
6. Preserve auth and rate limiting from backend hardening.

Work in these files:
- app/api/v1/assistant.py
- tests/integration/test_assistant_api.py

Extend integration tests to cover:
- eligible result → assistant_rendering has qualifying headline and no fix_strategy
- failed VNM result → assistant_rendering has quantified gap_analysis and fix_strategy
- missing facts → assistant_rendering reflects incomplete state
- NIM rendering fallback → deterministic rendering returned, assessment unchanged

When done, summarize:
- how rendering is triggered in the orchestration flow
- how the response envelope keeps assessment and rendering separate
- which failure modes are tested
```

**You run:**
```bash
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Prompt 5 — Add end-to-end rendering validation

```
Read all rendering and counterfactual tests.
Read tests/integration/test_nim_full_flow.py.

Add a full end-to-end validation scenario for the rendering layer.

Work in these files:
- tests/integration/test_decision_renderer_full_flow.py
- tests/unit/test_decision_renderer.py if helper fixtures are needed

Cover all seven required test cases:
1. Eligible result → clean qualifying narrative, no fix_strategy, no gap_analysis.
2. Failed VNM → quantified gap_analysis and actionable fix_strategy.
3. Failed CTH → tariff-shift fix narrative, no numeric gap.
4. Missing facts → incomplete assessment narrative, no invented certainty.
5. Pending rule status → warning appears in warnings, result is not blocked.
6. Contradictory NIM rendering → rejected and DecisionRenderer fallback used instead.
7. Empty or malformed NIM rendering → fallback used, no crash.

Assertions across all scenarios:
1. assessment fields are identical to what the deterministic engine produced.
2. assistant_rendering never overrides eligible, pathway_used, rule_status, or tariff_outcome.
3. No hallucinated fields appear in assistant_rendering.
4. The full response can be replayed through the audit layer using the persisted identifiers.
5. The assistant_rendering shape is stable across all scenarios.

When done, summarize:
- the scenarios covered and their assertions
- the deterministic invariants protected in each scenario
- any remaining gaps before trader UI work
```

**You run:**
```bash
python -m pytest tests/integration/test_decision_renderer_full_flow.py -v
python -m pytest tests/unit/test_decision_renderer.py tests/unit/test_counterfactual_engine.py tests/unit/test_rendering_service.py -v
python -m pytest tests/integration/test_assistant_api.py -v
```

---

## Recommended Execution Groups

### Group 1 — Deterministic rendering foundation

Prompts 1–2

### Group 2 — NIM rendering service

Prompt 3

### Group 3 — Orchestration wiring and validation

Prompts 4–5

---

## Exit Criteria

- `decision_renderer.py` is implemented and its output is contract-pinned by unit tests
- `counterfactual_engine.py` produces quantified, deterministic gap results from real pathway failures
- `rendering_service.py` validates NIM structured output and rejects contradictions before use
- fallback to `DecisionRenderer` is tested for every NIM failure mode
- the assistant response envelope keeps `assessment` and `assistant_rendering` separate
- all seven test scenarios from the reference document pass
- no deterministic engine field is altered by the rendering layer

Once these are true, the backend exposes a decision-support interface that is
safe, auditable, and ready for a trader-facing UI.
