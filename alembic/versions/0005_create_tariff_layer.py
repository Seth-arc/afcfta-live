"""Create the tariff schedule header, line, and yearly rate tables."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_create_tariff_layer"
down_revision: str | None = "0004_create_rules_layer"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          CREATE TYPE schedule_status_enum AS ENUM (
            'official',
            'provisional',
            'gazetted',
            'superseded',
            'draft'
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
          CREATE TYPE tariff_category_enum AS ENUM (
            'liberalised',
            'sensitive',
            'excluded',
            'unknown'
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
          CREATE TYPE staging_type_enum AS ENUM (
            'immediate',
            'linear',
            'stepwise',
            'unknown'
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
          CREATE TYPE rate_status_enum AS ENUM (
            'in_force',
            'projected',
            'provisional',
            'superseded'
          );
        EXCEPTION
          WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE tariff_schedule_header (
          schedule_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
          importing_state text NOT NULL,
          exporting_scope text NOT NULL,
          schedule_status schedule_status_enum NOT NULL,
          publication_date date,
          effective_date date,
          expiry_date date,
          hs_version text NOT NULL,
          category_system text,
          notes text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_tariff_schedule_header_source_corridor_hs_version
            UNIQUE (source_id, importing_state, exporting_scope, hs_version)
        );
        """
    )
    op.execute("CREATE INDEX idx_tariff_schedule_header_source ON tariff_schedule_header(source_id);")
    op.execute(
        "CREATE INDEX idx_tariff_schedule_header_importing_state "
        "ON tariff_schedule_header(importing_state);"
    )
    op.execute(
        "CREATE INDEX idx_tariff_schedule_header_status "
        "ON tariff_schedule_header(schedule_status);"
    )
    op.execute(
        "CREATE INDEX idx_tariff_schedule_header_effective_date "
        "ON tariff_schedule_header(effective_date);"
    )
    op.execute(
        """
        CREATE INDEX idx_tariff_schedule_header_corridor
        ON tariff_schedule_header(importing_state, exporting_scope, schedule_status, effective_date);
        """
    )

    op.execute(
        """
        CREATE TABLE tariff_schedule_line (
          schedule_line_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          schedule_id uuid NOT NULL REFERENCES tariff_schedule_header(schedule_id) ON DELETE CASCADE,
          hs_code text NOT NULL,
          product_description text NOT NULL,
          tariff_category tariff_category_enum NOT NULL DEFAULT 'unknown',
          mfn_base_rate numeric(8,4),
          base_year integer,
          target_rate numeric(8,4),
          target_year integer,
          staging_type staging_type_enum NOT NULL DEFAULT 'unknown',
          page_ref integer,
          table_ref text,
          row_ref text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT chk_tariff_schedule_line_rates
            CHECK (
              (mfn_base_rate IS NULL OR (mfn_base_rate >= 0 AND mfn_base_rate <= 1000))
              AND (target_rate IS NULL OR (target_rate >= 0 AND target_rate <= 1000))
            ),
          CONSTRAINT chk_tariff_schedule_line_years
            CHECK (target_year IS NULL OR base_year IS NULL OR target_year >= base_year)
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_tariff_schedule_line_schedule_hs_code_row_ref
        ON tariff_schedule_line (schedule_id, hs_code, COALESCE(row_ref, ''));
        """
    )
    op.execute("CREATE INDEX idx_tariff_schedule_line_schedule ON tariff_schedule_line(schedule_id);")
    op.execute("CREATE INDEX idx_tariff_schedule_line_hs_code ON tariff_schedule_line(hs_code);")
    op.execute(
        "CREATE INDEX idx_tariff_schedule_line_category ON tariff_schedule_line(tariff_category);"
    )
    op.execute(
        "CREATE INDEX idx_tariff_schedule_line_target_year ON tariff_schedule_line(target_year);"
    )
    op.execute(
        """
        CREATE INDEX idx_tariff_schedule_line_desc_trgm
        ON tariff_schedule_line USING GIN(product_description gin_trgm_ops);
        """
    )

    op.execute(
        """
        CREATE TABLE tariff_schedule_rate_by_year (
          year_rate_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          schedule_line_id uuid NOT NULL REFERENCES tariff_schedule_line(schedule_line_id) ON DELETE CASCADE,
          calendar_year integer NOT NULL,
          preferential_rate numeric(8,4) NOT NULL,
          rate_status rate_status_enum NOT NULL DEFAULT 'in_force',
          source_id uuid NOT NULL REFERENCES source_registry(source_id) ON DELETE RESTRICT,
          page_ref integer,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_tariff_schedule_rate_by_year_line_year
            UNIQUE (schedule_line_id, calendar_year),
          CONSTRAINT chk_tariff_rate_preferential_rate
            CHECK (preferential_rate >= 0 AND preferential_rate <= 1000)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tariff_rate_year_lookup
        ON tariff_schedule_rate_by_year(schedule_line_id, calendar_year);
        """
    )
    op.execute("CREATE INDEX idx_tariff_rate_year_line ON tariff_schedule_rate_by_year(schedule_line_id);")
    op.execute(
        "CREATE INDEX idx_tariff_rate_year_calendar ON tariff_schedule_rate_by_year(calendar_year);"
    )
    op.execute("CREATE INDEX idx_tariff_rate_year_status ON tariff_schedule_rate_by_year(rate_status);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tariff_schedule_rate_by_year;")
    op.execute("DROP TABLE IF EXISTS tariff_schedule_line;")
    op.execute("DROP TABLE IF EXISTS tariff_schedule_header;")
