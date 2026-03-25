"""NIM intake schemas: the structured draft produced by parsing a natural-language query.

NimAssessmentDraft carries two explicitly separated groups of fields:

ENGINE FIELDS — map directly to EligibilityRequest and pass to the engine unchanged:
  - product       → hs6_code, hs_version
  - trade_flow    → exporter, importer, year
  - context       → persona_mode
  - production_facts.material_inputs → production_facts (list[CaseFactIn])
  - existing_documents               → existing_documents

NIM-ONLY METADATA — produced by the model, used only by the intake and
clarification services, MUST be dropped before EligibilityRequest is constructed:
  - nim_confidence
  - nim_assumptions
  - HS6Candidate.product_description_parsed

The mapping layer in IntakeService.to_eligibility_request() is the only place
that touches nim_confidence and nim_assumptions. Nothing else should read them.

Field-name rule: use `existing_documents` exclusively. Never use `submitted_documents`
anywhere in this module, in mapping code, or in test fixtures.
"""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import PersonaModeEnum
from app.core.fact_keys import PRODUCTION_FACTS


def _normalize_and_validate_hs6(value: str) -> str:
    """Strip punctuation and return exactly 6 digits, or raise."""
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6:
        raise ValueError(
            f"HS6 code must contain at least 6 digits after stripping punctuation; "
            f"got {len(digits)} from '{value}'"
        )
    return digits[:6]


class HS6Candidate(BaseModel):
    """NIM's parsed product identification.

    `hs6_code` is normalized to exactly 6 digits (punctuation stripped, truncated).
    `product_description_parsed` is NIM-only metadata: it records what the model
    understood about the product and is logged but dropped before the engine call.
    """

    hs6_code: str | None = None
    hs_version: str = "HS2017"
    product_description_parsed: str | None = None  # NIM-only — drop before engine call

    model_config = ConfigDict(extra="forbid")

    @field_validator("hs6_code")
    @classmethod
    def validate_hs6_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_and_validate_hs6(value)


class TradeFlow(BaseModel):
    """NIM's parsed trade corridor: exporter, importer, and assessment year.

    Country codes are validated as exactly 3 uppercase characters. The engine
    performs the definitive v0.1 country-support check; the intake schema
    validates shape only so future country additions do not require schema
    changes.
    """

    exporter: str | None = Field(default=None, min_length=3, max_length=3)
    importer: str | None = Field(default=None, min_length=3, max_length=3)
    year: int | None = Field(default=None, ge=2020, le=2040)

    model_config = ConfigDict(extra="forbid")

    @field_validator("exporter", "importer", mode="before")
    @classmethod
    def uppercase_country_code(cls, value: str | None) -> str | None:
        return value.upper() if isinstance(value, str) else value


class AssessmentContext(BaseModel):
    """NIM's parsed assessment framing: who is asking and for what purpose.

    `persona_mode` maps directly to EligibilityRequest.persona_mode. If NIM
    cannot determine the persona from the user's message, leave it as None
    and the clarification service will ask.
    """

    persona_mode: PersonaModeEnum | None = None

    model_config = ConfigDict(extra="forbid")


class MaterialInput(BaseModel):
    """One NIM-extracted production fact, ready to map to a single CaseFactIn.

    `fact_key` must be a key from app.core.fact_keys.PRODUCTION_FACTS. This
    constraint prevents NIM from inventing fact keys that the engine does not
    accept.

    Exactly one typed value field (text_value, number_value, or boolean_value)
    must be non-None. The mapping layer uses the non-None field to determine
    CaseFactIn.fact_value_type.

    `unit` is passed through to CaseFactIn.unit unchanged.
    """

    fact_key: str
    text_value: str | None = None
    number_value: Decimal | None = None
    boolean_value: bool | None = None
    unit: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("fact_key")
    @classmethod
    def validate_fact_key(cls, value: str) -> str:
        if value not in PRODUCTION_FACTS:
            raise ValueError(
                f"Unknown fact_key '{value}'. "
                f"Must be one of: {sorted(PRODUCTION_FACTS)}"
            )
        return value

    @model_validator(mode="after")
    def require_exactly_one_value(self) -> MaterialInput:
        set_values = [
            f for f in ("text_value", "number_value", "boolean_value")
            if getattr(self, f) is not None
        ]
        if len(set_values) == 0:
            raise ValueError(
                "MaterialInput must have exactly one value set "
                "(text_value, number_value, or boolean_value)"
            )
        if len(set_values) > 1:
            raise ValueError(
                f"MaterialInput must have exactly one value set; "
                f"got multiple: {set_values}"
            )
        return self


