"""SQLAlchemy ORM models for evidence requirements and readiness support tables."""

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
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import PersonaModeEnum, RequirementTypeEnum, VerificationRiskCategoryEnum
from app.db.base import Base


def _enum_type(enum_cls: type, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class EvidenceRequirement(Base):
    """Persona-aware evidence requirement tied to an entity key and legal basis."""

    __tablename__ = "evidence_requirement"
    __table_args__ = (
        CheckConstraint("priority_level BETWEEN 1 AND 5", name="chk_evidence_priority"),
        Index("idx_evidence_requirement_entity", "entity_type", "entity_key"),
        Index("idx_evidence_requirement_persona", "persona_mode"),
        Index("idx_evidence_requirement_type", "requirement_type"),
        Index(
            "idx_evidence_requirement_match",
            "persona_mode",
            "entity_type",
            "entity_key",
            "priority_level",
        ),
        Index("idx_evidence_requirement_effective_window", "effective_from", "effective_to"),
        Index("idx_evidence_requirement_conditional_gin", "conditional_on", postgresql_using="gin"),
    )

    evidence_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    persona_mode: Mapped[PersonaModeEnum] = mapped_column(
        _enum_type(PersonaModeEnum, "persona_mode_enum"),
        nullable=False,
    )
    requirement_type: Mapped[RequirementTypeEnum] = mapped_column(
        _enum_type(RequirementTypeEnum, "requirement_type_enum"),
        nullable=False,
    )
    requirement_description: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis_provision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_provision.provision_id", ondelete="SET NULL"),
    )
    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    conditional_on: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    priority_level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("1"),
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
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


class VerificationQuestion(Base):
    """Checklist question tied to an entity key, persona, and legal basis."""

    __tablename__ = "verification_question"
    __table_args__ = (
        CheckConstraint(
            "priority_level BETWEEN 1 AND 5",
            name="chk_verification_question_priority",
        ),
        CheckConstraint("question_order >= 1", name="chk_verification_question_order"),
        Index("idx_verification_question_entity", "entity_type", "entity_key"),
        Index("idx_verification_question_persona", "persona_mode"),
        Index("idx_verification_question_risk", "risk_category"),
        Index("idx_verification_question_active", "active"),
    )

    question_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    persona_mode: Mapped[PersonaModeEnum] = mapped_column(
        _enum_type(PersonaModeEnum, "persona_mode_enum"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis_provision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("legal_provision.provision_id", ondelete="SET NULL"),
    )
    risk_category: Mapped[VerificationRiskCategoryEnum] = mapped_column(
        _enum_type(VerificationRiskCategoryEnum, "verification_risk_category_enum"),
        nullable=False,
        server_default=text("'general'"),
    )
    priority_level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("1"),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    question_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
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


class DocumentReadinessTemplate(Base):
    """Reusable document pack template scoped by HS code, corridor, and pathway."""

    __tablename__ = "document_readiness_template"
    __table_args__ = (
        Index(
            "uq_document_readiness_template",
            "hs_code",
            text("COALESCE(hs_version, '')"),
            "corridor_scope",
            text("COALESCE(origin_pathway_type, '')"),
            text("COALESCE(version_label, '')"),
            unique=True,
        ),
        Index("idx_document_readiness_template_hs_code", "hs_code"),
        Index("idx_document_readiness_template_corridor_scope", "corridor_scope"),
        Index("idx_document_readiness_template_active", "active"),
        Index(
            "idx_document_readiness_template_required_docs_gin",
            "required_docs",
            postgresql_using="gin",
        ),
        Index(
            "idx_document_readiness_template_optional_docs_gin",
            "optional_docs",
            postgresql_using="gin",
        ),
        Index(
            "idx_document_readiness_template_common_weaknesses_gin",
            "common_weaknesses",
            postgresql_using="gin",
        ),
        Index(
            "idx_document_readiness_template_officer_focus_points_gin",
            "officer_focus_points",
            postgresql_using="gin",
        ),
    )

    template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    hs_code: Mapped[str] = mapped_column(Text, nullable=False)
    hs_version: Mapped[str | None] = mapped_column(Text)
    corridor_scope: Mapped[str] = mapped_column(Text, nullable=False)
    origin_pathway_type: Mapped[str | None] = mapped_column(Text)
    required_docs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    optional_docs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    common_weaknesses: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    officer_focus_points: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    legal_basis_provision_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    version_label: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
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
