"""NIM rendering service: submit truth payload to NIM for natural-language rendering.

Responsibility boundary:
- Builds a system prompt and a structured truth payload from the engine output.
- Calls NimClient.generate_json() for a conversational rendering.
- Validates the structured JSON response against the NimRendering schema.
- Applies contradiction guardrails that reject any NIM output inconsistent
  with the deterministic engine fields.
- Falls back to DecisionRenderer on any failure (NIM disabled, timeout,
  invalid JSON, schema violation, guardrail rejection).
- Never lets a NIM failure block the assessment result.
- Never returns partial or unvalidated NIM output.
- Uses a dedicated logger (app.nim.rendering) to keep NIM rendering logs
  separate from the deterministic audit trail.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from app.schemas.nim.rendering import NimRendering
from app.services.nim.client import NimClient, NimClientError
from app.services.nim.decision_renderer import DecisionRenderer, RenderedDecision

logger = logging.getLogger("app.nim.rendering")

# ---------------------------------------------------------------------------
# Known pathway codes from the rule set
# ---------------------------------------------------------------------------

_KNOWN_PATHWAY_CODES: frozenset[str] = frozenset({
    "VNM", "VA", "CTH", "CTSH", "CC", "WO", "PROCESS",
})

# ---------------------------------------------------------------------------
# NIM system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
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
8. Output valid JSON only.\
"""

# ---------------------------------------------------------------------------
# Headline contradiction phrases
# ---------------------------------------------------------------------------

_QUALIFIES_PHRASES: tuple[str, ...] = (
    "qualifies",
    "is eligible",
    "meets the requirements",
    "satisfies the rules",
    "does qualify",
)

