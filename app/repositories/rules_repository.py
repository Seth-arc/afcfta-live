"""Data access for applicable PSRs resolved through the materialized applicability table."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
              pr.rule_scope,
              pr.product_description,
              pr.legal_rule_text_verbatim,
              pr.legal_rule_text_normalized,
              pr.rule_status,
              pr.page_ref,
              pr.row_ref,
              pr.source_id
            FROM hs6_product hp
            JOIN hs6_psr_applicability pa
              ON pa.hs6_id = hp.hs6_id
            JOIN psr_rule pr
              ON pr.psr_id = pa.psr_id
            WHERE hp.hs6_id = :hs6_id
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
        return result.mappings().first()
