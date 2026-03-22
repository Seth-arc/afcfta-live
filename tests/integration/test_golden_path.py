"""Golden-path integration tests against the live assessment API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from httpx import AsyncClient

from tests.fixtures.golden_cases import GOLDEN_CASES

pytestmark = pytest.mark.integration


def _golden_case(name_fragment: str) -> dict[str, Any]:
    """Return one golden case by a stable name fragment."""

    for case in GOLDEN_CASES:
        if name_fragment in case["name"]:
            return case
    raise AssertionError(f"Golden case not found for fragment: {name_fragment}")


def _fact_payload(fact_key: str, value: Any) -> dict[str, Any]:
    """Convert one golden-case fact into the API's CaseFactIn payload shape."""

    payload: dict[str, Any] = {
        "fact_type": fact_key,
        "fact_key": fact_key,
    }
    if isinstance(value, bool):
        payload["fact_value_type"] = "boolean"
        payload["fact_value_boolean"] = value
        return payload
    if isinstance(value, int | float):
        payload["fact_value_type"] = "number"
        payload["fact_value_number"] = value
        return payload
    if isinstance(value, list):
        payload["fact_value_type"] = "list"
        payload["fact_value_json"] = value
        return payload
    if isinstance(value, dict):
        payload["fact_value_type"] = "json"
        payload["fact_value_json"] = value
        return payload

    payload["fact_value_type"] = "text"
    payload["fact_value_text"] = value
    return payload


def _assessment_payload(
    case: Mapping[str, Any],
    *,
    persona_mode: str = "exporter",
) -> dict[str, Any]:
    """Transform one golden-case fixture into the live POST /assessments payload."""

    case_input = case["input"]
    return {
        "hs6_code": case_input["hs6_code"],
        "hs_version": case_input["hs_version"],
        "exporter": case_input["exporter"],
        "importer": case_input["importer"],
        "year": case_input["year"],
        "persona_mode": persona_mode,
        "production_facts": [
            _fact_payload(fact_key, value) for fact_key, value in case_input["facts"].items()
        ],
    }


@pytest.mark.asyncio
async def test_eligible_cth_pass(async_client: AsyncClient) -> None:
    """Golden case: GHA->NGA groats qualifies under a CTH pathway."""

    case = _golden_case("groats CTH pass")
    response = await async_client.post("/api/v1/assessments", json=_assessment_payload(case))

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert "CTH" in body["pathway_used"]
    assert body["rule_status"] == "agreed"


@pytest.mark.asyncio
async def test_ineligible_cth_fail(async_client: AsyncClient) -> None:
    """Golden case: same-heading input should fail the CTH rule."""

    case = _golden_case("groats CTH fail")
    response = await async_client.post("/api/v1/assessments", json=_assessment_payload(case))

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is False
    assert "FAIL_CTH_NOT_MET" in body["failures"]


@pytest.mark.asyncio
async def test_eligible_vnm_pass(async_client: AsyncClient) -> None:
    """Golden case: petroleum qualifies when VNM stays within the threshold."""

    case = _golden_case("petroleum VNM pass")
    response = await async_client.post("/api/v1/assessments", json=_assessment_payload(case))

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert "VNM" in body["pathway_used"]


@pytest.mark.asyncio
async def test_ineligible_vnm_fail(async_client: AsyncClient) -> None:
    """Golden case: petroleum fails when VNM exceeds the threshold."""

    case = _golden_case("petroleum VNM fail")
    response = await async_client.post("/api/v1/assessments", json=_assessment_payload(case))

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is False
    assert "FAIL_VNM_EXCEEDED" in body["failures"]


@pytest.mark.asyncio
async def test_missing_facts_incomplete(async_client: AsyncClient) -> None:
    """Golden case: missing source facts should yield an incomplete assessment."""

    case = _golden_case("Missing facts")
    response = await async_client.post("/api/v1/assessments", json=_assessment_payload(case))

    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is False
    assert body["missing_facts"]
    assert body["confidence_class"] == "incomplete"


@pytest.mark.asyncio
async def test_provisional_status(async_client: AsyncClient) -> None:
    """Golden case: provisional rules should downgrade confidence for the outcome."""

    case = _golden_case("Provisional rule status")
    response = await async_client.post("/api/v1/assessments", json=_assessment_payload(case))

    assert response.status_code == 200
    body = response.json()
    assert body["rule_status"] == "provisional" or body["confidence_class"] == "provisional"
