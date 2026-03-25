"""NIM intake schemas: the structured draft produced by parsing a natural-language query.

NimAssessmentDraft carries two distinct groups of fields:

1. Engine fields — these map directly to EligibilityRequest and are passed to
   the deterministic engine unchanged. All fields are optional because NIM
   may not extract every value from a single user message.

2. NIM-only metadata — `nim_confidence`, `nim_completeness_score`, and
   `nim_assumptions` are produced by the NIM model and used only by the
   intake and clarification services. They MUST be dropped by the mapping
   layer before EligibilityRequest is constructed. They must never reach
   the deterministic engine.

Field-name rule: use `existing_documents` exclusively. Never use
`submitted_documents` in this schema, in mapping code, or in test fixtures.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PersonaModeEnum
from app.schemas.cases import CaseFactIn


class NimConfidence(BaseModel):
    """NIM-only parsing confidence metadata. Dropped before engine call."""

    overall: float = Field(ge=0.0, le=1.0)
    hs6_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    corridor_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class NimAssessmentDraft(BaseModel):
    """Structured draft produced by the NIM intake parsing step.

    All engine-facing fields are optional because a single user message
    may not contain every required value. The clarification service uses
    the absent fields to determine what follow-up question to ask.

    NIM-only metadata fields (`nim_confidence`, `nim_completeness_score`,
    `nim_assumptions`) must be stripped by the mapping layer before the
    draft is converted to an EligibilityRequest.
    """

    # --- Engine fields (map to EligibilityRequest) ---
    hs6_code: str | None = None
    hs_version: str = "HS2017"
    exporter: str | None = Field(default=None, min_length=3, max_length=3)
    importer: str | None = Field(default=None, min_length=3, max_length=3)
    year: int | None = Field(default=None, ge=2020, le=2040)
    persona_mode: PersonaModeEnum | None = None
    production_facts: list[CaseFactIn] = Field(default_factory=list)
    existing_documents: list[str] = Field(default_factory=list)

    # --- NIM-only metadata (MUST be dropped before engine call) ---
    nim_confidence: NimConfidence | None = None
    nim_completeness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    nim_assumptions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def is_complete_for_assessment(self, min_completeness: float = 0.7) -> bool:
        """Return True when the draft has enough engine-facing facts to run.

        Checks for the four required engine fields and an optional
        completeness threshold. Called by the intake service to decide
        whether to proceed to the engine or return a clarification.
        """
        has_required = all([
            self.hs6_code is not None,
            self.exporter is not None,
            self.importer is not None,
            self.year is not None,
        ])
        if not has_required:
            return False
        if self.nim_completeness_score is not None:
            return self.nim_completeness_score >= min_completeness
        return True

    def missing_required_facts(self) -> list[str]:
        """Return the names of required engine fields that are absent."""
        missing = []
        if self.hs6_code is None:
            missing.append("hs6_code")
        if self.exporter is None:
            missing.append("exporter")
        if self.importer is None:
            missing.append("importer")
        if self.year is None:
            missing.append("year")
        if self.persona_mode is None:
            missing.append("persona_mode")
        return missing
