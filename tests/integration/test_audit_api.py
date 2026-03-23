"""Integration tests for the audit API endpoints backed by persisted evaluations."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.db.base import get_async_session_factory
from app.repositories.cases_repository import CasesRepository
from app.repositories.evaluations_repository import EvaluationsRepository
from tests.integration.test_quick_slice_e2e import (
    _assessment_payload,
    _best_effort_pass_facts,
    _cth_pass_facts,
    _fact_payload,
    _require_candidate,
    _select_supported_candidate,
)


pytestmark = pytest.mark.integration


async def _create_case_with_facts(
    *,
    hs6_code: str,
    exporter: str,
    importer: str,
    facts: dict,
) -> str:
    """Create a live case row with typed facts for audit replay tests."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        cases_repository = CasesRepository(session)
        case_id = await cases_repository.create_case(
            {
                "case_external_ref": f"IT-AUDIT-{uuid4()}",
                "persona_mode": "exporter",
                "exporter_state": exporter,
                "importer_state": importer,
                "hs_code": hs6_code,
                "hs_version": "HS2017",
                "declared_origin": exporter,
                "submission_status": "submitted",
                "title": "Integration audit API test case",
                "created_by": "pytest",
                "updated_by": "pytest",
            }
        )
        await cases_repository.add_facts(
            case_id,
            [_fact_payload(fact_key, value) for fact_key, value in facts.items()],
        )
        await session.commit()
        return case_id


def _evaluation_payload(
    *,
    case_id: str,
    evaluation_date: date,
    overall_outcome: str = "eligible",
    pathway_used: str | None = "CTH",
    confidence_class: str = "complete",
    rule_status_at_evaluation: str = "agreed",
    tariff_status_at_evaluation: str = "in_force",
) -> dict[str, object]:
    """Build one evaluation row for direct history-order assertions."""

    return {
        "case_id": case_id,
        "evaluation_date": evaluation_date,
        "overall_outcome": overall_outcome,
        "pathway_used": pathway_used,
        "confidence_class": confidence_class,
        "rule_status_at_evaluation": rule_status_at_evaluation,
        "tariff_status_at_evaluation": tariff_status_at_evaluation,
    }


