"""SQLAlchemy ORM models for PSR rules, rule components, pathways, and applicability."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    HsLevelEnum,
    OperatorTypeEnum,
    RuleComponentTypeEnum,
    RuleStatusEnum,
    ThresholdBasisEnum,
)
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class PSRRule(Base):
    """Parent PSR record sourced from Appendix IV or equivalent legal authority."""

    __tablename__ = "psr_rule"
    __table_args__ = (
        Index(
            "uq_psr_rule_source_hs_code_row_ref",
            "source_id",
            "hs_version",
            "hs_code",
            text("COALESCE(row_ref, '')"),
            unique=True,
        ),
        Index("idx_psr_rule_hs_code", "hs_code"),
        Index("idx_psr_rule_hs_version", "hs_version"),
        Index("idx_psr_rule_status", "rule_status"),
        Index("idx_psr_rule_hs_level", "hs_level"),
    )

    psr_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    appendix_version: Mapped[str | None] = mapped_column(Text)
    hs_version: Mapped[str] = mapped_column(Text, nullable=False)
    hs_code: Mapped[str] = mapped_column(Text, nullable=False)
    hs_code_start: Mapped[str | None] = mapped_column(Text)
    hs_code_end: Mapped[str | None] = mapped_column(Text)
    hs_level: Mapped[HsLevelEnum] = mapped_column(
        _enum_type(HsLevelEnum, "hs_level_enum"),
        nullable=False,
    )
    product_description: Mapped[str] = mapped_column(Text, nullable=False)
    legal_rule_text_verbatim: Mapped[str] = mapped_column(Text, nullable=False)
    legal_rule_text_normalized: Mapped[str | None] = mapped_column(Text)
    rule_status: Mapped[RuleStatusEnum] = mapped_column(
        _enum_type(RuleStatusEnum, "rule_status_enum"),
        nullable=False,
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    page_ref: Mapped[int | None] = mapped_column(Integer)
    table_ref: Mapped[str | None] = mapped_column(Text)
    row_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PSRRuleComponent(Base):
    """Atomic rule component used by the expression evaluator."""

    __tablename__ = "psr_rule_component"
    __table_args__ = (
        CheckConstraint(
            "threshold_percent IS NULL OR (threshold_percent >= 0 AND threshold_percent <= 100)",
            name="chk_psr_component_threshold",
        ),
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="chk_psr_component_confidence",
        ),
        Index("idx_psr_rule_component_psr_id", "psr_id"),
        Index("idx_psr_rule_component_type", "component_type"),
        Index("idx_psr_rule_component_order", "psr_id", "component_order"),
    )

    component_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    psr_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule.psr_id", ondelete="CASCADE"),
        nullable=False,
    )
    component_type: Mapped[RuleComponentTypeEnum] = mapped_column(
        _enum_type(RuleComponentTypeEnum, "rule_component_type_enum"),
        nullable=False,
    )
    operator_type: Mapped[OperatorTypeEnum] = mapped_column(
        _enum_type(OperatorTypeEnum, "operator_type_enum"),
        nullable=False,
        server_default=text("'standalone'"),
    )
    threshold_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    threshold_basis: Mapped[ThresholdBasisEnum | None] = mapped_column(
        _enum_type(ThresholdBasisEnum, "threshold_basis_enum")
    )
    tariff_shift_level: Mapped[HsLevelEnum | None] = mapped_column(
        _enum_type(HsLevelEnum, "hs_level_enum")
    )
    specific_process_text: Mapped[str | None] = mapped_column(Text)
    component_text_verbatim: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_expression: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.000"),
    )
    component_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EligibilityRulePathway(Base):
    """Executable AND/OR pathway combinations for a PSR."""

    __tablename__ = "eligibility_rule_pathway"
    __table_args__ = (
        Index(
            "idx_eligibility_rule_pathway_psr",
            "psr_id",
            "priority_rank",
            "effective_date",
            "expiry_date",
        ),
    )

    pathway_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    psr_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule.psr_id", ondelete="CASCADE"),
        nullable=False,
    )
    pathway_code: Mapped[str] = mapped_column(Text, nullable=False)
    pathway_label: Mapped[str] = mapped_column(Text, nullable=False)
    pathway_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'specific'"),
    )
    expression_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    threshold_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    threshold_basis: Mapped[ThresholdBasisEnum | None] = mapped_column(
        _enum_type(ThresholdBasisEnum, "threshold_basis_enum")
    )
    tariff_shift_level: Mapped[HsLevelEnum | None] = mapped_column(
        _enum_type(HsLevelEnum, "hs_level_enum")
    )
    required_process_text: Mapped[str | None] = mapped_column(Text)
    allows_cumulation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    allows_tolerance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    priority_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HS6PSRApplicability(Base):
    """Materialized resolver that maps each HS6 product to its applicable PSR."""

    __tablename__ = "hs6_psr_applicability"
    __table_args__ = (
        Index(
            "idx_hs6_psr_applicability_lookup",
            "hs6_id",
            "priority_rank",
            "effective_date",
            "expiry_date",
        ),
        Index("uq_hs6_psr_applicability_hs6_psr", "hs6_id", "psr_id", unique=True),
    )

    applicability_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    hs6_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hs6_product.hs6_id", ondelete="CASCADE"),
        nullable=False,
    )
    psr_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule.psr_id", ondelete="CASCADE"),
        nullable=False,
    )
    applicability_type: Mapped[str] = mapped_column(Text, nullable=False)
    priority_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
