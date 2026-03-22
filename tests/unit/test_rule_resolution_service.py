"""Unit tests for the PSR rule resolution service."""

from __future__ import annotations

from datetime import date
from uuid import UUID
from unittest.mock import AsyncMock

import pytest

from app.core.enums import HsLevelEnum, OperatorTypeEnum, RuleComponentTypeEnum, RuleStatusEnum
from app.core.exceptions import RuleNotFoundError
from app.services.rule_resolution_service import RuleResolutionService


class AttrDict(dict):
    """Mapping with attribute access for repository fixture rows."""

    __getattr__ = dict.__getitem__


def _uuid(value: int) -> UUID:
    """Build a stable UUID for test fixtures."""

    return UUID(f"00000000-0000-0000-0000-{value:012d}")


def _product(hs6_code: str = "110311") -> AttrDict:
    """Return a canonical HS6 backbone row."""

    return AttrDict(
        {
            "hs6_id": _uuid(1),
            "hs_version": "HS2017",
            "hs6_code": hs6_code,
            "hs6_display": f"{hs6_code} product",
            "chapter": hs6_code[:2],
            "heading": hs6_code[:4],
            "description": "Seed product",
            "section": "II",
            "section_name": "Vegetable Products",
        }
    )


def _applicable_rule(
    *,
    psr_id: UUID | None = None,
    hs6_code: str = "110311",
    rule_status: RuleStatusEnum = RuleStatusEnum.AGREED,
    applicability_type: str = "direct",
) -> AttrDict:
    """Return one resolved applicability row from hs6_psr_applicability."""

    return AttrDict(
        {
            "psr_id": psr_id or _uuid(10),
            "source_id": _uuid(20),
            "appendix_version": "seed-v0.1",
            "hs_version": "HS2017",
            "hs_code": hs6_code,
            "hs_code_start": None,
            "hs_code_end": None,
            "hs_level": HsLevelEnum.SUBHEADING,
            "rule_scope": "subheading",
            "product_description": "Seed product",
            "legal_rule_text_verbatim": "Seed rule text.",
            "legal_rule_text_normalized": "CTH",
            "rule_status": rule_status,
            "effective_date": date(2024, 1, 1),
            "page_ref": 1,
            "table_ref": "seed_psr",
            "row_ref": hs6_code,
            "applicability_type": applicability_type,
            "priority_rank": 1,
        }
    )


def _component(
    *,
    component_id: int,
    component_order: int,
    psr_id: UUID | None = None,
    expression: str = "tariff_heading_input != tariff_heading_output",
) -> AttrDict:
    """Return one PSR component row."""

    return AttrDict(
        {
            "component_id": _uuid(component_id),
            "psr_id": psr_id or _uuid(10),
            "component_type": RuleComponentTypeEnum.CTH,
            "operator_type": OperatorTypeEnum.STANDALONE,
            "threshold_percent": None,
            "threshold_basis": None,
            "tariff_shift_level": HsLevelEnum.HEADING,
            "specific_process_text": None,
            "component_text_verbatim": "Change in tariff heading.",
            "normalized_expression": expression,
            "confidence_score": 1,
            "component_order": component_order,
        }
    )


def _pathway(
    *,
    pathway_id: int,
    priority_rank: int,
    psr_id: UUID | None = None,
    pathway_code: str = "CTH",
    expression_json: dict | None = None,
) -> AttrDict:
    """Return one pathway row."""

    return AttrDict(
        {
            "pathway_id": _uuid(pathway_id),
            "psr_id": psr_id or _uuid(10),
            "pathway_code": pathway_code,
            "pathway_label": pathway_code,
            "pathway_type": "specific",
            "expression_json": expression_json
            or {
                "op": "fact_ne",
                "fact": "tariff_heading_input",
                "ref_fact": "tariff_heading_output",
            },
            "threshold_percent": None,
            "threshold_basis": None,
            "tariff_shift_level": HsLevelEnum.HEADING,
            "required_process_text": None,
            "allows_cumulation": True,
            "allows_tolerance": False,
            "priority_rank": priority_rank,
            "effective_date": date(2024, 1, 1),
            "expiry_date": None,
        }
    )


