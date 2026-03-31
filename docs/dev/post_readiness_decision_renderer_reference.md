# Post-Readiness Reference: Decision Renderer, NIM Rendering Contract, and Counterfactual Engine

This reference is intended for use **after completion of the NIM Readiness prompt implementation**. It assumes the backend hardening and NIM readiness work is already complete, including:

- deterministic eligibility decisions remain authoritative
- assistant-triggered decisions are persisted and replayable
- NIM may parse, clarify, and explain, but may not decide eligibility
- explanation output must not contradict deterministic fields
- assistant responses are contract-pinned and audit-linked

These constraints are established in the NIM readiness and advanced follow-on prompt books. fileciteturn0file0 fileciteturn0file1

---

# Purpose

This document covers the next major quality step after NIM readiness:

1. **Write exact `decision_renderer.py` (production-grade)**
2. **Define the NIM prompt + schema for rendering**
3. **Add counterfactual engine logic**

This is the layer that turns a safe, structured assistant into a **decision-support interface** that feels natural and conversational while remaining grounded in computable law.

---

# Freeze Window Guardrail (Mandatory)

When the 48-hour contract freeze is active, Decision Renderer work must stay
within the frozen public-surface rules from `docs/dev/pre_nim_gate_closure.md`.

Allowed during freeze:

- additive internal renderer/counterfactual logic
- internal refactors that do not change public request/response contracts
- tests and docs that do not alter frozen schema behavior

Blocked during freeze:

- edits to frozen schema files:
  - `app/schemas/assessments.py`
  - `app/schemas/cases.py`
  - `app/schemas/audit.py`
  - `app/schemas/nim/assistant.py`
  - `app/schemas/nim/clarification.py`
  - `app/schemas/nim/explanation.py`
  - `app/schemas/nim/intake.py`
- any serialized response-shape change for assessment, audit, or assistant
- alias/discriminator/validation behavior changes that alter contract semantics

If any blocked change is made, freeze is invalidated and a fresh full gate rerun
is required from a clean commit before release declaration.

---

# What this layer is and is not

## It is

A **post-engine rendering layer** that:

- reads deterministic assessment results
- turns them into decision-grade, user-facing language
- quantifies the gap where possible
- explains what to change next
- preserves replay and audit linkage

## It is not

It is **not** a legal decision-maker.

It must never:

- decide eligibility
- override `eligible`
- override `pathway_used`
- override `rule_status`
- override `tariff_outcome`
- invent legal facts
- invent thresholds
- fabricate corridor status
- hide missing facts
- claim audit compliance when persistence failed

---

# Recommended architecture

Use this sequence:

```text
Natural language input
→ NIM intake / clarification
→ deterministic assessment engine
→ persisted case/evaluation/audit linkage
→ structured explanation service
→ counterfactual engine
→ decision renderer
→ assistant response
```

The renderer should sit **after** the deterministic engine and **after** the explanation service.

Recommended location:

```text
app/services/nim/decision_renderer.py
```

The counterfactual logic can live either:

```text
app/services/nim/counterfactual_engine.py
```

or, if you want fewer moving parts initially:

```text
app/services/nim/decision_renderer.py
```

with the counterfactual logic factored into helper methods.

For maintainability, a separate `counterfactual_engine.py` is preferable.

---

# Target outcome

The goal is to move from this:

```json
{
  "eligible": false,
  "pathway_used": null,
  "failures": ["FAIL_VNM_EXCEEDED", "FAIL_CTH_NOT_MET"]
}
```

to something like this:

```json
{
  "headline": "This product does not qualify for AfCFTA preference yet.",
  "summary": "The main issue is value content. Non-originating materials account for 48% of the product, but the rule allows a maximum of 40%. It also does not satisfy the tariff-shift pathway because one or more non-originating inputs share the same heading as the final product.",
  "gap_analysis": "You are 8 percentage points above the VNM threshold.",
  "fix_strategy": "Reduce non-originating value by at least 8 percentage points or replace the conflicting non-originating inputs with originating inputs.",
  "next_steps": [
    "Confirm the current bill of materials and input cost breakdown.",
    "Identify which non-originating inputs are driving the threshold breach.",
    "Re-run the assessment after adjusting sourcing or value structure."
  ]
}
```