@pytest.mark.asyncio
async def test_create_case_accepts_production_facts_and_returns_nested_case_contract(
    async_client: AsyncClient,
) -> None:
    """POST /cases should accept production_facts and return the declared nested case response."""

    external_ref = f"IT-CASE-{uuid4()}"
    response = await async_client.post(
        "/api/v1/cases",
        json={
            "case_external_ref": external_ref,
            "persona_mode": "exporter",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "declared_origin": "GHA",
            "title": "Case creation contract test",
            "production_facts": [
                _fact_payload("wholly_obtained", True),
                _fact_payload("direct_transport", True),
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert set(body) == {"case_id", "case"}
    assert body["case_id"] == body["case"]["case_id"]
    assert body["case"]["case_external_ref"] == external_ref
    assert body["case"]["persona_mode"] == "exporter"
    assert body["case"]["exporter_state"] == "GHA"
    assert body["case"]["importer_state"] == "NGA"
    assert body["case"]["hs_code"] == "110311"
    assert "hs6_code" not in body

    detail_response = await async_client.get(f"/api/v1/cases/{body['case_id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail_body = detail_response.json()
    assert [fact["fact_key"] for fact in detail_body["facts"]] == [
        "direct_transport",
        "wholly_obtained",
    ]


@pytest.mark.asyncio
async def test_get_evaluation_audit_trail_returns_full_persisted_trace(
    async_client: AsyncClient,
) -> None:
    """One persisted assessment should be fully replayable through the audit endpoint."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported audit candidate with an executable WO, CTH, or VNM pathway was found.",
    )
    facts = _best_effort_pass_facts(candidate)
    case_id = await _create_case_with_facts(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=facts,
    )

    assessment_response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=candidate["hs6_code"],
                exporter=candidate["exporter"],
                importer=candidate["importer"],
                facts=facts,
            ),
            "case_id": case_id,
        },
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()

    history_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert history_response.status_code == 200, history_response.text
    history_body = history_response.json()
    assert len(history_body) >= 1

    evaluation_id = history_body[0]["evaluation_id"]
    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()

    assert trail_body["evaluation"]["evaluation_id"] == evaluation_id
    assert trail_body["evaluation"]["case_id"] == case_id
    assert trail_body["case"]["case_id"] == case_id
    assert trail_body["hs6_resolved"]["hs6_code"] == candidate["hs6_code"]
    assert trail_body["psr_rule"] is not None
    assert trail_body["tariff_outcome"] is not None
    assert trail_body["evidence_readiness"] is not None
    assert trail_body["final_decision"]["eligible"] == assessment_body["eligible"]
    assert trail_body["final_decision"]["pathway_used"] == assessment_body["pathway_used"]
    assert len(trail_body["original_input_facts"]) >= len(facts)

    check_types = {check["check_type"] for check in trail_body["atomic_checks"]}
    assert {
        "classification",
        "rule",
        "psr",
        "pathway",
        "general_rule",
        "status",
        "tariff",
        "evidence",
        "decision",
    }.issubset(check_types)


@pytest.mark.asyncio
async def test_list_case_evaluations_returns_newest_first(async_client: AsyncClient) -> None:
    """The case history endpoint should return persisted evaluations ordered newest first."""

    facts = {
        "tariff_heading_input": "9999",
        "tariff_heading_output": "1103",
        "non_originating_inputs": [{"hs4_code": "9999", "hs6_code": "999900"}],
        "output_hs6_code": "110311",
        "direct_transport": True,
        "cumulation_claimed": False,
    }
    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts=facts,
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        evaluations_repository = EvaluationsRepository(session)
        first = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2024, 1, 1),
                overall_outcome="not_eligible",
                confidence_class="incomplete",
                pathway_used=None,
            ),
            [],
        )
        second = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2025, 1, 1),
                overall_outcome="eligible",
                confidence_class="complete",
                pathway_used="CTH",
            ),
            [],
        )
        await session.commit()

    response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert response.status_code == 200, response.text
    body = response.json()

    assert [item["evaluation_id"] for item in body[:2]] == [
        str(second["evaluation"]["evaluation_id"]),
        str(first["evaluation"]["evaluation_id"]),
    ]
    assert [item["evaluation_date"] for item in body[:2]] == ["2025-01-01", "2024-01-01"]
    assert all(item["case_id"] == case_id for item in body[:2])


@pytest.mark.asyncio
async def test_get_latest_case_audit_trail_returns_newest_persisted_evaluation(
    async_client: AsyncClient,
) -> None:
    """Latest-by-case replay should return the newest stored evaluation without requiring evaluation_id."""

    facts = {
        "tariff_heading_input": "9999",
        "tariff_heading_output": "1103",
        "non_originating_inputs": [{"hs4_code": "9999", "hs6_code": "999900"}],
        "output_hs6_code": "110311",
        "direct_transport": True,
        "cumulation_claimed": False,
    }
    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts=facts,
    )

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        evaluations_repository = EvaluationsRepository(session)
        older = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2024, 1, 1),
                overall_outcome="not_eligible",
                confidence_class="incomplete",
                pathway_used=None,
            ),
            [],
        )
        newer = await evaluations_repository.persist_evaluation(
            _evaluation_payload(
                case_id=case_id,
                evaluation_date=date(2025, 1, 1),
                overall_outcome="eligible",
                confidence_class="complete",
                pathway_used="CTH",
            ),
            [],
        )
        await session.commit()

    response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["evaluation"]["evaluation_id"] == str(newer["evaluation"]["evaluation_id"])
    assert body["evaluation"]["evaluation_id"] != str(older["evaluation"]["evaluation_id"])
    assert body["evaluation"]["case_id"] == case_id


@pytest.mark.asyncio
async def test_special_cth_facts_round_trip_through_assessment_and_audit_replay(
    async_client: AsyncClient,
) -> None:
    """List-based CTH inputs should persist from assessment submission through audit replay."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("CTH",),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "CMR"),),
            require_corridors=(("GHA", "CMR"),),
        ),
        "No stable CTH audit replay candidate was found for special fact coverage.",
    )
    facts = _cth_pass_facts(candidate["hs6_code"], candidate["heading"])
    case_id = await _create_case_with_facts(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=facts,
    )

    response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=candidate["hs6_code"],
                exporter=candidate["exporter"],
                importer=candidate["importer"],
                facts=facts,
            ),
            "case_id": case_id,
        },
    )
    assert response.status_code == 200, response.text

    history_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert history_response.status_code == 200, history_response.text
    evaluation_id = history_response.json()[0]["evaluation_id"]

    trail_response = await async_client.get(f"/api/v1/audit/evaluations/{evaluation_id}")
    assert trail_response.status_code == 200, trail_response.text
    trail_body = trail_response.json()

    facts_by_key = {
        item["fact_key"]: item
        for item in trail_body["original_input_facts"]
    }
    assert facts_by_key["non_originating_inputs"]["fact_value_type"] == "list"
    assert facts_by_key["non_originating_inputs"]["fact_value_json"] == facts[
        "non_originating_inputs"
    ]
    assert facts_by_key["output_hs6_code"]["fact_value_type"] == "text"
    assert facts_by_key["output_hs6_code"]["fact_value_text"] == facts["output_hs6_code"]
    assert any(
        check["check_code"] in {"HEADING_NE_OUTPUT", "SUBHEADING_NE_OUTPUT"}
        for check in trail_body["atomic_checks"]
    )


