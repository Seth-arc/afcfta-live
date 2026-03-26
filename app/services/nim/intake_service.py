"""NIM intake service: parse natural-language input into a structured assessment draft.

Responsibility boundary:
- Owns the system-prompt construction for NIM parsing calls.
- Owns validation of the NIM model's JSON output against NimAssessmentDraft.
- Owns the mapping from NimAssessmentDraft to EligibilityRequest, including
  stripping NIM-only metadata before the engine is called.
- Does NOT call the deterministic engine.
- Does NOT decide eligibility.
- Does NOT access the database.

The mapping layer drops `nim_confidence`, `nim_assumptions`,
`nim_rejection_reason`, and `product.product_description_parsed` before
constructing EligibilityRequest.

Field-name rule: always map to `existing_documents`. Never pass
`submitted_documents` to the engine or include it in any returned schema.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.core.enums import FactSourceTypeEnum, FactValueTypeEnum
from app.schemas.assessments import EligibilityRequest
from app.schemas.cases import CaseFactIn
from app.schemas.nim.intake import (
    AssessmentContext,
    MaterialInput,
    NimAssessmentDraft,
    TradeFlow,
)
from app.services.nim.client import NimClient, NimClientError

logger = logging.getLogger(__name__)

# AGENTS.md / NIM Security Constraints: user_input must be capped at 2000
# characters before any request is sent to the NIM model.
NIM_MAX_INPUT_CHARS = 2000
NIM_REJECTION_REASON_INPUT_TOO_LONG = "INPUT_TOO_LONG"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_NIM_INTAKE_SYSTEM_PROMPT = """\
You are an intake parser for the AfCFTA trade eligibility assistant.
Parse the user's natural-language trade query into a structured JSON object.

Return ONLY a JSON object with this structure (use null for unknown values):

{
  "product": {
    "hs6_code": "<string: 6+ digit HS code, or null>",
    "hs_version": "HS2017",
    "product_description_parsed": "<string: product description, or null>"
  },
  "trade_flow": {
    "exporter": "<string: ISO alpha-3 uppercase, or null>",
    "importer": "<string: ISO alpha-3 uppercase, or null>",
    "year": <integer: 2020-2040, or null>
  },
  "context": {
    "persona_mode": "<one of: exporter, officer, analyst, system — or null>"
  },
  "production_facts": {
    "material_inputs": []
  },
  "existing_documents": [],
  "nim_confidence": {
    "overall": <float 0.0-1.0>,
    "hs6_confidence": <float 0.0-1.0>,
    "corridor_confidence": <float 0.0-1.0>,
    "facts_confidence": <float 0.0-1.0>
  },
  "nim_assumptions": ["<list any assumptions made>"]
}

Rules:
- hs6_code: strip punctuation ("11.03.11" → "110311"). Use first 6+ digits only.
- country codes: always 3 uppercase letters ("Ghana" → "GHA", "Nigeria" → "NGA").
- Supported countries: NGA, GHA, CIV, SEN, CMR.
- year: use the year mentioned; leave null if not stated.
- persona_mode: infer from context ("I want to export" → "exporter").
- nim_confidence.overall: your confidence that you extracted all required fields
  (hs6_code, exporter, importer, year, persona_mode).
- production_facts.material_inputs: only populate if the user explicitly states
  production facts (costs, tariff headings, process details). Do not invent facts.
- existing_documents: only populate if the user mentions documents they already have.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _material_input_to_case_fact(mi: MaterialInput) -> CaseFactIn:
    """Convert a NIM MaterialInput to a CaseFactIn for the eligibility engine."""
    if mi.text_value is not None:
        return CaseFactIn(
            fact_type=mi.fact_key,
            fact_key=mi.fact_key,
            fact_value_type=FactValueTypeEnum.TEXT,
            fact_value_text=mi.text_value,
            unit=mi.unit,
            source_type=FactSourceTypeEnum.USER_INPUT,
        )
    if mi.number_value is not None:
        return CaseFactIn(
            fact_type=mi.fact_key,
            fact_key=mi.fact_key,
            fact_value_type=FactValueTypeEnum.NUMBER,
            fact_value_number=mi.number_value,
            unit=mi.unit,
            source_type=FactSourceTypeEnum.USER_INPUT,
        )
    # boolean_value is non-None — guaranteed by MaterialInput's model validator
    return CaseFactIn(
        fact_type=mi.fact_key,
        fact_key=mi.fact_key,
        fact_value_type=FactValueTypeEnum.BOOLEAN,
        fact_value_boolean=mi.boolean_value,
        unit=mi.unit,
        source_type=FactSourceTypeEnum.USER_INPUT,
    )


def _build_context_hint_lines(context: Any) -> str:
    """Return a formatted hint block to append to the system prompt."""
    lines: list[str] = []
    if getattr(context, "exporter", None) is not None:
        lines.append(f"- exporter: {context.exporter}")
    if getattr(context, "importer", None) is not None:
        lines.append(f"- importer: {context.importer}")
    if getattr(context, "year", None) is not None:
        lines.append(f"- year: {context.year}")
    if getattr(context, "persona_mode", None) is not None:
        lines.append(f"- persona_mode: {context.persona_mode.value}")
    return "\n".join(lines)