The legal outcome stays the same. The usability changes completely.

---

# Part I — Exact `decision_renderer.py` (production-grade)

Below is a production-grade reference implementation.

## File
`app/services/nim/decision_renderer.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(slots=True)
class RenderedDecision:
    headline: str
    summary: str
    gap_analysis: str | None
    fix_strategy: str | None
    next_steps: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "summary": self.summary,
            "gap_analysis": self.gap_analysis,
            "fix_strategy": self.fix_strategy,
            "next_steps": self.next_steps,
            "warnings": self.warnings,
        }


class DecisionRendererError(RuntimeError):
    pass


class DecisionRenderer:
    """
    Converts deterministic assessment outputs plus validated explanation data
    into a user-facing decision narrative.

    This renderer never changes legal result fields. It only composes
    grounded language from deterministic outputs and validated derived guidance.
    """

    REQUIRED_TOP_LEVEL_KEYS = {
        "decision",
        "product",
        "pathway_analysis",
        "missing_facts",
        "failures",
        "evidence_required",
    }

    def render(
        self,
        *,
        engine_payload: Mapping[str, Any],
        counterfactuals: Sequence[Mapping[str, Any]] | None = None,
    ) -> RenderedDecision:
        self._validate_payload(engine_payload)

        decision = self._as_mapping(engine_payload["decision"])
        product = self._as_mapping(engine_payload["product"])
        pathway_analysis = self._as_list(engine_payload.get("pathway_analysis", []))
        missing_facts = self._as_list(engine_payload.get("missing_facts", []))
        tariff_outcome = self._as_mapping(engine_payload.get("tariff_outcome", {}))
        counterfactuals = [self._as_mapping(item) for item in (counterfactuals or [])]

        headline = self._build_headline(decision=decision, missing_facts=missing_facts)
        summary = self._build_summary(
            decision=decision,
            product=product,
            pathway_analysis=pathway_analysis,
            missing_facts=missing_facts,
            tariff_outcome=tariff_outcome,
        )
        gap_analysis = self._build_gap_analysis(
            decision=decision,
            pathway_analysis=pathway_analysis,
            counterfactuals=counterfactuals,
            missing_facts=missing_facts,
        )
        fix_strategy = self._build_fix_strategy(
            decision=decision,
            counterfactuals=counterfactuals,
            missing_facts=missing_facts,
        )
        next_steps = self._build_next_steps(
            decision=decision,
            counterfactuals=counterfactuals,
            missing_facts=missing_facts,
            evidence_required=self._as_list(engine_payload.get("evidence_required", [])),
        )
        warnings = self._build_warnings(
            decision=decision,
            missing_facts=missing_facts,
        )

        return RenderedDecision(
            headline=headline,
            summary=summary,
            gap_analysis=gap_analysis,
            fix_strategy=fix_strategy,
            next_steps=next_steps,
            warnings=warnings,
        )

    def _build_headline(
        self,
        *,
        decision: Mapping[str, Any],
        missing_facts: Sequence[Any],
    ) -> str:
        if missing_facts:
            return "I can’t complete the assessment yet."

        eligible = bool(decision.get("eligible"))
        rule_status = str(decision.get("rule_status", "")).strip()

        if eligible and rule_status == "pending":
            return "This product appears to qualify, but the rule status is still pending."
        if eligible:
            return "This product qualifies for AfCFTA preference."
        return "This product does not qualify for AfCFTA preference yet."

    def _build_summary(
        self,
        *,
        decision: Mapping[str, Any],
        product: Mapping[str, Any],
        pathway_analysis: Sequence[Any],
        missing_facts: Sequence[Any],
        tariff_outcome: Mapping[str, Any],
    ) -> str:
        hs6_code = str(product.get("hs6_code", "")).strip()
        description = str(
            product.get("product_description") or product.get("description") or "this product"
        ).strip()

        if missing_facts:
            pretty_missing = self._human_join(
                [self._humanize_fact_name(str(item)) for item in missing_facts]
            )
            return (
                f"I still need {pretty_missing} to complete the assessment for HS6 {hs6_code} "
                f"({description}). Without those details, I can’t test all of the relevant legal conditions reliably."
            )

        passed = [self._as_mapping(item) for item in pathway_analysis if self._as_mapping(item).get("passed") is True]
        failed = [self._as_mapping(item) for item in pathway_analysis if self._as_mapping(item).get("passed") is False]

        if bool(decision.get("eligible")):
            pathway_used = decision.get("pathway_used")
            reason = self._first_reason_for_pathway_code(passed, str(pathway_used or ""))
            tariff_text = self._render_tariff_sentence(tariff_outcome=tariff_outcome, eligible=True)

            if reason:
                return (
                    f"HS6 {hs6_code} ({description}) qualifies under the {pathway_used} pathway. "
                    f"{reason} {tariff_text}"
                ).strip()

            return (
                f"HS6 {hs6_code} ({description}) qualifies for AfCFTA preference. {tariff_text}"
            ).strip()

        primary_failure = self._best_failure_reason(failed)
        secondary_failure = self._second_failure_reason(failed, primary_failure)
        tariff_text = self._render_tariff_sentence(tariff_outcome=tariff_outcome, eligible=False)

        if primary_failure and secondary_failure:
            return (
                f"HS6 {hs6_code} ({description}) does not qualify yet. "
                f"The main issue is that {self._lowercase_first(primary_failure)} "
                f"It also appears that {self._lowercase_first(secondary_failure)} "
                f"{tariff_text}"
            ).strip()

        if primary_failure:
            return (
                f"HS6 {hs6_code} ({description}) does not qualify yet. "
                f"The main issue is that {self._lowercase_first(primary_failure)} "
                f"{tariff_text}"
            ).strip()

        return (
            f"HS6 {hs6_code} ({description}) does not qualify yet based on the current submitted facts. "
            f"{tariff_text}"
        ).strip()

    def _build_gap_analysis(
        self,
        *,
        decision: Mapping[str, Any],
        pathway_analysis: Sequence[Any],
        counterfactuals: Sequence[Mapping[str, Any]],
        missing_facts: Sequence[Any],
    ) -> str | None:
        if missing_facts or bool(decision.get("eligible")):
            return None

        for item in counterfactuals:
            delta = item.get("delta")
            kind = str(item.get("kind", "")).strip()
            pathway_code = str(item.get("pathway_code", "")).strip()

            if delta and kind in {"value_reduction", "value_add_increase"}:
                if pathway_code == "VNM":
                    return f"You are {delta} percentage points above the VNM threshold."
                if pathway_code == "VA":
                    return f"You are {delta} percentage points below the VA threshold."

        failed = [self._as_mapping(item) for item in pathway_analysis if self._as_mapping(item).get("passed") is False]
        if failed:
            top = sorted(failed, key=lambda x: int(x.get("priority_rank", 9999)))[0]
            pathway_code = str(top.get("pathway_code", "")).strip()
            if pathway_code:
                return f"The nearest failing pathway appears to be {pathway_code}, based on the current facts."

        return None

    def _build_fix_strategy(
        self,
        *,
        decision: Mapping[str, Any],
        counterfactuals: Sequence[Mapping[str, Any]],
        missing_facts: Sequence[Any],
    ) -> str | None:
        if missing_facts:
            return "The fastest way forward is to fill the missing legal and production facts before drawing a conclusion."

        if bool(decision.get("eligible")):
            return None

        messages = []
        for item in counterfactuals:
            msg = str(item.get("message", "")).strip()
            if msg:
                messages.append(self._ensure_sentence(msg))

        if messages:
            return " ".join(self._dedupe_preserve_order(messages[:2]))

        return "Review the failed pathway conditions against the current sourcing, classification, and cost structure."

    def _build_next_steps(
        self,
        *,
        decision: Mapping[str, Any],
        counterfactuals: Sequence[Mapping[str, Any]],
        missing_facts: Sequence[Any],
        evidence_required: Sequence[Any],
    ) -> list[str]:
        steps: list[str] = []

        if missing_facts:
            for fact in missing_facts[:3]:
                steps.append(f"Provide {self._humanize_fact_name(str(fact))}.")
            steps.append("Re-run the assessment once the missing facts are available.")
            return self._dedupe_preserve_order(steps)[:4]

        if bool(decision.get("eligible")):
            steps.extend([
                "Keep the supporting origin and costing records together for verification.",
                "Prepare the documentary evidence needed for the preference claim.",
                "Use the same fact pattern when filing or sharing the result downstream.",
            ])
            return self._dedupe_preserve_order(steps)[:4]

        for item in counterfactuals[:3]:
            msg = str(item.get("message", "")).strip()
            if msg:
                steps.append(self._ensure_sentence(msg))

        for evidence in evidence_required[:2]:
            val = str(evidence).strip()
            if val:
                steps.append(f"Gather {val}.")

        steps.append("Re-run the assessment after updating the sourcing, classification, or cost inputs.")
        return self._dedupe_preserve_order(steps)[:4]

    def _build_warnings(
        self,
        *,
        decision: Mapping[str, Any],
        missing_facts: Sequence[Any],
    ) -> list[str]:
        warnings: list[str] = []

        rule_status = str(decision.get("rule_status", "")).strip()
        confidence_class = str(decision.get("confidence_class", "")).strip()

        if rule_status == "pending":
            warnings.append("The applicable rule is marked as pending, so the legal position may still change.")

        if confidence_class == "incomplete" or missing_facts:
            warnings.append("This result depends on incomplete inputs and should not be treated as final.")

        return warnings[:3]

    def _validate_payload(self, payload: Mapping[str, Any]) -> None:
        missing = self.REQUIRED_TOP_LEVEL_KEYS.difference(payload.keys())
        if missing:
            raise DecisionRendererError(f"Missing required payload keys: {', '.join(sorted(missing))}")

        decision = payload.get("decision")
        if not isinstance(decision, Mapping):
            raise DecisionRendererError("decision must be an object")

        for key in ("eligible", "confidence_class", "rule_status"):
            if key not in decision:
                raise DecisionRendererError(f"decision missing required key: {key}")

    @staticmethod
    def _as_mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _humanize_fact_name(name: str) -> str:
        mapping = {
            "ex_works": "the ex-works value",
            "non_originating": "the non-originating value",
            "vnom_percent": "the non-originating value percentage",
            "va_percent": "the value-added percentage",
            "wholly_obtained": "confirmation of whether the product is wholly obtained",
            "non_originating_inputs": "the list of non-originating inputs",
            "output_hs6_code": "the final product classification",
            "direct_transport": "evidence of direct transport",
            "cumulation_partner_states": "the cumulation partner details",
            "specific_process_performed": "evidence that the required process was performed",
        }
        return mapping.get(name, name.replace("_", " "))

    @staticmethod
    def _human_join(items: Sequence[str]) -> str:
        cleaned = [item.strip() for item in items if item and item.strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return f"{", ".join(cleaned[:-1])}, and {cleaned[-1]}"

    @staticmethod
    def _ensure_sentence(text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return stripped
        if stripped.endswith((".", "!", "?")):
            return stripped
        return stripped + "."

    @staticmethod
    def _dedupe_preserve_order(items: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            norm = item.strip()
            if norm and norm not in seen:
                out.append(norm)
                seen.add(norm)
        return out

    @staticmethod
    def _lowercase_first(text: str) -> str:
        if not text:
            return text
        return text[0].lower() + text[1:]

    @staticmethod
    def _first_reason_for_pathway_code(
        pathways: Sequence[Mapping[str, Any]],
        pathway_code: str,
    ) -> str | None:
        for item in pathways:
            if str(item.get("pathway_code", "")).strip() == pathway_code:
                reasons = item.get("reasons", [])
                if isinstance(reasons, list) and reasons:
                    return str(reasons[0]).strip()
        return None

    @staticmethod
    def _best_failure_reason(pathways: Sequence[Mapping[str, Any]]) -> str | None:
        ranked = sorted(pathways, key=lambda x: int(x.get("priority_rank", 9999)))
        for item in ranked:
            reasons = item.get("reasons", [])
            if isinstance(reasons, list) and reasons:
                return str(reasons[0]).strip()
        return None

    @staticmethod
    def _second_failure_reason(
        pathways: Sequence[Mapping[str, Any]],
        first_reason: str | None,
    ) -> str | None:
        ranked = sorted(pathways, key=lambda x: int(x.get("priority_rank", 9999)))
        for item in ranked:
            reasons = item.get("reasons", [])
            if isinstance(reasons, list) and reasons:
                candidate = str(reasons[0]).strip()
                if candidate and candidate != first_reason:
                    return candidate
        return None

    @staticmethod
    def _render_tariff_sentence(
        *,
        tariff_outcome: Mapping[str, Any],
        eligible: bool,
    ) -> str:
        preferred_rate = tariff_outcome.get("preferred_rate")
        mfn_rate = tariff_outcome.get("mfn_rate") or tariff_outcome.get("mfm_rate")
        preference_available = tariff_outcome.get("preference_available")

        if eligible and preference_available is True and preferred_rate is not None:
            return f"The preferential rate is {preferred_rate}."
        if not eligible and mfn_rate is not None:
            return f"Without preference, the non-preferential rate remains {mfn_rate}."
        if preferred_rate is not None:
            return f"The preferential rate shown is {preferred_rate}."
        return ""
```

