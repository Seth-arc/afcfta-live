"""Integration tests for source registry API endpoints."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.enums import AuthorityTierEnum, SourceTypeEnum
from app.db.base import get_async_session_factory
from app.repositories.sources_repository import SourcesRepository


pytestmark = pytest.mark.integration


async def _create_source(
    *,
    source_type: SourceTypeEnum,
    authority_tier: AuthorityTierEnum,
    status: str,
    short_title_suffix: str,
) -> dict[str, object]:
    """Create one source row for API integration assertions."""

    checksum = uuid4().hex + uuid4().hex
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        repository = SourcesRepository(session)
        row = await repository.create_source(
            {
                "title": f"Source API fixture {short_title_suffix}",
                "short_title": f"SRC-{short_title_suffix}",
                "source_group": "pytest",
                "source_type": source_type,
                "authority_tier": authority_tier,
                "issuing_body": "pytest",
                "jurisdiction_scope": "test",
                "country_code": None,
                "customs_union_code": None,
                "publication_date": date(2025, 1, 1),
                "effective_date": date(2025, 1, 1),
                "expiry_date": None,
                "version_label": "pytest-v1",
                "status": status,
                "language": "en",
                "hs_version": "HS2017",
                "file_path": f"tests/{short_title_suffix}.txt",
                "mime_type": "text/plain",
                "source_url": f"https://example.test/{short_title_suffix}",
                "checksum_sha256": checksum,
                "supersedes_source_id": None,
                "superseded_by_source_id": None,
                "citation_preferred": f"Fixture citation {short_title_suffix}",
                "notes": "pytest fixture",
            }
        )
        await session.commit()
        return dict(row)


@pytest.mark.asyncio
async def test_get_source_detail_returns_source_registry_row(async_client: AsyncClient) -> None:
    """GET /sources/{source_id} should return one source using the provenance response schema."""

    created = await _create_source(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        status="current",
        short_title_suffix=f"detail-{uuid4()}",
    )

    response = await async_client.get(f"/api/v1/sources/{created['source_id']}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["source_id"] == str(created["source_id"])
    assert body["title"] == created["title"]
    assert body["short_title"] == created["short_title"]
    assert body["source_type"] == "appendix"
    assert body["authority_tier"] == "binding"
    assert body["status"] == "current"


@pytest.mark.asyncio
async def test_list_sources_supports_filtered_queries(async_client: AsyncClient) -> None:
    """GET /sources should support filtered list queries across provenance metadata."""

    matching = await _create_source(
        source_type=SourceTypeEnum.OTHER,
        authority_tier=AuthorityTierEnum.ANALYTIC_ENRICHMENT,
        status="archived",
        short_title_suffix=f"matching-{uuid4()}",
    )
    non_matching = await _create_source(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        status="current",
        short_title_suffix=f"other-{uuid4()}",
    )

    response = await async_client.get(
        "/api/v1/sources",
        params={
            "source_type": "other",
            "authority_tier": "analytic_enrichment",
            "status": "archived",
            "limit": 25,
            "offset": 0,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    returned_ids = {row["source_id"] for row in body}
    assert str(matching["source_id"]) in returned_ids
    assert str(non_matching["source_id"]) not in returned_ids
    assert all(row["source_type"] == "other" for row in body)
    assert all(row["authority_tier"] == "analytic_enrichment" for row in body)
    assert all(row["status"] == "archived" for row in body)