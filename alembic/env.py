"""Alembic environment configuration for async PostgreSQL migrations."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401
from app.db.base import Base
from app.local_db import build_local_database_urls

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def _resolve_database_url() -> str:
    """Choose a migration URL that works with the installed database drivers."""

    async_url = os.getenv("DATABASE_URL")
    sync_url = os.getenv("DATABASE_URL_SYNC")

    if async_url and "+asyncpg" in async_url:
        return async_url

    if sync_url:
        return sync_url

    if async_url:
        return async_url

    environment = os.getenv("ENV", "development")
    if environment in {"development", "test", "ci"}:
        derived_async_url, _ = build_local_database_urls(os.environ)
        return derived_async_url

    msg = "DATABASE_URL or DATABASE_URL_SYNC must be set for Alembic."
    raise RuntimeError(msg)


database_url = _resolve_database_url()
if not database_url:
    msg = "DATABASE_URL or DATABASE_URL_SYNC must be set for Alembic."
    raise RuntimeError(msg)

# Do NOT call config.set_main_option here — passwords containing % characters
# trigger ConfigParser interpolation errors. The URL is passed directly to the
# engine constructors below instead.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a live connection."""

    _ensure_alembic_version_table_width(connection)
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def _ensure_alembic_version_table_width(connection: Connection) -> None:
    """Keep Alembic's version table compatible with the project's revision ids.

    Alembic's default `version_num` width is `VARCHAR(32)`, but this repository
    uses human-readable revision identifiers longer than 32 characters. Fresh
    databases otherwise fail when the version row is updated to a long revision
    id during `upgrade head`.
    """

    if connection.dialect.name != "postgresql":
        return

    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(255) NOT NULL PRIMARY KEY
            )
            """
        )
    )
    connection.execute(
        text(
            """
            ALTER TABLE alembic_version
            ALTER COLUMN version_num TYPE VARCHAR(255)
            """
        )
    )
    if connection.in_transaction():
        connection.commit()


async def run_async_migrations() -> None:
    """Run migrations using an async engine."""

    connectable = create_async_engine(database_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    if "+asyncpg" in database_url:
        asyncio.run(run_async_migrations())
        return

    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