---

# Part II — NIM prompt + schema for rendering

## Design principle

The NIM renderer should not receive freeform raw state. It should receive a **tight truth payload**.

It should be instructed to:

- explain
- prioritize
- quantify the gap when possible
- propose the next action

But it must never:

- alter deterministic decision fields
- fabricate legal content
- hide uncertainty
- mask missing facts

---

## Recommended file

```text
app/services/nim/rendering_service.py
```

This service should:

1. build the NIM rendering prompt
2. submit the validated truth payload
3. parse structured JSON
4. validate the rendering schema
5. reject contradictions
6. fall back to `DecisionRenderer` if rendering fails

---

## Recommended rendering prompt

### System prompt

```text
You are a trade decision-support writer.

You do not decide eligibility.
You do not change legal conclusions.
You only explain a deterministic assessment in clear business language.

Hard rules:
1. Do not change any deterministic decision field.
2. Do not invent facts, products, thresholds, tariff rates, pathway outcomes, or legal text.
3. If facts are missing, say that the assessment is incomplete and explain what is missing.
4. If the product fails, explain the main blocker first.
5. If a quantified gap is available, state it plainly.
6. If a fix strategy is available, explain it plainly.
7. Keep the wording practical, calm, and non-legalistic.
8. Output valid JSON only.
```

