"""Seed 15 hand-entered Quick Slice PSR rules into the rules layer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.enums import (
    HsLevelEnum,
    OperatorTypeEnum,
    RuleComponentTypeEnum,
    RuleStatusEnum,
    ThresholdBasisEnum,
)
from app.db.base import get_async_session_factory
from app.db.models.hs import HS6Product
from app.db.models.rules import EligibilityRulePathway, PSRRule, PSRRuleComponent

HS_VERSION = "HS2017"
APPENDIX_VERSION = "December 2023 Compilation"
SOURCE_ID = UUID("a0000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class ComponentSpec:
    """Atomic component definition for one PSR."""

    component_sequence: int
    component_type: RuleComponentTypeEnum
    operator_type: OperatorTypeEnum
    component_order: int
    component_text_verbatim: str
    normalized_expression: str
    threshold_percent: Decimal | None = None
    threshold_basis: ThresholdBasisEnum | None = None
    tariff_shift_level: HsLevelEnum | None = None


@dataclass(frozen=True)
class PathwaySpec:
    """Executable pathway definition for one PSR."""

    pathway_sequence: int
    pathway_code: str
    pathway_label: str
    priority_rank: int
    expression_json: dict[str, object]
    threshold_percent: Decimal | None = None
    threshold_basis: ThresholdBasisEnum | None = None
    tariff_shift_level: HsLevelEnum | None = None
    allows_cumulation: bool = True
    allows_tolerance: bool = True


@dataclass(frozen=True)
class RuleSpec:
    """Complete PSR seed definition including components and pathways."""

    rule_sequence: int
    hs_code: str
    hs_level: HsLevelEnum
    product_description: str
    legal_rule_text_verbatim: str
    rule_status: RuleStatusEnum
    components: tuple[ComponentSpec, ...]
    pathways: tuple[PathwaySpec, ...]

    @property
    def legal_rule_text_normalized(self) -> str:
        return self.legal_rule_text_verbatim

    @property
    def applicability_type(self) -> str:
        if self.hs_level == HsLevelEnum.CHAPTER:
            return "inherited_chapter"
        return "inherited_heading"

    @property
    def applicability_priority_rank(self) -> int:
        if self.hs_level == HsLevelEnum.CHAPTER:
            return 3
        return 2


def prefixed_uuid(prefix: str, sequence: int) -> UUID:
    """Return a deterministic UUID with the requested leading nibble."""

    return UUID(f"{prefix}0000000-0000-0000-0000-{sequence:012d}")


def wo_component(component_sequence: int) -> ComponentSpec:
    return ComponentSpec(
        component_sequence=component_sequence,
        component_type=RuleComponentTypeEnum.WO,
        operator_type=OperatorTypeEnum.STANDALONE,
        component_order=1,
        component_text_verbatim="WO",
        normalized_expression="wholly_obtained == true",
    )


def cth_component(
    component_sequence: int,
    *,
    component_order: int = 1,
    operator_type: OperatorTypeEnum = OperatorTypeEnum.STANDALONE,
) -> ComponentSpec:
    return ComponentSpec(
        component_sequence=component_sequence,
        component_type=RuleComponentTypeEnum.CTH,
        operator_type=operator_type,
        component_order=component_order,
        component_text_verbatim="CTH",
        normalized_expression="tariff_heading_input != tariff_heading_output",
        tariff_shift_level=HsLevelEnum.HEADING,
    )


def vnm_component(
    component_sequence: int,
    threshold: str,
    *,
    component_order: int = 1,
    operator_type: OperatorTypeEnum = OperatorTypeEnum.STANDALONE,
) -> ComponentSpec:
    return ComponentSpec(
        component_sequence=component_sequence,
        component_type=RuleComponentTypeEnum.VNM,
        operator_type=operator_type,
        component_order=component_order,
        component_text_verbatim=f"MaxNOM {threshold}% (EXW)",
        normalized_expression=f"vnom_percent <= {threshold}",
        threshold_percent=Decimal(threshold),
        threshold_basis=ThresholdBasisEnum.EX_WORKS,
    )


def wo_pathway(pathway_sequence: int) -> PathwaySpec:
    return PathwaySpec(
        pathway_sequence=pathway_sequence,
        pathway_code="WO",
        pathway_label="Wholly Obtained",
        priority_rank=1,
        expression_json={"op": "fact_eq", "fact": "wholly_obtained", "value": True},
        allows_cumulation=False,
        allows_tolerance=False,
    )


def cth_pathway(pathway_sequence: int, *, priority_rank: int = 1) -> PathwaySpec:
    return PathwaySpec(
        pathway_sequence=pathway_sequence,
        pathway_code="CTH",
        pathway_label="Change of Tariff Heading",
        priority_rank=priority_rank,
        expression_json={
            "op": "every_non_originating_input",
            "test": {"op": "heading_ne_output"},
        },
        tariff_shift_level=HsLevelEnum.HEADING,
        allows_cumulation=True,
        allows_tolerance=True,
    )


def vnm_pathway(
    pathway_sequence: int,
    threshold: str,
    *,
    priority_rank: int = 1,
) -> PathwaySpec:
    return PathwaySpec(
        pathway_sequence=pathway_sequence,
        pathway_code="VNM",
        pathway_label=f"Maximum Non-Originating Materials {threshold}% (EXW)",
        priority_rank=priority_rank,
        expression_json={
            "op": "formula_lte",
            "formula": "vnom_percent",
            "value": int(Decimal(threshold)),
        },
        threshold_percent=Decimal(threshold),
        threshold_basis=ThresholdBasisEnum.EX_WORKS,
        allows_cumulation=True,
        allows_tolerance=True,
    )


RULE_SPECS: tuple[RuleSpec, ...] = (
    RuleSpec(
        rule_sequence=1,
        hs_code="01",
        hs_level=HsLevelEnum.CHAPTER,
        product_description="Live animals",
        legal_rule_text_verbatim="WO",
        rule_status=RuleStatusEnum.AGREED,
        components=(wo_component(1),),
        pathways=(wo_pathway(1),),
    ),
    RuleSpec(
        rule_sequence=2,
        hs_code="02",
        hs_level=HsLevelEnum.CHAPTER,
        product_description="Meat and edible offal",
        legal_rule_text_verbatim="WO",
        rule_status=RuleStatusEnum.AGREED,
        components=(wo_component(2),),
        pathways=(wo_pathway(2),),
    ),
    RuleSpec(
        rule_sequence=3,
        hs_code="03",
        hs_level=HsLevelEnum.CHAPTER,
        product_description="Fish and crustaceans",
        legal_rule_text_verbatim="WO",
        rule_status=RuleStatusEnum.AGREED,
        components=(wo_component(3),),
        pathways=(wo_pathway(3),),
    ),
    RuleSpec(
        rule_sequence=4,
        hs_code="04",
        hs_level=HsLevelEnum.CHAPTER,
        product_description="Dairy produce, eggs, honey",
        legal_rule_text_verbatim="WO",
        rule_status=RuleStatusEnum.AGREED,
        components=(wo_component(4),),
        pathways=(wo_pathway(4),),
    ),
    RuleSpec(
        rule_sequence=5,
        hs_code="0901",
        hs_level=HsLevelEnum.HEADING,
        product_description="Coffee",
        legal_rule_text_verbatim="CTH",
        rule_status=RuleStatusEnum.AGREED,
        components=(cth_component(5),),
        pathways=(cth_pathway(5),),
    ),
    RuleSpec(
        rule_sequence=6,
        hs_code="1103",
        hs_level=HsLevelEnum.HEADING,
        product_description="Cereal groats, meal, pellets",
        legal_rule_text_verbatim="CTH",
        rule_status=RuleStatusEnum.AGREED,
        components=(cth_component(6),),
        pathways=(cth_pathway(6),),
    ),
    RuleSpec(
        rule_sequence=7,
        hs_code="1006",
        hs_level=HsLevelEnum.HEADING,
        product_description="Rice",
        legal_rule_text_verbatim="CTH",
        rule_status=RuleStatusEnum.AGREED,
        components=(cth_component(7),),
        pathways=(cth_pathway(7),),
    ),
    RuleSpec(
        rule_sequence=8,
        hs_code="1701",
        hs_level=HsLevelEnum.HEADING,
        product_description="Cane or beet sugar",
        legal_rule_text_verbatim="CTH",
        rule_status=RuleStatusEnum.AGREED,
        components=(cth_component(8),),
        pathways=(cth_pathway(8),),
    ),
    RuleSpec(
        rule_sequence=9,
        hs_code="1801",
        hs_level=HsLevelEnum.HEADING,
        product_description="Cocoa beans",
        legal_rule_text_verbatim="WO",
        rule_status=RuleStatusEnum.AGREED,
        components=(wo_component(9),),
        pathways=(wo_pathway(9),),
    ),
    RuleSpec(
        rule_sequence=10,
        hs_code="2523",
        hs_level=HsLevelEnum.HEADING,
        product_description="Portland cement",
        legal_rule_text_verbatim="CTH",
        rule_status=RuleStatusEnum.AGREED,
        components=(cth_component(10),),
        pathways=(cth_pathway(10),),
    ),
    RuleSpec(
        rule_sequence=11,
        hs_code="4407",
        hs_level=HsLevelEnum.HEADING,
        product_description="Wood sawn or chipped",
        legal_rule_text_verbatim="CTH",
        rule_status=RuleStatusEnum.AGREED,
        components=(cth_component(11),),
        pathways=(cth_pathway(11),),
    ),
    RuleSpec(
        rule_sequence=12,
        hs_code="1806",
        hs_level=HsLevelEnum.HEADING,
        product_description="Chocolate and food preps",
        legal_rule_text_verbatim="CTH; or MaxNOM 55% (EXW)",
        rule_status=RuleStatusEnum.AGREED,
        components=(
            cth_component(12),
            vnm_component(13, "55", component_order=2, operator_type=OperatorTypeEnum.OR),
        ),
        pathways=(cth_pathway(12, priority_rank=1), vnm_pathway(13, "55", priority_rank=2)),
    ),
    RuleSpec(
        rule_sequence=13,
        hs_code="3923",
        hs_level=HsLevelEnum.HEADING,
        product_description="Plastic articles for packaging",
        legal_rule_text_verbatim="CTH; or MaxNOM 50% (EXW)",
        rule_status=RuleStatusEnum.AGREED,
        components=(
            cth_component(14),
            vnm_component(15, "50", component_order=2, operator_type=OperatorTypeEnum.OR),
        ),
        pathways=(cth_pathway(14, priority_rank=1), vnm_pathway(15, "50", priority_rank=2)),
    ),
    RuleSpec(
        rule_sequence=14,
        hs_code="7210",
        hs_level=HsLevelEnum.HEADING,
        product_description="Flat-rolled iron/steel, coated",
        legal_rule_text_verbatim="MaxNOM 55% (EXW)",
        rule_status=RuleStatusEnum.AGREED,
        components=(vnm_component(16, "55"),),
        pathways=(vnm_pathway(16, "55"),),
    ),
    RuleSpec(
        rule_sequence=15,
        hs_code="8703",
        hs_level=HsLevelEnum.HEADING,
        product_description="Motor vehicles",
        legal_rule_text_verbatim="MaxNOM 55% (EXW)",
        rule_status=RuleStatusEnum.PENDING,
        components=(vnm_component(17, "55"),),
        pathways=(vnm_pathway(17, "55"),),
    ),
)


async def ensure_prerequisites(session) -> None:
    """Validate required upstream seed data exists before inserts run."""

    source_exists = await session.scalar(
        text("SELECT 1 FROM source_registry WHERE source_id = :source_id LIMIT 1"),
        {"source_id": SOURCE_ID},
    )
    if source_exists is None:
        raise RuntimeError(
            "Appendix IV source row not found. Seed source_registry before running this script."
        )

    hs6_total = await session.scalar(
        select(func.count()).select_from(HS6Product).where(HS6Product.hs_version == HS_VERSION)
    )
    if not hs6_total:
        raise RuntimeError("hs6_product is empty for HS2017. Load the HS6 backbone first.")

    for rule in RULE_SPECS:
        scope_column = HS6Product.chapter if rule.hs_level == HsLevelEnum.CHAPTER else HS6Product.heading
        match_count = await session.scalar(
            select(func.count())
            .select_from(HS6Product)
            .where(HS6Product.hs_version == HS_VERSION, scope_column == rule.hs_code)
        )
        if not match_count:
            raise RuntimeError(
                f"No HS6 products found for {rule.hs_level.value} {rule.hs_code}; "
                "cannot seed applicability rows."
            )


def build_rule_row(rule: RuleSpec) -> dict[str, object]:
    return {
        "psr_id": prefixed_uuid("b", rule.rule_sequence),
        "source_id": SOURCE_ID,
        "appendix_version": APPENDIX_VERSION,
        "hs_version": HS_VERSION,
        "hs_code": rule.hs_code,
        "hs_code_start": None,
        "hs_code_end": None,
        "hs_level": rule.hs_level,
        "product_description": rule.product_description,
        "legal_rule_text_verbatim": rule.legal_rule_text_verbatim,
        "legal_rule_text_normalized": rule.legal_rule_text_normalized,
        "rule_status": rule.rule_status,
        "effective_date": None,
        "page_ref": None,
        "table_ref": None,
        "row_ref": None,
    }


def build_component_rows(rule: RuleSpec) -> list[dict[str, object]]:
    rule_id = prefixed_uuid("b", rule.rule_sequence)
    rows: list[dict[str, object]] = []
    for component in rule.components:
        rows.append(
            {
                "component_id": prefixed_uuid("c", component.component_sequence),
                "psr_id": rule_id,
                "component_type": component.component_type,
                "operator_type": component.operator_type,
                "threshold_percent": component.threshold_percent,
                "threshold_basis": component.threshold_basis,
                "tariff_shift_level": component.tariff_shift_level,
                "specific_process_text": None,
                "component_text_verbatim": component.component_text_verbatim,
                "normalized_expression": component.normalized_expression,
                "confidence_score": Decimal("1.000"),
                "component_order": component.component_order,
            }
        )
    return rows


def build_pathway_rows(rule: RuleSpec) -> list[dict[str, object]]:
    rule_id = prefixed_uuid("b", rule.rule_sequence)
    rows: list[dict[str, object]] = []
    for pathway in rule.pathways:
        rows.append(
            {
                "pathway_id": prefixed_uuid("d", pathway.pathway_sequence),
                "psr_id": rule_id,
                "pathway_code": pathway.pathway_code,
                "pathway_label": pathway.pathway_label,
                "pathway_type": "specific",
                "expression_json": pathway.expression_json,
                "threshold_percent": pathway.threshold_percent,
                "threshold_basis": pathway.threshold_basis,
                "tariff_shift_level": pathway.tariff_shift_level,
                "required_process_text": None,
                "allows_cumulation": pathway.allows_cumulation,
                "allows_tolerance": pathway.allows_tolerance,
                "priority_rank": pathway.priority_rank,
                "effective_date": None,
                "expiry_date": None,
            }
        )
    return rows


async def insert_rule(session, rule: RuleSpec) -> int:
    statement = insert(PSRRule).values(build_rule_row(rule)).on_conflict_do_nothing().returning(PSRRule.psr_id)
    result = await session.execute(statement)
    return len(result.scalars().all())


async def insert_components(session, rule: RuleSpec) -> int:
    statement = (
        insert(PSRRuleComponent)
        .values(build_component_rows(rule))
        .on_conflict_do_nothing()
        .returning(PSRRuleComponent.component_id)
    )
    result = await session.execute(statement)
    return len(result.scalars().all())


async def insert_pathways(session, rule: RuleSpec) -> int:
    statement = (
        insert(EligibilityRulePathway)
        .values(build_pathway_rows(rule))
        .on_conflict_do_nothing()
        .returning(EligibilityRulePathway.pathway_id)
    )
    result = await session.execute(statement)
    return len(result.scalars().all())


async def insert_applicability(session, rule: RuleSpec) -> int:
    scope_field = "chapter" if rule.hs_level == HsLevelEnum.CHAPTER else "heading"
    # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
    # `scope_field` is constrained to {"chapter","heading"} and remaining values are bound params.
    statement = text(  # nosemgrep
        f"""
        INSERT INTO hs6_psr_applicability (
          applicability_id,
          hs6_id,
          psr_id,
          applicability_type,
          priority_rank
        )
        SELECT
          uuid_generate_v4(),
          hp.hs6_id,
          :psr_id,
          :applicability_type,
          :priority_rank
        FROM hs6_product hp
        WHERE hp.hs_version = :hs_version
          AND hp.{scope_field} = :scope_code
        ON CONFLICT DO NOTHING
        RETURNING applicability_id
        """
    )
    result = await session.execute(
        statement,
        {
            "psr_id": prefixed_uuid("b", rule.rule_sequence),
            "applicability_type": rule.applicability_type,
            "priority_rank": rule.applicability_priority_rank,
            "hs_version": HS_VERSION,
            "scope_code": rule.hs_code,
        },
    )
    return len(result.scalars().all())


async def main() -> int:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        async with session.begin():
            await ensure_prerequisites(session)

            inserted_rules = 0
            inserted_components = 0
            inserted_pathways = 0
            inserted_applicability = 0

            for rule in RULE_SPECS:
                inserted_rules += await insert_rule(session, rule)
                inserted_components += await insert_components(session, rule)
                inserted_pathways += await insert_pathways(session, rule)
                inserted_applicability += await insert_applicability(session, rule)

    print("PSR seed summary")
    print(f"- Rules inserted: {inserted_rules}")
    print(f"- Components inserted: {inserted_components}")
    print(f"- Pathways inserted: {inserted_pathways}")
    print(f"- Applicability rows inserted: {inserted_applicability}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
