"""Data access for PSR rules, components, pathways, and materialized applicability."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings


class RulesRepository:
    """Repository for PSR resolution queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_applicable_psr(
        self,
        hs6_id: str,
        assessment_date: date,
    ) -> Mapping[str, Any] | None:
        """Resolve the governing PSR for a canonical HS6 product on an assessment date."""

        settings = get_settings()
        if settings.CACHE_STATIC_LOOKUPS:
            cache_key = ("psr", hs6_id, assessment_date.isoformat())
            hit, cached = cache.get(cache.psr_store, cache_key)
            if hit:
                return cached

        statement = text(
            """
            SELECT
              pr.*,
              pr.hs_level AS rule_scope,
              pa.applicability_type,
              pa.priority_rank
            FROM hs6_psr_applicability pa
            JOIN psr_rule pr ON pr.psr_id = pa.psr_id
            WHERE pa.hs6_id = :hs6_id
              AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
              AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
            ORDER BY pa.priority_rank ASC, pr.updated_at DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            statement,
            {"hs6_id": hs6_id, "assessment_date": assessment_date},
        )
        row = result.mappings().first()

        if settings.CACHE_STATIC_LOOKUPS:
            cached_value = dict(row) if row is not None else None
            cache.put(cache.psr_store, cache_key, cached_value, settings.CACHE_TTL_SECONDS)
            return cached_value

        return row

    async def get_rules_by_hs6(
        self,
        hs_version: str,
        hs6_code: str,
        assessment_date: date | None = None,
    ) -> Mapping[str, Any] | None:
        """Return the resolved rule bundle for an HS6 code."""

        resolved_date = assessment_date or date.today()
        statement = text(
            """
            SELECT
              hp.hs6_id,
              hp.hs_version,
              hp.hs6_code,
              hp.hs6_display,
              pa.psr_id,
              pa.applicability_type,
              pa.priority_rank,
              pr.hs_level AS rule_scope,
              pr.product_description,
              pr.legal_rule_text_verbatim,
              pr.legal_rule_text_normalized,
              pr.rule_status,
              pr.page_ref,
              pr.table_ref,
              pr.row_ref,
              pr.source_id
            FROM hs6_product hp
            JOIN hs6_psr_applicability pa
              ON pa.hs6_id = hp.hs6_id
            JOIN psr_rule pr
              ON pr.psr_id = pa.psr_id
            WHERE hp.hs_version = :hs_version
              AND hp.hs6_code = :hs6_code
              AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
              AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
            ORDER BY pa.priority_rank ASC, pr.updated_at DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            statement,
            {
                "hs_version": hs_version,
                "hs6_code": hs6_code,
                "assessment_date": resolved_date,
            },
        )
        psr = result.mappings().first()
        if not psr:
            return None

        components = await self.get_psr_components(str(psr["psr_id"]))
        pathways = await self.get_pathways(str(psr["psr_id"]), resolved_date)
        return {"psr": psr, "components": components, "pathways": pathways}

    async def get_psr_components(self, psr_id: str) -> list[Mapping[str, Any]]:
        """Return PSR components ordered by component_order."""

        settings = get_settings()
        if settings.CACHE_STATIC_LOOKUPS:
            cache_key = ("psr_components", psr_id)
            hit, cached = cache.get(cache.psr_store, cache_key)
            if hit:
                return cached

        statement = text(
            """
            SELECT
              prc.component_id,
              prc.component_type,
              prc.operator_type,
              prc.threshold_percent,
              prc.threshold_basis,
              prc.tariff_shift_level,
              prc.specific_process_text,
              prc.component_text_verbatim,
              prc.normalized_expression,
              prc.component_order,
              prc.confidence_score
            FROM psr_rule_component prc
            WHERE prc.psr_id = :psr_id
            ORDER BY prc.component_order ASC
            """
        )
        result = await self.session.execute(statement, {"psr_id": psr_id})
        rows = [dict(r) for r in result.mappings().all()]

        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.psr_store, cache_key, rows, settings.CACHE_TTL_SECONDS)

        return rows

    async def get_pathways(
        self,
        psr_id: str,
        assessment_date: date,
    ) -> list[Mapping[str, Any]]:
        """Return active executable pathways ordered by priority."""

        settings = get_settings()
        if settings.CACHE_STATIC_LOOKUPS:
            cache_key = ("pathways", psr_id, assessment_date.isoformat())
            hit, cached = cache.get(cache.psr_store, cache_key)
            if hit:
                return cached

        statement = text(
            """
            SELECT
              erp.pathway_id,
              erp.pathway_code,
              erp.pathway_label,
              erp.pathway_type,
              erp.expression_json,
              erp.threshold_percent,
              erp.threshold_basis,
              erp.tariff_shift_level,
              erp.required_process_text,
              erp.allows_cumulation,
              erp.allows_tolerance,
              erp.priority_rank
            FROM eligibility_rule_pathway erp
            WHERE erp.psr_id = :psr_id
              AND (erp.effective_date IS NULL OR erp.effective_date <= :assessment_date)
              AND (erp.expiry_date IS NULL OR erp.expiry_date >= :assessment_date)
            ORDER BY erp.priority_rank ASC
            """
        )
        result = await self.session.execute(
            statement,
            {"psr_id": psr_id, "assessment_date": assessment_date},
        )
        rows = [dict(r) for r in result.mappings().all()]

        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.psr_store, cache_key, rows, settings.CACHE_TTL_SECONDS)

        return rows