### User prompt contract

```json
{
  "task": "Render the deterministic assessment into a conversational decision-support response without changing any legal result fields.",
  "truth_source": {
    "decision": {
      "eligible": false,
      "pathway_used": null,
      "rule_status": "agreed",
      "confidence_class": "complete"
    },
    "product": {
      "hs6_code": "180631",
      "product_description": "Chocolate bars, filled"
    },
    "pathway_analysis": [
      {
        "pathway_code": "VNM",
        "priority_rank": 1,
        "passed": false,
        "reasons": [
          "Non-originating value is 48%, above the allowed 40%."
        ]
      },
      {
        "pathway_code": "CTH",
        "priority_rank": 2,
        "passed": false,
        "reasons": [
          "One or more non-originating inputs share the same heading as the final product."
        ]
      }
    ],
    "counterfactuals": [
      {
        "kind": "value_reduction",
        "message": "Reduce non-originating value by at least 8 percentage points to meet the VNM threshold of 40%.",
        "delta": "8",
        "pathway_code": "VNM"
      }
    ],
    "missing_facts": [],
    "evidence_required": [
      "Bill of materials",
      "Supplier declarations",
      "Cost breakdown"
    ],
    "tariff_outcome": {
      "preference_available": false,
      "mfn_rate": "20%"
    }
  },
  "output_rules": {
    "headline": "One short sentence with the answer first.",
    "summary": "One short paragraph explaining why it passed, failed, or is incomplete.",
    "gap_analysis": "One short sentence quantifying the gap if available. Otherwise null.",
    "fix_strategy": "One short paragraph or sentence explaining the most useful corrective path. Otherwise null.",
    "next_steps": "Two to four practical steps.",
    "warnings": "Only include real warnings tied to pending status or incomplete facts."
  }
}
```

