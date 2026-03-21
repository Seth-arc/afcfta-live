"""Create the PSR rules layer and applicability resolver tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_create_rules_layer"
down_revision: str | None = "0002_create_hs6_product"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE psr_rule (
          psr_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
          appendix_version text,
          hs_version text NOT NULL,
          hs_code text NOT NULL,
          hs_code_start text,
          hs_code_end text,
          hs_level hs_level_enum NOT NULL,
          product_description text NOT NULL,
          legal_rule_text_verbatim text NOT NULL,
          legal_rule_text_normalized text,
          rule_status rule_status_enum NOT NULL,
          effective_date date,
          page_ref integer,
          table_ref text,
          row_ref text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_psr_rule_source_hs_code_row_ref
        ON psr_rule (source_id, hs_version, hs_code, COALESCE(row_ref, ''));
        """
    )
    op.execute("CREATE INDEX idx_psr_rule_hs_code ON psr_rule(hs_code);")
    op.execute("CREATE INDEX idx_psr_rule_hs_version ON psr_rule(hs_version);")
    op.execute("CREATE INDEX idx_psr_rule_status ON psr_rule(rule_status);")
    op.execute("CREATE INDEX idx_psr_rule_hs_level ON psr_rule(hs_level);")

    op.execute(
        """
        CREATE TABLE psr_rule_component (
          component_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          psr_id uuid NOT NULL REFERENCES psr_rule(psr_id) ON DELETE CASCADE,
          component_type rule_component_type_enum NOT NULL,
          operator_type operator_type_enum NOT NULL DEFAULT 'standalone',
          threshold_percent numeric(7,3),
          threshold_basis threshold_basis_enum,
          tariff_shift_level hs_level_enum,
          specific_process_text text,
          component_text_verbatim text NOT NULL,
          normalized_expression text,
          confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
          component_order integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_psr_component_threshold
            CHECK (threshold_percent IS NULL OR (threshold_percent >= 0 AND threshold_percent <= 100)),
          CONSTRAINT chk_psr_component_confidence
            CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000)
        );
        """
    )
    op.execute("CREATE INDEX idx_psr_rule_component_psr_id ON psr_rule_component(psr_id);")
    op.execute("CREATE INDEX idx_psr_rule_component_type ON psr_rule_component(component_type);")
    op.execute(
        """
        CREATE INDEX idx_psr_rule_component_order
        ON psr_rule_component(psr_id, component_order);
        """
    )

    op.execute(
        """
        CREATE TABLE eligibility_rule_pathway (
          pathway_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          psr_id uuid NOT NULL REFERENCES psr_rule(psr_id) ON DELETE CASCADE,
          pathway_code text NOT NULL,
          pathway_label text NOT NULL,
          pathway_type text NOT NULL DEFAULT 'specific',
          expression_json jsonb NOT NULL,
          threshold_percent numeric(7,3),
          threshold_basis threshold_basis_enum,
          tariff_shift_level hs_level_enum,
          required_process_text text,
          allows_cumulation boolean NOT NULL DEFAULT true,
          allows_tolerance boolean NOT NULL DEFAULT true,
          priority_rank integer NOT NULL DEFAULT 1,
          effective_date date,
          expiry_date date,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX idx_eligibility_rule_pathway_psr
        ON eligibility_rule_pathway(psr_id, priority_rank, effective_date, expiry_date);
        """
    )

    op.execute(
        """
        CREATE TABLE hs6_psr_applicability (
          applicability_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          hs6_id uuid NOT NULL REFERENCES hs6_product(hs6_id) ON DELETE CASCADE,
          psr_id uuid NOT NULL REFERENCES psr_rule(psr_id) ON DELETE CASCADE,
          applicability_type text NOT NULL,
          priority_rank integer NOT NULL DEFAULT 1,
          effective_date date,
          expiry_date date,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (hs6_id, psr_id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX idx_hs6_psr_applicability_lookup
        ON hs6_psr_applicability(hs6_id, priority_rank, effective_date, expiry_date);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hs6_psr_applicability;")
    op.execute("DROP TABLE IF EXISTS eligibility_rule_pathway;")
    op.execute("DROP TABLE IF EXISTS psr_rule_component;")
    op.execute("DROP TABLE IF EXISTS psr_rule;")
