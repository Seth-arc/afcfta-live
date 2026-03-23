"""Thin route handlers for source registry lookup and filtered listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_sources_repository
from app.core.enums import AuthorityTierEnum, SourceStatusEnum, SourceTypeEnum
from app.repositories.sources_repository import SourcesRepository
from app.schemas.sources import SourceRegistryOut

router = APIRouter()


@router.get("/sources", response_model=list[SourceRegistryOut])
async def list_sources(
    source_type: SourceTypeEnum | None = Query(None),
    authority_tier: AuthorityTierEnum | None = Query(None),
    status: SourceStatusEnum | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sources_repository: SourcesRepository = Depends(get_sources_repository),
) -> list[SourceRegistryOut]:
    """Return source registry rows, optionally filtered by provenance metadata."""

    rows = await sources_repository.list_sources(
        source_type=source_type.value if source_type is not None else None,
        authority_tier=authority_tier.value if authority_tier is not None else None,
        status=status.value if status is not None else None,
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