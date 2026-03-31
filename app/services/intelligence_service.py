"""Advisory alert generation for operationally significant assessment conditions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from app.core.entity_keys import make_entity_key
from app.core.enums import AlertSeverityEnum, AlertStatusEnum, AlertTypeEnum
from app.schemas.assessments import EligibilityAssessmentResponse, EligibilityRequest
from app.schemas.rules import RuleResolutionResult
from app.schemas.status import StatusOverlay
from app.schemas.tariffs import TariffResolutionResult


class IntelligenceService:
    """Emit advisory alerts without changing deterministic assessment outputs.

    In v0.1 these alerts are informational workflow signals only. They are persisted for
    later retrieval through the intelligence APIs, but they do not modify eligibility,
    failure codes, or confidence_class on the assessment response.
    """

    def __init__(self, intelligence_repository: Any) -> None:
        self.intelligence_repository = intelligence_repository

    async def emit_assessment_alerts(
        self,
        *,
        request: EligibilityRequest,
        rule_bundle: RuleResolutionResult,
        tariff_result: TariffResolutionResult | None,
        corridor_overlay: StatusOverlay,
        response: EligibilityAssessmentResponse,
        assessment_date: date | None = None,
    ) -> list[Mapping[str, Any]]:
        """Persist advisory alerts for the supported assessment trigger conditions."""

        return await self.persist_alert_specs(
            self.build_assessment_alert_specs(
                request=request,
                rule_bundle=rule_bundle,
                tariff_result=tariff_result,
                corridor_overlay=corridor_overlay,
                response=response,
            )
        )

    async def persist_alert_specs(
        self,
        specs: Sequence[Mapping[str, Any]],
    ) -> list[Mapping[str, Any]]:
        """Persist advisory alert specs, skipping duplicate active alerts."""

        created_alerts: list[Mapping[str, Any]] = []
        for spec in specs:
            payload = dict(spec)
            active_alerts = await self.intelligence_repository.get_active_alerts(
                payload["entity_type"],
                payload["entity_key"],
            )
            if self._has_matching_active_alert(active_alerts, payload["alert_type"]):
                continue
            created_alerts.append(await self.intelligence_repository.create_alert(payload))
        return created_alerts

    def build_assessment_alert_specs(
        self,
        *,
        request: EligibilityRequest,
        rule_bundle: RuleResolutionResult,
        tariff_result: TariffResolutionResult | None,
        corridor_overlay: StatusOverlay,
        response: EligibilityAssessmentResponse,
    ) -> list[dict[str, Any]]:
        """Return advisory alert specs without performing any database writes."""

        return self._build_alert_specs(
            request=request,
            rule_bundle=rule_bundle,
            tariff_result=tariff_result,
            corridor_overlay=corridor_overlay,
            response=response,
        )

    def _build_alert_specs(
        self,
        *,
        request: EligibilityRequest,
        rule_bundle: RuleResolutionResult,
        tariff_result: TariffResolutionResult | None,
        corridor_overlay: StatusOverlay,
        response: EligibilityAssessmentResponse,
    ) -> list[dict[str, Any]]:
        """Return the advisory alert payloads supported in the initial intelligence slice."""

        specs: list[dict[str, Any]] = []
        corridor_key = make_entity_key(
            "corridor",
            exporter=request.exporter,
            importer=request.importer,
            hs6_code=response.hs6_code,
        )
        case_id = self._uuid_or_none(request.case_id)
        rule_status = self._normalize_value(rule_bundle.psr_rule.rule_status)
        if rule_status in {"pending", "partially_agreed"}:
            specs.append(
                {
                    "alert_type": AlertTypeEnum.RULE_STATUS_CHANGED,
                    "entity_type": "psr_rule",
                    "entity_key": make_entity_key(
                        "psr_rule",
                        psr_id=rule_bundle.psr_rule.psr_id,
                    ),
                    "related_case_id": case_id,
                    "severity": AlertSeverityEnum.HIGH,
                    "alert_status": AlertStatusEnum.OPEN,
                    "alert_message": (
                        f"PSR rule status is {rule_status} for HS6 {response.hs6_code} "
                        f"on corridor {request.exporter}->{request.importer}."
                    ),
                    "alert_payload": {
                        "advisory_only": True,
                        "trigger": "pending_rule_exposure",
                        "hs6_code": response.hs6_code,
                        "exporter": request.exporter,
                        "importer": request.importer,
                        "rule_status": rule_status,
                        "case_id": request.case_id,
                    },
                }
            )

        if tariff_result is None:
            specs.append(
                {
                    "alert_type": AlertTypeEnum.DATA_QUALITY_ISSUE,
                    "entity_type": "corridor",
                    "entity_key": corridor_key,
                    "related_case_id": case_id,
                    "severity": AlertSeverityEnum.MEDIUM,
                    "alert_status": AlertStatusEnum.OPEN,
                    "alert_message": (
                        f"No tariff schedule coverage was resolved for HS6 {response.hs6_code} "
                        f"on corridor {request.exporter}->{request.importer} in {request.year}."
                    ),
                    "alert_payload": {
                        "advisory_only": True,
                        "trigger": "missing_schedule_coverage",
                        "hs6_code": response.hs6_code,
                        "exporter": request.exporter,
                        "importer": request.importer,
                        "assessment_year": request.year,
                        "case_id": request.case_id,
                    },
                }
            )

        corridor_status = self._normalize_value(corridor_overlay.status_type)
        if corridor_status == "not_yet_operational":
            specs.append(
                {
                    "alert_type": AlertTypeEnum.CORRIDOR_RISK_CHANGED,
                    "entity_type": "corridor",
                    "entity_key": corridor_key,
                    "related_case_id": case_id,
                    "severity": AlertSeverityEnum.CRITICAL,
                    "alert_status": AlertStatusEnum.OPEN,
                    "alert_message": (
                        f"Corridor {request.exporter}->{request.importer} for HS6 {response.hs6_code} "
                        "is not yet operational."
                    ),
                    "alert_payload": {
                        "advisory_only": True,
                        "trigger": "corridor_not_operational",
                        "hs6_code": response.hs6_code,
                        "exporter": request.exporter,
                        "importer": request.importer,
                        "corridor_status": corridor_status,
                        "case_id": request.case_id,
                    },
                }
            )

        return specs

    @staticmethod
    def _has_matching_active_alert(
        active_alerts: Sequence[Mapping[str, Any]],
        alert_type: AlertTypeEnum,
    ) -> bool:
        """Return True when an open or acknowledged alert of the same type already exists."""

        return any(
            IntelligenceService._normalize_value(alert.get("alert_type")) == alert_type.value
            for alert in active_alerts
        )

    @staticmethod
    def _normalize_value(value: Any) -> str:
        """Convert enum-backed values into their stored lowercase representation."""

        if value is None:
            return ""
        return str(getattr(value, "value", value)).lower()

    @staticmethod
    def _uuid_or_none(value: str | None) -> UUID | None:
        """Parse optional UUID strings for related case ids."""

        if value is None:
            return None
        return UUID(str(value))
