"""Data access for tariff schedule resolution by corridor, HS6 code, and year."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings


class TariffsRepository:
    """Repository for corridor tariff resolution queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_tariff(
        self,
        exporter: str,
        importer: str,
        hs_version: str,
        hs6_code: str,
        year: int,
    ) -> Mapping[str, Any] | None:
        """Resolve the best matching tariff line and year rate for a corridor and HS6."""

        settings = get_settings()
        if settings.CACHE_STATIC_LOOKUPS:
            cache_key = ("tariff", exporter, importer, hs_version, hs6_code, year)
            hit, cached = cache.get(cache.tariff_store, cache_key)
            if hit:
                return cached

        schedule_statement = text(
            """
            SELECT
              tsh.schedule_id,
              tsh.source_id AS schedule_source_id,
              tsh.importing_state,
              tsh.exporting_scope,
              tsh.schedule_status,
              tsh.publication_date,
              tsh.effective_date,
              tsh.expiry_date,
              tsh.hs_version,
              tsh.category_system,
              tsh.notes,
              tsl.schedule_line_id,
              hp.hs6_id,
              hp.hs6_code,
              hp.hs6_display,
              tsl.product_description,
              tsl.tariff_category,
              tsl.mfn_base_rate,
              tsl.base_year,
              tsl.target_rate,
              tsl.target_year,
              tsl.staging_type,
              tsl.page_ref AS line_page_ref,
              tsl.table_ref,
              tsl.row_ref
            FROM tariff_schedule_header tsh
            JOIN tariff_schedule_line tsl
              ON tsl.schedule_id = tsh.schedule_id
            JOIN hs6_product hp
              ON hp.hs_version = tsh.hs_version
             AND hp.hs6_code = LEFT(tsl.hs_code, 6)
            WHERE tsh.importing_state = :importer
              AND tsh.exporting_scope = :exporter
              AND hp.hs_version = :hs_version
              AND hp.hs6_code = :hs6_code
              AND (tsh.effective_date IS NULL OR tsh.effective_date <= :year_end)
              AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= :year_start)
            ORDER BY
              CASE tsh.schedule_status
                WHEN 'gazetted' THEN 1
                WHEN 'official' THEN 2
                WHEN 'provisional' THEN 3
                ELSE 9
              END,
              tsh.updated_at DESC
            LIMIT 1
            """
        )
        schedule_result = await self.session.execute(
            schedule_statement,
            {
                "exporter": exporter,
                "importer": importer,
                "hs_version": hs_version,
                "hs6_code": hs6_code,
                "year_start": date(year, 1, 1),
                "year_end": date(year, 12, 31),
            },
        )
        tariff_bundle = schedule_result.mappings().first()
        if not tariff_bundle:
            return None

        rate_statement = text(
            """
            SELECT
              tsry.year_rate_id,
              tsry.calendar_year AS resolved_rate_year,
              tsry.preferential_rate,
              tsry.rate_status,
              tsry.source_id AS rate_source_id,
              tsry.page_ref AS rate_page_ref
            FROM tariff_schedule_rate_by_year tsry
            WHERE tsry.schedule_line_id = :schedule_line_id
              AND tsry.calendar_year <= :year
            ORDER BY
              CASE WHEN tsry.calendar_year = :year THEN 0 ELSE 1 END,
              tsry.calendar_year DESC
            LIMIT 1
            """
        )
        rate_result = await self.session.execute(
            rate_statement,
            {
                "schedule_line_id": tariff_bundle["schedule_line_id"],
                "year": year,
            },
        )
        rate_row = rate_result.mappings().first()

        payload = dict(tariff_bundle)
        payload["requested_year"] = year
        payload["used_fallback_rate"] = False
        if rate_row:
            payload.update(rate_row)
            payload["used_fallback_rate"] = rate_row["resolved_rate_year"] != year
        else:
            payload["year_rate_id"] = None
            payload["resolved_rate_year"] = None
            payload["preferential_rate"] = None
            payload["rate_status"] = None
            payload["rate_source_id"] = None
            payload["rate_page_ref"] = None

        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.tariff_store, cache_key, payload, settings.CACHE_TTL_SECONDS)

        return payload
