"""Integration tests for corridor intelligence and alert listing APIs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.enums import AlertSeverityEnum, AlertStatusEnum, AlertTypeEnum, CorridorStatusEnum
from app.db.base import get_async_session_factory
from app.db.models.intelligence import AlertEvent, CorridorProfile


pytestmark = pytest.mark.integration


async def _create_corridor_profile(
    *,
    exporter: str,
    importer: str,
    corridor_status: CorridorStatusEnum,
    method_version: str,
    effective_from: date,
    active: bool = True,
    operational_notes: str | None = None,
) -> CorridorProfile:
    """Create one corridor profile row for API integration assertions."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        row = CorridorProfile(
            exporter_state=exporter,
            importer_state=importer,
            corridor_status=corridor_status,
            schedule_maturity_score=Decimal("84.50"),
            documentation_complexity_score=Decimal("35.00"),
            verification_risk_score=Decimal("28.00"),
            transition_exposure_score=Decimal("12.00"),
            average_tariff_relief_score=Decimal("18.50"),
            pending_rule_exposure_score=Decimal("5.00"),
            operational_notes=operational_notes or "pytest corridor profile",
            source_summary={"source_ids": ["pytest-source"]},
            method_version=method_version,
            active=active,
            effective_from=effective_from,
            effective_to=None,
        )
        session.add(row)
        await session.flush()
        await session.commit()
        await session.refresh(row)
        return row


async def _create_alert(
    *,
    alert_type: AlertTypeEnum,
    entity_type: str,
    entity_key: str,
    severity: AlertSeverityEnum,
    alert_status: AlertStatusEnum,
    alert_message: str,
) -> AlertEvent:
    """Create one alert row for API integration assertions."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        row = AlertEvent(
            alert_type=alert_type,
            entity_type=entity_type,
            entity_key=entity_key,
            related_case_id=None,
            related_assessment_id=None,
            related_change_id=None,
            severity=severity,
            alert_status=alert_status,
            alert_message=alert_message,
            alert_payload={"pytest": True, "severity": severity.value},
            triggered_at=datetime.now(timezone.utc),
            acknowledged_at=None,
            resolved_at=None,
            owner=None,
            resolution_note=None,
        )
        session.add(row)
        await session.flush()
        await session.commit()
        await session.refresh(row)
        return row


@pytest.mark.asyncio
async def test_get_corridor_profile_returns_active_profile_for_exporter_importer(
    async_client: AsyncClient,
) -> None:
    """GET /intelligence/corridors/{exporter}/{importer} should return the active profile."""

    older = await _create_corridor_profile(
        exporter="GHA",
        importer="NGA",
        corridor_status=CorridorStatusEnum.PROVISIONAL,
        method_version="pytest-v1",
        effective_from=date(2024, 1, 1),
        operational_notes="older profile",
    )
    newer = await _create_corridor_profile(
        exporter="GHA",
        importer="NGA",
        corridor_status=CorridorStatusEnum.OPERATIONAL,
        method_version="pytest-v2",
        effective_from=date(2025, 1, 1),
        operational_notes="newer profile",
    )
    await _create_corridor_profile(
        exporter="CMR",
        importer="NGA",
        corridor_status=CorridorStatusEnum.PARTIALLY_OPERATIONAL,
        method_version="pytest-other",
        effective_from=date(2025, 1, 1),
        operational_notes="other corridor",
    )

    response = await async_client.get("/api/v1/intelligence/corridors/gha/nga")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["corridor_profile_id"] == str(newer.corridor_profile_id)
    assert body["corridor_profile_id"] != str(older.corridor_profile_id)
    assert body["exporter_state"] == "GHA"
    assert body["importer_state"] == "NGA"
    assert body["corridor_status"] == "operational"
    assert body["method_version"] == "pytest-v2"
    assert body["operational_notes"] == "newer profile"


@pytest.mark.asyncio
async def test_list_alerts_supports_status_severity_and_entity_filters(
    async_client: AsyncClient,
) -> None:
    """GET /intelligence/alerts should support read-only filtering over alerts."""

    matching = await _create_alert(
        alert_type=AlertTypeEnum.CORRIDOR_RISK_CHANGED,
        entity_type="corridor",
        entity_key="corridor:GHA:NGA",
        severity=AlertSeverityEnum.HIGH,
        alert_status=AlertStatusEnum.OPEN,
        alert_message="Matching alert",
    )
    await _create_alert(
        alert_type=AlertTypeEnum.SCHEDULE_UPDATED,
        entity_type="corridor",
        entity_key="corridor:GHA:NGA",
        severity=AlertSeverityEnum.MEDIUM,
        alert_status=AlertStatusEnum.OPEN,
        alert_message="Wrong severity",
    )
    await _create_alert(
        alert_type=AlertTypeEnum.CASE_REVIEW_NEEDED,
        entity_type="case",
        entity_key="case:fixture-1",
        severity=AlertSeverityEnum.HIGH,
        alert_status=AlertStatusEnum.ACKNOWLEDGED,
        alert_message="Wrong entity",
    )
    await _create_alert(
        alert_type=AlertTypeEnum.DATA_QUALITY_ISSUE,
        entity_type="corridor",
        entity_key="corridor:GHA:NGA",
        severity=AlertSeverityEnum.HIGH,
        alert_status=AlertStatusEnum.RESOLVED,
        alert_message="Wrong status",
    )

    response = await async_client.get(
        "/api/v1/intelligence/alerts",
        params={
            "status": "open",
            "severity": "high",
            "entity_type": "corridor",
            "entity_key": "corridor:GHA:NGA",
            "limit": 25,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    returned_ids = {row["alert_id"] for row in body}
    assert str(matching.alert_id) in returned_ids
    assert all(row["alert_status"] == "open" for row in body)
    assert all(row["severity"] == "high" for row in body)
    assert all(row["entity_type"] == "corridor" for row in body)
    assert all(row["entity_key"] == "corridor:GHA:NGA" for row in body)