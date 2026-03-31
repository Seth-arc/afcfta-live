"""NIM clarification schemas: inputs and outputs for the clarification service.

The clarification service is deterministic in how it prioritises missing items.
It selects the highest-priority gap, then asks NIM to phrase a focused question.
NIM is used only for phrasing — the gap selection logic lives in the service,
not in the model.

Clarification handling order:
1. NIM intake rejection reasons from non-HTTP callers or other internal paths
   that require a deterministic retry prompt before any gap-based question.
2. Required engine facts absent from the draft (hs6_code, exporter, importer,
   year, persona_mode) — must be resolved before the engine can run at all.
3. Missing production facts reported in the engine's `missing_facts` field
   after a partial run — these unblock pathway evaluation.
4. Missing evidence items reported in the engine's `missing_evidence` field.

The clarification service must never infer eligibility or promise outcomes.
It must produce exactly one focused question at a time.
A ClarificationContext with no gaps and no rejection reason is invalid and is
rejected at construction time.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClarificationContext(BaseModel):
    """Input to the clarification service: gaps identified from the draft and engine.

    `missing_draft_facts` are fields absent from NimAssessmentDraft that are
    required to construct an EligibilityRequest (hs6_code, exporter, importer,
    year, persona_mode).

    `missing_engine_facts` are fact_key values reported in the engine's
    `missing_facts` field after a partial run.

    `missing_evidence` are document keys reported in the engine's
    `missing_evidence` field.

    `failure_codes` are engine failure codes from `failures` that may help
    the clarification service pick the most actionable question.

    `nim_rejection_reason` is set when an internal intake path intentionally
    declines to send the user's text to NIM (for example because a non-HTTP
    caller bypassed the AssistantRequest schema and exceeded the AGENTS.md
    input-length boundary) and the assistant should ask the user to resend a
    shorter description.

    At least one of missing_draft_facts, missing_engine_facts,
    missing_evidence, or nim_rejection_reason must be present. A context with
    no gaps or rejection reason has nothing to clarify and is rejected at
    validation time.
    """

    missing_draft_facts: list[str] = Field(default_factory=list)
    missing_engine_facts: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    failure_codes: list[str] = Field(default_factory=list)
    nim_rejection_reason: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_at_least_one_gap(self) -> ClarificationContext:
        if not self.has_any_gap():
            raise ValueError(
                "ClarificationContext must have at least one gap or rejection reason "
                "(missing_draft_facts, missing_engine_facts, missing_evidence, or "
                "nim_rejection_reason). A context with none of these has nothing to clarify."
            )
        return self

    def highest_priority_gap(self) -> str | None:
        """Return the single highest-priority gap key, or None if nothing is missing.

        Priority: draft facts → engine facts → evidence items.
        Within each group the order matches the list order, which callers
        should maintain as highest-to-lowest priority (e.g. hs6_code before
        exporter, following NimAssessmentDraft.missing_required_facts() order).
        """
        if self.missing_draft_facts:
            return self.missing_draft_facts[0]
        if self.missing_engine_facts:
            return self.missing_engine_facts[0]
        if self.missing_evidence:
            return self.missing_evidence[0]
        return None

    def has_any_gap(self) -> bool:
        """Return True when there is something actionable to clarify."""
        return bool(
            self.missing_draft_facts
            or self.missing_engine_facts
            or self.missing_evidence
            or self.nim_rejection_reason
        )
