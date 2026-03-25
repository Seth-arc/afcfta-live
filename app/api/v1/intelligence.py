"""Thin route handlers for corridor intelligence profile and alert listing."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_intelligence_repository
from app.core.enums import AlertSeverityEnum, AlertStatusEnum
from app.repositories.intelligence_repository import IntelligenceRepository
from app.schemas.intelligence import AlertEventOut, CorridorProfileOut

router = APIRouter()


@router.get(
    "/intelligence/corridors/{exporter}/{importer}",
    response_model=CorridorProfileOut,
)
async def get_corridor_profile(
    exporter: str,
    importer: str,
    as_of_date: date | None = Query(None, description="Snapshot date (YYYY-MM-DD). Defaults to today."),
    intelligence_repository: IntelligenceRepository = Depends(get_intelligence_repository),
) -> CorridorProfileOut:
    """Return the active corridor profile for one exporter-importer pair."""

    row = await intelligence_repository.get_corridor_profile(
        exporter=exporter.upper(),
        importer=importer.upper(),
        as_of_date=as_of_date,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active corridor profile was found for '{exporter.upper()}->{importer.upper()}'",
        )
    return CorridorProfileOut.model_validate(row)


@router.get("/intelligence/alerts", response_model=list[AlertEventOut])
async def list_alerts(
    status: AlertStatusEnum | None = Query(None),
    severity: AlertSeverityEnum | None = Query(None),
    entity_type: str | None = Query(None),
    entity_key: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    intelligence_repository: IntelligenceRepository = Depends(get_intelligence_repository),
) -> list[AlertEventOut]:
    """Return alerts filtered by status, severity, and optional entity scope."""

    rows = await intelligence_repository.list_alerts(
        status=status.value if status is not None else None,
        severity=severity.value if severity is not None else None,
        entity_type=entity_type,
        entity_key=entity_key,
        limit=limit,
    )
    return [AlertEventOut.model_validate(row) for row in rows]