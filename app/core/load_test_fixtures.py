"""Shared steady-state assessment fixtures for load testing and seed data."""

from __future__ import annotations

from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5

LOAD_FIXTURE_CREATED_BY = "seed_data/load_fixtures"


def _case_id(slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"afcfta-live/load-case/{slug}"))


def _fixture(
    *,
    slug: str,
    hs6_code: str,
    exporter: str,
    importer: str,
    year: int,
    existing_documents: list[str],
    production_facts: list[dict[str, object]],
) -> dict[str, object]:
    case_id = _case_id(slug)
    return {
        "slug": slug,
        "case_id": case_id,
        "case_external_ref": f"LOAD-{slug.upper()}",
        "request": {
            "case_id": case_id,
            "hs6_code": hs6_code,
            "hs_version": "HS2017",
            "exporter": exporter,
            "importer": importer,
            "year": year,
            "persona_mode": "exporter",
            "existing_documents": existing_documents,
            "production_facts": production_facts,
        },
    }


def _replicate_fixtures(
    base_fixtures: list[dict[str, object]],
    *,
    replicas_per_fixture: int,
) -> list[dict[str, object]]:
    """Expand a small scenario set into a larger deterministic case pool."""

    expanded: list[dict[str, object]] = []
    for replica_index in range(replicas_per_fixture):
        suffix = f"-r{replica_index + 1:02d}"
        for fixture in base_fixtures:
            slug = f"{fixture['slug']}{suffix}"
            case_id = _case_id(slug)
            request_payload = deepcopy(fixture["request"])
            request_payload["case_id"] = case_id
            expanded.append(
                {
                    "slug": slug,
                    "case_id": case_id,
                    "case_external_ref": f"LOAD-{slug.upper()}",
                    "request": request_payload,
                }
            )
    return expanded


_BASE_LOAD_TEST_FIXTURES: list[dict[str, object]] = [
    _fixture(
        slug="gha-nga-110311-cth-pass",
        hs6_code="110311",
        exporter="GHA",
        importer="NGA",
        year=2025,
        existing_documents=["certificate_of_origin", "invoice"],
        production_facts=[
            {
                "fact_type": "tariff_heading_input",
                "fact_key": "tariff_heading_input",
                "fact_value_type": "text",
                "fact_value_text": "1001",
            },
            {
                "fact_type": "tariff_heading_output",
                "fact_key": "tariff_heading_output",
                "fact_value_type": "text",
                "fact_value_text": "1103",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    ),
    _fixture(
        slug="cmr-nga-271019-vnm-pass",
        hs6_code="271019",
        exporter="CMR",
        importer="NGA",
        year=2025,
        existing_documents=["certificate_of_origin"],
        production_facts=[
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": "100000",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": "55000",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    ),
    _fixture(
        slug="civ-nga-080111-wo-pass",
        hs6_code="080111",
        exporter="CIV",
        importer="NGA",
        year=2025,
        existing_documents=["certificate_of_origin"],
        production_facts=[
            {
                "fact_type": "wholly_obtained",
                "fact_key": "wholly_obtained",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    ),
    _fixture(
        slug="sen-nga-290110-vnm-pass",
        hs6_code="290110",
        exporter="SEN",
        importer="NGA",
        year=2025,
        existing_documents=["certificate_of_origin", "supplier_declaration"],
        production_facts=[
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": "100000",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": "35000",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    ),
    _fixture(
        slug="cmr-nga-271019-vnm-fail",
        hs6_code="271019",
        exporter="CMR",
        importer="NGA",
        year=2025,
        existing_documents=[],
        production_facts=[
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": "100000",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": "65000",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    ),
]


LOAD_TEST_FIXTURES: list[dict[str, object]] = _replicate_fixtures(
    _BASE_LOAD_TEST_FIXTURES,
    replicas_per_fixture=20,
)
