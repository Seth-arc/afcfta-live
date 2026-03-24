"""Unit tests for the tariff resolution service."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.countries import V01_COUNTRIES
from app.core.enums import RateStatusEnum, ScheduleStatusEnum, StagingTypeEnum, TariffCategoryEnum
from app.core.exceptions import CorridorNotSupportedError, TariffNotFoundError
from app.services.tariff_resolution_service import TariffResolutionService

_V01_CODES = sorted(V01_COUNTRIES.keys())


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


# ---------------------------------------------------------------------------
# Property-based tests — country code validation and normalisation
# ---------------------------------------------------------------------------


@given(
    country=st.sampled_from(_V01_CODES),
    transform=st.sampled_from([str.upper, str.lower, str.title]),
)
@settings(max_examples=100)
def test_v01_country_codes_are_accepted_in_any_case(country: str, transform) -> None:  # type: ignore[type-arg]
    """Country code validation must be case-insensitive for all v0.1 codes.

    Catches: a case-sensitive equality check instead of .upper() normalisation,
    which would silently reject lowercase or mixed-case input from callers.
    """
    normalised = TariffResolutionService._normalize_country_code(transform(country))
    assert normalised == country.upper()


@given(
    country=st.sampled_from(_V01_CODES),
    padding=st.text(
        alphabet=st.characters(whitelist_categories=("Zs",)),
        min_size=0,
        max_size=3,
    ),
)
@settings(max_examples=100)
def test_v01_country_codes_are_accepted_with_surrounding_whitespace(
    country: str, padding: str
) -> None:
    """Whitespace surrounding a valid code must be stripped before validation.

    Catches: a validator that compares before calling .strip(), causing
    ' GHA ' to be rejected while 'GHA' is accepted.
    """
    normalised = TariffResolutionService._normalize_country_code(padding + country + padding)
    assert normalised == country.upper()


@given(
    code=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=2,
        max_size=6,
    ).filter(lambda c: c.strip().upper() not in V01_COUNTRIES)
)
@settings(max_examples=300)
def test_any_non_v01_country_code_always_raises_corridor_not_supported(code: str) -> None:
    """Every country code outside the v0.1 whitelist must raise CorridorNotSupportedError.

    Catches: an accidental whitelist expansion, a permissive default that
    allows unknown codes through, or a missing validation branch.
    """
    with pytest.raises(CorridorNotSupportedError):
        TariffResolutionService._normalize_country_code(code)
