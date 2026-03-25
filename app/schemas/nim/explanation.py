"""NIM explanation schemas: inputs and outputs for the explanation service.

The explanation service wraps a deterministic assessment result in plain
language. Its output is additive only — it must never contradict the engine.

Contradiction guard (enforced in explanation_service.py):
The service must reject any explanation payload that contradicts these
engine output fields:
  - eligible
  - pathway_used
  - rule_status
  - tariff_outcome
  - confidence_class

If the explanation service fails or produces an invalid payload, the fallback
is None — the assessment result is returned without explanation text. The
deterministic result is never blocked by explanation failure.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.assessments import EligibilityAssessmentResponse


class ExplanationContext(BaseModel):
    """Input to the explanation service: the completed deterministic assessment.

    The service uses these fields to:
    1. Build the system prompt (what the engine decided and why).
    2. Validate the NIM model's explanation output against the decision fields.
    3. Produce next-step guidance grounded in real engine outputs.

    The explanation service must not alter or re-derive any field in `assessment`.
    """

    assessment: EligibilityAssessmentResponse
    persona_mode: str | None = None

    model_config = ConfigDict(extra="forbid")


class ExplanationResult(BaseModel):
    """Output of the explanation service.

    `text` is the plain-language explanation. It is None when:
    - The explanation service is not yet wired (stub).
    - The NIM model call failed or timed out.
    - The model output failed the contradiction guard.

    `fallback_used` is True when the service returned the minimal deterministic
    summary rather than a model-generated explanation.
    """

    text: str | None = None
    fallback_used: bool = False

    model_config = ConfigDict(extra="forbid")
