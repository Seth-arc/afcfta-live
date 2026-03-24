"""Integration tests for persisted eligibility evaluations and check rows."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_async_session_factory
from app.repositories.cases_repository import CasesRepository
from app.repositories.evaluations_repository import EvaluationsRepository


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def repositories() -> AsyncIterator[
    tuple[AsyncSession, CasesRepository, EvaluationsRepository]
]:
    """Provide a live session with the repositories under test."""

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session, CasesRepository(session), EvaluationsRepository(session)


async def _create_case(
    session: AsyncSession,
    cases_repository: CasesRepository,
) -> str:
    """Create one unique case row suitable for evaluation persistence tests."""

    case_id = await cases_repository.create_case(
        {
            "case_external_ref": f"IT-EVAL-{uuid4()}",
            "persona_mode": "exporter",
            "exporter_state": "GHA",
            "importer_state": "NGA",
            "hs_code": "110311",
            "hs_version": "HS2017",
            "declared_origin": "GHA",
            "declared_pathway": "CTH",
            "submission_status": "submitted",
            "title": "Integration evaluation repository test case",
            "created_by": "pytest",
            "updated_by": "pytest",
        }
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
    """Build one evaluation insert payload."""

    return {
        "case_id": case_id,
        "evaluation_date": evaluation_date,
        "overall_outcome": overall_outcome,
        "pathway_used": pathway_used,
        "confidence_class": confidence_class,
        "rule_status_at_evaluation": rule_status_at_evaluation,
        "tariff_status_at_evaluation": tariff_status_at_evaluation,
    }


def _check_payload(
    *,
    check_type: str,
    check_code: str,
    passed: bool,
    severity: str,
    explanation: str,
    expected_value: str | None = None,
    observed_value: str | None = None,
    details_json: dict | None = None,
) -> dict[str, object]:
    """Build one atomic check insert payload."""

    return {
        "check_type": check_type,
        "check_code": check_code,
        "passed": passed,
        "severity": severity,
        "expected_value": expected_value,
        "observed_value": observed_value,
        "explanation": explanation,
        "details_json": details_json,
    }


@pytest.mark.asyncio
async def test_persist_evaluation_inserts_evaluation_and_atomic_checks(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Persisting an evaluation should insert the header row and all check rows atomically."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)

    result = await evaluations_repository.persist_evaluation(
        _evaluation_payload(case_id=case_id, evaluation_date=date(2025, 1, 1)),
        [
            _check_payload(
                check_type="psr",
                check_code="CTH",
                passed=True,
                severity="info",
                explanation="CTH pathway passed.",
                details_json={"pathway_code": "CTH"},
            ),
            _check_payload(
                check_type="status",
                check_code="STATUS_OVERLAY",
                passed=True,
                severity="info",
                explanation="Status overlay resolved.",
                details_json={"status_type": "agreed"},
            ),
        ],
    )
    await session.commit()

    assert result["evaluation"] is not None
    assert len(result["checks"]) == 2
    assert str(result["evaluation"]["case_id"]) == case_id
    assert getattr(result["evaluation"]["overall_outcome"], "value", result["evaluation"]["overall_outcome"]) == "eligible"
    assert {str(check["check_code"]) for check in result["checks"]} == {"CTH", "STATUS_OVERLAY"}


@pytest.mark.asyncio
async def test_get_evaluation_with_checks_returns_checks_ordered_by_code_with_same_insert_batch(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Evaluation replay should return stored check rows in repository order."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)
    persisted = await evaluations_repository.persist_evaluation(
        _evaluation_payload(case_id=case_id, evaluation_date=date(2025, 1, 2)),
        [
            _check_payload(
                check_type="status",
                check_code="STATUS_OVERLAY",
                passed=True,
                severity="info",
                explanation="Status resolved.",
            ),
            _check_payload(
                check_type="blocker",
                check_code="CORE_FACTS_PRESENT",
                passed=True,
                severity="minor",
                explanation="Core facts were available.",
            ),
        ],
    )
    await session.commit()

    bundle = await evaluations_repository.get_evaluation_with_checks(
        str(persisted["evaluation"]["evaluation_id"])
    )

    assert bundle is not None
    assert str(bundle["evaluation"]["evaluation_id"]) == str(
        persisted["evaluation"]["evaluation_id"]
    )
    assert [str(check["check_code"]) for check in bundle["checks"]] == [
        "CORE_FACTS_PRESENT",
        "STATUS_OVERLAY",
    ]


@pytest.mark.asyncio
async def test_get_evaluations_for_case_returns_newest_first(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Case history lookup should return evaluations newest first."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)
    first = await evaluations_repository.persist_evaluation(
        _evaluation_payload(
            case_id=case_id,
            evaluation_date=date(2025, 1, 1),
            overall_outcome="not_eligible",
            confidence_class="incomplete",
            rule_status_at_evaluation="pending",
            tariff_status_at_evaluation="provisional",
        ),
        [],
    )
    second = await evaluations_repository.persist_evaluation(
        _evaluation_payload(
            case_id=case_id,
            evaluation_date=date(2025, 1, 3),
            overall_outcome="eligible",
        ),
        [],
    )
    await session.commit()

    evaluations = await evaluations_repository.get_evaluations_for_case(case_id)

    assert len(evaluations) >= 2
    assert str(evaluations[0]["evaluation_id"]) == str(second["evaluation"]["evaluation_id"])
    assert str(evaluations[1]["evaluation_id"]) == str(first["evaluation"]["evaluation_id"])
    assert evaluations[0]["evaluation_date"] >= evaluations[1]["evaluation_date"]


@pytest.mark.asyncio
async def test_get_latest_evaluation_for_case_returns_newest_row(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Latest-evaluation lookup should return only the newest stored row for a case."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)
    await evaluations_repository.persist_evaluation(
        _evaluation_payload(
            case_id=case_id,
            evaluation_date=date(2025, 1, 1),
            overall_outcome="not_eligible",
        ),
        [],
    )
    newest = await evaluations_repository.persist_evaluation(
        _evaluation_payload(
            case_id=case_id,
            evaluation_date=date(2025, 1, 7),
            overall_outcome="eligible",
        ),
        [],
    )
    await session.commit()

    latest = await evaluations_repository.get_latest_evaluation_for_case(case_id)

    assert latest is not None
    assert str(latest["evaluation_id"]) == str(newest["evaluation"]["evaluation_id"])
    assert latest["evaluation_date"] == date(2025, 1, 7)


@pytest.mark.asyncio
async def test_get_evaluation_with_checks_returns_none_for_missing_id(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Missing evaluation ids should return None rather than raising."""

    _, _, evaluations_repository = repositories

    bundle = await evaluations_repository.get_evaluation_with_checks(str(uuid4()))

    assert bundle is None


