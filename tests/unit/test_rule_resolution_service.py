"""Unit tests for PSR rule resolution orchestration."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import RuleNotFoundError
from app.repositories.hs_repository import HSRepository
from app.repositories.rules_repository import RulesRepository
from app.schemas.rules import RuleResolutionResult
from app.services.rule_resolution_service import RuleResolutionService


def build_hs_product() -> SimpleNamespace:
    """Build a minimal canonical HS product object for tests."""

    return SimpleNamespace(
        hs6_id="hs6-111",
        hs_version="HS2017",
        hs6_code="040630",
    )


def build_resolved_psr() -> dict[str, object]:
    """Build a resolved applicable PSR row mapping."""

    return {
        "psr_id": "psr-111",
        "hs_version": "HS2017",
        "hs_code": "040630",
        "rule_scope": "subheading",
        "product_description": "Cheese and curd",
        "legal_rule_text_verbatim": "CTH or VNM <= 40%",
        "legal_rule_text_normalized": "CTH OR VNM<=40",
        "rule_status": "agreed",
        "source_id": "source-111",
        "page_ref": 8,
        "row_ref": "12",
        "applicability_type": "direct",
        "priority_rank": 1,
    }


def build_component(
    component_id: str,
    component_order: int,
    component_type: str = "CTH",
) -> dict[str, object]:
    """Build a PSR component row mapping."""

    return {
        "component_id": component_id,
        "component_type": component_type,
        "operator_type": "standalone",
        "threshold_percent": Decimal("40.000") if component_type == "VNM" else None,
        "threshold_basis": "ex_works" if component_type == "VNM" else None,
        "tariff_shift_level": "heading" if component_type == "CTH" else None,
        "specific_process_text": None,
        "component_text_verbatim": component_type,
        "normalized_expression": None if component_type == "CTH" else "vnom_percent <= 40",
        "component_order": component_order,
        "confidence_score": Decimal("1.000"),
    }


def build_pathway(
    pathway_id: str,
    pathway_code: str,
    priority_rank: int,
    pathway_type: str = "or",
) -> dict[str, object]:
    """Build an executable pathway row mapping."""

    return {
        "pathway_id": pathway_id,
        "pathway_code": pathway_code,
        "pathway_label": pathway_code,
        "pathway_type": pathway_type,
        "expression_json": {
            "pathway_code": pathway_code,
            "expression": {"op": "all", "args": []},
        },
        "threshold_percent": None,
        "threshold_basis": None,
        "tariff_shift_level": None,
        "required_process_text": None,
        "allows_cumulation": False,
        "allows_tolerance": False,
        "priority_rank": priority_rank,
    }


@pytest.mark.asyncio
async def test_resolve_rule_bundle_single_rule_one_pathway() -> None:
    hs_repository = AsyncMock(spec=HSRepository)
    rules_repository = AsyncMock(spec=RulesRepository)
    hs_repository.get_by_code.return_value = build_hs_product()
    rules_repository.resolve_applicable_psr.return_value = build_resolved_psr()
    rules_repository.get_psr_components.return_value = [build_component("component-1", 1)]
    rules_repository.get_pathways.return_value = [build_pathway("pathway-1", "CTH", 1)]
    service = RuleResolutionService(hs_repository, rules_repository)

    result = await service.resolve_rule_bundle("HS2017", "040630", date(2026, 3, 21))

    hs_repository.get_by_code.assert_awaited_once_with("HS2017", "040630")
    rules_repository.resolve_applicable_psr.assert_awaited_once_with(
        "hs6-111",
        date(2026, 3, 21),
    )
    rules_repository.get_psr_components.assert_awaited_once_with("psr-111")
    rules_repository.get_pathways.assert_awaited_once_with("psr-111", date(2026, 3, 21))
    assert isinstance(result, RuleResolutionResult)
    assert result.psr_rule.rule_status.value == "agreed"
    assert result.psr_rule.legal_rule_text_verbatim == "CTH or VNM <= 40%"
    assert result.applicability_type == "direct"
    assert [pathway.pathway_code for pathway in result.pathways] == ["CTH"]


@pytest.mark.asyncio
async def test_resolve_rule_bundle_with_multiple_or_pathways() -> None:
    hs_repository = AsyncMock(spec=HSRepository)
    rules_repository = AsyncMock(spec=RulesRepository)
    hs_repository.get_by_code.return_value = build_hs_product()
    rules_repository.resolve_applicable_psr.return_value = build_resolved_psr()
    rules_repository.get_psr_components.return_value = [
        build_component("component-2", 2, "VNM"),
        build_component("component-1", 1, "CTH"),
    ]
    rules_repository.get_pathways.return_value = [
        build_pathway("pathway-2", "VNM<=40", 2),
        build_pathway("pathway-1", "CTH", 1),
    ]
    service = RuleResolutionService(hs_repository, rules_repository)

    result = await service.resolve_rule_bundle("HS2017", "040630", date(2026, 3, 21))

    assert [pathway.pathway_code for pathway in result.pathways] == ["CTH", "VNM<=40"]
    assert [pathway.priority_rank for pathway in result.pathways] == [1, 2]


@pytest.mark.asyncio
async def test_resolve_rule_bundle_raises_when_no_psr_found() -> None:
    hs_repository = AsyncMock(spec=HSRepository)
    rules_repository = AsyncMock(spec=RulesRepository)
    hs_repository.get_by_code.return_value = build_hs_product()
    rules_repository.resolve_applicable_psr.return_value = None
    service = RuleResolutionService(hs_repository, rules_repository)

    with pytest.raises(RuleNotFoundError) as exc_info:
        await service.resolve_rule_bundle("HS2017", "040630", date(2026, 3, 21))

    rules_repository.get_psr_components.assert_not_awaited()
    rules_repository.get_pathways.assert_not_awaited()
    assert exc_info.value.detail == {"hs_version": "HS2017", "hs6_code": "040630"}


@pytest.mark.asyncio
async def test_resolve_rule_bundle_preserves_component_order() -> None:
    hs_repository = AsyncMock(spec=HSRepository)
    rules_repository = AsyncMock(spec=RulesRepository)
    hs_repository.get_by_code.return_value = build_hs_product()
    rules_repository.resolve_applicable_psr.return_value = build_resolved_psr()
    rules_repository.get_psr_components.return_value = [
        build_component("component-1", 2, "CTH"),
        build_component("component-2", 1, "VNM"),
    ]
    rules_repository.get_pathways.return_value = [build_pathway("pathway-1", "CTH", 1)]
    service = RuleResolutionService(hs_repository, rules_repository)

    result = await service.resolve_rule_bundle("HS2017", "040630", date(2026, 3, 21))

    assert [component.component_order for component in result.components] == [1, 2]
    assert [component.component_type.value for component in result.components] == ["VNM", "CTH"]
