"""Integration tests for source registry API endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.enums import AuthorityTierEnum, InstrumentTypeEnum, SourceTypeEnum
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


async def _create_provision(
    *,
    source_id: str,
    topic_primary: str,
    annex_ref: str | None,
    instrument_name_suffix: str,
) -> dict[str, object]:
    """Create one legal provision row for API integration assertions."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        repository = SourcesRepository(session)
        row = await repository.create_provision(
            {
                "source_id": source_id,
                "instrument_name": f"Instrument {instrument_name_suffix}",
                "instrument_type": InstrumentTypeEnum.APPENDIX,
                "article_ref": "Art. 5",
                "annex_ref": annex_ref,
                "appendix_ref": "Appendix IV",
                "section_ref": "Section 1",
                "subsection_ref": None,
                "page_start": 1,
                "page_end": 2,
                "topic_primary": topic_primary,
                "topic_secondary": ["origin", topic_primary],
                "provision_text_verbatim": f"Verbatim provision text {instrument_name_suffix}",
                "provision_text_normalized": f"Normalized provision text {instrument_name_suffix}",
                "effective_date": date(2025, 1, 1),
                "expiry_date": None,
                "status": "in_force",
                "cross_reference_refs": ["Annex 2", "Appendix IV"],
                "authority_weight": Decimal("1.000"),
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


@pytest.mark.asyncio
async def test_get_provision_detail_returns_legal_provision_row(async_client: AsyncClient) -> None:
    """GET /provisions/{provision_id} should return one legal provision using the provenance response schema."""

    source = await _create_source(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        status="current",
        short_title_suffix=f"provision-detail-{uuid4()}",
    )
    provision = await _create_provision(
        source_id=str(source["source_id"]),
        topic_primary="origin_rules",
        annex_ref="Annex 2",
        instrument_name_suffix=f"detail-{uuid4()}",
    )

    response = await async_client.get(f"/api/v1/provisions/{provision['provision_id']}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["provision_id"] == str(provision["provision_id"])
    assert body["source_id"] == str(source["source_id"])
    assert body["topic_primary"] == "origin_rules"
    assert body["annex_ref"] == "Annex 2"
    assert body["instrument_type"] == "appendix"


@pytest.mark.asyncio
async def test_list_provisions_supports_topic_and_source_filters(async_client: AsyncClient) -> None:
    """GET /provisions should support filtered list queries by topic_primary and source_id."""

    matching_source = await _create_source(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        status="current",
        short_title_suffix=f"provision-match-{uuid4()}",
    )
    other_source = await _create_source(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        status="current",
        short_title_suffix=f"provision-other-{uuid4()}",
    )
    matching_provision = await _create_provision(
        source_id=str(matching_source["source_id"]),
        topic_primary="tariff_liberalisation",
        annex_ref="Annex 1",
        instrument_name_suffix=f"matching-{uuid4()}",
    )
    non_matching_topic = await _create_provision(
        source_id=str(matching_source["source_id"]),
        topic_primary="origin_rules",
        annex_ref="Annex 2",
        instrument_name_suffix=f"other-topic-{uuid4()}",
    )
    non_matching_source = await _create_provision(
        source_id=str(other_source["source_id"]),
        topic_primary="tariff_liberalisation",
        annex_ref="Annex 1",
        instrument_name_suffix=f"other-source-{uuid4()}",
    )

    response = await async_client.get(
        "/api/v1/provisions",
        params={
            "topic_primary": "tariff_liberalisation",
            "source_id": str(matching_source["source_id"]),
            "limit": 25,
            "offset": 0,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    returned_ids = {row["provision_id"] for row in body}
    assert str(matching_provision["provision_id"]) in returned_ids
    assert str(non_matching_topic["provision_id"]) not in returned_ids
    assert str(non_matching_source["provision_id"]) not in returned_ids
    assert all(row["topic_primary"] == "tariff_liberalisation" for row in body)
    assert all(row["source_id"] == str(matching_source["source_id"]) for row in body)


@pytest.mark.asyncio
async def test_provisions_source_id_filter_is_the_traversal_path_from_audit_provenance(
    async_client: AsyncClient,
) -> None:
    """GET /provisions?source_id= must be the canonical traversal path from audit provenance source_id.

    This test pins the contract that a client holding a ``source_id`` from
    ``final_decision.provenance.rule.source_id`` or
    ``final_decision.provenance.tariff.schedule_source_id`` can resolve all backing
    provisions by issuing ``GET /provisions?source_id={source_id}``.
    """

    source = await _create_source(
        source_type=SourceTypeEnum.APPENDIX,
        authority_tier=AuthorityTierEnum.BINDING,
        status="current",
        short_title_suffix=f"traversal-{uuid4()}",
    )
    source_id = str(source["source_id"])

    p1 = await _create_provision(
        source_id=source_id,
        topic_primary="origin_rules",
        annex_ref="Annex 2",
        instrument_name_suffix=f"traversal-a-{uuid4()}",
    )
    p2 = await _create_provision(
        source_id=source_id,
        topic_primary="tariff_liberalisation",
        annex_ref="Annex 1",
        instrument_name_suffix=f"traversal-b-{uuid4()}",
    )

    # The traversal query: source_id only, no topic filter — returns all provisions for that source
    response = await async_client.get(
        "/api/v1/provisions",
        params={"source_id": source_id, "limit": 10, "offset": 0},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    returned_ids = {row["provision_id"] for row in body}
    assert str(p1["provision_id"]) in returned_ids
    assert str(p2["provision_id"]) in returned_ids
    assert all(row["source_id"] == source_id for row in body)

    # Each provision returned must also resolve individually
    for row in body:
        if row["provision_id"] not in {str(p1["provision_id"]), str(p2["provision_id"])}:
            continue
        detail_response = await async_client.get(f"/api/v1/provisions/{row['provision_id']}")
        assert detail_response.status_code == 200, detail_response.text
        detail = detail_response.json()
        assert detail["provision_id"] == row["provision_id"]
        assert detail["source_id"] == source_id
        assert "provision_text_verbatim" in detail