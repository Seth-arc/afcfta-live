"""Unit tests for case routes with mocked repositories and services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.deps import (
    get_assessment_eligibility_service,
    get_audit_service,
    get_cases_repository,
)
from app.core.enums import (
    CaseSubmissionStatusEnum,
    FactSourceTypeEnum,
    FactValueTypeEnum,
    PersonaModeEnum,
    RuleStatusEnum,
)
from app.schemas.assessments import EligibilityAssessmentResponse, TariffOutcomeResponse


def _case_row() -> dict[str, object]:
    return {
        "case_id": uuid4(),
        "case_external_ref": "CASE-001",
        "persona_mode": PersonaModeEnum.EXPORTER,
        "exporter_state": "GHA",
        "importer_state": "NGA",
        "hs_code": "110311",
        "hs_version": "HS2017",
        "declared_origin": "GHA",
        "declared_pathway": "CTH",
        "submission_status": CaseSubmissionStatusEnum.SUBMITTED,
        "title": "Test case",
        "notes": "Pytest case",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


def _fact_row(case_id) -> dict[str, object]:
    return {
        "fact_id": uuid4(),
        "case_id": case_id,
        "fact_type": "direct_transport",
        "fact_key": "direct_transport",
        "fact_value_type": FactValueTypeEnum.BOOLEAN,
        "fact_value_boolean": True,
        "source_type": FactSourceTypeEnum.USER_INPUT,
        "source_reference": None,
        "fact_order": 1,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


def _assessment_response() -> EligibilityAssessmentResponse:
    return EligibilityAssessmentResponse(
        hs6_code="110311",
        eligible=True,
        pathway_used="CTH",
        rule_status=RuleStatusEnum.AGREED,
        tariff_outcome=TariffOutcomeResponse(
            preferential_rate="0.0000",
            base_rate="15.0000",
            status="in_force",
        ),
        failures=[],
        missing_facts=[],
        evidence_required=["certificate_of_origin"],
        missing_evidence=[],
        readiness_score=1.0,
        completeness_ratio=1.0,
        confidence_class="complete",
        audit_persisted=True,
    )


@pytest.mark.asyncio
async def test_create_case_without_assessment_persists_case_and_facts(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())
    case_row = _case_row()
    case_row["case_id"] = case_id
    fact_row = _fact_row(case_id)

    class FakeCasesRepository:
        def __init__(self) -> None:
            self.create_case_calls: list[dict[str, object]] = []
            self.add_facts_calls: list[tuple[str, list[dict[str, object]]]] = []
            self.session = SimpleNamespace(commit=pytest.fail)

        async def create_case(self, payload: dict[str, object]) -> str:
            self.create_case_calls.append(payload)
            return case_id

        async def add_facts(self, created_case_id: str, facts: list[dict[str, object]]) -> None:
            self.add_facts_calls.append((created_case_id, facts))

        async def get_case_with_facts(self, requested_case_id: str) -> dict[str, object]:
            assert requested_case_id == case_id
            return {"case": case_row, "facts": [fact_row]}

    repo = FakeCasesRepository()

    async def override_cases_repository() -> FakeCasesRepository:
        return repo

    app.dependency_overrides[get_cases_repository] = override_cases_repository

    try:
        response = await async_client.post(
            "/api/v1/cases",
            json={
                "case_external_ref": "CASE-001",
                "persona_mode": "exporter",
                "exporter_state": "GHA",
                "importer_state": "NGA",
                "hs6_code": "110311",
                "assessment": None,
                "production_facts": [
                    {
                        "fact_type": "direct_transport",
                        "fact_key": "direct_transport",
                        "fact_value_type": "boolean",
                        "fact_value_boolean": True,
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(get_cases_repository, None)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["case_id"] == case_id
    assert body["evaluation_id"] is None
    assert body["audit_url"] is None
    assert body["audit_persisted"] is False
    assert repo.create_case_calls
    assert repo.add_facts_calls[0][0] == case_id


@pytest.mark.asyncio
async def test_create_case_with_assessment_commits_and_sets_replay_headers(
    app: FastAPI,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())
    case_row = _case_row()
    case_row["case_id"] = case_id
    fact_row = _fact_row(case_id)
    rate_limit_calls: list[tuple[object, object]] = []
    commit_calls: list[str] = []
    assess_calls: list[tuple[str, object]] = []

    class FakeCasesRepository:
        def __init__(self) -> None:
            self.session = SimpleNamespace(commit=self._commit)

        async def _commit(self) -> None:
            commit_calls.append("commit")

        async def create_case(self, payload: dict[str, object]) -> str:
            return case_id

        async def add_facts(self, created_case_id: str, facts: list[dict[str, object]]) -> None:
            assert created_case_id == case_id
            assert len(facts) == 1

        async def get_case_with_facts(self, requested_case_id: str) -> dict[str, object]:
            assert requested_case_id == case_id
            return {"case": case_row, "facts": [fact_row]}

    class FakeEligibilityService:
        async def assess_interface_case(self, requested_case_id: str, payload) -> object:
            assess_calls.append((requested_case_id, payload))
            return SimpleNamespace(
                case_id=case_id,
                evaluation_id=evaluation_id,
                response=_assessment_response(),
            )

    async def fake_rate_limit(request, settings) -> None:
        rate_limit_calls.append((request, settings))

    @asynccontextmanager
    async def fake_context():
        yield FakeEligibilityService()

    monkeypatch.setattr("app.api.v1.cases.require_assessment_rate_limit", fake_rate_limit)
    monkeypatch.setattr("app.api.v1.cases.assessment_eligibility_service_context", fake_context)

    async def override_cases_repository() -> FakeCasesRepository:
        return FakeCasesRepository()

    app.dependency_overrides[get_cases_repository] = override_cases_repository

    try:
        response = await async_client.post(
            "/api/v1/cases",
            json={
                "case_external_ref": "CASE-001",
                "persona_mode": "exporter",
                "exporter_state": "GHA",
                "importer_state": "NGA",
                "hs6_code": "110311",
                "assess": True,
                "assessment": {
                    "year": 2025,
                    "submitted_documents": ["certificate_of_origin"],
                },
                "production_facts": [
                    {
                        "fact_type": "direct_transport",
                        "fact_key": "direct_transport",
                        "fact_value_type": "boolean",
                        "fact_value_boolean": True,
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(get_cases_repository, None)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["evaluation_id"] == evaluation_id
    assert body["audit_url"] == f"/api/v1/audit/evaluations/{evaluation_id}"
    assert body["audit_persisted"] is True
    assert response.headers["X-AIS-Case-Id"] == case_id
    assert response.headers["X-AIS-Evaluation-Id"] == evaluation_id
    assert response.headers["X-AIS-Audit-URL"] == f"/api/v1/audit/evaluations/{evaluation_id}"
    assert len(rate_limit_calls) == 1
    assert commit_calls == ["commit"]
    assert assess_calls[0][0] == case_id
    assert assess_calls[0][1].existing_documents == ["certificate_of_origin"]


@pytest.mark.asyncio
async def test_create_case_returns_not_found_if_case_bundle_missing_after_creation(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())

    class FakeCasesRepository:
        def __init__(self) -> None:
            self.session = SimpleNamespace(commit=lambda: None)

        async def create_case(self, payload: dict[str, object]) -> str:
            return case_id

        async def add_facts(self, created_case_id: str, facts: list[dict[str, object]]) -> None:
            return None

        async def get_case_with_facts(self, requested_case_id: str):
            return None

    async def override_cases_repository() -> FakeCasesRepository:
        return FakeCasesRepository()

    app.dependency_overrides[get_cases_repository] = override_cases_repository

    try:
        response = await async_client.post(
            "/api/v1/cases",
            json={
                "case_external_ref": "CASE-404",
                "persona_mode": "exporter",
                "production_facts": [],
            },
        )
    finally:
        app.dependency_overrides.pop(get_cases_repository, None)

    assert response.status_code == 404, response.text
    assert response.json()["error"]["details"]["case_id"] == case_id


@pytest.mark.asyncio
async def test_get_case_with_facts_returns_encoded_case_bundle(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())
    case_row = _case_row()
    case_row["case_id"] = case_id
    fact_row = _fact_row(case_id)

    class FakeCasesRepository:
        async def get_case_with_facts(self, requested_case_id: str) -> dict[str, object]:
            assert requested_case_id == case_id
            return {"case": case_row, "facts": [fact_row]}

    async def override_cases_repository() -> FakeCasesRepository:
        return FakeCasesRepository()

    app.dependency_overrides[get_cases_repository] = override_cases_repository

    try:
        response = await async_client.get(f"/api/v1/cases/{case_id}")
    finally:
        app.dependency_overrides.pop(get_cases_repository, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["case"]["case_id"] == case_id
    assert body["facts"][0]["case_id"] == case_id
    assert body["facts"][0]["fact_key"] == "direct_transport"


@pytest.mark.asyncio
async def test_get_case_with_facts_returns_404_for_missing_case(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())

    class FakeCasesRepository:
        async def get_case_with_facts(self, requested_case_id: str):
            assert requested_case_id == case_id
            return None

    async def override_cases_repository() -> FakeCasesRepository:
        return FakeCasesRepository()

    app.dependency_overrides[get_cases_repository] = override_cases_repository

    try:
        response = await async_client.get(f"/api/v1/cases/{case_id}")
    finally:
        app.dependency_overrides.pop(get_cases_repository, None)

    assert response.status_code == 404, response.text
    assert response.json()["error"]["details"]["case_id"] == case_id


@pytest.mark.asyncio
async def test_case_assess_route_sets_replay_headers(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())

    class FakeEligibilityService:
        async def assess_interface_case(self, requested_case_id: str, payload) -> object:
            assert requested_case_id == case_id
            assert payload.year == 2025
            assert payload.existing_documents == ["certificate_of_origin"]
            return SimpleNamespace(
                case_id=case_id,
                evaluation_id=evaluation_id,
                response=_assessment_response(),
            )

    async def override_service() -> FakeEligibilityService:
        return FakeEligibilityService()

    app.dependency_overrides[get_assessment_eligibility_service] = override_service

    try:
        response = await async_client.post(
            f"/api/v1/cases/{case_id}/assess",
            json={"year": 2025, "submitted_documents": ["certificate_of_origin"]},
        )
    finally:
        app.dependency_overrides.pop(get_assessment_eligibility_service, None)

    assert response.status_code == 200, response.text
    assert response.headers["X-AIS-Case-Id"] == case_id
    assert response.headers["X-AIS-Evaluation-Id"] == evaluation_id
    assert response.json()["audit_persisted"] is True


@pytest.mark.asyncio
async def test_latest_case_audit_route_delegates_to_audit_service(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    case_id = str(uuid4())
    evaluation_id = str(uuid4())
    audit_trail = {
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

    class FakeAuditService:
        async def get_latest_decision_trace(self, requested_case_id: str) -> dict[str, object]:
            assert requested_case_id == case_id
            return audit_trail

    async def override_audit_service() -> FakeAuditService:
        return FakeAuditService()

    app.dependency_overrides[get_audit_service] = override_audit_service

    try:
        response = await async_client.get(f"/api/v1/cases/{case_id}/latest")
    finally:
        app.dependency_overrides.pop(get_audit_service, None)

    assert response.status_code == 200, response.text
    assert response.json()["evaluation"]["evaluation_id"] == evaluation_id