---

## Recommended rendering response schema

Use this exact shape:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "headline",
    "summary",
    "gap_analysis",
    "fix_strategy",
    "next_steps",
    "warnings"
  ],
  "properties": {
    "headline": {
      "type": "string"
    },
    "summary": {
      "type": "string"
    },
    "gap_analysis": {
      "type": ["string", "null"]
    },
    "fix_strategy": {
      "type": ["string", "null"]
    },
    "next_steps": {
      "type": "array",
      "minItems": 2,
      "maxItems": 4,
      "items": {
        "type": "string"
      }
    },
    "warnings": {
      "type": "array",
      "maxItems": 3,
      "items": {
        "type": "string"
      }
    }
  }
}
```

---

## Contradiction guardrails

After NIM returns structured JSON, validate:

1. `headline` must not claim qualification when `eligible == false`
2. `headline` must not claim failure when `eligible == true`
3. `summary` must not introduce pathways not present in `pathway_analysis`
4. `gap_analysis` must not invent a delta not present in `counterfactuals`
5. `fix_strategy` must not propose unsupported legal pathways
6. `warnings` must only mention:
   - pending rule status
   - incomplete facts
   - real deterministic caveats

If validation fails:
- discard NIM output
- return deterministic `DecisionRenderer` output

---

# Part III — Counterfactual engine logic

## Why this matters

This is the piece that makes the assistant feel like **decision support** rather than **result display**.

You need the system to say:

- how far off the product is
- what change would bring it into compliance
- which pathway is closest to success

---

## Recommended file

```text
app/services/nim/counterfactual_engine.py
```

---

## Design rules

Counterfactual logic should be:

- deterministic where possible
- tied directly to actual pathway failures
- quantifiable when thresholds exist
- conservative when they do not

It must never:
- speculate unsupported fixes
- invent legal alternatives not present in the rule set
- hide missing facts

---

## Reference implementation

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


@dataclass(slots=True)
class CounterfactualResult:
    kind: str
    message: str
    delta: str | None = None
    pathway_code: str | None = None
    fact_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "delta": self.delta,
            "pathway_code": self.pathway_code,
            "fact_key": self.fact_key,
        }


class CounterfactualEngine:
    """
    Deterministic helper for deriving actionable changes from failed pathways.
    """

    def generate(
        self,
        *,
        normalized_facts: Mapping[str, Any],
        pathway_analysis: Sequence[Mapping[str, Any]],
        selected_pathway: str | None = None,
    ) -> list[CounterfactualResult]:
        results: list[CounterfactualResult] = []

        for pathway in pathway_analysis:
            code = str(pathway.get("pathway_code", "")).strip().upper()
            passed = pathway.get("passed")

            if passed is not False:
                continue

            if code == "VNM":
                actual = self._safe_decimal(normalized_facts.get("vnom_percent"))
                threshold = self._extract_threshold_from_pathway(pathway)
                if actual is not None and threshold is not None and actual > threshold:
                    delta = actual - threshold
                    results.append(
                        CounterfactualResult(
                            kind="value_reduction",
                            message=(
                                f"Reduce non-originating value by at least {self._fmt(delta)} percentage points "
                                f"to meet the VNM threshold of {self._fmt(threshold)}%."
                            ),
                            delta=self._fmt(delta),
                            pathway_code="VNM",
                            fact_key="non_originating",
                        )
                    )

            elif code == "VA":
                actual = self._safe_decimal(normalized_facts.get("va_percent"))
                threshold = self._extract_threshold_from_pathway(pathway)
                if actual is not None and threshold is not None and actual < threshold:
                    delta = threshold - actual
                    results.append(
                        CounterfactualResult(
                            kind="value_add_increase",
                            message=(
                                f"Increase value added by at least {self._fmt(delta)} percentage points "
                                f"to meet the VA threshold of {self._fmt(threshold)}%."
                            ),
                            delta=self._fmt(delta),
                            pathway_code="VA",
                            fact_key="ex_works",
                        )
                    )

            elif code == "CTH":
                results.append(
                    CounterfactualResult(
                        kind="tariff_shift_fix",
                        message=(
                            "Use non-originating inputs classified outside the final product heading, "
                            "or replace the conflicting non-originating inputs with originating inputs."
                        ),
                        pathway_code="CTH",
                        fact_key="non_originating_inputs",
                    )
                )

            elif code == "CTSH":
                results.append(
                    CounterfactualResult(
                        kind="tariff_shift_fix",
                        message=(
                            "Use non-originating inputs classified outside the final product subheading, "
                            "or replace the conflicting non-originating inputs with originating inputs."
                        ),
                        pathway_code="CTSH",
                        fact_key="non_originating_inputs",
                    )
                )

            elif code == "WO":
                results.append(
                    CounterfactualResult(
                        kind="origin_fix",
                        message=(
                            "Confirm whether the product can genuinely be treated as wholly obtained, "
                            "or rely on another qualifying pathway if the rule permits it."
                        ),
                        pathway_code="WO",
                        fact_key="wholly_obtained",
                    )
                )

            elif code == "PROCESS":
                results.append(
                    CounterfactualResult(
                        kind="process_fix",
                        message=(
                            "Document or perform the specific manufacturing process required by the rule."
                        ),
                        pathway_code="PROCESS",
                        fact_key="specific_process_performed",
                    )
                )

        return self._dedupe(results)

    @staticmethod
    def _extract_threshold_from_pathway(pathway: Mapping[str, Any]) -> Decimal | None:
        value = pathway.get("threshold_percent")
        return CounterfactualEngine._safe_decimal(value)

    @staticmethod
    def _safe_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _fmt(value: Decimal) -> str:
        norm = value.normalize()
        return format(norm, "f").rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _dedupe(items: Sequence[CounterfactualResult]) -> list[CounterfactualResult]:
        seen: set[tuple[str, str, str | None]] = set()
        out: list[CounterfactualResult] = []

        for item in items:
            key = (item.kind, item.message, item.pathway_code)
            if key not in seen:
                seen.add(key)
                out.append(item)

        return out
```

