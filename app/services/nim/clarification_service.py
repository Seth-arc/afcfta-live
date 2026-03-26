"""NIM clarification service: generate a focused follow-up question from engine gaps.

Responsibility boundary:
- Owns the priority logic that selects which gap to ask about first.
- Uses NimClient to phrase the selected gap as a natural-language question.
- Falls back to a deterministic question template when NIM is unavailable,
  returns invalid JSON, or produces a question that implies an eligibility
  outcome.
- Does NOT infer eligibility or promise outcomes.
- Does NOT access the database.
- Does NOT call the deterministic engine.

Priority order for gap selection (deterministic, not model-driven):
0. Intake rejection reasons that require a deterministic retry prompt
   before any gap-based clarification (for example oversized input).
1. Required draft facts absent from NimAssessmentDraft (hs6_code, exporter,
   importer, year, persona_mode) — must be resolved before the engine can run.
2. Missing production facts reported in the engine's `missing_facts` field
   after a partial run — these unblock pathway evaluation.
3. Missing evidence items reported in the engine's `missing_evidence` field.

The model is used only to phrase the question once the gap has been selected.
If the model call fails or produces outcome-implying language, a deterministic
template is returned instead. The fallback path never infers eligibility.
"""

from __future__ import annotations

import json
import logging

from app.core.fact_keys import PRODUCTION_FACTS
from app.schemas.nim.assistant import ClarificationResponse
from app.schemas.nim.clarification import ClarificationContext
from app.services.nim.client import NimClient, NimClientError
from app.services.nim.intake_service import NIM_REJECTION_REASON_INPUT_TOO_LONG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Human-readable labels for required draft intake fields
# ---------------------------------------------------------------------------

_DRAFT_FACT_LABELS: dict[str, str] = {
    "hs6_code": "HS6 product code (e.g. 110311 for wheat groats)",
    "exporter": "exporting country ISO alpha-3 code (e.g. GHA for Ghana)",
    "importer": "importing country ISO alpha-3 code (e.g. NGA for Nigeria)",
    "year": "assessment year (e.g. 2025)",
    "persona_mode": "user role — exporter, customs officer, or trade analyst",
}

_ENGINE_FACT_LABELS: dict[str, str] = {
    "ex_works": "the ex-works value of the finished goods",
    "non_originating": "the value of the non-originating materials used",
    "tariff_heading_input": (
        "the tariff heading of the imported materials before processing"
    ),
    "tariff_heading_output": (
        "the tariff heading of the finished goods after processing"
    ),
    "wholly_obtained": (
        "whether the goods are wholly obtained in the exporting country"
    ),
    "direct_transport": (
        "whether the goods were shipped directly from the exporting country "
        "to the importing country"
    ),
    "cumulation_claimed": (
        "whether you are claiming cumulation with materials or processing "
        "from another AfCFTA country"
    ),
    "va_percent": (
        "the percentage of the finished goods' value added in the exporting "
        "country"
    ),
    "vnom_percent": (
        "the percentage of the ex-works value that comes from "
        "non-originating materials"
    ),
}

# ---------------------------------------------------------------------------
# Deterministic fallback question templates
# ---------------------------------------------------------------------------

_DRAFT_FACT_QUESTIONS: dict[str, str] = {
    "hs6_code": (
        "What is the HS6 product code for the goods you are trading? "
        "(e.g. 110311 for wheat groats)"
    ),
    "exporter": (
        "Which country is exporting the goods? "
        "Please provide the 3-letter ISO code (e.g. GHA for Ghana)."
    ),
    "importer": (
        "Which country is importing the goods? "
        "Please provide the 3-letter ISO code (e.g. NGA for Nigeria)."
    ),
    "year": "Which year do you need the assessment for? (e.g. 2025)",
    "persona_mode": (
        "Are you enquiring as an exporter, customs officer, or trade analyst?"
    ),
}

_ENGINE_FACT_QUESTION = (
    "To continue the assessment, I need to know {readable_label}. "
    "Could you provide that?"
)
_EVIDENCE_QUESTION = (
    "Do you have the following document available: {evidence_key}?"
)
_INPUT_TOO_LONG_QUESTION = (
    "Your description is longer than 2000 characters. Please resend a shorter "
    "summary focused on the product, corridor, year, and the key production facts."
)

