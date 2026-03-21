"""Create evidence requirements, verification questions, and readiness templates."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_create_evidence_layer"
down_revision: str | None = "0006_create_status_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE persona_mode_enum AS ENUM (
            'officer',
            'analyst',
            'exporter',
            'system'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE requirement_type_enum AS ENUM (
            'certificate_of_origin',
            'supplier_declaration',
            'process_record',
            'bill_of_materials',
            'cost_breakdown',
            'invoice',
            'transport_record',
            'customs_supporting_doc',
            'valuation_support',
            'inspection_record',
            'other'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE verification_risk_category_enum AS ENUM (
            'origin_claim',
            'documentary_gap',
            'valuation_risk',
            'cumulation_risk',
            'process_risk',
            'tariff_classification_risk',
            'schedule_status_risk',
            'general'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE evidence_requirement (
          evidence_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          entity_type text NOT NULL,
          entity_key text NOT NULL,
          persona_mode persona_mode_enum NOT NULL,
          requirement_type requirement_type_enum NOT NULL,
          requirement_description text NOT NULL,
          legal_basis_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
          required boolean NOT NULL DEFAULT true,
          conditional_on jsonb,
          priority_level smallint NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_evidence_priority
            CHECK (priority_level BETWEEN 1 AND 5)
        );
        """
    )
    op.execute("CREATE INDEX idx_evidence_requirement_entity ON evidence_requirement(entity_type, entity_key);")
    op.execute("CREATE INDEX idx_evidence_requirement_persona ON evidence_requirement(persona_mode);")
    op.execute("CREATE INDEX idx_evidence_requirement_type ON evidence_requirement(requirement_type);")
    op.execute(
        """
        CREATE INDEX idx_evidence_requirement_match
        ON evidence_requirement(persona_mode, entity_type, entity_key, priority_level);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_evidence_requirement_conditional_gin
        ON evidence_requirement USING GIN(conditional_on);
        """
    )

    op.execute(
        """
        CREATE TABLE verification_question (
          question_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          entity_type text NOT NULL,
          entity_key text NOT NULL,
          persona_mode persona_mode_enum NOT NULL,
          question_text text NOT NULL,
          purpose text NOT NULL,
          legal_basis_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
          risk_category verification_risk_category_enum NOT NULL DEFAULT 'general',
          priority_level smallint NOT NULL DEFAULT 1,
          active boolean NOT NULL DEFAULT true,
          question_order integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_verification_question_priority
            CHECK (priority_level BETWEEN 1 AND 5),
          CONSTRAINT chk_verification_question_order
            CHECK (question_order >= 1)
        );
        """
    )
    op.execute("CREATE INDEX idx_verification_question_entity ON verification_question(entity_type, entity_key);")
    op.execute("CREATE INDEX idx_verification_question_persona ON verification_question(persona_mode);")
    op.execute("CREATE INDEX idx_verification_question_risk ON verification_question(risk_category);")
    op.execute("CREATE INDEX idx_verification_question_active ON verification_question(active);")

    op.execute(
        """
        CREATE TABLE document_readiness_template (
          template_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          hs_code text NOT NULL,
          hs_version text,
          corridor_scope text NOT NULL,
          origin_pathway_type text,
          required_docs jsonb NOT NULL,
          optional_docs jsonb,
          common_weaknesses jsonb,
          officer_focus_points jsonb,
          legal_basis_provision_ids uuid[],
          active boolean NOT NULL DEFAULT true,
          version_label text,
          notes text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_document_readiness_template
        ON document_readiness_template (
          hs_code,
          COALESCE(hs_version, ''),
          corridor_scope,
          COALESCE(origin_pathway_type, ''),
          COALESCE(version_label, '')
        );
        """
    )
    op.execute("CREATE INDEX idx_document_readiness_template_hs_code ON document_readiness_template(hs_code);")
    op.execute(
        """
        CREATE INDEX idx_document_readiness_template_corridor_scope
        ON document_readiness_template(corridor_scope);
        """
    )
    op.execute("CREATE INDEX idx_document_readiness_template_active ON document_readiness_template(active);")
    op.execute(
        """
        CREATE INDEX idx_document_readiness_template_required_docs_gin
        ON document_readiness_template USING GIN(required_docs);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_document_readiness_template_optional_docs_gin
        ON document_readiness_template USING GIN(optional_docs);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_document_readiness_template_common_weaknesses_gin
        ON document_readiness_template USING GIN(common_weaknesses);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_document_readiness_template_officer_focus_points_gin
        ON document_readiness_template USING GIN(officer_focus_points);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS document_readiness_template;")
    op.execute("DROP TABLE IF EXISTS verification_question;")
    op.execute("DROP TABLE IF EXISTS evidence_requirement;")
