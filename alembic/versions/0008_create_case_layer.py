"""Create case file, fact, failure, and counterfactual tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_create_case_layer"
down_revision: str | None = "0007_create_evidence_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE case_submission_status_enum AS ENUM (
            'draft',
            'submitted',
            'under_review',
            'closed',
            'archived'
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
          CREATE TYPE fact_source_type_enum AS ENUM (
            'user_input',
            'document_upload',
            'system_inferred',
            'officer_note',
            'external_data'
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
          CREATE TYPE fact_value_type_enum AS ENUM (
            'text',
            'number',
            'boolean',
            'date',
            'json',
            'list'
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
          CREATE TYPE failure_type_enum AS ENUM (
            'rule_not_met',
            'threshold_not_met',
            'tariff_shift_not_met',
            'specific_process_not_met',
            'missing_document',
            'insufficient_evidence',
            'cumulation_not_supported',
            'valuation_not_supported',
            'classification_uncertain',
            'schedule_not_operational',
            'status_pending',
            'status_provisional',
            'data_gap',
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
          CREATE TYPE severity_enum AS ENUM (
            'critical',
            'high',
            'medium',
            'low'
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
          CREATE TYPE counterfactual_type_enum AS ENUM (
            'sourcing_change',
            'value_adjustment',
            'process_change',
            'documentation_addition',
            'cumulation_change',
            'classification_review',
            'corridor_change',
            'timing_change',
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
          CREATE TYPE projected_outcome_enum AS ENUM (
            'likely_eligible',
            'likely_not_eligible',
            'still_uncertain',
            'requires_more_evidence'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE case_file (
          case_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          case_external_ref text NOT NULL UNIQUE,
          persona_mode persona_mode_enum NOT NULL,
          exporter_state text,
          importer_state text,
          hs_code text,
          hs_version text,
          declared_origin text,
          declared_pathway text,
          submission_status case_submission_status_enum NOT NULL DEFAULT 'draft',
          title text,
          notes text,
          opened_at timestamptz NOT NULL DEFAULT now(),
          submitted_at timestamptz,
          closed_at timestamptz,
          created_by text,
          updated_by text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_case_file_dates
            CHECK (
              (submitted_at IS NULL OR submitted_at >= opened_at)
              AND (closed_at IS NULL OR closed_at >= opened_at)
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_case_file_persona_mode ON case_file(persona_mode);")
    op.execute("CREATE INDEX idx_case_file_submission_status ON case_file(submission_status);")
    op.execute("CREATE INDEX idx_case_file_exporter_state ON case_file(exporter_state);")
    op.execute("CREATE INDEX idx_case_file_importer_state ON case_file(importer_state);")
    op.execute("CREATE INDEX idx_case_file_hs_code ON case_file(hs_code);")
    op.execute("CREATE INDEX idx_case_file_declared_pathway ON case_file(declared_pathway);")

    op.execute(
        """
        CREATE TABLE case_input_fact (
          fact_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          case_id uuid NOT NULL REFERENCES case_file(case_id) ON DELETE CASCADE,
          fact_type text NOT NULL,
          fact_key text NOT NULL,
          fact_value_type fact_value_type_enum NOT NULL,
          fact_value_text text,
          fact_value_number numeric(18,6),
          fact_value_boolean boolean,
          fact_value_date date,
          fact_value_json jsonb,
          unit text,
          source_type fact_source_type_enum NOT NULL DEFAULT 'user_input',
          source_reference text,
          confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
          fact_order integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_case_fact UNIQUE (case_id, fact_key, fact_order),
          CONSTRAINT chk_case_input_fact_confidence
            CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000),
          CONSTRAINT chk_case_input_fact_one_value
            CHECK (
              (
                CASE WHEN fact_value_text IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN fact_value_number IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN fact_value_boolean IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN fact_value_date IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN fact_value_json IS NOT NULL THEN 1 ELSE 0 END
              ) >= 1
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_case_input_fact_case_id ON case_input_fact(case_id);")
    op.execute("CREATE INDEX idx_case_input_fact_fact_type ON case_input_fact(fact_type);")
    op.execute("CREATE INDEX idx_case_input_fact_fact_key ON case_input_fact(fact_key);")
    op.execute("CREATE INDEX idx_case_input_fact_source_type ON case_input_fact(source_type);")
    op.execute("CREATE INDEX idx_case_input_fact_json_gin ON case_input_fact USING GIN(fact_value_json);")

    op.execute(
        """
        CREATE TABLE case_failure_mode (
          failure_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          case_id uuid NOT NULL REFERENCES case_file(case_id) ON DELETE CASCADE,
          failure_type failure_type_enum NOT NULL,
          severity severity_enum NOT NULL DEFAULT 'medium',
          failure_reason text NOT NULL,
          linked_rule_component_id uuid REFERENCES psr_rule_component(component_id) ON DELETE SET NULL,
          linked_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
          linked_evidence_id uuid REFERENCES evidence_requirement(evidence_id) ON DELETE SET NULL,
          remediation_suggestion text,
          blocking boolean NOT NULL DEFAULT true,
          confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
          failure_order integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_case_failure_mode_confidence
            CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000),
          CONSTRAINT chk_case_failure_mode_order
            CHECK (failure_order >= 1)
        );
        """
    )
    op.execute("CREATE INDEX idx_case_failure_mode_case ON case_failure_mode(case_id);")
    op.execute("CREATE INDEX idx_case_failure_mode_type ON case_failure_mode(failure_type);")
    op.execute("CREATE INDEX idx_case_failure_mode_severity ON case_failure_mode(severity);")
    op.execute("CREATE INDEX idx_case_failure_mode_blocking ON case_failure_mode(blocking);")
    op.execute("CREATE INDEX idx_case_failure_mode_order ON case_failure_mode(case_id, failure_order);")

    op.execute(
        """
        CREATE TABLE case_counterfactual (
          counterfactual_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          case_id uuid NOT NULL REFERENCES case_file(case_id) ON DELETE CASCADE,
          counterfactual_type counterfactual_type_enum NOT NULL,
          scenario_label text NOT NULL,
          input_change jsonb NOT NULL,
          projected_outcome projected_outcome_enum NOT NULL,
          projected_reasoning text NOT NULL,
          projected_linked_rule_component_id uuid REFERENCES psr_rule_component(component_id) ON DELETE SET NULL,
          projected_linked_provision_id uuid REFERENCES legal_provision(provision_id) ON DELETE SET NULL,
          estimated_tariff_impact jsonb,
          feasibility_note text,
          confidence_score numeric(4,3) NOT NULL DEFAULT 0.800,
          scenario_order integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_case_counterfactual_confidence
            CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000),
          CONSTRAINT chk_case_counterfactual_order
            CHECK (scenario_order >= 1)
        );
        """
    )
    op.execute("CREATE INDEX idx_case_counterfactual_case ON case_counterfactual(case_id);")
    op.execute("CREATE INDEX idx_case_counterfactual_type ON case_counterfactual(counterfactual_type);")
    op.execute("CREATE INDEX idx_case_counterfactual_outcome ON case_counterfactual(projected_outcome);")
    op.execute(
        """
        CREATE INDEX idx_case_counterfactual_input_change_gin
        ON case_counterfactual USING GIN(input_change);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_case_counterfactual_tariff_impact_gin
        ON case_counterfactual USING GIN(estimated_tariff_impact);
        """
    )
    op.execute("CREATE INDEX idx_case_counterfactual_order ON case_counterfactual(case_id, scenario_order);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS case_counterfactual;")
    op.execute("DROP TABLE IF EXISTS case_failure_mode;")
    op.execute("DROP TABLE IF EXISTS case_input_fact;")
    op.execute("DROP TABLE IF EXISTS case_file;")
