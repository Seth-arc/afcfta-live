"""Unit tests for EvaluationsRepository atomic persistence and replay lookups."""

from __future__ import annotations

from uuid import uuid4

from app.repositories.evaluations_repository import EvaluationsRepository

from ._repo_fakes import FakeResult, RecordingSession


async def test_atomic_scope_uses_begin_when_not_already_in_transaction() -> None:
    session = RecordingSession([], in_transaction=False)
    repository = EvaluationsRepository(session)

    async with repository._atomic_scope():
        pass

    assert session.events == ["enter:begin", "exit:begin"]


async def test_atomic_scope_uses_begin_nested_inside_existing_transaction() -> None:
    session = RecordingSession([], in_transaction=True)
    repository = EvaluationsRepository(session)

    async with repository._atomic_scope():
        pass

    assert session.events == ["enter:begin_nested", "exit:begin_nested"]


async def test_persist_evaluation_inserts_evaluation_and_checks() -> None:
    evaluation_row = {"evaluation_id": uuid4(), "case_id": uuid4()}
    check_row = {"check_result_id": uuid4(), "evaluation_id": evaluation_row["evaluation_id"]}
    session = RecordingSession(
        [
            FakeResult(),
            FakeResult(one_mapping=evaluation_row),
            FakeResult(all_mappings=[check_row]),
        ]
    )
    repository = EvaluationsRepository(session)

    result = await repository.persist_evaluation(
        {
            "case_id": evaluation_row["case_id"],
            "overall_outcome": "eligible",
            "pathway_used": "CTH",
            "confidence_class": "complete",
            "rule_status_at_evaluation": "agreed",
            "tariff_status_at_evaluation": "in_force",
        },
        [
            {
                "check_type": "rule",
                "check_code": "PSR_RESOLUTION",
                "passed": True,
                "severity": "info",
                "explanation": "resolved",
            }
        ],
    )

    assert result == {"evaluation": evaluation_row, "checks": [check_row]}
    assert session.events == ["enter:begin", "exit:begin"]
    assert len(session.calls) == 3


async def test_persist_evaluation_skips_check_insert_when_no_checks() -> None:
    evaluation_row = {"evaluation_id": uuid4(), "case_id": uuid4()}
    session = RecordingSession(
        [
            FakeResult(),
            FakeResult(one_mapping=evaluation_row),
        ]
    )
    repository = EvaluationsRepository(session)

    result = await repository.persist_evaluation(
        {
            "case_id": evaluation_row["case_id"],
            "overall_outcome": "eligible",
            "confidence_class": "complete",
            "rule_status_at_evaluation": "agreed",
            "tariff_status_at_evaluation": "in_force",
        },
        [],
    )

    assert result == {"evaluation": evaluation_row, "checks": []}
    assert len(session.calls) == 2


async def test_get_evaluation_with_checks_returns_none_when_missing() -> None:
    session = RecordingSession([FakeResult(first_mapping=None)])
    repository = EvaluationsRepository(session)

    assert await repository.get_evaluation_with_checks(str(uuid4())) is None


async def test_get_evaluation_with_checks_returns_evaluation_and_checks() -> None:
    evaluation_row = {"evaluation_id": uuid4()}
    check_row = {"check_result_id": uuid4()}
    session = RecordingSession(
        [
            FakeResult(first_mapping=evaluation_row),
            FakeResult(all_mappings=[check_row]),
        ]
    )
    repository = EvaluationsRepository(session)

    result = await repository.get_evaluation_with_checks(str(evaluation_row["evaluation_id"]))

    assert result == {"evaluation": evaluation_row, "checks": [check_row]}


async def test_evaluation_list_queries_return_rows() -> None:
    evaluation_row = {"evaluation_id": uuid4()}
    latest_row = {"evaluation_id": uuid4()}
    session = RecordingSession(
        [
            FakeResult(all_mappings=[evaluation_row]),
            FakeResult(first_mapping=latest_row),
        ]
    )
    repository = EvaluationsRepository(session)

    assert await repository.get_evaluations_for_case(str(uuid4())) == [evaluation_row]
    assert await repository.get_latest_evaluation_for_case(str(uuid4())) == latest_row