---

# Integration guidance

## Recommended orchestration flow

Inside the assistant orchestration path:

1. run deterministic assessment
2. generate structured explanation
3. generate counterfactuals from deterministic failure state
4. run NIM rendering over the truth payload
5. validate structured rendering
6. if NIM fails or contradicts the result:
   - fall back to `DecisionRenderer`

---

## Response envelope recommendation

Add a section like this to the assistant response:

```json
{
  "assistant_rendering": {
    "headline": "...",
    "summary": "...",
    "gap_analysis": "...",
    "fix_strategy": "...",
    "next_steps": ["..."],
    "warnings": []
  }
}
```

But keep deterministic fields separate and unchanged:

```json
{
  "assessment": {
    "eligible": false,
    "pathway_used": null,
    "rule_status": "agreed",
    "tariff_outcome": {
      "preference_available": false,
      "mfn_rate": "20%"
    }
  }
}
```

This preserves the architecture set out in the NIM readiness materials. fileciteturn0file0

---

# Recommended tests

Before using this in production, add:

## Unit tests
- `test_decision_renderer.py`
- `test_counterfactual_engine.py`
- `test_rendering_service.py`

## Test cases
1. eligible result → clean qualifying narrative
2. failed VNM → quantified gap and fix
3. failed CTH → tariff-shift fix narrative
4. missing facts → incomplete response, no fake certainty
5. pending rule status → warning appears
6. contradictory NIM rendering → rejected and fallback used
7. empty or malformed NIM rendering → fallback used