def _apply_context_hints(draft: NimAssessmentDraft, context: Any) -> NimAssessmentDraft:
    """Fill gaps in the draft from caller-supplied context hints.

    Context values are applied only when the model left the corresponding
    field as None. They never override a value the model already extracted.
    """
    trade_flow_updates: dict[str, Any] = {}

    if getattr(context, "exporter", None) is not None:
        current = draft.trade_flow.exporter if draft.trade_flow else None
        if current is None:
            trade_flow_updates["exporter"] = context.exporter

    if getattr(context, "importer", None) is not None:
        current = draft.trade_flow.importer if draft.trade_flow else None
        if current is None:
            trade_flow_updates["importer"] = context.importer

    if getattr(context, "year", None) is not None:
        current = draft.trade_flow.year if draft.trade_flow else None
        if current is None:
            trade_flow_updates["year"] = context.year

    if trade_flow_updates:
        existing = draft.trade_flow or TradeFlow()
        draft = draft.model_copy(
            update={"trade_flow": existing.model_copy(update=trade_flow_updates)}
        )

    if getattr(context, "persona_mode", None) is not None:
        current = draft.context.persona_mode if draft.context else None
        if current is None:
            new_ctx = AssessmentContext(persona_mode=context.persona_mode)
            draft = draft.model_copy(update={"context": new_ctx})

    return draft


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IntakeService:
    """Parse natural-language user input into a validated NimAssessmentDraft.

    Injected with a NimClient so the HTTP call can be replaced with a stub
    in tests without patching internal implementation details.
    """

    def __init__(self, nim_client: NimClient) -> None:
        self.nim_client = nim_client

    async def parse_user_input(
        self,
        user_input: str,
        context: Any | None = None,
    ) -> NimAssessmentDraft:
        """Parse a natural-language trade query into a structured assessment draft.

        Calls the NIM model with a structured system prompt, parses the raw
        JSON response, and validates it against NimAssessmentDraft. Context
        hints (if supplied) are merged into the draft after validation, filling
        only the fields the model left as None.

        When NIM is disabled, the model call fails, or the raw user input
        exceeds the AGENTS.md length boundary, returns an empty
        NimAssessmentDraft so the caller can proceed to clarification.

        Returns:
            NimAssessmentDraft with NIM-only metadata populated. Callers must
            call to_eligibility_request() to strip that metadata before
            passing the draft to the engine.
        """
        if len(user_input) > NIM_MAX_INPUT_CHARS:
            logger.warning(
                "NIM intake rejected oversized user_input: user_input_char_count=%d max_input_chars=%d",
                len(user_input),
                NIM_MAX_INPUT_CHARS,
            )
            return NimAssessmentDraft(
                nim_rejection_reason=NIM_REJECTION_REASON_INPUT_TOO_LONG
            )

        # Append context hints to the system prompt when available
        system_prompt = _NIM_INTAKE_SYSTEM_PROMPT
        if context is not None:
            hint_lines = _build_context_hint_lines(context)
            if hint_lines:
                system_prompt = (
                    system_prompt
                    + "\n\nContext hints already known (use these if the user did not state them):\n"
                    + hint_lines
                )

        try:
            raw = await self.nim_client.generate_json(system_prompt, user_input)
        except NimClientError as exc:
            logger.warning("NIM intake call failed: %s", exc)
            raw = None

        if raw is None:
            # NIM disabled or call failed — return empty draft for clarification
            draft = NimAssessmentDraft()
        else:
            try:
                data = json.loads(raw)
                draft = NimAssessmentDraft.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning("NIM intake parse/validation error: %s", exc)
                draft = NimAssessmentDraft()

        if context is not None:
            draft = _apply_context_hints(draft, context)

        return draft

    def to_eligibility_request(self, draft: NimAssessmentDraft) -> EligibilityRequest:
        """Map a validated NimAssessmentDraft to a live EligibilityRequest.

        Strips all NIM-only metadata (nim_confidence, nim_assumptions,
        nim_rejection_reason, product.product_description_parsed) — these
        fields never reach the deterministic engine.

        Raises:
            ValueError: If required engine fields (hs6_code, exporter, importer,
                        year, persona_mode) are absent in the draft.
            pydantic.ValidationError: If the mapped values fail EligibilityRequest
                        validation (e.g. unsupported country codes).
        """
        missing = draft.missing_required_facts()
        if missing:
            raise ValueError(
                f"Draft is missing required engine fields: {missing}. "
                "Trigger clarification before calling the engine."
            )

        case_facts: list[CaseFactIn] = []
        if draft.production_facts is not None:
            for mi in draft.production_facts.material_inputs:
                case_facts.append(_material_input_to_case_fact(mi))

        return EligibilityRequest(
            hs6_code=draft.product.hs6_code,  # type: ignore[union-attr]
            hs_version=draft.product.hs_version,  # type: ignore[union-attr]
            exporter=draft.trade_flow.exporter,  # type: ignore[union-attr]
            importer=draft.trade_flow.importer,  # type: ignore[union-attr]
            year=draft.trade_flow.year,  # type: ignore[union-attr]
            persona_mode=draft.context.persona_mode,  # type: ignore[union-attr]
            production_facts=case_facts,
            existing_documents=draft.existing_documents,
            # nim_confidence, nim_assumptions, nim_rejection_reason,
            # product_description_parsed DROPPED here
        )
