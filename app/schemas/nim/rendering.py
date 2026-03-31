"""NIM rendering schemas: structured output from the NIM rendering service.

The rendering service submits a deterministic truth payload to NIM and
validates the structured response against this schema. If validation fails
or contradiction guardrails trigger, the service discards the NIM output
and falls back to the deterministic DecisionRenderer.

Fields mirror RenderedDecision from decision_renderer.py so that the
fallback path returns the same shape without conversion.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NimRendering(BaseModel):
    """Strict Pydantic model for validated NIM rendering output.

    Every field must match the contract defined in the reference document
    (Part II). The service layer applies contradiction guardrails on top
    of this structural validation before accepting the output.
    """

    headline: str
    summary: str
    gap_analysis: str | None = None
    fix_strategy: str | None = None
    next_steps: list[str] = Field(min_length=2, max_length=4)
    warnings: list[str] = Field(default_factory=list, max_length=3)

    model_config = ConfigDict(extra="forbid")
