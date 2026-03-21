"""Create corridor profile and alert event tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_create_intelligence_layer"
down_revision: str | None = "0009_create_evaluation_audit_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE alert_type_enum AS ENUM (
            'rule_status_changed',
            'schedule_updated',
            'rate_changed',
            'provision_updated',
            'transition_expiring',
            'document_requirement_changed',
            'corridor_risk_changed',
            'case_review_needed',
            'data_quality_issue',
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
          CREATE TYPE alert_severity_enum AS ENUM (
            'critical',
            'high',
            'medium',
            'low',
            'info'
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
          CREATE TYPE alert_status_enum AS ENUM (
            'open',
            'acknowledged',
            'resolved',
            'dismissed'
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
          CREATE TYPE corridor_status_enum AS ENUM (
            'operational',
            'partially_operational',
            'provisional',
            'not_yet_operational',
            'unknown'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE alert_event (
          alert_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          alert_type alert_type_enum NOT NULL,
          entity_type text NOT NULL,
          entity_key text NOT NULL,
          related_case_id uuid REFERENCES case_file(case_id) ON DELETE SET NULL,
          related_assessment_id text,
          related_change_id text,
          severity alert_severity_enum NOT NULL DEFAULT 'medium',
          alert_status alert_status_enum NOT NULL DEFAULT 'open',
          alert_message text NOT NULL,
          alert_payload jsonb,
          triggered_at timestamptz NOT NULL DEFAULT now(),
          acknowledged_at timestamptz,
          resolved_at timestamptz,
          owner text,
          resolution_note text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_alert_event_dates
            CHECK (
              (acknowledged_at IS NULL OR acknowledged_at >= triggered_at)
              AND (resolved_at IS NULL OR resolved_at >= triggered_at)
            )
        );
        """
    )
    op.execute("CREATE INDEX idx_alert_event_type ON alert_event(alert_type);")
    op.execute("CREATE INDEX idx_alert_event_entity ON alert_event(entity_type, entity_key);")
    op.execute("CREATE INDEX idx_alert_event_status ON alert_event(alert_status);")
    op.execute("CREATE INDEX idx_alert_event_severity ON alert_event(severity);")
    op.execute("CREATE INDEX idx_alert_event_triggered_at ON alert_event(triggered_at);")
    op.execute("CREATE INDEX idx_alert_event_case ON alert_event(related_case_id);")
    op.execute("CREATE INDEX idx_alert_event_assessment ON alert_event(related_assessment_id);")
    op.execute("CREATE INDEX idx_alert_event_payload_gin ON alert_event USING GIN(alert_payload);")

    op.execute(
        """
        CREATE TABLE corridor_profile (
          corridor_profile_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          exporter_state text NOT NULL,
          importer_state text NOT NULL,
          corridor_status corridor_status_enum NOT NULL DEFAULT 'unknown',
          schedule_maturity_score numeric(5,2) NOT NULL DEFAULT 0.00,
          documentation_complexity_score numeric(5,2) NOT NULL DEFAULT 0.00,
          verification_risk_score numeric(5,2) NOT NULL DEFAULT 0.00,
          transition_exposure_score numeric(5,2) NOT NULL DEFAULT 0.00,
          average_tariff_relief_score numeric(5,2),
          pending_rule_exposure_score numeric(5,2),
          operational_notes text,
          source_summary jsonb,
          method_version text NOT NULL,
          active boolean NOT NULL DEFAULT true,
          effective_from date,
          effective_to date,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_corridor_profile_scores
            CHECK (
              schedule_maturity_score BETWEEN 0 AND 100
              AND documentation_complexity_score BETWEEN 0 AND 100
              AND verification_risk_score BETWEEN 0 AND 100
              AND transition_exposure_score BETWEEN 0 AND 100
              AND (average_tariff_relief_score IS NULL OR average_tariff_relief_score BETWEEN 0 AND 100)
              AND (pending_rule_exposure_score IS NULL OR pending_rule_exposure_score BETWEEN 0 AND 100)
            ),
          CONSTRAINT chk_corridor_profile_dates
            CHECK (
              effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from
            )
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_corridor_profile
        ON corridor_profile (
          exporter_state,
          importer_state,
          method_version,
          COALESCE(effective_from, DATE '1900-01-01')
        );
        """
    )
    op.execute(
        """
        CREATE INDEX idx_corridor_profile_states
        ON corridor_profile(exporter_state, importer_state);
        """
    )
    op.execute("CREATE INDEX idx_corridor_profile_status ON corridor_profile(corridor_status);")
    op.execute("CREATE INDEX idx_corridor_profile_active ON corridor_profile(active);")
    op.execute(
        """
        CREATE INDEX idx_corridor_profile_effective_from
        ON corridor_profile(effective_from);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_corridor_profile_source_summary_gin
        ON corridor_profile USING GIN(source_summary);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS corridor_profile;")
    op.execute("DROP TABLE IF EXISTS alert_event;")
