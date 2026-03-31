"""SQLAlchemy ORM models for persisted eligibility evaluations and check results."""

from __future__ import annotations

from datetime import date, datetime
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
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CheckSeverity, LegalOutcome, RuleStatusEnum
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class EligibilityEvaluation(Base):
    """Persisted outcome snapshot for one deterministic assessment run."""

    __tablename__ = "eligibility_evaluation"
    __table_args__ = (
        CheckConstraint(
            "confidence_class IN ('complete', 'provisional', 'incomplete')",
            name="chk_eligibility_evaluation_confidence_class",
        ),
        Index("idx_eligibility_evaluation_case", "case_id"),
        Index("idx_eligibility_evaluation_date", "evaluation_date"),
        Index("idx_eligibility_evaluation_case_date", "case_id", "evaluation_date"),
        Index("idx_eligibility_evaluation_outcome", "overall_outcome"),
    )

    evaluation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_file.case_id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluation_date: Mapped[date] = mapped_column(Date, nullable=False)
    overall_outcome: Mapped[LegalOutcome] = mapped_column(
        _enum_type(LegalOutcome, "legal_outcome_enum"),
        nullable=False,
    )
    pathway_used: Mapped[str | None] = mapped_column(Text)
    confidence_class: Mapped[str] = mapped_column(Text, nullable=False)
    rule_status_at_evaluation: Mapped[RuleStatusEnum] = mapped_column(
        _enum_type(RuleStatusEnum, "rule_status_enum"),
        nullable=False,
    )
    tariff_status_at_evaluation: Mapped[str] = mapped_column(Text, nullable=False)
    decision_snapshot_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EligibilityCheckResult(Base):
    """Persisted audit-stage record captured across the full eligibility evaluation flow."""

    __tablename__ = "eligibility_check_result"
    __table_args__ = (
        CheckConstraint(
            "check_type IN ('classification', 'rule', 'psr', 'pathway', 'general_rule', 'status', 'tariff', 'evidence', 'decision', 'blocker')",
            name="chk_eligibility_check_result_type",
        ),
        Index("idx_eligibility_check_result_evaluation", "evaluation_id"),
        Index("idx_eligibility_check_result_type", "check_type"),
        Index("idx_eligibility_check_result_code", "check_code"),
        Index("idx_eligibility_check_result_component", "linked_component_id"),
    )

    check_result_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    evaluation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("eligibility_evaluation.evaluation_id", ondelete="CASCADE"),
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    check_code: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[CheckSeverity] = mapped_column(
        _enum_type(CheckSeverity, "check_severity_enum"),
        nullable=False,
    )
    expected_value: Mapped[str | None] = mapped_column(Text)
    observed_value: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB)
    linked_component_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("psr_rule_component.component_id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
