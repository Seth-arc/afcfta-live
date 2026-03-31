"""Deterministic counterfactual engine for deriving actionable changes from failed pathways.

This module reads real pathway failures and quantifies real gaps. It never
speculates unsupported fixes or invents legal alternatives not present in
the rule set. All percentage arithmetic uses Decimal to avoid float drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


@dataclass(slots=True)
class CounterfactualResult:
    """A single actionable change derived from a failed pathway."""

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
    """Deterministic helper for deriving actionable changes from failed pathways."""

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
                                f"Reduce non-originating value by at least "
                                f"{self._fmt(delta)} percentage points "
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
                                f"Increase value added by at least "
                                f"{self._fmt(delta)} percentage points "
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
                            "Use non-originating inputs classified outside the final "
                            "product heading, or replace the conflicting non-originating "
                            "inputs with originating inputs."
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
                            "Use non-originating inputs classified outside the final "
                            "product subheading, or replace the conflicting "
                            "non-originating inputs with originating inputs."
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
                            "Confirm whether the product can genuinely be treated as "
                            "wholly obtained, or rely on another qualifying pathway "
                            "if the rule permits it."
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
                            "Document or perform the specific manufacturing process "
                            "required by the rule."
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
        text = format(norm, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

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
