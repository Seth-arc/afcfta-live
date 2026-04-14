"""Canonical local PostgreSQL contract shared by settings, Alembic, and tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

DEFAULT_LOCAL_DB_HOST = "localhost"
DEFAULT_LOCAL_DB_PORT = 5432
DEFAULT_LOCAL_DB_NAME = "afcfta"
DEFAULT_LOCAL_DB_USER = "afcfta"
DEFAULT_LOCAL_DB_PASSWORD = "afcfta_dev"


def _coerce_int(value: Any, *, default: int) -> int:
    """Parse one integer-like environment value with a safe default."""

    if value in (None, ""):
        return default
    return int(value)


def resolve_local_db_settings(values: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the canonical local database settings from one environment mapping."""

    source = values or {}
    return {
        "host": str(source.get("LOCAL_DB_HOST") or DEFAULT_LOCAL_DB_HOST),
        "port": _coerce_int(source.get("LOCAL_DB_PORT"), default=DEFAULT_LOCAL_DB_PORT),
        "name": str(source.get("LOCAL_DB_NAME") or DEFAULT_LOCAL_DB_NAME),
        "user": str(source.get("LOCAL_DB_USER") or DEFAULT_LOCAL_DB_USER),
        "password": str(source.get("LOCAL_DB_PASSWORD") or DEFAULT_LOCAL_DB_PASSWORD),
    }


def build_local_database_urls(values: Mapping[str, Any] | None = None) -> tuple[str, str]:
    """Build the async and sync SQLAlchemy URLs for the canonical local database."""

    settings = resolve_local_db_settings(values)
    encoded_password = quote(settings["password"], safe="")
    authority = (
        f"{settings['user']}:{encoded_password}"
        f"@{settings['host']}:{settings['port']}/{settings['name']}"
    )
    return (
        f"postgresql+asyncpg://{authority}",
        f"postgresql://{authority}",
    )
