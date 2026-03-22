"""Thin route handlers for corridor tariff lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_tariff_resolution_service
from app.schemas.tariffs import TariffResolutionResult
from app.services.tariff_resolution_service import TariffResolutionService

router = APIRouter()


@router.get("/tariffs", response_model=TariffResolutionResult)
async def get_tariff_for_corridor(
    exporter: str = Query(..., min_length=3, max_length=3),
    importer: str = Query(..., min_length=3, max_length=3),
    hs6: str = Query(...),
    year: int = Query(...),
    hs_version: str = Query("HS2017"),
    tariff_resolution_service: TariffResolutionService = Depends(get_tariff_resolution_service),
) -> TariffResolutionResult:
    """Resolve the tariff outcome for one corridor, HS6 code, and year."""

    return await tariff_resolution_service.resolve(
        exporter_country=exporter,
        importer_country=importer,
        hs_version=hs_version,
        hs6_code=hs6,
        year=year,
    )
