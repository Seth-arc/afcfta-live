"""SQLAlchemy ORM models for status assertions and transition clauses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import StatusTypeEnum
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class StatusAssertion(Base):
    """Polymorphic status assertion for rules, schedules, corridors, and related entities."""

    __tablename__ = "status_assertion"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="chk_status_assertion_dates",
        ),
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="chk_status_assertion_confidence",
        ),
        Index("idx_status_assertion_entity", "entity_type", "entity_key"),
        Index(
            "idx_status_assertion_entity_window",
            "entity_type",
            "entity_key",
            "effective_from",
            "effective_to",
        ),
        Index("idx_status_assertion_status_type", "status_type"),
        Index("idx_status_assertion_source", "source_id"),
    )

    status_assertion_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    status_type: Mapped[StatusTypeEnum] = mapped_column(
        _enum_type(StatusTypeEnum, "status_type_enum"),
        nullable=False,
    )
    status_text_verbatim: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    page_ref: Mapped[int | None] = mapped_column(Integer)
    clause_ref: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.000"),
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


class TransitionClause(Base):
    """Time-bound transition clause attached to a polymorphic entity key."""

    __tablename__ = "transition_clause"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="chk_transition_clause_dates",
        ),
        Index("idx_transition_clause_entity", "entity_type", "entity_key"),
        Index(
            "idx_transition_clause_entity_window",
            "entity_type",
            "entity_key",
            "start_date",
            "end_date",
        ),
        Index("idx_transition_clause_source", "source_id"),
    )

    transition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    transition_type: Mapped[str] = mapped_column(Text, nullable=False)
    transition_text_verbatim: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    review_trigger: Mapped[str | None] = mapped_column(Text)
    page_ref: Mapped[int | None] = mapped_column(Integer)
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