@pytest.mark.asyncio
async def test_case_assessment_endpoint_matches_direct_assessment_response(
    async_client: AsyncClient,
) -> None:
    """Assessing by stored case_id should reuse the same logic and return the same decision shape."""

    candidate = _require_candidate(
        await _select_supported_candidate(
            require_component_types=("WO", "CTH", "VNM"),
            preferred_hs6_codes=("110311",),
            preferred_corridors=(("GHA", "NGA"), ("CMR", "NGA")),
        ),
        "No supported assess-by-case candidate with an executable WO, CTH, or VNM pathway was found.",
    )
    facts = _best_effort_pass_facts(candidate)
    case_id = await _create_case_with_facts(
        hs6_code=candidate["hs6_code"],
        exporter=candidate["exporter"],
        importer=candidate["importer"],
        facts=facts,
    )

    direct_response = await async_client.post(
        "/api/v1/assessments",
        json={
            **_assessment_payload(
                hs6_code=candidate["hs6_code"],
                exporter=candidate["exporter"],
                importer=candidate["importer"],
                facts=facts,
            ),
            "case_id": case_id,
        },
    )
    assert direct_response.status_code == 200, direct_response.text

    case_response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025},
    )
    assert case_response.status_code == 200, case_response.text

    direct_body = direct_response.json()
    case_body = case_response.json()

    assert case_body == direct_body

    history_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/evaluations")
    assert history_response.status_code == 200, history_response.text
    history_body = history_response.json()
    assert len(history_body) >= 2
    assert all(item["case_id"] == case_id for item in history_body[:2])


@pytest.mark.asyncio
async def test_failed_case_backed_assessment_persists_and_replays_immediately(
    async_client: AsyncClient,
) -> None:
    """A failed assess-by-case run should still persist evaluation and be replayable immediately."""

    case_id = await _create_case_with_facts(
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        facts={"direct_transport": True},
    )

    assessment_response = await async_client.post(
        f"/api/v1/assessments/cases/{case_id}",
        json={"year": 2025},
    )
    assert assessment_response.status_code == 200, assessment_response.text
    assessment_body = assessment_response.json()
    assert assessment_body["eligible"] is False
    assert "MISSING_CORE_FACTS" in assessment_body["failures"]

    latest_response = await async_client.get(f"/api/v1/audit/cases/{case_id}/latest")
    assert latest_response.status_code == 200, latest_response.text
    latest_body = latest_response.json()

    assert latest_body["evaluation"]["case_id"] == case_id
    assert latest_body["final_decision"]["eligible"] is False
    assert "MISSING_CORE_FACTS" in latest_body["final_decision"]["failure_codes"]
    assert latest_body["evaluation"]["overall_outcome"] == "insufficient_information"