"""Create eligibility evaluation audit tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_create_evaluation_audit_layer"
down_revision: str | None = "0008_create_case_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE legal_outcome_enum AS ENUM (
            'eligible',
            'not_eligible',
            'uncertain',
            'not_yet_operational',
            'insufficient_information'
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
          CREATE TYPE check_severity_enum AS ENUM (
            'blocker',
            'major',
            'minor',
            'info'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE eligibility_evaluation (
          evaluation_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          case_id uuid NOT NULL REFERENCES case_file(case_id) ON DELETE CASCADE,
          evaluation_date date NOT NULL,
          overall_outcome legal_outcome_enum NOT NULL,
          pathway_used text,
          confidence_class text NOT NULL,
          rule_status_at_evaluation rule_status_enum NOT NULL,
          tariff_status_at_evaluation text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_eligibility_evaluation_confidence_class
            CHECK (confidence_class IN ('complete', 'provisional', 'incomplete'))
        );
        """
    )
    op.execute("CREATE INDEX idx_eligibility_evaluation_case ON eligibility_evaluation(case_id);")
    op.execute("CREATE INDEX idx_eligibility_evaluation_date ON eligibility_evaluation(evaluation_date);")
    op.execute(
        """
        CREATE INDEX idx_eligibility_evaluation_case_date
        ON eligibility_evaluation(case_id, evaluation_date);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_eligibility_evaluation_outcome
        ON eligibility_evaluation(overall_outcome);
        """
    )

    op.execute(
        """
        CREATE TABLE eligibility_check_result (
          check_result_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          evaluation_id uuid NOT NULL REFERENCES eligibility_evaluation(evaluation_id) ON DELETE CASCADE,
          check_type text NOT NULL,
          check_code text NOT NULL,
          passed boolean NOT NULL,
          severity check_severity_enum NOT NULL,
          expected_value text,
          observed_value text,
          explanation text NOT NULL,
          details_json jsonb,
          linked_component_id uuid REFERENCES psr_rule_component(component_id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_eligibility_check_result_type
            CHECK (check_type IN ('psr', 'general_rule', 'status', 'blocker'))
        );
        """
    )
    op.execute(
        """
        CREATE INDEX idx_eligibility_check_result_evaluation
        ON eligibility_check_result(evaluation_id);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_eligibility_check_result_type
        ON eligibility_check_result(check_type);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_eligibility_check_result_code
        ON eligibility_check_result(check_code);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_eligibility_check_result_component
        ON eligibility_check_result(linked_component_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS eligibility_check_result;")
    op.execute("DROP TABLE IF EXISTS eligibility_evaluation;")
