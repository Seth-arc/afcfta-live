"""Data access for persisted eligibility evaluations and their atomic check rows."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cases import CaseFile
from app.db.models.evaluations import EligibilityCheckResult, EligibilityEvaluation


class EvaluationsRepository:
    """Repository for audit-grade evaluation persistence and replay lookups."""

    _DB_ALLOWED_CHECK_TYPES = {"psr", "general_rule", "status", "blocker"}
    _SURROGATE_CHECK_TYPE = "status"

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
    ) -> Mapping[str, Any]:
        """Atomically insert one evaluation and all of its check rows."""

        evaluation_table = EligibilityEvaluation.__table__
        check_table = EligibilityCheckResult.__table__
        evaluation_payload = {
            key: value
            for key, value in dict(evaluation_data).items()
            if key in evaluation_table.c and value is not None
        }

        async with self._atomic_scope():
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
            if check_results:
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
                    persisted_row = self._prepare_check_row_for_insert(row)
                    normalized_row = {
                        "evaluation_id": persisted_row["evaluation_id"],
                        "check_type": persisted_row["check_type"],
                        "check_code": persisted_row["check_code"],
                        "passed": persisted_row["passed"],
                        "severity": persisted_row["severity"],
                        "expected_value": persisted_row.get("expected_value"),
                        "observed_value": persisted_row.get("observed_value"),
                        "explanation": persisted_row["explanation"],
                        "details_json": persisted_row.get("details_json"),
                        "linked_component_id": persisted_row.get("linked_component_id"),
                    }
                    rows.append(
                        {
                            key: value
                            for key, value in normalized_row.items()
                            if key in insertable_columns and key in check_table.c
                        }
                    )

                check_statement = insert(check_table).values(rows).returning(*check_table.c)
                inserted_result = await self.session.execute(check_statement)
                inserted_checks = [
                    self._restore_check_row(dict(row))
                    for row in inserted_result.mappings().all()
                ]

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
            "checks": [
                self._restore_check_row(dict(row))
                for row in checks_result.mappings().all()
            ],
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

    @classmethod
    def _prepare_check_row_for_insert(cls, row: Mapping[str, Any]) -> dict[str, Any]:
        """Persist unsupported logical check types under a schema-compatible surrogate."""

        persisted_row = dict(row)
        original_check_type = str(persisted_row["check_type"])
        if original_check_type in cls._DB_ALLOWED_CHECK_TYPES:
            return persisted_row

        details = persisted_row.get("details_json")
        if isinstance(details, dict):
            normalized_details = deepcopy(details)
        elif details is None:
            normalized_details = {}
        else:
            normalized_details = {"original_payload": details}
        normalized_details["original_check_type"] = original_check_type
        persisted_row["check_type"] = cls._SURROGATE_CHECK_TYPE
        persisted_row["details_json"] = normalized_details
        return persisted_row

    @classmethod
    def _restore_check_row(cls, row: Mapping[str, Any]) -> dict[str, Any]:
        """Restore the canonical logical check type for replay consumers."""

        restored_row = dict(row)
        details = restored_row.get("details_json")
        if not isinstance(details, dict):
            return restored_row

        original_check_type = details.get("original_check_type")
        if not original_check_type:
            return restored_row

        restored_row["check_type"] = original_check_type
        cleaned_details = dict(details)
        cleaned_details.pop("original_check_type", None)
        if cleaned_details.get("original_payload") is not None and len(cleaned_details) == 1:
            restored_row["details_json"] = cleaned_details["original_payload"]
            return restored_row
        cleaned_details.pop("original_payload", None)
        restored_row["details_json"] = cleaned_details or None
        return restored_row