_FAILS_PHRASES: tuple[str, ...] = (
    "does not qualify",
    "not eligible",
    "ineligible",
    "fails to qualify",
    "cannot qualify",
    "does not meet",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_user_prompt(
    *,
    decision: Mapping[str, Any],
    product: Mapping[str, Any],
    pathway_analysis: Sequence[Mapping[str, Any]],
    counterfactuals: Sequence[Mapping[str, Any]],
    missing_facts: Sequence[Any],
    evidence_required: Sequence[Any],
    tariff_outcome: Mapping[str, Any],
) -> str:
    """Build the user prompt containing the truth payload for NIM."""
    payload = {
        "task": (
            "Render the deterministic assessment into a conversational "
            "decision-support response without changing any legal result fields."
        ),
        "truth_source": {
            "decision": dict(decision),
            "product": dict(product),
            "pathway_analysis": [dict(p) for p in pathway_analysis],
            "counterfactuals": [dict(c) for c in counterfactuals],
            "missing_facts": list(missing_facts),
            "evidence_required": list(evidence_required),
            "tariff_outcome": dict(tariff_outcome),
        },
        "output_rules": {
            "headline": "One short sentence with the answer first.",
            "summary": (
                "One short paragraph explaining why it passed, "
                "failed, or is incomplete."
            ),
            "gap_analysis": (
                "One short sentence quantifying the gap if available. "
                "Otherwise null."
            ),
            "fix_strategy": (
                "One short paragraph or sentence explaining the most useful "
                "corrective path. Otherwise null."
            ),
            "next_steps": "Two to four practical steps.",
            "warnings": (
                "Only include real warnings tied to pending status "
                "or incomplete facts."
            ),
        },
    }
    return json.dumps(payload, indent=2, default=str)


def _extract_pathway_codes(
    pathway_analysis: Sequence[Mapping[str, Any]],
) -> set[str]:
    """Extract the set of pathway codes present in pathway_analysis."""
    codes: set[str] = set()
    for p in pathway_analysis:
        code = str(p.get("pathway_code", "")).strip().upper()
        if code:
            codes.add(code)
    return codes


def _extract_counterfactual_deltas(
    counterfactuals: Sequence[Mapping[str, Any]],
) -> set[str]:
    """Extract all delta values present in counterfactuals."""
    deltas: set[str] = set()
    for c in counterfactuals:
        delta = str(c.get("delta", "")).strip()
        if delta:
            deltas.add(delta)
    return deltas


# ---------------------------------------------------------------------------
# Contradiction guardrails
# ---------------------------------------------------------------------------


def _check_headline_contradiction(
    headline: str,
    eligible: bool,
) -> str | None:
    """Return a reason string if the headline contradicts eligibility, else None."""
    lower = headline.lower()

    if not eligible:
        for phrase in _QUALIFIES_PHRASES:
            if phrase in lower:
                return (
                    f"headline claims qualification ('{phrase}') "
                    f"but eligible is false"
                )

    if eligible:
        for phrase in _FAILS_PHRASES:
            if phrase in lower:
                return (
                    f"headline claims failure ('{phrase}') "
                    f"but eligible is true"
                )

    return None


def _check_summary_invented_pathways(
    summary: str,
    valid_codes: set[str],
) -> str | None:
    """Return a reason if the summary references pathways not in pathway_analysis."""
    for code in _KNOWN_PATHWAY_CODES:
        if code not in valid_codes:
            # Check for the pathway code as a standalone word
            pattern = rf"\b{re.escape(code)}\b"
            if re.search(pattern, summary, re.IGNORECASE):
                return (
                    f"summary references pathway '{code}' "
                    f"absent from pathway_analysis"
                )
    return None


def _check_gap_analysis_invented_delta(
    gap_analysis: str | None,
    valid_deltas: set[str],
) -> str | None:
    """Return a reason if gap_analysis invents a numeric delta not in counterfactuals."""
    if not gap_analysis:
        return None

    # Extract all numbers from the gap_analysis text
    numbers_in_text = set(re.findall(r"\d+(?:\.\d+)?", gap_analysis))
    if not numbers_in_text:
        return None

    # At least one number must match a known delta
    if not numbers_in_text & valid_deltas:
        return (
            f"gap_analysis contains delta(s) {numbers_in_text} "
            f"not present in counterfactuals"
        )
    return None


def _check_fix_strategy_invented_pathways(
    fix_strategy: str | None,
    valid_codes: set[str],
) -> str | None:
    """Return a reason if fix_strategy proposes pathways absent from the rule set."""
    if not fix_strategy:
        return None

    for code in _KNOWN_PATHWAY_CODES:
        if code not in valid_codes:
            pattern = rf"\b{re.escape(code)}\b"
            if re.search(pattern, fix_strategy, re.IGNORECASE):
                return (
                    f"fix_strategy references pathway '{code}' "
                    f"absent from pathway_analysis"
                )
    return None


def _check_warnings_valid(
    warnings: list[str],
    decision: Mapping[str, Any],
    missing_facts: Sequence[Any],
) -> str | None:
    """Return a reason if warnings reference topics beyond the allowed set.

    Warnings may only reference:
    - pending or provisional rule status
    - incomplete facts / missing information
    - real caveats from the deterministic assessment
    """
    rule_status = str(decision.get("rule_status", "")).strip().lower()
    confidence_class = str(decision.get("confidence_class", "")).strip().lower()

    has_pending_status = rule_status in {"pending", "partially_agreed", "provisional"}
    has_incomplete = confidence_class == "incomplete" or bool(missing_facts)

    for warning in warnings:
        lower = warning.lower()
        mentions_status = any(
            kw in lower
            for kw in ("pending", "provisional", "partially", "rule status", "not settled")
        )
        mentions_incomplete = any(
            kw in lower
            for kw in ("incomplete", "missing", "not final", "subject to change")
        )
        mentions_caveat = any(
            kw in lower
            for kw in ("caveat", "caution", "note", "provisional", "verify")
        )

        if not (mentions_status or mentions_incomplete or mentions_caveat):
            return f"warning '{warning[:60]}...' references unsupported topic"

        if mentions_status and not has_pending_status:
            return (
                f"warning mentions pending/provisional status but "
                f"rule_status is '{rule_status}'"
            )
        if mentions_incomplete and not has_incomplete:
            return (
                f"warning mentions incomplete facts but "
                f"confidence_class is '{confidence_class}' and no facts are missing"
            )

    return None


def _run_guardrails(
    rendering: NimRendering,
    *,
    decision: Mapping[str, Any],
    pathway_analysis: Sequence[Mapping[str, Any]],
    counterfactuals: Sequence[Mapping[str, Any]],
    missing_facts: Sequence[Any],
) -> str | None:
    """Run all contradiction guardrails. Return the first failure reason, or None."""
    eligible = bool(decision.get("eligible"))
    valid_codes = _extract_pathway_codes(pathway_analysis)
    valid_deltas = _extract_counterfactual_deltas(counterfactuals)

    checks = [
        _check_headline_contradiction(rendering.headline, eligible),
        _check_summary_invented_pathways(rendering.summary, valid_codes),
        _check_gap_analysis_invented_delta(rendering.gap_analysis, valid_deltas),
        _check_fix_strategy_invented_pathways(rendering.fix_strategy, valid_codes),
        _check_warnings_valid(rendering.warnings, decision, missing_facts),
    ]

    for reason in checks:
        if reason is not None:
            return reason
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RenderingService:
    """Submit truth payload to NIM for natural-language rendering with fallback.

    Injected with a NimClient and a DecisionRenderer. On any NIM failure,
    returns the deterministic DecisionRenderer output transparently.
    """

    def __init__(
        self,
        nim_client: NimClient,
        decision_renderer: DecisionRenderer | None = None,
    ) -> None:
        self.nim_client = nim_client
        self._renderer = decision_renderer or DecisionRenderer()

    async def render(
        self,
        *,
        engine_payload: Mapping[str, Any],
        counterfactuals: Sequence[Mapping[str, Any]] | None = None,
    ) -> RenderedDecision:
        """Render the assessment via NIM with deterministic fallback.

        Steps:
        1. Build system prompt and user prompt from the truth payload.
        2. Call NimClient.generate_json().
        3. Parse and validate against NimRendering.
        4. Run contradiction guardrails.
        5. On any failure, return DecisionRenderer output instead.

        Never raises — the deterministic fallback is always available.
        """
        decision = _as_mapping(engine_payload.get("decision"))
        product = _as_mapping(engine_payload.get("product"))
        pathway_analysis = _as_list(engine_payload.get("pathway_analysis"))
        missing_facts = _as_list(engine_payload.get("missing_facts"))
        evidence_required = _as_list(engine_payload.get("evidence_required"))
        tariff_outcome = _as_mapping(engine_payload.get("tariff_outcome"))
        normalized_counterfactuals = [
            _as_mapping(item) for item in _as_list(counterfactuals or [])
        ]

        # Attempt NIM rendering
        nim_result = await self._try_nim(
            decision=decision,
            product=product,
            pathway_analysis=[_as_mapping(p) for p in pathway_analysis],
            counterfactuals=normalized_counterfactuals,
            missing_facts=missing_facts,
            evidence_required=evidence_required,
            tariff_outcome=tariff_outcome,
        )

        if nim_result is not None:
            return nim_result

        # Deterministic fallback
        logger.info("Using deterministic DecisionRenderer fallback")
        return self._renderer.render(
            engine_payload=engine_payload,
            counterfactuals=counterfactuals,
        )

    async def _try_nim(
        self,
        *,
        decision: Mapping[str, Any],
        product: Mapping[str, Any],
        pathway_analysis: Sequence[Mapping[str, Any]],
        counterfactuals: Sequence[Mapping[str, Any]],
        missing_facts: Sequence[Any],
        evidence_required: Sequence[Any],
        tariff_outcome: Mapping[str, Any],
    ) -> RenderedDecision | None:
        """Attempt NIM rendering. Return None on any failure."""
        user_prompt = _build_user_prompt(
            decision=decision,
            product=product,
            pathway_analysis=pathway_analysis,
            counterfactuals=counterfactuals,
            missing_facts=missing_facts,
            evidence_required=evidence_required,
            tariff_outcome=tariff_outcome,
        )

        # Step 1-2: Call NIM
        try:
            raw = await self.nim_client.generate_json(_SYSTEM_PROMPT, user_prompt)
        except NimClientError as exc:
            logger.warning("NIM rendering call failed: %s", exc)
            return None

        if raw is None:
            logger.info("NIM is disabled, skipping rendering")
            return None

        # Step 3: Parse JSON
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("NIM rendering returned invalid JSON: %s", exc)
            return None

        # Step 4: Validate against schema
        try:
            rendering = NimRendering.model_validate(data)
        except ValidationError as exc:
            logger.warning("NIM rendering failed schema validation: %s", exc)
            return None

        # Step 5: Contradiction guardrails
        guardrail_failure = _run_guardrails(
            rendering,
            decision=decision,
            pathway_analysis=pathway_analysis,
            counterfactuals=counterfactuals,
            missing_facts=missing_facts,
        )
        if guardrail_failure is not None:
            logger.warning(
                "NIM rendering failed guardrail check: %s", guardrail_failure
            )
            return None

        # All checks passed — convert to RenderedDecision
        return RenderedDecision(
            headline=rendering.headline,
            summary=rendering.summary,
            gap_analysis=rendering.gap_analysis,
            fix_strategy=rendering.fix_strategy,
            next_steps=rendering.next_steps,
            warnings=rendering.warnings,
        )


# ---------------------------------------------------------------------------
# Type coercion helpers (mirrors DecisionRenderer)
# ---------------------------------------------------------------------------


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []
