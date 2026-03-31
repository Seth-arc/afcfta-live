"""Data access for current status assertions and active transition clauses."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.cache as cache
from app.config import get_settings


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

    async def get_status_overlay_rows(
        self,
        targets: list[tuple[str, str]],
        as_of_date: date | None = None,
    ) -> list[Mapping[str, Any]]:
        """Return ordered status rows with aggregated transitions for each target."""

        if not targets:
            return []

        resolved_date = as_of_date or date.today()
        settings = get_settings()
        cache_key = (
            "status-overlay-rows",
            resolved_date.isoformat(),
            tuple((entity_type, entity_key) for entity_type, entity_key in targets),
        )
        if settings.CACHE_STATUS_LOOKUPS:
            hit, cached = cache.get(cache.status_store, cache_key)
            if hit:
                return cached
        value_fragments: list[str] = []
        params: dict[str, Any] = {"as_of_date": resolved_date}
        for ordinal, (entity_type, entity_key) in enumerate(targets):
            value_fragments.append(
                "("
                f"CAST(:entity_type_{ordinal} AS text), "
                f"CAST(:entity_key_{ordinal} AS text), "
                f"CAST(:ordinal_{ordinal} AS integer)"
                ")"
            )
            params[f"entity_type_{ordinal}"] = entity_type
            params[f"entity_key_{ordinal}"] = entity_key
            params[f"ordinal_{ordinal}"] = ordinal

        statement = text(
            f"""
            WITH targets(entity_type, entity_key, ordinal) AS (
              VALUES {", ".join(value_fragments)}
            )
            SELECT
              targets.ordinal,
              targets.entity_type,
              targets.entity_key,
              (
                SELECT row_to_json(status_row)
                FROM (
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
                  WHERE sa.entity_type = targets.entity_type
                    AND sa.entity_key = targets.entity_key
                    AND (sa.effective_from IS NULL OR sa.effective_from <= :as_of_date)
                    AND (sa.effective_to IS NULL OR sa.effective_to >= :as_of_date)
                  ORDER BY sa.confidence_score DESC, sa.updated_at DESC
                  LIMIT 1
                ) AS status_row
              ) AS status,
              COALESCE(
                (
                  SELECT json_agg(
                    json_build_object(
                      'transition_id', tc.transition_id,
                      'entity_type', tc.entity_type,
                      'entity_key', tc.entity_key,
                      'transition_type', tc.transition_type,
                      'transition_text_verbatim', tc.transition_text_verbatim,
                      'start_date', tc.start_date,
                      'end_date', tc.end_date,
                      'review_trigger', tc.review_trigger,
                      'page_ref', tc.page_ref,
                      'source_id', tc.source_id,
                      'created_at', tc.created_at,
                      'updated_at', tc.updated_at
                    )
                    ORDER BY
                      COALESCE(tc.end_date, DATE '9999-12-31') ASC,
                      tc.start_date DESC,
                      tc.updated_at DESC
                  )
                  FROM transition_clause tc
                  WHERE tc.entity_type = targets.entity_type
                    AND tc.entity_key = targets.entity_key
                    AND (tc.start_date IS NULL OR tc.start_date <= :as_of_date)
                    AND (tc.end_date IS NULL OR tc.end_date >= :as_of_date)
                ),
                '[]'::json
              ) AS transitions
            FROM targets
            ORDER BY targets.ordinal ASC
            """
        )
        result = await self.session.execute(statement, params)
        rows = list(result.mappings().all())
        if settings.CACHE_STATUS_LOOKUPS:
            cache.put(cache.status_store, cache_key, rows, settings.CACHE_TTL_SECONDS)
        return rows
