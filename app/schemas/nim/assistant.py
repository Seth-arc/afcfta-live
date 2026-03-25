"""Pydantic schemas for the NIM assistant request/response contract.

Architectural constraint (non-negotiable):
- NIM may parse, clarify, and explain. It may never decide eligibility.
- All deterministic decision fields in `assessment` come from the eligibility
  engine, unchanged.
- `audit_persisted` at the envelope level is the authoritative flag. The
  assistant must not claim audit compliance when this is False.
- Replay identifiers (`case_id`, `evaluation_id`, `audit_url`) are always
  populated when `audit_persisted` is True and `response_type` is "assessment".
- `explanation` is additive only: it must never contradict any field in
  `assessment` (`eligible`, `pathway_used`, `rule_status`, `tariff_outcome`,
  `confidence_class`, `failures`, `missing_facts`).
- Use `existing_documents` exclusively. Never use `submitted_documents` in
  NIM schemas or test fixtures.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PersonaModeEnum
from app.schemas.assessments import EligibilityAssessmentResponse


class AssistantContext(BaseModel):
    """Optional structured hints the caller can supply alongside natural-language input.

    These are intake hints only — they do not bypass NIM parsing and are
    stripped before any facts are passed to the deterministic engine.
    """

    persona_mode: PersonaModeEnum | None = None
    exporter: str | None = Field(default=None, min_length=3, max_length=3)
    importer: str | None = Field(default=None, min_length=3, max_length=3)
    year: int | None = Field(default=None, ge=2020, le=2040)

    model_config = ConfigDict(extra="forbid")


class AssistantRequest(BaseModel):
    """NIM assistant request: natural-language user input with optional context hints."""

    user_input: str = Field(min_length=1, max_length=4000)
    context: AssistantContext | None = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "user_input": "Can I export wheat groats (HS 110311) from Ghana to Nigeria?",
                    "context": {
                        "persona_mode": "exporter",
                        "exporter": "GHA",
                        "importer": "NGA",
                        "year": 2025,
                    },
                }
            ]
        },
    )


class ClarificationResponse(BaseModel):
    """A single focused follow-up question grounded in real engine gaps.

    Clarification must target actual missing facts or evidence gaps, not
    speculative guidance. It must not infer eligibility or promise outcomes.
    """

    question: str
    missing_facts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class AssistantError(BaseModel):
    """Structured error for input rejection and validation failures.

    Returned when the request is invalid before the engine is called.
    Distinct from clarification: error means the request cannot proceed;
    clarification means it can proceed once facts are supplied.
    """

    code: str
    message: str
    detail: dict[str, object] | None = None

    model_config = ConfigDict(extra="forbid")


class AssistantResponseEnvelope(BaseModel):
    """Combined NIM assistant response envelope.

    `response_type` is the discriminator field:

    - ``"clarification"`` — NIM needs more information before the engine can
      run. `clarification` is populated. `assessment`, `case_id`,
      `evaluation_id`, `audit_url` are all None. `audit_persisted` is False.

    - ``"assessment"`` — The deterministic engine ran and a decision was
      produced. `assessment` carries all engine output fields unchanged.
      `case_id`, `evaluation_id`, `audit_url`, and `audit_persisted` are all
      populated. `explanation` may be present as additive plain-language text.

    - ``"error"`` — The request was rejected before the engine ran. `error`
      is populated with a structured failure code. All other payload fields
      are None.

    Invariants the assistant layer must preserve:
    1. Never set `audit_persisted` to True unless persistence was confirmed.
    2. Never alter `assessment` fields after receiving them from the engine.
    3. Never populate both `clarification` and `assessment` in the same
       response.
    4. `explanation` must be set to None rather than fabricated if the
       explanation service fails or is not yet wired.
    """

    response_type: Literal["clarification", "assessment", "error"]

    # Replay identifiers — populated when response_type == "assessment"
    case_id: str | None = None
    evaluation_id: str | None = None
    audit_url: str | None = None
    audit_persisted: bool = False

    # Payload fields — exactly one is non-null, matching response_type
    assessment: EligibilityAssessmentResponse | None = None
    clarification: ClarificationResponse | None = None
    explanation: str | None = None  # additive only; never contradicts assessment
    error: AssistantError | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "response_type": "assessment",
                    "case_id": "29dc2946-6ef0-46a0-b3eb-0f6a64e40db7",
                    "evaluation_id": "4c651cd2-8f0f-4c16-9f37-8dfceef41f26",
                    "audit_url": (
                        "/api/v1/audit/evaluations/4c651cd2-8f0f-4c16-9f37-8dfceef41f26"
                    ),
                    "audit_persisted": True,
                    "assessment": {
                        "hs6_code": "110311",
                        "eligible": True,
                        "pathway_used": "CTH",
                        "rule_status": "agreed",
                        "tariff_outcome": {
                            "preferential_rate": "0.0000",
                            "base_rate": "15.0000",
                            "status": "in_force",
                        },
                        "failures": [],
                        "missing_facts": [],
                        "evidence_required": ["certificate_of_origin"],
                        "missing_evidence": [],
                        "readiness_score": 1.0,
                        "completeness_ratio": 1.0,
                        "confidence_class": "complete",
                        "audit_persisted": True,
                    },
                    "clarification": None,
                    "explanation": (
                        "Ghana wheat groats exported to Nigeria qualify under "
                        "the CTH rule with a 0% preferential tariff rate."
                    ),
                    "error": None,
                },
                {
                    "response_type": "clarification",
                    "case_id": None,
                    "evaluation_id": None,
                    "audit_url": None,
                    "audit_persisted": False,
                    "assessment": None,
                    "clarification": {
                        "question": (
                            "What is the HS6 code for the product you are exporting?"
                        ),
                        "missing_facts": ["hs6_code"],
                        "missing_evidence": [],
                    },
                    "explanation": None,
                    "error": None,
                },
                {
                    "response_type": "error",
                    "case_id": None,
                    "evaluation_id": None,
                    "audit_url": None,
                    "audit_persisted": False,
                    "assessment": None,
                    "clarification": None,
                    "explanation": None,
                    "error": {
                        "code": "INPUT_REJECTED",
                        "message": "The supplied HS code is not supported in v0.1.",
                        "detail": {"hs6_code": "999999"},
                    },
                },
            ]
        },
    )
