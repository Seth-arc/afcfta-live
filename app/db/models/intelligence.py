"""SQLAlchemy ORM models for corridor intelligence and alert notifications."""

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
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertTypeEnum,
    CorridorStatusEnum,
)
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class AlertEvent(Base):
    """Actionable alert tied to a polymorphic entity key and optional related records."""

    __tablename__ = "alert_event"
    __table_args__ = (
        CheckConstraint(
            "(acknowledged_at IS NULL OR acknowledged_at >= triggered_at) "
            "AND (resolved_at IS NULL OR resolved_at >= triggered_at)",
            name="chk_alert_event_dates",
        ),
        Index("idx_alert_event_type", "alert_type"),
        Index("idx_alert_event_entity", "entity_type", "entity_key"),
        Index("idx_alert_event_status", "alert_status"),
        Index("idx_alert_event_severity", "severity"),
        Index("idx_alert_event_triggered_at", "triggered_at"),
        Index("idx_alert_event_case", "related_case_id"),
        Index("idx_alert_event_assessment", "related_assessment_id"),
        Index("idx_alert_event_payload_gin", "alert_payload", postgresql_using="gin"),
    )

    alert_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    alert_type: Mapped[AlertTypeEnum] = mapped_column(
        _enum_type(AlertTypeEnum, "alert_type_enum"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    related_case_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_file.case_id", ondelete="SET NULL"),
    )
    related_assessment_id: Mapped[str | None] = mapped_column(Text)
    related_change_id: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[AlertSeverityEnum] = mapped_column(
        _enum_type(AlertSeverityEnum, "alert_severity_enum"),
        nullable=False,
        server_default=text("'medium'"),
    )
    alert_status: Mapped[AlertStatusEnum] = mapped_column(
        _enum_type(AlertStatusEnum, "alert_status_enum"),
        nullable=False,
        server_default=text("'open'"),
    )
    alert_message: Mapped[str] = mapped_column(Text, nullable=False)
    alert_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
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


class CorridorProfile(Base):
    """Reusable corridor intelligence snapshot for an exporter-importer pair."""

    __tablename__ = "corridor_profile"
    __table_args__ = (
        CheckConstraint(
            "schedule_maturity_score BETWEEN 0 AND 100 "
            "AND documentation_complexity_score BETWEEN 0 AND 100 "
            "AND verification_risk_score BETWEEN 0 AND 100 "
            "AND transition_exposure_score BETWEEN 0 AND 100 "
            "AND (average_tariff_relief_score IS NULL "
            "OR average_tariff_relief_score BETWEEN 0 AND 100) "
            "AND (pending_rule_exposure_score IS NULL "
            "OR pending_rule_exposure_score BETWEEN 0 AND 100)",
            name="chk_corridor_profile_scores",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="chk_corridor_profile_dates",
        ),
        Index(
            "uq_corridor_profile",
            "exporter_state",
            "importer_state",
            "method_version",
            text("COALESCE(effective_from, DATE '1900-01-01')"),
            unique=True,
        ),
        Index("idx_corridor_profile_states", "exporter_state", "importer_state"),
        Index("idx_corridor_profile_status", "corridor_status"),
        Index("idx_corridor_profile_active", "active"),
        Index("idx_corridor_profile_effective_from", "effective_from"),
        Index("idx_corridor_profile_source_summary_gin", "source_summary", postgresql_using="gin"),
    )

    corridor_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    exporter_state: Mapped[str] = mapped_column(Text, nullable=False)
    importer_state: Mapped[str] = mapped_column(Text, nullable=False)
    corridor_status: Mapped[CorridorStatusEnum] = mapped_column(
        _enum_type(CorridorStatusEnum, "corridor_status_enum"),
        nullable=False,
        server_default=text("'unknown'"),
    )
    schedule_maturity_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0.00"),
    )
    documentation_complexity_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0.00"),
    )
    verification_risk_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0.00"),
    )
    transition_exposure_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0.00"),
    )
    average_tariff_relief_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pending_rule_exposure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    operational_notes: Mapped[str | None] = mapped_column(Text)
    source_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    method_version: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
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
