"""Pydantic schemas for PSR rule lookup and pathway resolution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.core.enums import (
    HsLevelEnum,
    OperatorTypeEnum,
    RuleComponentTypeEnum,
    RuleStatusEnum,
    ThresholdBasisEnum,
)



class PSRComponentOut(BaseModel):
    """One normalized PSR component attached to a parent rule."""

    component_id: UUID
    psr_id: UUID | None = None
    component_type: RuleComponentTypeEnum
    operator_type: OperatorTypeEnum
    threshold_percent: Decimal | None = None
    threshold_basis: ThresholdBasisEnum | None = None
    tariff_shift_level: HsLevelEnum | None = None
    specific_process_text: str | None = None
    component_text_verbatim: str
    normalized_expression: str | None = None
    confidence_score: Decimal | None = None
    component_order: int

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class RulePathwayOut(BaseModel):
    """Executable OR-pathway for one PSR."""

    pathway_id: UUID
    psr_id: UUID | None = None
    pathway_code: str
    pathway_label: str
    pathway_type: str
    expression_json: dict[str, Any]
    threshold_percent: Decimal | None = None
    threshold_basis: ThresholdBasisEnum | None = None
    tariff_shift_level: HsLevelEnum | None = None
    required_process_text: str | None = None
    allows_cumulation: bool = True
    allows_tolerance: bool = True
    priority_rank: int
    effective_date: date | None = None
    expiry_date: date | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class PSRRuleResolvedOut(BaseModel):
    """Parent PSR row returned by rule resolution."""

    psr_id: UUID
    source_id: UUID
    provenance_ids: list[UUID] = Field(default_factory=list)
    appendix_version: str | None = None
    hs_version: str
    hs6_code: str = Field(
        validation_alias=AliasChoices("hs6_code", "hs_code"),
        serialization_alias="hs6_code",
    )
    hs_code_start: str | None = None
    hs_code_end: str | None = None
    hs_level: HsLevelEnum | None = None
    rule_scope: str | None = None
    product_description: str
    legal_rule_text_verbatim: str
    legal_rule_text_normalized: str | None = None
    rule_status: RuleStatusEnum
    effective_date: date | None = None
    page_ref: int | None = None
    table_ref: str | None = None
    row_ref: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def normalize_provenance_ids(cls, value: Any) -> Any:
        """Populate provenance_ids from source_id when callers omit it."""

        if value is None:
            return value
        if isinstance(value, dict):
            payload = dict(value)
        elif hasattr(value, "model_dump"):
            payload = value.model_dump(mode="python")
        elif hasattr(value, "_mapping"):
            payload = dict(value._mapping)
        else:
            return value

        if "provenance_ids" not in payload or payload.get("provenance_ids") is None:
            source_id = payload.get("source_id")
            payload["provenance_ids"] = [source_id] if source_id is not None else []
        return payload


class RuleResolutionResult(BaseModel):
    """Fully resolved rule bundle for one HS6 product."""

    psr_rule: PSRRuleResolvedOut
    components: list[PSRComponentOut] = Field(default_factory=list)
    pathways: list[RulePathwayOut] = Field(default_factory=list)
    applicability_type: str

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class RuleLookupResponse(PSRRuleResolvedOut):
    """Flat API response model for `/rules/{hs6}` lookups."""

    applicability_type: str
    components: list[PSRComponentOut] = Field(default_factory=list)
    pathways: list[RulePathwayOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def flatten_service_output(cls, value: Any) -> Any:
        """Accept either the nested service result or the route's flat response dict."""

        payload = cls._coerce_to_dict(value)
        if not isinstance(payload, dict):
            return payload

        if "psr_rule" in payload:
            return cls._flatten_rule_bundle(payload)

        for bundle_key in ("rule_resolution", "result", "rule_bundle"):
            nested_bundle = payload.get(bundle_key)
            if nested_bundle is None:
                continue
            flat_payload = cls._flatten_rule_bundle(cls._coerce_to_dict(nested_bundle))
            product = cls._coerce_to_dict(payload.get("product"))
            if isinstance(product, dict):
                flat_payload.setdefault("hs6_code", product.get("hs6_code"))
            return flat_payload

        if "hs6_code" not in payload and "hs_code" in payload:
            payload["hs6_code"] = payload.get("hs_code")
        return payload

    @classmethod
    def _flatten_rule_bundle(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Flatten a nested `RuleResolutionResult`-style payload for route validation."""

        psr_rule = cls._coerce_to_dict(payload.get("psr_rule"))
        flat_payload = dict(psr_rule) if isinstance(psr_rule, dict) else {}
        flat_payload["applicability_type"] = payload.get("applicability_type")
        flat_payload["components"] = payload.get("components", [])
        flat_payload["pathways"] = payload.get("pathways", [])
        flat_payload.setdefault("hs6_code", flat_payload.get("hs_code"))
        return flat_payload

    @staticmethod
    def _coerce_to_dict(value: Any) -> Any:
        """Convert Pydantic models and ORM-ish objects into plain dict-like payloads."""

        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="python")
        if hasattr(value, "_mapping"):
            return dict(value._mapping)
        return value


PSRRuleOut = PSRRuleResolvedOut