@pytest.mark.asyncio
async def test_persist_evaluation_with_no_checks_returns_empty_check_list(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Persisting an evaluation without check rows should still succeed cleanly."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)

    result = await evaluations_repository.persist_evaluation(
        _evaluation_payload(case_id=case_id, evaluation_date=date(2025, 1, 4)),
        [],
    )
    await session.commit()

    assert result["evaluation"] is not None
    assert result["checks"] == []
    assert str(result["evaluation"]["case_id"]) == case_id


@pytest.mark.asyncio
async def test_add_facts_accepts_mixed_value_types_in_one_batch(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Case fact inserts should support heterogeneous typed values in one batch."""

    session, cases_repository, _ = repositories
    case_id = await _create_case(session, cases_repository)

    fact_ids = await cases_repository.add_facts(
        case_id,
        [
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": 10000,
            },
            {
                "fact_type": "non_originating_inputs",
                "fact_key": "non_originating_inputs",
                "fact_value_type": "list",
                "fact_value_json": [{"hs4_code": "9999", "hs6_code": "999900"}],
            },
            {
                "fact_type": "output_hs6_code",
                "fact_key": "output_hs6_code",
                "fact_value_type": "text",
                "fact_value_text": "110311",
            },
        ],
    )
    await session.commit()

    bundle = await cases_repository.get_case_with_facts(case_id)

    assert len(fact_ids) == 4
    assert bundle is not None
    stored_fact_keys = {fact["fact_key"] for fact in bundle["facts"]}
    assert {
        "direct_transport",
        "ex_works",
        "non_originating_inputs",
        "output_hs6_code",
    }.issubset(stored_fact_keys)


@pytest.mark.asyncio
async def test_persist_evaluation_accepts_mixed_check_shapes_in_one_batch(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Audit persistence should support checks with and without optional detail fields together."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)

    result = await evaluations_repository.persist_evaluation(
        _evaluation_payload(case_id=case_id, evaluation_date=date(2025, 1, 5)),
        [
            _check_payload(
                check_type="classification",
                check_code="HS6_RESOLUTION",
                passed=True,
                severity="info",
                explanation="HS6 classification resolved.",
                details_json={"product": {"hs6_code": "110311"}},
            ),
            _check_payload(
                check_type="status",
                check_code="STATUS_OVERLAY",
                passed=True,
                severity="info",
                explanation="Status overlay resolved.",
            ),
        ],
    )
    await session.commit()

    assert len(result["checks"]) == 2
    assert {str(check["check_code"]) for check in result["checks"]} == {
        "HS6_RESOLUTION",
        "STATUS_OVERLAY",
    }
    assert {str(check["check_type"]) for check in result["checks"]} == {
        "classification",
        "status",
    }


@pytest.mark.asyncio
async def test_persist_evaluation_rolls_back_header_when_check_batch_fails(
    repositories: tuple[AsyncSession, CasesRepository, EvaluationsRepository],
) -> None:
    """Evaluation persistence should remain atomic when a later check row normalization fails."""

    session, cases_repository, evaluations_repository = repositories
    case_id = await _create_case(session, cases_repository)

    with pytest.raises(KeyError):
        await evaluations_repository.persist_evaluation(
            _evaluation_payload(case_id=case_id, evaluation_date=date(2025, 1, 8)),
            [
                {
                    "check_code": "BROKEN_ROW",
                    "passed": False,
                    "severity": "major",
                    "explanation": "This malformed row should abort the transaction.",
                }
            ],
        )

    await session.rollback()
    evaluations = await evaluations_repository.get_evaluations_for_case(case_id)
    assert evaluations == []