# ---------------------------------------------------------------------------
# Outcome-implication guard
# ---------------------------------------------------------------------------

# These phrases in the model's question text indicate it is asserting an
# eligibility conclusion rather than asking a neutral follow-up question.
_OUTCOME_PHRASES: frozenset[str] = frozenset({
    "will qualify",
    "will not qualify",
    "won't qualify",
    "is eligible",
    "not eligible",
    "are eligible",
    "will be eligible",
    "likely to qualify",
    "unlikely to qualify",
    "will pass",
    "will fail",
    "is compliant",
    "not compliant",
    "will be approved",
    "will be rejected",
})

# ---------------------------------------------------------------------------
# NIM phrasing system prompt
# ---------------------------------------------------------------------------

_NIM_PHRASING_SYSTEM_PROMPT = """\
You are an assistant for the AfCFTA trade eligibility service.
Your task is to ask ONE focused follow-up question to gather a single missing
piece of information.

Rules:
- Ask about exactly the gap described below — nothing else.
- Do NOT state or imply what the eligibility outcome might be.
- Do NOT promise that providing the information will lead to approval.
- Do NOT use language like "eligible", "qualifies", "compliant", or similar.
- Keep the question short, clear, and suitable for a trader or customs official.
- Do not ask multiple questions in the same response.

Return ONLY a JSON object: {"question": "<your single focused question>"}
"""