---

# Prompt handbook insertion note

After NIM readiness is complete, this reference should be used for a new prompt group such as:

```text
Group 4 — Decision rendering and counterfactual layer
```

Suggested sequence:

1. create `counterfactual_engine.py`
2. create `decision_renderer.py`
3. create `rendering_service.py`
4. pin unit tests
5. wire into assistant flow
6. add contradiction/fallback integration tests

---

# Final implementation goal

When this is done, the assistant should still be:

- deterministic
- replayable
- auditable
- non-hallucinatory

But it should also feel:

- conversational
- business-usable
- action-oriented
- decision-supportive

That is the actual target state.

---

# Show exact API response shape after upgrade

After integrating:

- deterministic engine
- counterfactual engine
- NIM rendering layer
- decision renderer fallback

Your **API response MUST be structurally split** into:

1. deterministic truth (authoritative)
2. assistant rendering (derived, replaceable)
3. audit + trace layer (optional but recommended)

---

## Final API response (production shape)

```json
{
  "request_id": "req_9f3a2c",
  "timestamp": "2026-03-24T23:10:00Z",

  "input": {
    "query": "Does chocolate HS6 180631 qualify from Ghana to Kenya?"
  },

  "assessment": {
    "eligible": false,
    "pathway_used": null,
    "rule_status": "agreed",
    "confidence_class": "complete",

    "product": {
      "hs6_code": "180631",
      "description": "Chocolate bars, filled"
    },

    "pathway_analysis": [
      {
        "pathway_code": "VNM",
        "passed": false,
        "priority_rank": 1,
        "reasons": [
          "Non-originating value is 48%, above the allowed 40%."
        ]
      },
      {
        "pathway_code": "CTH",
        "passed": false,
        "priority_rank": 2,
        "reasons": [
          "One or more non-originating inputs share the same heading as the final product."
        ]
      }
    ],

    "tariff_outcome": {
      "preference_available": false,
      "mfn_rate": "20%",
      "preferred_rate": null
    }
  },

  "counterfactuals": [
    {
      "kind": "value_reduction",
      "message": "Reduce non-originating value by at least 8 percentage points to meet the VNM threshold of 40%.",
      "delta": "8",
      "pathway_code": "VNM",
      "fact_key": "non_originating"
    }
  ],

  "assistant_rendering": {
    "headline": "This product does not qualify for AfCFTA preference yet.",
    "summary": "The main issue is value content. Non-originating materials account for 48%, exceeding the 40% threshold. It also fails the tariff-shift pathway because some inputs share the same heading.",
    "gap_analysis": "You are 8 percentage points above the VNM threshold.",
    "fix_strategy": "Reduce non-originating value by at least 8 percentage points or replace conflicting inputs with originating inputs.",
    "next_steps": [
      "Confirm the bill of materials and cost structure.",
      "Identify inputs causing the threshold breach.",
      "Adjust sourcing or value composition.",
      "Re-run the assessment."
    ],
    "warnings": []
  },

  "trace": {
    "case_id": "case_7721",
    "evaluation_id": "eval_8821",
    "engine_version": "v0.3.2",
    "rendering_model": "nim-llama-3-70b",
    "fallback_used": false
  }
}
```

