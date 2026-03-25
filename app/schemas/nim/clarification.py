"""NIM clarification schemas: inputs and outputs for the clarification service.

The clarification service is deterministic in how it prioritises missing items.
It selects the highest-priority gap, then asks NIM to phrase a focused question.
NIM is used only for phrasing — the gap selection logic lives in the service,
not in the model.

Priority order (highest to lowest):
1. Required engine facts absent from the draft (hs6_code, exporter, importer, year)
2. Missing production facts needed to unblock all pathways
3. Missing evidence items

The clarification service must never infer eligibility or promise outcomes.
It must produce exactly one focused question at a time.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClarificationContext(BaseModel):
    """Input to the clarification service: gaps identified from the draft and engine.

    `missing_draft_facts` are fields absent from NimAssessmentDraft that are
    required to construct an EligibilityRequest.

    `missing_engine_facts` are fact_key values reported in the engine's
    `missing_facts` field after a partial run.

    `missing_evidence` are document keys reported in the engine's
    `missing_evidence` field.

    `failure_codes` are engine failure codes from `failures` that may help
    the clarification service pick the most actionable question.
    """

    missing_draft_facts: list[str] = Field(default_factory=list)
    missing_engine_facts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    failure_codes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def highest_priority_gap(self) -> str | None:
        """Return the single highest-priority gap key, or None if nothing is missing."""
        if self.missing_draft_facts:
            return self.missing_draft_facts[0]
        if self.missing_engine_facts:
            return self.missing_engine_facts[0]
        if self.missing_evidence:
            return self.missing_evidence[0]
        return None

    def has_any_gap(self) -> bool:
        """Return True when there is at least one missing fact or evidence item."""
        return bool(
            self.missing_draft_facts
            or self.missing_engine_facts
            or self.missing_evidence
        )
