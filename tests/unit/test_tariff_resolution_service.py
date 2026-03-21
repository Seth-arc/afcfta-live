"""Unit tests for tariff resolution service orchestration and corridor validation."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import CorridorNotSupportedError, TariffNotFoundError
from app.repositories.tariffs_repository import TariffsRepository
from app.schemas.tariffs import TariffResolutionResult
from app.services.tariff_resolution_service import TariffResolutionService


def build_tariff_row(
    *,
    resolved_rate_year: int | None,
    preferential_rate: Decimal | None,
    rate_status: str | None,
    tariff_category: str = "liberalised",
    schedule_status: str = "official",
) -> dict[str, object]:
    """Build a minimal repository payload for tariff service tests."""

    return {
        "mfn_base_rate": Decimal("15.0000"),
        "preferential_rate": preferential_rate,
        "resolved_rate_year": resolved_rate_year,
        "rate_status": rate_status,
        "tariff_category": tariff_category,
        "schedule_status": schedule_status,
    }


@pytest.mark.asyncio
async def test_resolve_tariff_bundle_with_exact_year_match() -> None:
    repository = AsyncMock(spec=TariffsRepository)
    repository.get_tariff.return_value = build_tariff_row(
        resolved_rate_year=2026,
        preferential_rate=Decimal("5.0000"),
        rate_status="in_force",
    )
    service = TariffResolutionService(repository)

    result = await service.resolve_tariff_bundle("GHA", "NGA", "HS2017", "110311", 2026)

    repository.get_tariff.assert_awaited_once_with(
        exporter="GHA",
        importer="NGA",
        hs_version="HS2017",
        hs6_code="110311",
        year=2026,
    )
    assert isinstance(result, TariffResolutionResult)
    assert result.base_rate == Decimal("15.0000")
    assert result.preferential_rate == Decimal("5.0000")
    assert result.staging_year == 2026
    assert result.tariff_status.value == "in_force"
    assert result.schedule_status.value == "official"


@pytest.mark.asyncio
async def test_resolve_tariff_bundle_uses_fallback_rate_year() -> None:
    repository = AsyncMock(spec=TariffsRepository)
    repository.get_tariff.return_value = build_tariff_row(
        resolved_rate_year=2025,
        preferential_rate=Decimal("7.5000"),
        rate_status="in_force",
    )
    service = TariffResolutionService(repository)

    result = await service.resolve_tariff_bundle("CMR", "NGA", "HS2017", "040630", 2026)

    assert result.preferential_rate == Decimal("7.5000")
    assert result.staging_year == 2025
    assert result.tariff_status.value == "in_force"


@pytest.mark.asyncio
async def test_resolve_tariff_bundle_raises_when_schedule_missing() -> None:
    repository = AsyncMock(spec=TariffsRepository)
    repository.get_tariff.return_value = None
    service = TariffResolutionService(repository)

    with pytest.raises(TariffNotFoundError) as exc_info:
        await service.resolve_tariff_bundle("GHA", "NGA", "HS2017", "110311", 2026)

    assert exc_info.value.detail == {
        "exporter_country": "GHA",
        "importer_country": "NGA",
        "hs_version": "HS2017",
        "hs6_code": "110311",
        "year": 2026,
    }


@pytest.mark.asyncio
async def test_resolve_tariff_bundle_raises_for_unsupported_country() -> None:
    repository = AsyncMock(spec=TariffsRepository)
    service = TariffResolutionService(repository)

    with pytest.raises(CorridorNotSupportedError) as exc_info:
        await service.resolve_tariff_bundle("KEN", "NGA", "HS2017", "110311", 2026)

    repository.get_tariff.assert_not_awaited()
    assert exc_info.value.detail == {"country_code": "KEN"}


@pytest.mark.asyncio
async def test_resolve_tariff_bundle_preserves_excluded_category() -> None:
    repository = AsyncMock(spec=TariffsRepository)
    repository.get_tariff.return_value = build_tariff_row(
        resolved_rate_year=None,
        preferential_rate=None,
        rate_status=None,
        tariff_category="excluded",
        schedule_status="official",
    )
    service = TariffResolutionService(repository)

    result = await service.resolve_tariff_bundle("GHA", "NGA", "HS2017", "240220", 2026)

    assert result.tariff_category.value == "excluded"
    assert result.tariff_status == "incomplete"
    assert result.preferential_rate is None
