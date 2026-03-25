"""NIM clarification service: generate a focused follow-up question from engine gaps.

Responsibility boundary:
- Owns the priority logic that selects which gap to ask about first.
- Uses NimClient to phrase the selected gap as a natural-language question.
- Falls back to a deterministic question template when NIM is unavailable.
- Does NOT infer eligibility or promise outcomes.
- Does NOT access the database.
- Does NOT call the deterministic engine.

Priority order for gap selection (deterministic, not model-driven):
1. Required draft facts absent from NimAssessmentDraft (hs6_code, exporter,
   importer, year, persona_mode) — these must be resolved before the engine
   can run at all.
2. Missing production facts reported in the engine's `missing_facts` field
   after a partial run — these unblock pathway evaluation.
3. Missing evidence items reported in the engine's `missing_evidence` field.

The model is used only to phrase the question once the gap has been selected.
If the model call fails, a deterministic template is returned instead.
"""

from __future__ import annotations

from app.schemas.nim.assistant import ClarificationResponse
from app.schemas.nim.clarification import ClarificationContext
from app.services.nim.client import NimClient


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

        Falls back to a deterministic question template if the model call
        fails, times out, or NIM is disabled.

        The returned ClarificationResponse must:
        - Contain exactly one focused question.
        - List only the missing items that were passed in the context.
        - Never infer eligibility or promise outcomes.

        Raises nothing — deterministic fallback is always available.
        """
        # Stub: NIM phrasing call and fallback are implemented in Prompt 7.
        raise NotImplementedError(
            "ClarificationService.generate_clarification is not yet wired. "
            "Implement in Prompt 7 (app/services/nim/clarification_service.py)."
        )
