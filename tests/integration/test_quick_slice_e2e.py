"""Quick Slice end-to-end integration tests against the live assessment API."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


def _fact_payload(fact_key: str, value: Any) -> dict[str, Any]:
    """Convert a simple fact mapping into the API's CaseFactIn payload shape."""

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
    *,
    hs6_code: str,
    exporter: str,
    importer: str,
    facts: dict[str, Any],
    year: int = 2025,
    persona_mode: str = "exporter",
) -> dict[str, Any]:
    """Build a live POST /api/v1/assessments payload."""

    return {
        "hs6_code": hs6_code,
        "hs_version": "HS2017",
        "exporter": exporter,
        "importer": importer,
        "year": year,
        "persona_mode": persona_mode,
        "production_facts": [
            _fact_payload(fact_key, value) for fact_key, value in facts.items()
        ],
    }


def _assert_response_shape(body: dict[str, Any]) -> None:
    """Assert the core response shape aligns with the acceptance fixture contract."""

    assert set(body).issuperset(
        {
            "hs6_code",
            "eligible",
            "pathway_used",
            "rule_status",
            "tariff_outcome",
            "failures",
            "missing_facts",
            "evidence_required",
            "confidence_class",
        }
    )


@pytest.mark.asyncio
async def test_quick_slice_wo_pass(async_client: AsyncClient) -> None:
    """WO should pass for live animals when wholly obtained is declared."""

    payload = _assessment_payload(
        hs6_code="010121",
        exporter="GHA",
        importer="CMR",
        facts={
            "wholly_obtained": True,
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "WO" in body["pathway_used"]
    assert body["confidence_class"] == "complete"


@pytest.mark.asyncio
async def test_quick_slice_cth_pass(async_client: AsyncClient) -> None:
    """CTH should pass for 110311 when the input heading differs from output."""

    payload = _assessment_payload(
        hs6_code="110311",
        exporter="GHA",
        importer="CMR",
        facts={
            "tariff_heading_input": "1001",
            "tariff_heading_output": "1103",
            "non_originating_inputs": [{"hs4_code": "1001", "hs6_code": "100190"}],
            "output_hs6_code": "110311",
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "CTH" in body["pathway_used"]


@pytest.mark.asyncio
async def test_quick_slice_cth_fail_no_tariff_shift(async_client: AsyncClient) -> None:
    """CTH should fail when the input heading matches the output heading."""

    payload = _assessment_payload(
        hs6_code="110311",
        exporter="GHA",
        importer="CMR",
        facts={
            "tariff_heading_input": "1103",
            "tariff_heading_output": "1103",
            "non_originating_inputs": [{"hs4_code": "1103", "hs6_code": "110311"}],
            "output_hs6_code": "110311",
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is False
    assert body["failures"]


@pytest.mark.asyncio
async def test_quick_slice_vnm_pass(async_client: AsyncClient) -> None:
    """VNM should pass when non-originating content is under the seeded threshold."""

    payload = _assessment_payload(
        hs6_code="721049",
        exporter="GHA",
        importer="CMR",
        facts={
            "ex_works": 10000,
            "non_originating": 5000,
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "VNM" in body["pathway_used"]


@pytest.mark.asyncio
async def test_quick_slice_or_fallback_to_vnm(async_client: AsyncClient) -> None:
    """When CTH fails for 180631, the engine should fall through to the VNM pathway."""

    payload = _assessment_payload(
        hs6_code="180631",
        exporter="CMR",
        importer="GHA",
        facts={
            "tariff_heading_input": "1806",
            "tariff_heading_output": "1806",
            "non_originating_inputs": [{"hs4_code": "1806", "hs6_code": "180631"}],
            "output_hs6_code": "180631",
            "ex_works": 10000,
            "non_originating": 5000,
            "direct_transport": True,
            "cumulation_claimed": False,
        },
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["eligible"] is True
    assert body["pathway_used"] is not None and "VNM" in body["pathway_used"]


@pytest.mark.asyncio
async def test_quick_slice_missing_facts(async_client: AsyncClient) -> None:
    """Missing production facts should return an incomplete assessment."""

    payload = _assessment_payload(
        hs6_code="110311",
        exporter="GHA",
        importer="CMR",
        facts={},
    )

    response = await async_client.post("/api/v1/assessments", json=payload)

    assert response.status_code == 200
    body = response.json()
    _assert_response_shape(body)
    assert body["missing_facts"]
    assert body["confidence_class"] == "incomplete"