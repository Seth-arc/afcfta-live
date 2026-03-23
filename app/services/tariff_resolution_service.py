"""Resolve tariff outcomes for a supported corridor and HS6/year."""

from __future__ import annotations

from app.core.countries import V01_COUNTRIES
from app.core.exceptions import CorridorNotSupportedError, TariffNotFoundError
from app.repositories.tariffs_repository import TariffsRepository
from app.schemas.tariffs import TariffResolutionResult


class TariffResolutionService:
    """Service for corridor tariff lookup and v0.1 country validation."""

    def __init__(self, tariffs_repository: TariffsRepository) -> None:
        self.tariffs_repository = tariffs_repository

    async def resolve_tariff_bundle(
        self,
        exporter_country: str,
        importer_country: str,
        hs_version: str,
        hs6_code: str,
        year: int,
    ) -> TariffResolutionResult:
        """Resolve the tariff outcome for a corridor, HS6 code, and calendar year."""

        exporter = self._normalize_country_code(exporter_country)
        importer = self._normalize_country_code(importer_country)

        tariff = await self.tariffs_repository.get_tariff(
            exporter=exporter,
            importer=importer,
            hs_version=hs_version,
            hs6_code=hs6_code,
            year=year,
        )
        if tariff is None:
            raise TariffNotFoundError(
                (
                    "No tariff schedule found for exporter "
                    f"'{exporter}', importer '{importer}', hs_version '{hs_version}', "
                    f"hs6_code '{hs6_code}', year {year}"
                ),
                detail={
                    "exporter_country": exporter,
                    "importer_country": importer,
                    "hs_version": hs_version,
                    "hs6_code": hs6_code,
                    "year": year,
                },
            )

        tariff_status = tariff["rate_status"] if tariff["rate_status"] is not None else "incomplete"
        return TariffResolutionResult(
            base_rate=tariff["mfn_base_rate"],
            preferential_rate=tariff["preferential_rate"],
            staging_year=tariff["resolved_rate_year"],
            tariff_status=tariff_status,
            tariff_category=tariff["tariff_category"],
            schedule_status=tariff["schedule_status"],
            schedule_id=tariff["schedule_id"],
            schedule_line_id=tariff["schedule_line_id"],
            year_rate_id=tariff["year_rate_id"],
            schedule_source_id=tariff["schedule_source_id"],
            rate_source_id=tariff["rate_source_id"],
            resolved_rate_year=tariff["resolved_rate_year"],
            line_page_ref=tariff["line_page_ref"],
            rate_page_ref=tariff["rate_page_ref"],
            table_ref=tariff["table_ref"],
            row_ref=tariff["row_ref"],
            used_fallback_rate=tariff["used_fallback_rate"],
        )

    async def resolve(
        self,
        exporter_country: str,
        importer_country: str,
        hs_version: str,
        hs6_code: str,
        year: int,
    ) -> TariffResolutionResult:
        """Compatibility wrapper for API handlers that call the service via resolve()."""

        return await self.resolve_tariff_bundle(
            exporter_country=exporter_country,
            importer_country=importer_country,
            hs_version=hs_version,
            hs6_code=hs6_code,
            year=year,
        )

    @staticmethod
    def _normalize_country_code(country_code: str) -> str:
        """Normalize and validate a v0.1 country code."""

        normalized_code = country_code.strip().upper()
        if normalized_code not in V01_COUNTRIES:
            raise CorridorNotSupportedError(
                f"Country '{country_code}' is not supported in v0.1",
                detail={"country_code": normalized_code},
            )
        return normalized_code
