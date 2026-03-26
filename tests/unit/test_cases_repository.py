"""Unit tests for CasesRepository normalization and retrieval branches."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.repositories.cases_repository import CasesRepository

from ._repo_fakes import FakeResult, RecordingSession


async def test_create_case_normalizes_hs6_code_and_returns_case_id() -> None:
    case_id = uuid4()
    session = RecordingSession([FakeResult(scalar_one_value=case_id)])
    repository = CasesRepository(session)

    created = await repository.create_case(
        {
            "case_external_ref": "CASE-001",
            "hs6_code": "110311",
            "notes": None,
        }
    )

    assert created == str(case_id)
    statement, _ = session.calls[0]
    compiled = str(statement)
    assert "hs_code" in compiled


async def test_add_facts_returns_empty_list_when_no_facts_supplied() -> None:
    repository = CasesRepository(RecordingSession([]))

    assert await repository.add_facts(str(uuid4()), []) == []


async def test_add_facts_normalizes_defaults_and_returns_fact_ids() -> None:
    fact_ids = [uuid4(), uuid4()]
    session = RecordingSession([FakeResult(scalar_all_values=fact_ids)])
    repository = CasesRepository(session)

    created = await repository.add_facts(
        str(uuid4()),
        [
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
                "source_ref": "source-ref-1",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": Decimal("12.5"),
            },
        ],
    )

    assert created == [str(fact_id) for fact_id in fact_ids]
    statement, _ = session.calls[0]
    compiled = str(statement)
    assert "source_reference" in compiled


async def test_get_case_with_facts_returns_none_when_case_missing() -> None:
    session = RecordingSession([FakeResult(first_mapping=None)])
    repository = CasesRepository(session)

    assert await repository.get_case_with_facts(str(uuid4())) is None


async def test_get_case_with_facts_returns_case_and_ordered_facts() -> None:
    case_row = {"case_id": uuid4()}
    fact_row = {"fact_id": uuid4()}
    session = RecordingSession(
        [
            FakeResult(first_mapping=case_row),
            FakeResult(all_mappings=[fact_row]),
        ]
    )
    repository = CasesRepository(session)

    result = await repository.get_case_with_facts(str(case_row["case_id"]))

    assert result == {"case": case_row, "facts": [fact_row]}
