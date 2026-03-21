"""SQLAlchemy ORM models for case files, facts, failures, and counterfactuals."""

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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    CaseSubmissionStatusEnum,
    CounterfactualTypeEnum,
    FailureTypeEnum,
    FactSourceTypeEnum,
    FactValueTypeEnum,
    PersonaModeEnum,
    ProjectedOutcomeEnum,
    SeverityEnum,
)
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class CaseFile(Base):
    """Case header for a corridor/product assessment using HS code text."""

    __tablename__ = "case_file"
    __table_args__ = (
        CheckConstraint(
            "(submitted_at IS NULL OR submitted_at >= opened_at) "
            "AND (closed_at IS NULL OR closed_at >= opened_at)",
            name="chk_case_file_dates",
        ),
        Index("idx_case_file_persona_mode", "persona_mode"),
        Index("idx_case_file_submission_status", "submission_status"),
        Index("idx_case_file_exporter_state", "exporter_state"),
        Index("idx_case_file_importer_state", "importer_state"),
        Index("idx_case_file_hs_code", "hs_code"),
        Index("idx_case_file_declared_pathway", "declared_pathway"),
    )

    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    case_external_ref: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    persona_mode: Mapped[PersonaModeEnum] = mapped_column(
        _enum_type(PersonaModeEnum, "persona_mode_enum"),
        nullable=False,
    )
    exporter_state: Mapped[str | None] = mapped_column(Text)
    importer_state: Mapped[str | None] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(Text)
    hs_version: Mapped[str | None] = mapped_column(Text)
    declared_origin: Mapped[str | None] = mapped_column(Text)
    declared_pathway: Mapped[str | None] = mapped_column(Text)
    submission_status: Mapped[CaseSubmissionStatusEnum] = mapped_column(
        _enum_type(CaseSubmissionStatusEnum, "case_submission_status_enum"),
        nullable=False,
        server_default=text("'draft'"),
    )
    title: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(Text)
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


class CaseInputFact(Base):
    """Typed case fact captured for deterministic rule evaluation."""

    __tablename__ = "case_input_fact"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="chk_case_input_fact_confidence",
        ),
        CheckConstraint(
            "("
            "  CASE WHEN fact_value_text IS NOT NULL THEN 1 ELSE 0 END +"
            "  CASE WHEN fact_value_number IS NOT NULL THEN 1 ELSE 0 END +"
            "  CASE WHEN fact_value_boolean IS NOT NULL THEN 1 ELSE 0 END +"
            "  CASE WHEN fact_value_date IS NOT NULL THEN 1 ELSE 0 END +"
            "  CASE WHEN fact_value_json IS NOT NULL THEN 1 ELSE 0 END"
            ") >= 1",
            name="chk_case_input_fact_one_value",
        ),
        UniqueConstraint("case_id", "fact_key", "fact_order", name="uq_case_fact"),
        Index("idx_case_input_fact_case_id", "case_id"),
        Index("idx_case_input_fact_fact_type", "fact_type"),
        Index("idx_case_input_fact_fact_key", "fact_key"),
        Index("idx_case_input_fact_source_type", "source_type"),
        Index("idx_case_input_fact_json_gin", "fact_value_json", postgresql_using="gin"),
    )

    fact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_file.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value_type: Mapped[FactValueTypeEnum] = mapped_column(
        _enum_type(FactValueTypeEnum, "fact_value_type_enum"),
        nullable=False,
    )
    fact_value_text: Mapped[str | None] = mapped_column(Text)
    fact_value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    fact_value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    fact_value_date: Mapped[date | None] = mapped_column(Date)
    fact_value_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[FactSourceTypeEnum] = mapped_column(
        _enum_type(FactSourceTypeEnum, "fact_source_type_enum"),
        nullable=False,
        server_default=text("'user_input'"),
    )
    source_reference: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.000"),
    )
    fact_order: Mapped[int] = mapped_column(
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


class CaseFailureMode(Base):
    """Case-level failure reason linked to optional rule, provision, and evidence context."""

    __tablename__ = "case_failure_mode"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="chk_case_failure_mode_confidence",
        ),
        CheckConstraint("failure_order >= 1", name="chk_case_failure_mode_order"),
        Index("idx_case_failure_mode_case", "case_id"),
        Index("idx_case_failure_mode_type", "failure_type"),
        Index("idx_case_failure_mode_severity", "severity"),
        Index("idx_case_failure_mode_blocking", "blocking"),
        Index("idx_case_failure_mode_order", "case_id", "failure_order"),
    )

    failure_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_file.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    failure_type: Mapped[FailureTypeEnum] = mapped_column(
        _enum_type(FailureTypeEnum, "failure_type_enum"),
        nullable=False,
    )
    severity: Mapped[SeverityEnum] = mapped_column(
        _enum_type(SeverityEnum, "severity_enum"),
        nullable=False,
        server_default=text("'medium'"),
    )
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    linked_rule_component_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule_component.component_id", ondelete="SET NULL"),
    )
    linked_provision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_provision.provision_id", ondelete="SET NULL"),
    )
    linked_evidence_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evidence_requirement.evidence_id", ondelete="SET NULL"),
    )
    remediation_suggestion: Mapped[str | None] = mapped_column(Text)
    blocking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.000"),
    )
    failure_order: Mapped[int] = mapped_column(
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


class CaseCounterfactual(Base):
    """Case-level counterfactual scenario describing a plausible outcome change."""

    __tablename__ = "case_counterfactual"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="chk_case_counterfactual_confidence",
        ),
        CheckConstraint("scenario_order >= 1", name="chk_case_counterfactual_order"),
        Index("idx_case_counterfactual_case", "case_id"),
        Index("idx_case_counterfactual_type", "counterfactual_type"),
        Index("idx_case_counterfactual_outcome", "projected_outcome"),
        Index(
            "idx_case_counterfactual_input_change_gin",
            "input_change",
            postgresql_using="gin",
        ),
        Index(
            "idx_case_counterfactual_tariff_impact_gin",
            "estimated_tariff_impact",
            postgresql_using="gin",
        ),
        Index("idx_case_counterfactual_order", "case_id", "scenario_order"),
    )

    counterfactual_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_file.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    counterfactual_type: Mapped[CounterfactualTypeEnum] = mapped_column(
        _enum_type(CounterfactualTypeEnum, "counterfactual_type_enum"),
        nullable=False,
    )
    scenario_label: Mapped[str] = mapped_column(Text, nullable=False)
    input_change: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, nullable=False)
    projected_outcome: Mapped[ProjectedOutcomeEnum] = mapped_column(
        _enum_type(ProjectedOutcomeEnum, "projected_outcome_enum"),
        nullable=False,
    )
    projected_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    projected_linked_rule_component_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule_component.component_id", ondelete="SET NULL"),
    )
    projected_linked_provision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_provision.provision_id", ondelete="SET NULL"),
    )
    estimated_tariff_impact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    feasibility_note: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("0.800"),
    )
    scenario_order: Mapped[int] = mapped_column(
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
