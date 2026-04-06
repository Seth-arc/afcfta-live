"""Thin route handlers for canonical HS6 rule lookup."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_classification_service, get_rule_resolution_service
from app.schemas.rules import RuleLookupResponse
from app.services.classification_service import ClassificationService
from app.services.rule_resolution_service import RuleResolutionService

router = APIRouter()


@router.get("/rules/{hs6}", response_model=RuleLookupResponse)
async def get_rules_for_hs6(
    hs6: str,
    hs_version: str = Query("HS2017"),
    as_of_date: date | None = Query(
        default=None,
        description="Snapshot date (YYYY-MM-DD). Defaults to today.",
    ),
    classification_service: ClassificationService = Depends(get_classification_service),
    rule_resolution_service: RuleResolutionService = Depends(get_rule_resolution_service),
) -> RuleLookupResponse:
    """Resolve the canonical HS6 product and return its governing PSR bundle."""

    product = await classification_service.resolve_hs6(hs6, hs_version)
    rule_bundle = await rule_resolution_service.resolve_rule_bundle(
        hs_version,
        product.hs6_code,
        assessment_date=as_of_date,
    )
    return RuleLookupResponse(
        hs6_id=product.hs6_id,
        hs_version=product.hs_version,
        hs6_code=product.hs6_code,
        product_description=rule_bundle.psr_rule.product_description,
        psr_id=rule_bundle.psr_rule.psr_id,
        rule_scope=rule_bundle.psr_rule.rule_scope,
        rule_status=rule_bundle.psr_rule.rule_status,
        legal_rule_text_verbatim=rule_bundle.psr_rule.legal_rule_text_verbatim,
        legal_rule_text_normalized=rule_bundle.psr_rule.legal_rule_text_normalized,
        applicability_type=rule_bundle.applicability_type,
        components=rule_bundle.components,
        pathways=rule_bundle.pathways,
        source_id=rule_bundle.psr_rule.source_id,
        page_ref=rule_bundle.psr_rule.page_ref,
        table_ref=rule_bundle.psr_rule.table_ref,
        row_ref=rule_bundle.psr_rule.row_ref,
    )
