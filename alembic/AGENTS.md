# Alembic Migrations

- Every new table or schema change requires a migration
- The human runs all alembic commands — do not run them in the sandbox
- Migration SQL must match docs/Concrete_Contract.md
- Include uuid-ossp and pg_trgm extensions in the first migration
- Include CREATE TYPE for all enums
- Never modify a migration that has already been applied — create a new one
