"""Unit tests for thin public routes not otherwise exercised by unit coverage."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import (
    get_audit_service,
    get_classification_service,
    get_evidence_service,
    get_rule_resolution_service,
    get_tariff_resolution_service,
)
from app.core.enums import HsLevelEnum, PersonaModeEnum, RuleStatusEnum
from app.schemas.evaluations import EligibilityEvaluationResponse
from app.schemas.health import PoolStats
from app.schemas.rules import PSRRuleResolvedOut, RuleResolutionResult
from app.schemas.tariffs import TariffResolutionResult


def _audit_trail(case_id: str, evaluation_id: str) -> dict[str, object]:
    return {
        "evaluation": {
            "evaluation_id": evaluation_id,
            "case_id": case_id,
            "evaluation_date": "2025-01-01",
            "overall_outcome": "eligible",
            "pathway_used": "CTH",
            "confidence_class": "complete",
            "rule_status_at_evaluation": "agreed",
            "tariff_status_at_evaluation": "in_force",
        },
        "case": {
            "case_id": case_id,
            "case_external_ref": "CASE-001",
            "persona_mode": "exporter",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "hs_code": "110311",
            "hs_version": "HS2017",
            "submission_status": "submitted",
        },
        "original_input_facts": [],
        "atomic_checks": [],
        "final_decision": {
            "eligible": True,
            "overall_outcome": "eligible",
            "pathway_used": "CTH",
            "rule_status": "agreed",
            "tariff_status": "in_force",
            "confidence_class": "complete",
            "failure_codes": [],
            "missing_facts": [],
            "missing_evidence": [],
            "provenance": {"rule": None, "tariff": None},
        },
    }


@pytest.mark.asyncio
async def test_audit_routes_delegate_to_audit_service(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())

    class FakeAuditService:
        async def get_decision_trace(self, *, evaluation_id: str) -> dict[str, object]:
            return _audit_trail(case_id, evaluation_id)

        async def get_evaluations_for_case(self, case_id: str) -> list[EligibilityEvaluationResponse]:
            return [
                EligibilityEvaluationResponse(
                    evaluation_id=uuid4(),
                    case_id=uuid4(),
                    evaluation_date=date(2025, 1, 1),
                    overall_outcome="eligible",
                    pathway_used="CTH",
                    confidence_class="complete",
                    rule_status_at_evaluation="agreed",
                    tariff_status_at_evaluation="in_force",
                )
            ]

        async def get_latest_decision_trace(self, case_id: str) -> dict[str, object]:
            return _audit_trail(case_id, evaluation_id)

    async def override_audit_service() -> FakeAuditService:
        return FakeAuditService()

    app.dependency_overrides[get_audit_service] = override_audit_service

    try:
        trace_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
        list_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
        latest_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")
    finally:
        app.dependency_overrides.pop(get_audit_service, None)

    assert trace_response.status_code == 200, trace_response.text
    assert trace_response.json()["evaluation"]["evaluation_id"] == evaluation_id
    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()) == 1
    assert latest_response.status_code == 200, latest_response.text
    assert latest_response.json()["evaluation"]["evaluation_id"] == evaluation_id


@pytest.mark.asyncio
async def test_rules_route_resolves_product_and_returns_flat_rule_payload(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    rule = PSRRuleResolvedOut.model_validate(
        {
            "psr_id": uuid4(),
            "source_id": uuid4(),
            "hs_version": "HS2017",
            "hs6_code": "110311",
            "hs_level": HsLevelEnum.SUBHEADING,
            "rule_scope": "subheading",
            "product_description": "Groats and meal",
            "legal_rule_text_verbatim": "CTH",
            "legal_rule_text_normalized": "CTH",
            "rule_status": RuleStatusEnum.AGREED,
            "page_ref": 1,
            "table_ref": "T1",
            "row_ref": "R1",
        }
    )
    bundle = RuleResolutionResult(
        psr_rule=rule,
        components=[],
        pathways=[],
        applicability_type="direct",
    )

    class FakeClassificationService:
        async def resolve_hs6(self, hs6: str, hs_version: str) -> object:
            assert hs6 == "11031100"
            assert hs_version == "HS2017"
            return SimpleNamespace(hs6_id=uuid4(), hs_version="HS2017", hs6_code="110311")

    class FakeRuleResolutionService:
        async def resolve_rule_bundle(self, hs_version: str, hs6_code: str) -> RuleResolutionResult:
            assert hs_version == "HS2017"
            assert hs6_code == "110311"
            return bundle

    async def override_classification() -> FakeClassificationService:
        return FakeClassificationService()

    async def override_rules() -> FakeRuleResolutionService:
        return FakeRuleResolutionService()

    app.dependency_overrides[get_classification_service] = override_classification
    app.dependency_overrides[get_rule_resolution_service] = override_rules

    try:
        response = await async_client.get("/api/v1/rules/11031100")
    finally:
        app.dependency_overrides.pop(get_classification_service, None)
        app.dependency_overrides.pop(get_rule_resolution_service, None)

    assert response.status_code == 200, response.text
    assert response.json()["hs6_code"] == "110311"
    assert response.json()["rule_status"] == "agreed"


@pytest.mark.asyncio
async def test_tariff_and_evidence_routes_delegate_to_services(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    class FakeTariffResolutionService:
        async def resolve(self, **kwargs) -> TariffResolutionResult:
            assert kwargs["exporter_country"] == "GHA"
            assert kwargs["importer_country"] == "NGA"
            return TariffResolutionResult(
                hs6_code="110311",
                exporter="GHA",
                importer="NGA",
                year=2025,
                preferential_rate="0.0000",
                base_rate="15.0000",
                rate_status="in_force",
                schedule_status="official",
                tariff_status="in_force",
                rule_status="agreed",
            )

    class FakeEvidenceService:
        async def get_readiness(self, **kwargs):
            assert kwargs["entity_type"] == "hs6_rule"
            assert kwargs["entity_key"] == "HS6_RULE:test"
            assert kwargs["persona_mode"] == PersonaModeEnum.EXPORTER
            return {
                "required_items": ["certificate_of_origin"],
                "missing_items": [],
                "verification_questions": ["Can you provide the certificate?"],
                "readiness_score": 1.0,
                "completeness_ratio": 1.0,
            }

    async def override_tariff_service() -> FakeTariffResolutionService:
        return FakeTariffResolutionService()

    async def override_evidence_service() -> FakeEvidenceService:
        return FakeEvidenceService()

    app.dependency_overrides[get_tariff_resolution_service] = override_tariff_service
    app.dependency_overrides[get_evidence_service] = override_evidence_service

    try:
        tariff_response = await async_client.get(
            "/api/v1/tariffs",
            params={"exporter": "GHA", "importer": "NGA", "hs6": "110311", "year": 2025},
        )
        evidence_response = await async_client.post(
            "/api/v1/evidence/readiness",
            json={
                "entity_type": "hs6_rule",
                "entity_key": "HS6_RULE:test",
                "persona_mode": "exporter",
                "existing_documents": ["certificate_of_origin"],
            },
        )
    finally:
        app.dependency_overrides.pop(get_tariff_resolution_service, None)
        app.dependency_overrides.pop(get_evidence_service, None)

    assert tariff_response.status_code == 200, tariff_response.text
    assert tariff_response.json()["preferential_rate"] == "0.0000"
    assert evidence_response.status_code == 200, evidence_response.text
    assert evidence_response.json()["verification_questions"] == ["Can you provide the certificate?"]


def test_pool_stats_schema_accepts_valid_pressure_values() -> None:
    stats = PoolStats(
        checked_out=1,
        pool_size=5,
        overflow=0,
        checked_in=4,
        pool_pressure="ok",
    )

    assert stats.pool_pressure == "ok"
