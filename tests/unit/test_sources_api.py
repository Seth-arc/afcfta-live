"""Unit tests for source and provision routes with mocked repositories."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import get_sources_repository
from app.core.enums import (
    AuthorityTierEnum,
    InstrumentTypeEnum,
    ProvisionStatusEnum,
    SourceStatusEnum,
    SourceTypeEnum,
)


def _source_row() -> dict[str, object]:
    return {
        "source_id": uuid4(),
        "title": "Appendix IV",
        "short_title": "Appendix IV",
        "source_group": "agreement",
        "source_type": SourceTypeEnum.APPENDIX,
        "authority_tier": AuthorityTierEnum.BINDING,
        "issuing_body": "AfCFTA Secretariat",
        "jurisdiction_scope": "afcfta",
        "status": SourceStatusEnum.CURRENT,
        "language": "en",
        "file_path": "sources/appendix-iv.pdf",
        "mime_type": "application/pdf",
        "checksum_sha256": "a" * 64,
        "publication_date": date(2025, 1, 1),
        "effective_date": date(2025, 1, 1),
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


def _provision_row(source_id) -> dict[str, object]:
    return {
        "provision_id": uuid4(),
        "source_id": source_id,
        "instrument_name": "AfCFTA Appendix IV",
        "instrument_type": InstrumentTypeEnum.APPENDIX,
        "annex_ref": "Appendix IV",
        "topic_primary": "origin_rules",
        "topic_secondary": ["qualification"],
        "provision_text_verbatim": "Products are originating if...",
        "status": ProvisionStatusEnum.IN_FORCE,
        "authority_weight": Decimal("1.0"),
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_list_sources_passes_string_filters_to_repository(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    source_row = _source_row()
    calls: list[dict[str, object]] = []

    class FakeSourcesRepository:
        async def list_sources(self, **kwargs) -> list[dict[str, object]]:
            calls.append(kwargs)
            return [source_row]

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        response = await async_client.get(
            "/api/v1/sources",
            params={
                "source_type": "appendix",
                "authority_tier": "binding",
                "status": "current",
                "limit": 5,
                "offset": 2,
            },
        )
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 200, response.text
    assert response.json()[0]["source_id"] == str(source_row["source_id"])
    assert calls == [
        {
            "source_type": "appendix",
            "authority_tier": "binding",
            "status": "current",
            "limit": 5,
            "offset": 2,
        }
    ]


@pytest.mark.asyncio
async def test_get_source_detail_returns_404_when_missing(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    source_id = str(uuid4())

    class FakeSourcesRepository:
        async def get_source(self, requested_source_id: str):
            assert requested_source_id == source_id
            return None

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        response = await async_client.get(f"/api/v1/sources/{source_id}")
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 404
    assert response.json()["detail"] == f"Source '{source_id}' was not found"


@pytest.mark.asyncio
async def test_get_source_detail_returns_validated_source_row(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    source_row = _source_row()
    source_id = str(source_row["source_id"])

    class FakeSourcesRepository:
        async def get_source(self, requested_source_id: str):
            assert requested_source_id == source_id
            return source_row

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        response = await async_client.get(f"/api/v1/sources/{source_id}")
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Appendix IV"


@pytest.mark.asyncio
async def test_list_provisions_passes_filters_to_repository(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    source_row = _source_row()
    provision_row = _provision_row(source_row["source_id"])
    calls: list[dict[str, object]] = []

    class FakeSourcesRepository:
        async def list_provisions(self, **kwargs) -> list[dict[str, object]]:
            calls.append(kwargs)
            return [provision_row]

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        response = await async_client.get(
            "/api/v1/provisions",
            params={
                "topic_primary": "origin_rules",
                "source_id": str(source_row["source_id"]),
                "annex_ref": "Appendix IV",
                "limit": 10,
                "offset": 1,
            },
        )
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 200, response.text
    assert response.json()[0]["source_id"] == str(source_row["source_id"])
    assert calls == [
        {
            "topic_primary": "origin_rules",
            "annex_ref": "Appendix IV",
            "source_id": str(source_row["source_id"]),
            "limit": 10,
            "offset": 1,
        }
    ]


@pytest.mark.asyncio
async def test_get_provision_detail_returns_404_when_missing(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    provision_id = str(uuid4())

    class FakeSourcesRepository:
        async def get_provision(self, requested_provision_id: str):
            assert requested_provision_id == provision_id
            return None

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        response = await async_client.get(f"/api/v1/provisions/{provision_id}")
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 404
    assert response.json()["detail"] == f"Provision '{provision_id}' was not found"


@pytest.mark.asyncio
async def test_get_provision_detail_returns_validated_provision_row(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    source_row = _source_row()
    provision_row = _provision_row(source_row["source_id"])
    provision_id = str(provision_row["provision_id"])

    class FakeSourcesRepository:
        async def get_provision(self, requested_provision_id: str):
            assert requested_provision_id == provision_id
            return provision_row

    async def override_sources_repository() -> FakeSourcesRepository:
        return FakeSourcesRepository()

    app.dependency_overrides[get_sources_repository] = override_sources_repository

    try:
        response = await async_client.get(f"/api/v1/provisions/{provision_id}")
    finally:
        app.dependency_overrides.pop(get_sources_repository, None)

    assert response.status_code == 200, response.text
    assert response.json()["instrument_name"] == "AfCFTA Appendix IV"