_NIM_MULTI_GAP_SYSTEM_PROMPT = """\
You are an assistant for the AfCFTA trade eligibility service.
Your task is to ask for all of the listed missing intake fields in ONE short
message.

Rules:
- Ask only for the listed intake fields and nothing else.
- Ask for all listed items in one clear message.
- Do NOT state or imply what the eligibility outcome might be.
- Do NOT promise that providing the information will lead to approval.
- Do NOT use language like "eligible", "qualifies", "compliant", or similar.
- Keep the message short, clear, and suitable for a trader or customs official.
- Keep the listed items in the same order they are provided below.

Return ONLY a JSON object: {"question": "<your short message asking for all listed items>"}
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _gap_context_lines(gap_key: str, context: ClarificationContext) -> str:
    """Build the user-input text describing the gap for the NIM phrasing call."""
    if gap_key in context.missing_draft_facts:
        label = _DRAFT_FACT_LABELS.get(gap_key, gap_key.replace("_", " "))
        gap_type = "required intake field"
    elif gap_key in context.missing_engine_facts:
        label = _ENGINE_FACT_LABELS.get(gap_key, gap_key.replace("_", " "))
        gap_type = "production fact needed by the engine"
    else:
        label = gap_key.replace("_", " ")
        gap_type = "supporting document"

    return f"Gap type: {gap_type}\nGap key: {gap_key}\nDescription: {label}"


def _multi_gap_context_lines(gap_keys: list[str]) -> str:
    """Build the user-input text describing multiple required draft gaps."""
    labels = [
        _DRAFT_FACT_LABELS.get(gap_key, gap_key.replace("_", " "))
        for gap_key in gap_keys
    ]
    descriptions = "\n".join(
        f"- {gap_key}: {label}" for gap_key, label in zip(gap_keys, labels)
    )
    return (
        "Gap type: required intake fields\n"
        f"Gap keys: {', '.join(gap_keys)}\n"
        f"Descriptions:\n{descriptions}"
    )


def _multi_gap_fallback_question(gap_keys: list[str]) -> str:
    """Return the deterministic fallback for multiple missing draft facts."""
    labels = [
        _DRAFT_FACT_LABELS.get(gap_key, gap_key.replace("_", " "))
        for gap_key in gap_keys
    ]
    return f"To get started, I need a few things: {', '.join(labels)}."


def _deterministic_question(gap_key: str) -> str:
    """Return a deterministic fallback question for the given gap key."""
    if gap_key in _DRAFT_FACT_QUESTIONS:
        return _DRAFT_FACT_QUESTIONS[gap_key]
    if gap_key in PRODUCTION_FACTS or gap_key in _ENGINE_FACT_LABELS:
        readable_label = _ENGINE_FACT_LABELS.get(
            gap_key, gap_key.replace("_", " ")
        )
        return _ENGINE_FACT_QUESTION.format(readable_label=readable_label)
    return _EVIDENCE_QUESTION.format(evidence_key=gap_key.replace("_", " "))


def _question_implies_outcome(question: str) -> bool:
    """Return True if the question text asserts an eligibility outcome."""
    lower = question.lower()
    return any(phrase in lower for phrase in _OUTCOME_PHRASES)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ClarificationService:
    """Generate one focused clarification question grounded in real engine gaps.

    Injected with a NimClient for question phrasing. The gap selection
    logic is deterministic and lives in this class, not in the model.
    """

    def __init__(self, nim_client: NimClient) -> None:
        self.nim_client = nim_client

    async def generate_clarification(
        self, context: ClarificationContext
    ) -> ClarificationResponse:
        """Select the highest-priority gap and ask NIM to phrase a question.

        Gap selection is deterministic (draft facts → engine facts → evidence).
        NIM is used only to phrase the selected gap as natural language.

        Falls back to a deterministic template if:
        - the NIM call fails or times out
        - NIM is disabled (returns None)
        - the model output cannot be parsed as JSON
        - the model's question implies an eligibility outcome

        The returned ClarificationResponse:
        - contains exactly one focused question
        - lists all missing facts (draft + engine) and evidence from the context
        - never infers eligibility or promises outcomes

        Raises nothing — deterministic fallback is always available.
        """
        if context.nim_rejection_reason == NIM_REJECTION_REASON_INPUT_TOO_LONG:
            return ClarificationResponse(
                question=_INPUT_TOO_LONG_QUESTION,
                missing_facts=[],
                missing_evidence=[],
            )

        # 1. Deterministic gap selection — not model-driven
        if len(context.missing_draft_facts) > 1:
            question = await self._phrase_multi_gap_question(
                context.missing_draft_facts
            )
        else:
            gap_key = context.highest_priority_gap()
            # gap_key cannot be None here because ClarificationContext validates
            # that at least one gap is present
            assert gap_key is not None  # schema invariant
            question = await self._phrase_question(gap_key, context)

        # 3. Assemble full missing-item lists for the response
        all_missing_facts = context.missing_draft_facts + context.missing_engine_facts

        return ClarificationResponse(
            question=question,
            missing_facts=all_missing_facts,
            missing_evidence=context.missing_evidence,
        )

    async def _phrase_question(
        self, gap_key: str, context: ClarificationContext
    ) -> str:
        """Ask NIM to phrase a question for the gap, or return a fallback."""
        user_input = _gap_context_lines(gap_key, context)

        try:
            raw = await self.nim_client.generate_json(
                _NIM_PHRASING_SYSTEM_PROMPT, user_input
            )
        except NimClientError as exc:
            logger.warning("NIM clarification phrasing failed: %s", exc)
            return _deterministic_question(gap_key)

        if raw is None:
            return _deterministic_question(gap_key)

        try:
            data = json.loads(raw)
            question = str(data.get("question", "")).strip()
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            logger.warning("NIM clarification response parse error: %s", exc)
            return _deterministic_question(gap_key)

        if not question or _question_implies_outcome(question):
            if question:
                logger.warning(
                    "NIM clarification question implies outcome, using fallback: %r",
                    question,
                )
            return _deterministic_question(gap_key)

        return question

    async def _phrase_multi_gap_question(self, gap_keys: list[str]) -> str:
        """Ask NIM to phrase one message covering multiple required draft facts."""
        user_input = _multi_gap_context_lines(gap_keys)

        try:
            raw = await self.nim_client.generate_json(
                _NIM_MULTI_GAP_SYSTEM_PROMPT, user_input
            )
        except NimClientError as exc:
            logger.warning("NIM clarification multi-gap phrasing failed: %s", exc)
            return _multi_gap_fallback_question(gap_keys)

        if raw is None:
            return _multi_gap_fallback_question(gap_keys)

        try:
            data = json.loads(raw)
            question = str(data.get("question", "")).strip()
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            logger.warning("NIM clarification multi-gap response parse error: %s", exc)
            return _multi_gap_fallback_question(gap_keys)

        if not question or _question_implies_outcome(question):
            if question:
                logger.warning(
                    "NIM clarification multi-gap question implies outcome, using fallback: %r",
                    question,
                )
            return _multi_gap_fallback_question(gap_keys)

        return question
