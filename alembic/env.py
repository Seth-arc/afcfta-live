"""Alembic environment configuration for async PostgreSQL migrations."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.db.models  # noqa: F401
from app.db.base import Base

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

    msg = "DATABASE_URL or DATABASE_URL_SYNC must be set for Alembic."
    raise RuntimeError(msg)


database_url = _resolve_database_url()
if not database_url:
    msg = "DATABASE_URL or DATABASE_URL_SYNC must be set for Alembic."
    raise RuntimeError(msg)

config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a live connection."""

    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    configuration = config.get_section(config.config_ini_section, {})

    if "+asyncpg" in database_url:
        asyncio.run(run_async_migrations())
        return

    if importlib.util.find_spec("psycopg2") is None:
        async_url = os.getenv("DATABASE_URL")
        if async_url and "+asyncpg" in async_url:
            config.set_main_option("sqlalchemy.url", async_url)
            asyncio.run(run_async_migrations())
            return

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
