from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

from app.config import Settings
from app.local_db import (
    DEFAULT_LOCAL_DB_HOST,
    DEFAULT_LOCAL_DB_NAME,
    DEFAULT_LOCAL_DB_PASSWORD,
    DEFAULT_LOCAL_DB_PORT,
    DEFAULT_LOCAL_DB_USER,
    build_local_database_urls,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_settings_derives_local_database_urls_from_local_contract() -> None:
    async_url, sync_url = build_local_database_urls(
        {
            "LOCAL_DB_HOST": DEFAULT_LOCAL_DB_HOST,
            "LOCAL_DB_PORT": DEFAULT_LOCAL_DB_PORT,
            "LOCAL_DB_NAME": DEFAULT_LOCAL_DB_NAME,
            "LOCAL_DB_USER": DEFAULT_LOCAL_DB_USER,
            "LOCAL_DB_PASSWORD": DEFAULT_LOCAL_DB_PASSWORD,
        }
    )

    settings = Settings(
        API_AUTH_KEY="test-key",
        ENV="development",
        DATABASE_URL="",
        DATABASE_URL_SYNC=None,
        LOCAL_DB_HOST=DEFAULT_LOCAL_DB_HOST,
        LOCAL_DB_PORT=DEFAULT_LOCAL_DB_PORT,
        LOCAL_DB_NAME=DEFAULT_LOCAL_DB_NAME,
        LOCAL_DB_USER=DEFAULT_LOCAL_DB_USER,
        LOCAL_DB_PASSWORD=DEFAULT_LOCAL_DB_PASSWORD,
    )

    assert settings.DATABASE_URL == async_url
    assert settings.DATABASE_URL_SYNC == sync_url


def test_env_example_freezes_local_db_defaults() -> None:
    env_values = dotenv_values(REPO_ROOT / ".env.example")

    assert env_values["LOCAL_DB_HOST"] == DEFAULT_LOCAL_DB_HOST
    assert int(env_values["LOCAL_DB_PORT"]) == DEFAULT_LOCAL_DB_PORT
    assert env_values["LOCAL_DB_NAME"] == DEFAULT_LOCAL_DB_NAME
    assert env_values["LOCAL_DB_USER"] == DEFAULT_LOCAL_DB_USER
    assert env_values["LOCAL_DB_PASSWORD"] == DEFAULT_LOCAL_DB_PASSWORD
    assert "DATABASE_URL" not in env_values
    assert "DATABASE_URL_SYNC" not in env_values


def test_local_docker_compose_uses_local_db_env_defaults() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "POSTGRES_DB: ${LOCAL_DB_NAME:-afcfta}" in compose_text
    assert "POSTGRES_USER: ${LOCAL_DB_USER:-afcfta}" in compose_text
    assert "POSTGRES_PASSWORD: ${LOCAL_DB_PASSWORD:-afcfta_dev}" in compose_text
    assert '- "${LOCAL_DB_PORT:-5432}:5432"' in compose_text
