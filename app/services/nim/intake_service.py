"""NIM intake service: parse natural-language input into a structured assessment draft.

Responsibility boundary:
- Owns the system-prompt construction for NIM parsing calls.
- Owns validation of the NIM model's JSON output against NimAssessmentDraft.
- Owns the mapping from NimAssessmentDraft to EligibilityRequest, including
  stripping NIM-only metadata before the engine is called.
- Does NOT call the deterministic engine.
- Does NOT decide eligibility.
- Does NOT access the database.

The mapping layer must drop `nim_confidence`, `nim_completeness_score`, and
`nim_assumptions` before constructing EligibilityRequest. These fields are
for the intake and clarification services only.

Field-name rule: always map to `existing_documents`. Never pass
`submitted_documents` to the engine or include it in any returned schema.
"""

from __future__ import annotations

from app.schemas.assessments import EligibilityRequest
from app.schemas.nim.intake import NimAssessmentDraft
from app.services.nim.client import NimClient


class IntakeService:
    """Parse natural-language user input into a validated NimAssessmentDraft.

    Injected with a NimClient so the HTTP call can be replaced with a stub
    in tests without mocking internal implementation details.
    """

    def __init__(self, nim_client: NimClient) -> None:
        self.nim_client = nim_client

    async def parse_user_input(
        self,
        user_input: str,
        context: object | None = None,
    ) -> NimAssessmentDraft:
        """Parse a natural-language trade query into a structured assessment draft.

        Calls the NIM model with a structured system prompt, parses the raw
        JSON response, and validates it against NimAssessmentDraft. Any context
        hints supplied by the caller are merged into the draft after validation.

        Returns a NimAssessmentDraft with NIM-only metadata populated. Callers
        must call `to_eligibility_request()` to strip that metadata before
        passing the draft to the engine.

        Raises:
            NimClientError: If the model call fails and no fallback is available.
            ValidationError: If the model output cannot be parsed as NimAssessmentDraft.
        """
        # Stub: NIM model call and JSON parsing are implemented in Prompt 6.
        raise NotImplementedError(
            "IntakeService.parse_user_input is not yet wired. "
            "Implement in Prompt 6 (app/services/nim/intake_service.py)."
        )

    def to_eligibility_request(self, draft: NimAssessmentDraft) -> EligibilityRequest:
        """Map a validated NimAssessmentDraft to a live EligibilityRequest.

        Strips all NIM-only metadata fields (`nim_confidence`,
        `nim_completeness_score`, `nim_assumptions`) before constructing
        the request. These fields must never reach the deterministic engine.

        Raises:
            ValueError: If required engine fields are still absent in the draft.
        """
        # Stub: mapping logic is implemented in Prompt 6.
        raise NotImplementedError(
            "IntakeService.to_eligibility_request is not yet wired. "
            "Implement in Prompt 6 (app/services/nim/intake_service.py)."
        )