@pytest.mark.asyncio
async def test_single_rule_with_one_pathway() -> None:
    """Return the resolved PSR plus its one component and one pathway."""

    hs_repository = AsyncMock()
    rules_repository = AsyncMock()
    service = RuleResolutionService(hs_repository, rules_repository)

    hs_repository.get_by_code.return_value = _product("110311")
    rules_repository.resolve_applicable_psr.return_value = _applicable_rule(hs6_code="110311")
    rules_repository.get_psr_components.return_value = [_component(component_id=101, component_order=1)]
    rules_repository.get_pathways.return_value = [_pathway(pathway_id=201, priority_rank=1)]

    result = await service.resolve_rule_bundle("HS2017", "110311", date(2025, 1, 1))

    assert result.psr_rule.hs6_code == "110311"
    assert result.psr_rule.rule_status == RuleStatusEnum.AGREED
    assert result.applicability_type == "direct"
    assert len(result.components) == 1
    assert len(result.pathways) == 1
    assert result.pathways[0].pathway_code == "CTH"


@pytest.mark.asyncio
async def test_rule_with_multiple_or_pathways() -> None:
    """Preserve alternative OR pathways in priority order."""

    psr_id = _uuid(11)
    hs_repository = AsyncMock()
    rules_repository = AsyncMock()
    service = RuleResolutionService(hs_repository, rules_repository)

    hs_repository.get_by_code.return_value = _product("610910")
    rules_repository.resolve_applicable_psr.return_value = _applicable_rule(
        psr_id=psr_id,
        hs6_code="610910",
        rule_status=RuleStatusEnum.PROVISIONAL,
    )
    rules_repository.get_psr_components.return_value = [
        _component(component_id=102, component_order=1, psr_id=psr_id),
        _component(
            component_id=103,
            component_order=2,
            psr_id=psr_id,
            expression="vnom_percent <= 50",
        ),
    ]
    rules_repository.get_pathways.return_value = [
        _pathway(pathway_id=202, priority_rank=1, psr_id=psr_id, pathway_code="CTH"),
        _pathway(
            pathway_id=203,
            priority_rank=2,
            psr_id=psr_id,
            pathway_code="VNM",
            expression_json={"op": "formula_lte", "formula": "vnom_percent", "value": 50},
        ),
    ]

    result = await service.resolve_rule_bundle("HS2017", "610910", date(2025, 1, 1))

    assert [pathway.pathway_code for pathway in result.pathways] == ["CTH", "VNM"]
    assert [pathway.priority_rank for pathway in result.pathways] == [1, 2]


@pytest.mark.asyncio
async def test_no_psr_found_raises_rule_not_found_error() -> None:
    """Raise the domain exception when no applicable PSR exists."""

    hs_repository = AsyncMock()
    rules_repository = AsyncMock()
    service = RuleResolutionService(hs_repository, rules_repository)

    hs_repository.get_by_code.return_value = _product("271019")
    rules_repository.resolve_applicable_psr.return_value = None

    with pytest.raises(RuleNotFoundError):
        await service.resolve_rule_bundle("HS2017", "271019", date(2025, 1, 1))


@pytest.mark.asyncio
async def test_components_returned_in_component_order() -> None:
    """The resolved component bundle should preserve component ordering."""

    hs_repository = AsyncMock()
    rules_repository = AsyncMock()
    service = RuleResolutionService(hs_repository, rules_repository)

    hs_repository.get_by_code.return_value = _product("870421")
    rules_repository.resolve_applicable_psr.return_value = _applicable_rule(hs6_code="870421")
    rules_repository.get_psr_components.return_value = [
        _component(component_id=104, component_order=1),
        _component(component_id=105, component_order=2, expression="vnom_percent <= 60"),
    ]
    rules_repository.get_pathways.return_value = [_pathway(pathway_id=204, priority_rank=1)]

    result = await service.resolve_rule_bundle("HS2017", "870421", date(2025, 1, 1))

    assert [component.component_order for component in result.components] == [1, 2]
