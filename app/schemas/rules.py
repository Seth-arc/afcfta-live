"""Pydantic schemas for PSR rule lookup responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    HsLevelEnum,
    OperatorTypeEnum,
    RuleComponentTypeEnum,
    RuleStatusEnum,
    ThresholdBasisEnum,
)


class PSRComponentOut(BaseModel):
    """Serialized PSR component used by the expression evaluator."""

    component_id: str
    component_type: RuleComponentTypeEnum
    operator_type: OperatorTypeEnum
    threshold_percent: Decimal | None = None
    threshold_basis: ThresholdBasisEnum | None = None
    tariff_shift_level: HsLevelEnum | None = None
    specific_process_text: str | None = None
    component_text_verbatim: str
    normalized_expression: str | None = None
    component_order: int
    confidence_score: Decimal

    model_config = ConfigDict(from_attributes=True)


class RulePathwayOut(BaseModel):
    """Serialized executable rule pathway."""

    pathway_id: str
    pathway_code: str
    pathway_label: str
    pathway_type: str
    expression_json: dict[str, Any]
    threshold_percent: Decimal | None = None
    threshold_basis: ThresholdBasisEnum | None = None
    tariff_shift_level: HsLevelEnum | None = None
    required_process_text: str | None = None
    allows_cumulation: bool
    allows_tolerance: bool
    priority_rank: int

    model_config = ConfigDict(from_attributes=True)


class PSRRuleResolvedOut(BaseModel):
    """Serialized resolved PSR rule metadata used by rule-resolution service."""

    psr_id: str
    hs_version: str
    hs_code: str = Field(pattern=r"^\d{2,6}$")
    rule_scope: HsLevelEnum | None = None
    product_description: str
    legal_rule_text_verbatim: str
    legal_rule_text_normalized: str | None = None
    rule_status: RuleStatusEnum
    source_id: str | None = None
    page_ref: int | None = None
    row_ref: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RuleResolutionResult(BaseModel):
    """Resolved PSR bundle including the governing rule, components, and OR pathways."""

    psr_rule: PSRRuleResolvedOut
    components: list[PSRComponentOut]
    pathways: list[RulePathwayOut]
    applicability_type: str

    model_config = ConfigDict(from_attributes=True)


class RuleLookupResponse(BaseModel):
    """Serialized rule bundle for an HS6 lookup."""

    hs6_id: str
    hs_version: str
    hs6_code: str = Field(pattern=r"^\d{6}$")
    product_description: str
    psr_id: str
    rule_scope: HsLevelEnum | None = None
    rule_status: RuleStatusEnum
    legal_rule_text_verbatim: str
    legal_rule_text_normalized: str | None = None
    applicability_type: str
    components: list[PSRComponentOut]
    pathways: list[RulePathwayOut]
    source_id: str | None = None
    page_ref: int | None = None
    row_ref: str | None = None

    model_config = ConfigDict(from_attributes=True)
