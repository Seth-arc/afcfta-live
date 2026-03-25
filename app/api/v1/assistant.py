"""Thin route handler for the NIM assistant endpoint.

This is the contract harness (NIM Readiness Prompt 2).
Model-calling logic is NOT yet wired — see Prompt 9 for full orchestration.

Architectural constraints enforced here:
- NIM may parse, clarify, and explain. It may never decide eligibility.
- Every assessment response must include replay identifiers and set
  X-AIS-Case-Id, X-AIS-Evaluation-Id, and X-AIS-Audit-URL headers.
- `audit_persisted` must be True only when persistence was confirmed by the
  engine's InterfaceAssessmentResult.
- Explanation content is additive only: it must not alter any assessment field.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.nim.assistant import (
    AssistantRequest,
    AssistantResponseEnvelope,
    ClarificationResponse,
)

router = APIRouter()


@router.post("/assistant/assess", response_model=AssistantResponseEnvelope)
async def assistant_assess(
    payload: AssistantRequest,
) -> AssistantResponseEnvelope:
    """NIM-assisted eligibility assessment endpoint.

    Contract harness — model-calling and engine-wiring are not yet implemented.
    Returns a clarification stub so that the response contract and integration
    tests are pinned before live model calls are added.

    When the full orchestration flow is wired (Prompt 9), this handler will:
    1. Call intake_service.parse_user_input(payload.user_input, payload.context)
    2. If confidence or completeness is insufficient, return clarification.
    3. Map the NIM draft to a live EligibilityRequest (dropping NIM-only metadata).
    4. Call eligibility_service.assess_interface_request(request).
    5. Add a Response parameter and set X-AIS-Case-Id, X-AIS-Evaluation-Id,
       and X-AIS-Audit-URL headers from InterfaceAssessmentResult.
    6. Call explanation_service (with fallback to None on failure).
    7. Return the combined AssistantResponseEnvelope.
    """

    # Harness stub: no model or engine calls yet.
    # payload and response will be used once the NIM intake service and
    # eligibility engine are wired in Prompt 9. The response shape is
    # fully pinned by the integration tests in test_assistant_api.py.
    return AssistantResponseEnvelope(
        response_type="clarification",
        audit_persisted=False,
        clarification=ClarificationResponse(
            question=(
                "Please provide the HS6 product code, exporter country (ISO alpha-3), "
                "importer country (ISO alpha-3), and assessment year."
            ),
            missing_facts=["hs6_code", "exporter", "importer", "year"],
        ),
    )
