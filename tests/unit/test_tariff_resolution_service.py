"""Unit tests for the tariff resolution service."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from unittest.mock import AsyncMock

import pytest

from app.core.enums import RateStatusEnum, ScheduleStatusEnum, StagingTypeEnum, TariffCategoryEnum
from app.core.exceptions import CorridorNotSupportedError, TariffNotFoundError
from app.services.tariff_resolution_service import TariffResolutionService


def _uuid(value: int) -> UUID:
    """Build a stable UUID for test fixtures."""

    return UUID(f"00000000-0000-0000-0000-{value:012d}")


def _tariff_row(
    *,
    resolved_rate_year: int,
    preferential_rate: str,
    tariff_category: TariffCategoryEnum = TariffCategoryEnum.LIBERALISED,
) -> dict[str, object]:
    """Return one repository tariff row."""

    return {
        "schedule_id": _uuid(1),
        "schedule_line_id": _uuid(2),
        "year_rate_id": _uuid(3),
        "resolved_rate_year": resolved_rate_year,
        "mfn_base_rate": Decimal("15.0000"),
        "preferential_rate": Decimal(preferential_rate),
        "rate_status": RateStatusEnum.IN_FORCE,
        "tariff_category": tariff_category,
        "schedule_status": ScheduleStatusEnum.OFFICIAL,
        "staging_type": StagingTypeEnum.LINEAR,
    }


@pytest.mark.asyncio
async def test_normal_lookup_with_exact_year_match() -> None:
    """Return the resolved rate for the requested year."""

    repository = AsyncMock()
    repository.get_tariff.return_value = _tariff_row(
        resolved_rate_year=2025,
        preferential_rate="0.0000",
    )
    service = TariffResolutionService(repository)

    result = await service.resolve("GHA", "NGA", "HS2017", "110311", 2025)

    assert result.base_rate == Decimal("15.0000")
    assert result.preferential_rate == Decimal("0.0000")
    assert result.staging_year == 2025
    assert result.tariff_status == "in_force"


@pytest.mark.asyncio
async def test_year_fallback_uses_latest_prior_rate() -> None:
    """The repository fallback year should be surfaced by the service."""

    repository = AsyncMock()
    repository.get_tariff.return_value = _tariff_row(
        resolved_rate_year=2025,
        preferential_rate="5.0000",
    )
    service = TariffResolutionService(repository)

    result = await service.resolve("GHA", "NGA", "HS2017", "110311", 2026)

    assert result.staging_year == 2025
    assert result.preferential_rate == Decimal("5.0000")
    assert result.tariff_status == "in_force"


@pytest.mark.asyncio
async def test_missing_schedule_raises_tariff_not_found() -> None:
    """Missing schedule rows should raise the domain exception."""

    repository = AsyncMock()
    repository.get_tariff.return_value = None
    service = TariffResolutionService(repository)

    with pytest.raises(TariffNotFoundError):
        await service.resolve("GHA", "NGA", "HS2017", "110311", 2025)


@pytest.mark.asyncio
async def test_unsupported_country_raises_corridor_not_supported() -> None:
    """Corridors outside v0.1 scope must fail before repository access."""

    repository = AsyncMock()
    service = TariffResolutionService(repository)

    with pytest.raises(CorridorNotSupportedError):
        await service.resolve("USA", "NGA", "HS2017", "110311", 2025)

    repository.get_tariff.assert_not_awaited()


@pytest.mark.asyncio
async def test_excluded_product_preserves_tariff_category() -> None:
    """Excluded products should still return a structured tariff result."""

    repository = AsyncMock()
    repository.get_tariff.return_value = _tariff_row(
        resolved_rate_year=2025,
        preferential_rate="15.0000",
        tariff_category=TariffCategoryEnum.EXCLUDED,
    )
    service = TariffResolutionService(repository)

    result = await service.resolve("GHA", "NGA", "HS2017", "110311", 2025)

    assert result.tariff_category == "excluded"
