"""Deterministic decision narrative renderer for post-engine outputs.

This module turns structured deterministic assessment payloads into
user-facing narrative blocks. It never mutates or overrides deterministic
decision fields; it only composes additive text from validated inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(slots=True)
class RenderedDecision:
    """Structured, deterministic narrative blocks for assistant display."""

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
    """Raised when payload structure is insufficient for deterministic rendering."""


class DecisionRenderer:
    """Render deterministic decision-support narrative from engine payloads."""

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

        decision = self._as_mapping(engine_payload.get("decision"))
        product = self._as_mapping(engine_payload.get("product"))
        pathway_analysis = self._as_list(engine_payload.get("pathway_analysis"))
        missing_facts = self._as_list(engine_payload.get("missing_facts"))
        evidence_required = self._as_list(engine_payload.get("evidence_required"))
        tariff_outcome = self._as_mapping(engine_payload.get("tariff_outcome"))
        normalized_counterfactuals = [
            self._as_mapping(item) for item in self._as_list(counterfactuals or [])
        ]

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
            counterfactuals=normalized_counterfactuals,
            missing_facts=missing_facts,
        )
        fix_strategy = self._build_fix_strategy(
            decision=decision,
            pathway_analysis=pathway_analysis,
            counterfactuals=normalized_counterfactuals,
            missing_facts=missing_facts,
        )
        next_steps = self._build_next_steps(
            decision=decision,
            pathway_analysis=pathway_analysis,
            counterfactuals=normalized_counterfactuals,
            missing_facts=missing_facts,
            evidence_required=evidence_required,
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
            return "I can't complete the assessment yet."

        eligible = bool(decision.get("eligible"))
        rule_status = str(decision.get("rule_status", "")).strip().lower()

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
        hs6_code = str(product.get("hs6_code", "")).strip() or "unknown"
        description = str(
            product.get("product_description") or product.get("description") or "this product"
        ).strip()
        path_items = [self._as_mapping(item) for item in pathway_analysis]

        if missing_facts:
            fact_names = [self._humanize_fact_name(str(item)) for item in missing_facts]
            pretty_missing = self._human_join(fact_names)
            return (
                f"I still need {pretty_missing} to complete the assessment for HS6 {hs6_code} "
                f"({description}). Without those details, I cannot test all legal conditions "
                "reliably."
            )

        passed = [item for item in path_items if item.get("passed") is True]
        failed = [item for item in path_items if item.get("passed") is False]
        tariff_sentence = self._render_tariff_sentence(
            tariff_outcome=tariff_outcome,
            eligible=bool(decision.get("eligible")),
        )

        if bool(decision.get("eligible")):
            pathway_used = str(decision.get("pathway_used") or "").strip()
            reason = self._first_reason_for_pathway_code(passed, pathway_used)
            if pathway_used and reason:
                return (
                    f"HS6 {hs6_code} ({description}) qualifies under the {pathway_used} pathway. "
                    f"{self._ensure_sentence(reason)} {tariff_sentence}"
                ).strip()
            if pathway_used:
                return (
                    f"HS6 {hs6_code} ({description}) qualifies under the {pathway_used} pathway. "
                    f"{tariff_sentence}"
                ).strip()
            return (
                f"HS6 {hs6_code} ({description}) qualifies for AfCFTA preference. "
                f"{tariff_sentence}"
            ).strip()

        primary_failure = self._best_failure_reason(failed)
        secondary_failure = self._second_failure_reason(failed, primary_failure)

        if primary_failure and secondary_failure:
            return (
                f"HS6 {hs6_code} ({description}) does not qualify yet. "
                "The main issue is that "
                f"{self._lowercase_first(self._ensure_sentence(primary_failure))} "
                "It also appears that "
                f"{self._lowercase_first(self._ensure_sentence(secondary_failure))} "
                f"{tariff_sentence}"
            ).strip()
        if primary_failure:
            return (
                f"HS6 {hs6_code} ({description}) does not qualify yet. "
                "The main issue is that "
                f"{self._lowercase_first(self._ensure_sentence(primary_failure))} "
                f"{tariff_sentence}"
            ).strip()
        return (
            f"HS6 {hs6_code} ({description}) does not qualify yet based on the submitted facts. "
            f"{tariff_sentence}"
        ).strip()

    def _build_gap_analysis(
        self,
        *,
        decision: Mapping[str, Any],
        counterfactuals: Sequence[Mapping[str, Any]],
        missing_facts: Sequence[Any],
    ) -> str | None:
        if missing_facts or bool(decision.get("eligible")):
            return None

        for item in counterfactuals:
            delta = str(item.get("delta", "")).strip()
            if not delta:
                continue
            kind = str(item.get("kind", "")).strip()
            pathway_code = str(item.get("pathway_code", "")).strip().upper()

            if kind in {"value_reduction", "value_add_increase"} and pathway_code == "VNM":
                return f"You are {delta} percentage points above the VNM threshold."
            if kind in {"value_reduction", "value_add_increase"} and pathway_code == "VA":
                return f"You are {delta} percentage points below the VA threshold."

        return None

    def _build_fix_strategy(
        self,
        *,
        decision: Mapping[str, Any],
        pathway_analysis: Sequence[Any],
        counterfactuals: Sequence[Mapping[str, Any]],
        missing_facts: Sequence[Any],
    ) -> str | None:
        if missing_facts:
            return (
                "The fastest way forward is to fill the missing legal and production facts "
                "before drawing a conclusion."
            )
        if bool(decision.get("eligible")):
            return None

        messages = []
        for item in counterfactuals:
            msg = str(item.get("message", "")).strip()
            if msg:
                messages.append(self._ensure_sentence(msg))
        deduped_messages = self._dedupe_preserve_order(messages)
        if deduped_messages:
            return " ".join(deduped_messages[:2])

        top_failure_code = self._top_failed_pathway_code(pathway_analysis)
        if top_failure_code == "CTH":
            return (
                "Use non-originating inputs classified outside the final product heading, "
                "or replace conflicting non-originating inputs with originating inputs."
            )
        if top_failure_code == "CTSH":
            return (
                "Use non-originating inputs classified outside the final product subheading, "
                "or replace conflicting non-originating inputs with originating inputs."
            )
        if top_failure_code == "PROCESS":
            return "Document or perform the specific manufacturing process required by the rule."
        if top_failure_code == "WO":
            return (
                "Confirm whether the product can genuinely be treated as wholly obtained, "
                "or rely on another legal pathway if available."
            )
        return (
            "Review the failed pathway conditions against the current sourcing, "
            "classification, and cost structure."
        )

    def _build_next_steps(
        self,
        *,
        decision: Mapping[str, Any],
        pathway_analysis: Sequence[Any],
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
            steps.extend(
                [
                    "Keep the supporting origin and costing records together for verification.",
                    "Prepare the documentary evidence needed for the preference claim.",
                    "Use the same fact pattern when filing or sharing this result downstream.",
                ]
            )
            if evidence_required:
                joined = ", ".join(
                    str(item).strip() for item in evidence_required if str(item).strip()
                )
                if joined:
                    steps.insert(1, f"Assemble required evidence: {joined}.")
            return self._dedupe_preserve_order(steps)[:4]

        for item in counterfactuals[:3]:
            msg = str(item.get("message", "")).strip()
            if msg:
                steps.append(self._ensure_sentence(msg))

        if not steps:
            top_failure_code = self._top_failed_pathway_code(pathway_analysis)
            if top_failure_code == "CTH":
                steps.append(
                    "Review non-originating inputs and confirm they shift tariff heading "
                    "from the final product heading."
                )
            elif top_failure_code == "VNM":
                steps.append(
                    "Recheck the non-originating share against the applicable VNM threshold."
                )

        for evidence in evidence_required[:2]:
            val = str(evidence).strip()
            if val:
                steps.append(f"Gather {val}.")

        steps.append(
            "Re-run the assessment after updating sourcing, classification, or cost inputs."
        )
        return self._dedupe_preserve_order(steps)[:4]

    def _build_warnings(
        self,
        *,
        decision: Mapping[str, Any],
        missing_facts: Sequence[Any],
    ) -> list[str]:
        warnings: list[str] = []

        rule_status = str(decision.get("rule_status", "")).strip().lower()
        confidence_class = str(decision.get("confidence_class", "")).strip().lower()

        if rule_status == "pending":
            warnings.append(
                "The applicable rule is marked as pending, so the legal position may still change."
            )
        elif rule_status in {"partially_agreed", "provisional"}:
            warnings.append(
                "The applicable rule is not fully settled, "
                "so this result should be treated as provisional."
            )

        if confidence_class == "incomplete" or missing_facts:
            warnings.append("This result is incomplete and should not be treated as final.")
        elif confidence_class == "provisional":
            warnings.append(
                "This result is provisional and may change as legal status is finalized."
            )

        return warnings[:3]

    def _validate_payload(self, payload: Mapping[str, Any]) -> None:
        if not isinstance(payload, Mapping):
            raise DecisionRendererError("engine_payload must be an object")

        missing = self.REQUIRED_TOP_LEVEL_KEYS.difference(payload.keys())
        if missing:
            keys = ", ".join(sorted(missing))
            raise DecisionRendererError(f"Missing required payload keys: {keys}")

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
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []

    @staticmethod
    def _humanize_fact_name(name: str) -> str:
        mapping = {
            "ex_works": "the ex-works value",
            "non_originating": "the non-originating value",
            "vnom_percent": "the non-originating value percentage",
            "va_percent": "the value-added percentage",
            "fob_value": "the FOB value",
            "customs_value": "the customs value",
            "originating_materials_value": "the originating materials value",
            "non_originating_inputs": "the list of non-originating inputs",
            "output_hs6_code": "the final product classification",
            "tariff_heading_input": "the non-originating input tariff heading",
            "tariff_heading_output": "the final product tariff heading",
            "tariff_subheading_input": "the non-originating input tariff subheading",
            "tariff_subheading_output": "the final product tariff subheading",
            "wholly_obtained": "confirmation of whether the product is wholly obtained",
            "specific_process_performed": "evidence that the required process was performed",
            "specific_process_description": "the specific process description",
            "direct_transport": "evidence of direct transport",
            "transshipment_country": "the transshipment country details",
            "cumulation_claimed": "confirmation of whether cumulation is claimed",
            "cumulation_partner_states": "the cumulation partner details",
        }
        return mapping.get(name, name.replace("_", " ").strip())

    @staticmethod
    def _human_join(items: Sequence[str]) -> str:
        cleaned = [item.strip() for item in items if item and item.strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"

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
            value = item.strip()
            if value and value not in seen:
                out.append(value)
                seen.add(value)
        return out

    @staticmethod
    def _lowercase_first(text: str) -> str:
        if not text:
            return text
        return text[0].lower() + text[1:]

    @staticmethod
    def _priority_rank(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 9999

    def _top_failed_pathway_code(self, pathway_analysis: Sequence[Any]) -> str | None:
        failed = [
            self._as_mapping(item)
            for item in pathway_analysis
            if self._as_mapping(item).get("passed") is False
        ]
        if not failed:
            return None
        ranked = sorted(failed, key=lambda x: self._priority_rank(x.get("priority_rank")))
        code = str(ranked[0].get("pathway_code", "")).strip().upper()
        return code or None

    def _first_reason_for_pathway_code(
        self,
        pathways: Sequence[Mapping[str, Any]],
        pathway_code: str,
    ) -> str | None:
        wanted = pathway_code.strip().upper()
        if not wanted:
            return None
        for item in pathways:
            code = str(item.get("pathway_code", "")).strip().upper()
            if code != wanted:
                continue
            reasons = item.get("reasons")
            if isinstance(reasons, list) and reasons:
                candidate = str(reasons[0]).strip()
                if candidate:
                    return candidate
        return None

    def _best_failure_reason(self, pathways: Sequence[Mapping[str, Any]]) -> str | None:
        ranked = sorted(pathways, key=lambda x: self._priority_rank(x.get("priority_rank")))
        for item in ranked:
            reasons = item.get("reasons")
            if isinstance(reasons, list) and reasons:
                candidate = str(reasons[0]).strip()
                if candidate:
                    return candidate
        return None

    def _second_failure_reason(
        self,
        pathways: Sequence[Mapping[str, Any]],
        first_reason: str | None,
    ) -> str | None:
        ranked = sorted(pathways, key=lambda x: self._priority_rank(x.get("priority_rank")))
        for item in ranked:
            reasons = item.get("reasons")
            if not (isinstance(reasons, list) and reasons):
                continue
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
        if not tariff_outcome:
            return ""

        preferred_rate = tariff_outcome.get("preferential_rate")
        if preferred_rate is None:
            preferred_rate = tariff_outcome.get("preferred_rate")

        base_rate = tariff_outcome.get("base_rate")
        if base_rate is None:
            base_rate = tariff_outcome.get("mfn_rate")
        if base_rate is None:
            base_rate = tariff_outcome.get("mfm_rate")

        preference_available = tariff_outcome.get("preference_available")
        status = str(tariff_outcome.get("status", "")).strip()

        if eligible and preferred_rate is not None:
            if status:
                return f"The preferential rate is {preferred_rate} ({status})."
            return f"The preferential rate is {preferred_rate}."
        if eligible and preference_available is False:
            return "No preferential tariff rate is currently available."
        if not eligible and base_rate is not None:
            if status:
                return (
                    "Without preference, the non-preferential rate remains "
                    f"{base_rate} ({status})."
                )
            return f"Without preference, the non-preferential rate remains {base_rate}."
        if preferred_rate is not None:
            return f"The preferential rate shown is {preferred_rate}."
        return ""
