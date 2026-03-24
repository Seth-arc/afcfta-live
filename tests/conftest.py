"""Shared pytest fixtures for API application tests."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Override database settings for tests."""

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://afcfta:afcfta_dev@localhost:5432/afcfta",
    )
    monkeypatch.setenv(
        "DATABASE_URL_SYNC",
        "postgresql://afcfta:afcfta_dev@localhost:5432/afcfta",
    )
    monkeypatch.setenv("API_AUTH_KEY", "pytest-api-key")
    monkeypatch.setenv("API_AUTH_PRINCIPAL", "pytest-suite")
    monkeypatch.setenv("API_AUTH_HEADER_NAME", "X-API-Key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_DEFAULT_MAX_REQUESTS", "100")
    monkeypatch.setenv("RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS", "20")
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
