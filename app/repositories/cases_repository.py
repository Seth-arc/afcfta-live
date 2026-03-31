"""Data access for case creation and typed fact retrieval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings
from app.db.models.cases import CaseFile, CaseInputFact


class CasesRepository:
    """Repository for case headers and their submitted facts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_case(self, data: Mapping[str, Any]) -> str:
        """Insert a case_file row and return the generated case_id."""

        case_table = CaseFile.__table__
        payload = dict(data)
        if "hs6_code" in payload and "hs_code" not in payload:
            payload["hs_code"] = payload.pop("hs6_code")
        payload = {
            key: value
            for key, value in payload.items()
            if key in case_table.c and value is not None
        }
        statement = insert(case_table).values(**payload).returning(case_table.c.case_id)
        result = await self.session.execute(statement)
        return str(result.scalar_one())

    async def add_facts(
        self,
        case_id: str,
        facts: Sequence[Mapping[str, Any]],
        *,
        return_ids: bool = True,
    ) -> list[str]:
        """Insert case_input_fact rows for a case and optionally return fact ids."""

        if not facts:
            return []

        settings = get_settings()
        fact_table = CaseInputFact.__table__
        rows: list[dict[str, Any]] = []
        insertable_columns = {
            "case_id",
            "fact_type",
            "fact_key",
            "fact_value_type",
            "fact_value_text",
            "fact_value_number",
            "fact_value_boolean",
            "fact_value_date",
            "fact_value_json",
            "unit",
            "source_type",
            "source_reference",
            "confidence_score",
            "fact_order",
        }
        for fact in facts:
            row = dict(fact)
            if "source_ref" in row and "source_reference" not in row:
                row["source_reference"] = row.pop("source_ref")
            row["case_id"] = case_id
            normalized_row = {
                "case_id": row["case_id"],
                "fact_type": row["fact_type"],
                "fact_key": row["fact_key"],
                "fact_value_type": row["fact_value_type"],
                "fact_value_text": row.get("fact_value_text"),
                "fact_value_number": row.get("fact_value_number"),
                "fact_value_boolean": row.get("fact_value_boolean"),
                "fact_value_date": row.get("fact_value_date"),
                "fact_value_json": row.get("fact_value_json"),
                "unit": row.get("unit"),
                "source_type": row.get("source_type", "user_input"),
                "source_reference": row.get("source_reference"),
                "confidence_score": row.get("confidence_score", Decimal("1.000")),
                "fact_order": row.get("fact_order", 1),
            }
            rows.append(
                {
                    key: value
                    for key, value in normalized_row.items()
                    if key in insertable_columns and key in fact_table.c
                }
            )

        if not return_ids:
            await self.session.execute(insert(fact_table).values(rows))
            if settings.CACHE_STATIC_LOOKUPS:
                cache.case_store.pop(("case-with-facts", case_id), None)
            return []

        statement = insert(fact_table).values(rows).returning(fact_table.c.fact_id)
        result = await self.session.execute(statement)
        if settings.CACHE_STATIC_LOOKUPS:
            cache.case_store.pop(("case-with-facts", case_id), None)
        return [str(fact_id) for fact_id in result.scalars().all()]

    async def get_case_with_facts(self, case_id: str) -> Mapping[str, Any] | None:
        """Return a case row with all associated facts."""

        settings = get_settings()
        cache_key = ("case-with-facts", case_id)
        if settings.CACHE_STATIC_LOOKUPS:
            hit, cached = cache.get(cache.case_store, cache_key)
            if hit:
                return cached

        case_table = CaseFile.__table__
        fact_table = CaseInputFact.__table__

        case_statement = select(*case_table.c).where(case_table.c.case_id == case_id)
        case_result = await self.session.execute(case_statement)
        case_row = case_result.mappings().first()
        if case_row is None:
            if settings.CACHE_STATIC_LOOKUPS:
                cache.put(cache.case_store, cache_key, None, settings.CACHE_TTL_SECONDS)
            return None

        fact_statement = (
            select(*fact_table.c)
            .where(fact_table.c.case_id == case_id)
            .order_by(
                fact_table.c.fact_type.asc(),
                fact_table.c.fact_order.asc(),
                fact_table.c.created_at.asc(),
            )
        )
        fact_result = await self.session.execute(fact_statement)
        bundle = {
            "case": case_row,
            "facts": list(fact_result.mappings().all()),
        }
        if settings.CACHE_STATIC_LOOKUPS:
            cache.put(cache.case_store, cache_key, bundle, settings.CACHE_TTL_SECONDS)
        return bundle
