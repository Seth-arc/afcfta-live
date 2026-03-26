"""Thin route handlers for source registry and legal provision lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_sources_repository
from app.core.enums import AuthorityTierEnum, SourceStatusEnum, SourceTypeEnum
from app.repositories.sources_repository import SourcesRepository
from app.schemas.sources import LegalProvisionOut, SourceRegistryOut

router = APIRouter()


@router.get("/sources", response_model=list[SourceRegistryOut])
async def list_sources(
    topic: str | None = Query(None),
    source_type: SourceTypeEnum | None = Query(None),
    authority_tier: AuthorityTierEnum | None = Query(None),
    status: SourceStatusEnum | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sources_repository: SourcesRepository = Depends(get_sources_repository),
) -> list[SourceRegistryOut]:
    """Return source registry rows, optionally filtered by provenance metadata."""

    source_type_value = source_type.value if source_type is not None else None
    authority_tier_value = authority_tier.value if authority_tier is not None else None
    status_value = status.value if status is not None else None
    if topic is not None:
        rows = await sources_repository.list_sources_by_topic(
            topic=topic,
            source_type=source_type_value,
            authority_tier=authority_tier_value,
            status=status_value,
            limit=limit,
            offset=offset,
        )
    else:
        rows = await sources_repository.list_sources(
            source_type=source_type_value,
            authority_tier=authority_tier_value,
            status=status_value,
            limit=limit,
            offset=offset,
        )
    return [SourceRegistryOut.model_validate(row) for row in rows]


@router.get("/sources/{source_id}", response_model=SourceRegistryOut)
async def get_source_detail(
    source_id: str,
    sources_repository: SourcesRepository = Depends(get_sources_repository),
) -> SourceRegistryOut:
    """Return one source registry row by source_id."""

    row = await sources_repository.get_source(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' was not found")
    return SourceRegistryOut.model_validate(row)


@router.get("/provisions", response_model=list[LegalProvisionOut])
async def list_provisions(
    topic: str | None = Query(None),
    topic_primary: str | None = Query(None),
    source_id: str | None = Query(None),
    annex_ref: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sources_repository: SourcesRepository = Depends(get_sources_repository),
) -> list[LegalProvisionOut]:
    """Return legal provisions filtered by topic, source, or annex metadata."""

    rows = await sources_repository.list_provisions(
        topic_primary=topic_primary if topic_primary is not None else topic,
        annex_ref=annex_ref,
        source_id=source_id,
        limit=limit,
        offset=offset,
    )
    return [LegalProvisionOut.model_validate(row) for row in rows]


@router.get("/provisions/{provision_id}", response_model=LegalProvisionOut)
async def get_provision_detail(
    provision_id: str,
    sources_repository: SourcesRepository = Depends(get_sources_repository),
) -> LegalProvisionOut:
    """Return one legal provision by provision_id."""

    row = await sources_repository.get_provision(provision_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Provision '{provision_id}' was not found")
    return LegalProvisionOut.model_validate(row)
