"""Data access for current status assertions and active transition clauses."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class StatusRepository:
    """Repository for status-window and transition-window lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_status(
      self,
      entity_type: str,
      entity_key: str,
      as_of_date: date | None = None,
    ) -> Mapping[str, Any] | None:
      """Return the highest-confidence status assertion active on the requested date."""

      resolved_date = as_of_date or date.today()
        statement = text(
            """
            SELECT
              sa.status_assertion_id,
              sa.entity_type,
              sa.entity_key,
              sa.status_type,
              sa.status_text_verbatim,
              sa.effective_from,
              sa.effective_to,
              sa.page_ref,
              sa.clause_ref,
              sa.confidence_score,
              sa.source_id,
              sa.created_at,
              sa.updated_at
            FROM status_assertion sa
            WHERE sa.entity_type = :entity_type
              AND sa.entity_key = :entity_key
              AND (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
              AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
            ORDER BY sa.confidence_score DESC, sa.updated_at DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            statement,
            {
                "entity_type": entity_type,
                "entity_key": entity_key,
                "as_of_date": resolved_date,
            },
        )
        return result.mappings().first()

    async def get_active_transitions(
        self,
        entity_type: str,
        entity_key: str,
      as_of_date: date | None = None,
    ) -> list[Mapping[str, Any]]:
      """Return transition clauses active on the requested date for an entity key."""

      resolved_date = as_of_date or date.today()
        statement = text(
            """
            SELECT
              tc.transition_id,
              tc.entity_type,
              tc.entity_key,
              tc.transition_type,
              tc.transition_text_verbatim,
              tc.start_date,
              tc.end_date,
              tc.review_trigger,
              tc.page_ref,
              tc.source_id,
              tc.created_at,
              tc.updated_at
            FROM transition_clause tc
            WHERE tc.entity_type = :entity_type
              AND tc.entity_key = :entity_key
              AND (tc.start_date IS NULL OR tc.start_date <= :as_of_date)
              AND (tc.end_date IS NULL OR tc.end_date >= :as_of_date)
            ORDER BY
              COALESCE(tc.end_date, DATE '9999-12-31') ASC,
              tc.start_date DESC,
              tc.updated_at DESC
            """
        )
        result = await self.session.execute(
            statement,
            {
                "entity_type": entity_type,
                "entity_key": entity_key,
                "as_of_date": resolved_date,
            },
        )
        return list(result.mappings().all())
