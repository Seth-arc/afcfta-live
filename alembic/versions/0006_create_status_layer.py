"""Create status assertion and transition clause tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_create_status_layer"
down_revision: str | None = "0005_create_tariff_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE status_type_enum AS ENUM (
            'agreed',
            'pending',
            'provisional',
            'under_review',
            'transitional',
            'superseded',
            'in_force',
            'not_yet_operational',
            'expired'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE status_assertion (
          status_assertion_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
          entity_type text NOT NULL,
          entity_key text NOT NULL,
          status_type status_type_enum NOT NULL,
          status_text_verbatim text NOT NULL,
          effective_from date,
          effective_to date,
          page_ref integer,
          clause_ref text,
          confidence_score numeric(4,3) NOT NULL DEFAULT 1.000,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_status_assertion_dates
            CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from),
          CONSTRAINT chk_status_assertion_confidence
            CHECK (confidence_score >= 0.000 AND confidence_score <= 1.000)
        );
        """
    )
    op.execute("CREATE INDEX idx_status_assertion_entity ON status_assertion(entity_type, entity_key);")
    op.execute(
        """
        CREATE INDEX idx_status_assertion_entity_window
        ON status_assertion(entity_type, entity_key, effective_from, effective_to);
        """
    )
    op.execute("CREATE INDEX idx_status_assertion_status_type ON status_assertion(status_type);")
    op.execute("CREATE INDEX idx_status_assertion_source ON status_assertion(source_id);")

    op.execute(
        """
        CREATE TABLE transition_clause (
          transition_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
          entity_type text NOT NULL,
          entity_key text NOT NULL,
          transition_type text NOT NULL,
          transition_text_verbatim text NOT NULL,
          start_date date,
          end_date date,
          review_trigger text,
          page_ref integer,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_transition_clause_dates
            CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
        );
        """
    )
    op.execute("CREATE INDEX idx_transition_clause_entity ON transition_clause(entity_type, entity_key);")
    op.execute(
        """
        CREATE INDEX idx_transition_clause_entity_window
        ON transition_clause(entity_type, entity_key, start_date, end_date);
        """
    )
    op.execute("CREATE INDEX idx_transition_clause_source ON transition_clause(source_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transition_clause;")
    op.execute("DROP TABLE IF EXISTS status_assertion;")