class ProductionFacts(BaseModel):
    """NIM-extracted production facts, grouped for clean mapping to the engine.

    `material_inputs` maps to EligibilityRequest.production_facts (list[CaseFactIn]).
    Each MaterialInput is independently validated against the known fact-key registry.

    `existing_documents` is kept at NimAssessmentDraft level, not here, to match
    the EligibilityRequest structure where it is a top-level field alongside
    production_facts.
    """

    material_inputs: list[MaterialInput] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class NimConfidence(BaseModel):
    """NIM-only parsing confidence scores. Dropped before the engine call.

    All scores are in [0.0, 1.0]. `overall` is the aggregate confidence.
    The intake service uses `overall` to decide whether to proceed to the
    engine or return a clarification response.
    """

    overall: float = Field(ge=0.0, le=1.0)
    hs6_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    corridor_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    facts_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class NimAssessmentDraft(BaseModel):
    """Structured draft produced by the NIM intake parsing step.

    Sub-schemas group engine-facing fields by concern so the mapping layer
    can process each group independently and cleanly drop NIM-only metadata.

    ENGINE-FIELD MAPPING (IntakeService.to_eligibility_request does this):
      draft.product.hs6_code           → EligibilityRequest.hs6_code
      draft.product.hs_version         → EligibilityRequest.hs_version
      draft.trade_flow.exporter        → EligibilityRequest.exporter
      draft.trade_flow.importer        → EligibilityRequest.importer
      draft.trade_flow.year            → EligibilityRequest.year
      draft.context.persona_mode       → EligibilityRequest.persona_mode
      draft.production_facts.material_inputs (→ CaseFactIn list)
                                       → EligibilityRequest.production_facts
      draft.existing_documents         → EligibilityRequest.existing_documents

    DROPPED BEFORE ENGINE CALL (never reaches EligibilityRequest):
      draft.nim_confidence
      draft.nim_assumptions
      draft.product.product_description_parsed
    """

    # --- Engine fields ---
    product: HS6Candidate | None = None
    trade_flow: TradeFlow | None = None
    context: AssessmentContext | None = None
    production_facts: ProductionFacts | None = None
    existing_documents: list[str] = Field(default_factory=list)

    # --- NIM-only metadata (dropped before engine call) ---
    nim_confidence: NimConfidence | None = None
    nim_assumptions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def is_complete_for_assessment(self, min_confidence: float = 0.7) -> bool:
        """Return True when the draft has enough engine-facing facts to run.

        Checks the four required engine fields (hs6_code, exporter, importer,
        year). When nim_confidence is present, also checks that overall
        confidence meets min_confidence. Called by IntakeService to decide
        whether to proceed to the engine or return a clarification.
        """
        if self.product is None or self.product.hs6_code is None:
            return False
        if self.trade_flow is None:
            return False
        if self.trade_flow.exporter is None:
            return False
        if self.trade_flow.importer is None:
            return False
        if self.trade_flow.year is None:
            return False
        if (
            self.nim_confidence is not None
            and self.nim_confidence.overall < min_confidence
        ):
            return False
        return True

    def missing_required_facts(self) -> list[str]:
        """Return the fact-key names of required engine fields that are absent.

        The clarification service uses this list to select the highest-priority
        gap and phrase a focused follow-up question.
        """
        missing: list[str] = []
        if self.product is None or self.product.hs6_code is None:
            missing.append("hs6_code")
        if self.trade_flow is None or self.trade_flow.exporter is None:
            missing.append("exporter")
        if self.trade_flow is None or self.trade_flow.importer is None:
            missing.append("importer")
        if self.trade_flow is None or self.trade_flow.year is None:
            missing.append("year")
        if self.context is None or self.context.persona_mode is None:
            missing.append("persona_mode")
        return missing
