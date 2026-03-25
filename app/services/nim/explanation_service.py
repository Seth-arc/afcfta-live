"""NIM explanation service: wrap a deterministic assessment in plain-language text.

Responsibility boundary:
- Owns the system-prompt construction that grounds NIM in the engine's output.
- Owns the contradiction guard: rejects any model output that contradicts the
  deterministic decision fields.
- Returns a minimal deterministic fallback when the model fails or produces
  an invalid explanation.
- Does NOT alter any field in EligibilityAssessmentResponse.
- Does NOT access the database.
- Does NOT call the deterministic engine.

Contradiction guard — the service must reject any explanation that contradicts:
  - eligible
  - pathway_used
  - rule_status
  - tariff_outcome (status field)
  - confidence_class

If the explanation fails the contradiction guard, `fallback_used` is set to True
and a minimal deterministic summary is returned. The assessment result is never
blocked by explanation failure.
"""

from __future__ import annotations

from app.schemas.assessments import EligibilityAssessmentResponse
from app.schemas.nim.explanation import ExplanationResult
from app.services.nim.client import NimClient


class ExplanationService:
    """Generate a plain-language explanation for a deterministic assessment result.

    Injected with a NimClient for text generation. The contradiction guard
    is deterministic and must run before any model output is returned.
    """

    def __init__(self, nim_client: NimClient) -> None:
        self.nim_client = nim_client

    async def generate_explanation(
        self,
        assessment: EligibilityAssessmentResponse,
        persona_mode: str | None = None,
    ) -> ExplanationResult:
        """Generate a plain-language explanation grounded in the assessment result.

        Calls the NIM model with a system prompt that includes the deterministic
        decision fields. Validates the model's output against the contradiction
        guard before returning it.

        On any failure (model error, timeout, validation rejection), returns an
        ExplanationResult with `text=None` and `fallback_used=True`. The
        deterministic assessment is always returned to the caller regardless of
        whether explanation succeeds.

        Raises nothing — the fallback path is always available.
        """
        # Stub: NIM call, contradiction guard, and fallback are in Prompt 8.
        raise NotImplementedError(
            "ExplanationService.generate_explanation is not yet wired. "
            "Implement in Prompt 8 (app/services/nim/explanation_service.py)."
        )

    def _passes_contradiction_guard(
        self,
        explanation_text: str,
        assessment: EligibilityAssessmentResponse,
    ) -> bool:
        """Return True when explanation_text does not contradict the assessment.

        Checks for the presence of contradicting outcome language relative
        to the deterministic decision. Exact logic is implemented in Prompt 8.
        """
        # Stub: implemented in Prompt 8.
        raise NotImplementedError(
            "ExplanationService._passes_contradiction_guard is not yet wired. "
            "Implement in Prompt 8 (app/services/nim/explanation_service.py)."
        )
