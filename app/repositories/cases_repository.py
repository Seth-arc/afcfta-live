"""Data access for case creation and typed fact retrieval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def add_facts(self, case_id: str, facts: Sequence[Mapping[str, Any]]) -> list[str]:
        """Insert case_input_fact rows for a case and return the fact ids."""

        if not facts:
            return []

        fact_table = CaseInputFact.__table__
        rows: list[dict[str, Any]] = []
        for fact in facts:
            row = dict(fact)
            if "source_ref" in row and "source_reference" not in row:
                row["source_reference"] = row.pop("source_ref")
            row["case_id"] = case_id
            rows.append(
                {
                    key: value
                    for key, value in row.items()
                    if key in fact_table.c and value is not None
                }
            )

        statement = insert(fact_table).values(rows).returning(fact_table.c.fact_id)
        result = await self.session.execute(statement)
        return [str(fact_id) for fact_id in result.scalars().all()]

    async def get_case_with_facts(self, case_id: str) -> Mapping[str, Any] | None:
        """Return a case row with all associated facts."""

        case_table = CaseFile.__table__
        fact_table = CaseInputFact.__table__

        case_statement = select(*case_table.c).where(case_table.c.case_id == case_id)
        case_result = await self.session.execute(case_statement)
        case_row = case_result.mappings().first()
        if case_row is None:
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
        return {
            "case": case_row,
            "facts": list(fact_result.mappings().all()),
        }