---

## Key design constraints (non-negotiable)

### 1. Hard separation of concerns

- `assessment` = **ground truth**
- `assistant_rendering` = **replaceable layer**
- `counterfactuals` = **derived but deterministic**
- `trace` = **auditability**

Never merge these.

---

### 2. Rendering can fail safely

If NIM fails or contradicts:

```json
"assistant_rendering_source": "fallback_decision_renderer"
```

---

### 3. UI should bind like this

- headline → decision banner
- summary → explanation panel
- gap_analysis → insight badge
- fix_strategy → recommendation block
- next_steps → checklist UI
- warnings → alert banner

---

### 4. Enables future upgrades

This structure allows:

- swapping NIM models
- adding multi-pathway simulation
- injecting pricing / corridor intelligence
- streaming partial outputs

without breaking contracts

---

## Anti-patterns (do not do)

❌ Merge rendering into assessment  
❌ Let LLM modify eligibility  
❌ Return freeform text  
❌ Hide counterfactuals  
❌ Skip trace linkage  

---

## Minimal version (if you need to ship fast)

```json
{
  "assessment": { ... },
  "assistant_rendering": { ... }
}
```

Everything else can be layered later.

---

## End state

If implemented correctly:

- backend = deterministic + auditable
- assistant = interpretable + useful
- UX = decision-grade, not document-grade

This is the actual upgrade.
