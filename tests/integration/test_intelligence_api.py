"""Integration tests for corridor intelligence and alert listing APIs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.core.enums import (
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertTypeEnum,
    CorridorStatusEnum,
    HsLevelEnum,
    RuleStatusEnum,
)
from app.core.entity_keys import make_entity_key
from app.db.base import get_async_session_factory
from app.db.models.intelligence import AlertEvent, CorridorProfile
from app.repositories.intelligence_repository import IntelligenceRepository
from app.schemas.assessments import EligibilityAssessmentResponse, EligibilityRequest
from app.schemas.cases import CaseFactIn
from app.schemas.intelligence import AlertEventOut
from app.schemas.rules import PSRRuleResolvedOut, RulePathwayOut, RuleResolutionResult
from app.schemas.status import StatusOverlay
from app.services.intelligence_service import IntelligenceService
from tests.integration.test_golden_path import _fact_payload, _seed_not_operational_candidate


pytestmark = pytest.mark.integration


def _uuid(value: int) -> UUID:
    """Build a stable UUID for intelligence test fixtures."""

    return UUID(f"00000000-0000-0000-0000-{value:012d}")


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

    version_suffix = uuid4().hex
    older = await _create_corridor_profile(
        exporter="GHA",
        importer="NGA",
        corridor_status=CorridorStatusEnum.PROVISIONAL,
        method_version=f"pytest-v1-{version_suffix}",
        effective_from=date(2024, 1, 1),
        operational_notes="older profile",
    )
    newer = await _create_corridor_profile(
        exporter="GHA",
        importer="NGA",
        corridor_status=CorridorStatusEnum.OPERATIONAL,
        method_version=f"pytest-v2-{version_suffix}",
        effective_from=date(2025, 1, 1),
        operational_notes="newer profile",
    )
    await _create_corridor_profile(
        exporter="CMR",
        importer="NGA",
        corridor_status=CorridorStatusEnum.PARTIALLY_OPERATIONAL,
        method_version=f"pytest-other-{version_suffix}",
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
    assert body["method_version"] == f"pytest-v2-{version_suffix}"
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


@pytest.mark.asyncio
async def test_generated_alerts_are_visible_through_alert_listing_api(
    async_client: AsyncClient,
) -> None:
    """Alerts emitted by the intelligence service should be discoverable through the API."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        service = IntelligenceService(IntelligenceRepository(session))
        await service.emit_assessment_alerts(
            request=EligibilityRequest(
                hs6_code="110311",
                hs_version="HS2017",
                exporter="GHA",
                importer="NGA",
                year=2025,
                persona_mode="exporter",
                production_facts=[
                    CaseFactIn(
                        fact_type="direct_transport",
                        fact_key="direct_transport",
                        fact_value_type="boolean",
                        fact_value_boolean=True,
                        source_ref=None,
                    )
                ],
            ),
            rule_bundle=RuleResolutionResult(
                psr_rule=PSRRuleResolvedOut(
                    psr_id=_uuid(10),
                    source_id=_uuid(11),
                    appendix_version="seed-v0.1",
                    hs_version="HS2017",
                    hs6_code="110311",
                    hs_code_start=None,
                    hs_code_end=None,
                    hs_level=HsLevelEnum.SUBHEADING,
                    rule_scope="subheading",
                    product_description="Seed product",
                    legal_rule_text_verbatim="Seed rule text.",
                    legal_rule_text_normalized="CTH",
                    rule_status=RuleStatusEnum.PENDING,
                    effective_date=date(2024, 1, 1),
                    page_ref=1,
                    table_ref="seed_psr",
                    row_ref="110311",
                ),
                components=[],
                pathways=[
                    RulePathwayOut(
                        pathway_id=_uuid(12),
                        psr_id=_uuid(10),
                        pathway_code="CTH",
                        pathway_label="CTH",
                        pathway_type="specific",
                        expression_json={"op": "fact_eq", "fact": "direct_transport", "value": True},
                        threshold_percent=None,
                        threshold_basis=None,
                        tariff_shift_level=HsLevelEnum.HEADING,
                        required_process_text=None,
                        allows_cumulation=True,
                        allows_tolerance=False,
                        priority_rank=1,
                        effective_date=date(2024, 1, 1),
                        expiry_date=None,
                    )
                ],
                applicability_type="direct",
            ),
            tariff_result=None,
            corridor_overlay=StatusOverlay(
                status_type="in_force",
                effective_from=date(2024, 1, 1),
                effective_to=None,
                confidence_class="complete",
                active_transitions=[],
                constraints=[],
                source_text_verbatim="Corridor is operational.",
            ),
            response=EligibilityAssessmentResponse(
                hs6_code="110311",
                eligible=False,
                pathway_used=None,
                rule_status=RuleStatusEnum.PENDING,
                tariff_outcome=None,
                failures=["RULE_STATUS_PENDING"],
                missing_facts=[],
                evidence_required=[],
                missing_evidence=[],
                readiness_score=None,
                completeness_ratio=None,
                confidence_class="provisional",
            ),
        )
        await session.commit()

    response = await async_client.get(
        "/api/v1/intelligence/alerts",
        params={
            "status": "open",
            "severity": "high",
            "entity_type": "psr_rule",
            "limit": 25,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert any(row["alert_type"] == "rule_status_changed" for row in body)
    assert any("PSR rule status is pending" in row["alert_message"] for row in body)


@pytest.mark.asyncio
async def test_direct_assessment_emits_corridor_alert_visible_via_alert_listing_api(
    async_client: AsyncClient,
) -> None:
    """A seeded `not_yet_operational` corridor overlay should emit a corridor alert.

    The fixture intentionally seeds the corridor status blocker because
    `IntelligenceService._build_alert_specs()` only creates a corridor-scoped alert row
    when the resolved corridor overlay status is `not_yet_operational`.
    """

    candidate = await _seed_not_operational_candidate()
    corridor_key = make_entity_key(
        "corridor",
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        hs6_code=candidate["hs6_code"],
    )

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json={
            "hs6_code": candidate["hs6_code"],
            "hs_version": "HS2017",
            "exporter": candidate["exporter"],
            "importer": candidate["importer"],
            "year": 2025,
            "persona_mode": "exporter",
            "production_facts": [
                _fact_payload("wholly_obtained", True),
                _fact_payload("direct_transport", True),
            ],
        },
    )

    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    assert assessment_body["failures"] == ["NOT_OPERATIONAL"]

    alerts_response = await async_client.get(
        "/api/v1/intelligence/alerts",
        params={
            "status": "open",
            "entity_type": "corridor",
            "entity_key": corridor_key,
            "limit": 25,
        },
    )

    assert alerts_response.status_code == 200, alerts_response.text
    body = alerts_response.json()
    assert body, "Expected at least one emitted corridor alert for the assessed entity_key."
    assert {"entity_type", "entity_key", "severity", "alert_status"}.issubset(body[0])

    alert = AlertEventOut.model_validate(body[0])
    assert alert.entity_type == "corridor"
    assert alert.entity_key == corridor_key
    assert alert.severity == AlertSeverityEnum.CRITICAL
    assert alert.alert_status == AlertStatusEnum.OPEN
