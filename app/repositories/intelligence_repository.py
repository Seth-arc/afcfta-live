"""Data access for corridor intelligence and alert-event lookups."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class IntelligenceRepository:
    """Repository for corridor-profile and alert-event queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_corridor_profile(
        self,
        exporter: str,
        importer: str,
    ) -> Mapping[str, Any] | None:
        """Return the current active corridor profile for an exporter-importer pair."""

        as_of_date = date.today()
        statement = text(
            """
            SELECT
              cp.corridor_profile_id,
              cp.exporter_state,
              cp.importer_state,
              cp.corridor_status,
              cp.schedule_maturity_score,
              cp.documentation_complexity_score,
              cp.verification_risk_score,
              cp.transition_exposure_score,
              cp.average_tariff_relief_score,
              cp.pending_rule_exposure_score,
              cp.operational_notes,
              cp.source_summary,
              cp.method_version,
              cp.active,
              cp.effective_from,
              cp.effective_to,
              cp.created_at,
              cp.updated_at
            FROM corridor_profile cp
            WHERE cp.exporter_state = :exporter
              AND cp.importer_state = :importer
              AND cp.active = true
              AND (cp.effective_from IS NULL OR cp.effective_from <= :as_of_date)
              AND (cp.effective_to IS NULL OR cp.effective_to >= :as_of_date)
            ORDER BY
              COALESCE(cp.effective_from, DATE '1900-01-01') DESC,
              cp.updated_at DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            statement,
            {
                "exporter": exporter,
                "importer": importer,
                "as_of_date": as_of_date,
            },
        )
        return result.mappings().first()

    async def get_active_alerts(
        self,
        entity_type: str,
        entity_key: str,
    ) -> list[Mapping[str, Any]]:
        """Return open or acknowledged alerts for one entity key."""

        statement = text(
            """
            SELECT
              ae.alert_id,
              ae.alert_type,
              ae.entity_type,
              ae.entity_key,
              ae.related_case_id,
              ae.related_assessment_id,
              ae.related_change_id,
              ae.severity,
              ae.alert_status,
              ae.alert_message,
              ae.alert_payload,
              ae.triggered_at,
              ae.acknowledged_at,
              ae.resolved_at,
              ae.owner,
              ae.resolution_note,
              ae.created_at,
              ae.updated_at
            FROM alert_event ae
            WHERE ae.entity_type = :entity_type
              AND ae.entity_key = :entity_key
              AND ae.alert_status IN ('open', 'acknowledged')
            ORDER BY ae.triggered_at DESC, ae.created_at DESC
            """
        )
        result = await self.session.execute(
            statement,
            {
                "entity_type": entity_type,
                "entity_key": entity_key,
            },
        )
        return list(result.mappings().all())

    async def list_alerts(
        self,
        status: str | None,
        severity: str | None,
        limit: int,
    ) -> list[Mapping[str, Any]]:
        """List alerts with optional status and severity filters."""

        params: dict[str, Any] = {"limit": limit}
        statement_text = """
            SELECT
              ae.alert_id,
              ae.alert_type,
              ae.entity_type,
              ae.entity_key,
              ae.related_case_id,
              ae.related_assessment_id,
              ae.related_change_id,
              ae.severity,
              ae.alert_status,
              ae.alert_message,
              ae.alert_payload,
              ae.triggered_at,
              ae.acknowledged_at,
              ae.resolved_at,
              ae.owner,
              ae.resolution_note,
              ae.created_at,
              ae.updated_at
            FROM alert_event ae
            WHERE 1 = 1
        """
        if status is not None:
            statement_text += "\n  AND ae.alert_status = :status"
            params["status"] = status
        if severity is not None:
            statement_text += "\n  AND ae.severity = :severity"
            params["severity"] = severity
        statement_text += """
            ORDER BY ae.triggered_at DESC, ae.created_at DESC
            LIMIT :limit
        """
        result = await self.session.execute(text(statement_text), params)
        return list(result.mappings().all())
