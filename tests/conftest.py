"""Shared pytest fixtures for API application tests."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.local_db import (
    DEFAULT_LOCAL_DB_HOST,
    DEFAULT_LOCAL_DB_NAME,
    DEFAULT_LOCAL_DB_PASSWORD,
    DEFAULT_LOCAL_DB_PORT,
    DEFAULT_LOCAL_DB_USER,
    build_local_database_urls,
)


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Override database settings for tests."""

    local_db_env = {
        "LOCAL_DB_HOST": DEFAULT_LOCAL_DB_HOST,
        "LOCAL_DB_PORT": str(DEFAULT_LOCAL_DB_PORT),
        "LOCAL_DB_NAME": DEFAULT_LOCAL_DB_NAME,
        "LOCAL_DB_USER": DEFAULT_LOCAL_DB_USER,
        "LOCAL_DB_PASSWORD": DEFAULT_LOCAL_DB_PASSWORD,
    }
    for key, value in local_db_env.items():
        monkeypatch.setenv(key, value)
    async_url, sync_url = build_local_database_urls(local_db_env)
    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("DATABASE_URL_SYNC", sync_url)
    monkeypatch.setenv("API_AUTH_KEY", "pytest-api-key")
    monkeypatch.setenv("API_AUTH_PRINCIPAL", "pytest-suite")
    monkeypatch.setenv("API_AUTH_HEADER_NAME", "X-API-Key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_MAX_REQUESTS", "100")
    monkeypatch.setenv("RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS", "20")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_REQUESTS_ENABLED", "true")
    monkeypatch.setenv("LOG_DISABLE_UVICORN_ACCESS_LOG", "true")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    """Create a FastAPI application configured for tests."""

    import app.main as main_module

    importlib.reload(main_module)
    return main_module.create_app()


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Create an async HTTP client bound to the FastAPI test app."""

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-API-Key": "pytest-api-key"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def unauthenticated_async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Create an async HTTP client without credentials for auth enforcement tests."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
