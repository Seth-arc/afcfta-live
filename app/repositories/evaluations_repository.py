"""Data access for persisted eligibility evaluations and their atomic check rows."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cases import CaseFile
from app.db.models.evaluations import EligibilityCheckResult, EligibilityEvaluation


class EvaluationsRepository:
    """Repository for audit-grade evaluation persistence and replay lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @asynccontextmanager
    async def _atomic_scope(self) -> AsyncIterator[None]:
        if self.session.in_transaction():
            async with self.session.begin_nested():
                yield
            return

        async with self.session.begin():
            yield

    async def persist_evaluation(
        self,
        evaluation_data: Mapping[str, Any],
        check_results: Sequence[Mapping[str, Any]],
        *,
        lock_case: bool = True,
        persist_check_results: bool = True,
        return_inserted_checks: bool = True,
    ) -> Mapping[str, Any]:
        """Atomically insert one evaluation and, optionally, its check rows."""

        evaluation_table = EligibilityEvaluation.__table__
        check_table = EligibilityCheckResult.__table__
        evaluation_payload = {
            key: value
            for key, value in dict(evaluation_data).items()
            if key in evaluation_table.c and value is not None
        }

        async with self._atomic_scope():
            if lock_case:
                lock_statement = (
                    select(CaseFile.case_id)
                    .where(CaseFile.case_id == evaluation_payload["case_id"])
                    .with_for_update()
                )
                await self.session.execute(lock_statement)

            evaluation_statement = (
                insert(evaluation_table).values(**evaluation_payload).returning(*evaluation_table.c)
            )
            evaluation_result = await self.session.execute(evaluation_statement)
            evaluation_row = evaluation_result.mappings().one()

            inserted_checks: list[Mapping[str, Any]] = []
            if persist_check_results and check_results:
                rows: list[dict[str, Any]] = []
                insertable_columns = {
                    "evaluation_id",
                    "check_type",
                    "check_code",
                    "passed",
                    "severity",
                    "expected_value",
                    "observed_value",
                    "explanation",
                    "details_json",
                    "linked_component_id",
                }
                for check_result in check_results:
                    row = dict(check_result)
                    row["evaluation_id"] = evaluation_row["evaluation_id"]
                    normalized_row = {
                        "evaluation_id": row["evaluation_id"],
                        "check_type": row["check_type"],
                        "check_code": row["check_code"],
                        "passed": row["passed"],
                        "severity": row["severity"],
                        "expected_value": row.get("expected_value"),
                        "observed_value": row.get("observed_value"),
                        "explanation": row["explanation"],
                        "details_json": row.get("details_json"),
                        "linked_component_id": row.get("linked_component_id"),
                    }
                    rows.append(
                        {
                            key: value
                            for key, value in normalized_row.items()
                            if key in insertable_columns and key in check_table.c
                        }
                    )

                if return_inserted_checks:
                    check_statement = insert(check_table).values(rows).returning(*check_table.c)
                    inserted_result = await self.session.execute(check_statement)
                    inserted_checks = list(inserted_result.mappings().all())
                else:
                    await self.session.execute(insert(check_table).values(rows))

        return {
            "evaluation": evaluation_row,
            "checks": inserted_checks,
        }

    async def get_evaluation_with_checks(self, evaluation_id: str) -> Mapping[str, Any] | None:
        """Return one persisted evaluation and all of its atomic checks."""

        evaluation_table = EligibilityEvaluation.__table__
        check_table = EligibilityCheckResult.__table__

        evaluation_statement = select(*evaluation_table.c).where(
            evaluation_table.c.evaluation_id == evaluation_id
        )
        evaluation_result = await self.session.execute(evaluation_statement)
        evaluation_row = evaluation_result.mappings().first()
        if evaluation_row is None:
            return None

        checks_statement = (
            select(*check_table.c)
            .where(check_table.c.evaluation_id == evaluation_id)
            .order_by(check_table.c.created_at.asc(), check_table.c.check_code.asc())
        )
        checks_result = await self.session.execute(checks_statement)
        return {
            "evaluation": evaluation_row,
            "checks": list(checks_result.mappings().all()),
        }

    async def get_evaluations_for_case(self, case_id: str) -> list[Mapping[str, Any]]:
        """Return all persisted evaluations for a case, newest first."""

        evaluation_table = EligibilityEvaluation.__table__
        statement = (
            select(*evaluation_table.c)
            .where(evaluation_table.c.case_id == case_id)
            .order_by(
                evaluation_table.c.evaluation_date.desc(),
                evaluation_table.c.created_at.desc(),
            )
        )
        result = await self.session.execute(statement)
        return list(result.mappings().all())

    async def get_latest_evaluation_for_case(self, case_id: str) -> Mapping[str, Any] | None:
        """Return the newest persisted evaluation for a case, or None when absent."""

        evaluation_table = EligibilityEvaluation.__table__
        statement = (
            select(*evaluation_table.c)
            .where(evaluation_table.c.case_id == case_id)
            .order_by(
                evaluation_table.c.evaluation_date.desc(),
                evaluation_table.c.created_at.desc(),
            )
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.mappings().first()
