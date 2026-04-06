"""Unit tests for evidence readiness scoring and persona-aware filtering."""

from __future__ import annotations

import asyncio
from datetime import date
import logging
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.evidence import EvidenceReadinessRequest, EvidenceReadinessResult
from app.services.evidence_service import EvidenceService

# ---------------------------------------------------------------------------
# Strategies for property tests
# ---------------------------------------------------------------------------

# Domain-relevant document type identifiers mirroring real seed data.
_DOC_TYPES = [
    "certificate_of_origin",
    "invoice",
    "bill_of_lading",
    "supplier_declaration",
    "packing_list",
    "inspection_record",
    "customs_declaration",
    "laboratory_analysis",
]

_ASSESSMENT_DATE = date(2025, 1, 1)

# A single required evidence requirement row.
_requirement_strategy = st.fixed_dictionaries(
    {
        "requirement_type": st.sampled_from(_DOC_TYPES),
        "requirement_description": st.just("A required document"),
        "persona_mode": st.just("system"),  # "system" is visible to all personas
        "required": st.just(True),
    }
)


def _run_readiness(
    requirements: list[dict],
    documents: list[str],
    persona_mode: str = "exporter",
    confidence_class: str | None = None,
) -> EvidenceReadinessResult:
    """Run the async build_readiness call synchronously inside a property test."""

    async def _inner() -> EvidenceReadinessResult:
        repo = AsyncMock(spec=EvidenceRepository)
        repo.get_requirements.return_value = requirements
        repo.get_verification_questions.return_value = []
        return await EvidenceService(repo).build_readiness(
            entity_type="hs6_rule",
            entity_key="HS6_RULE:prop-test",
            persona_mode=persona_mode,
            existing_documents=documents,
            confidence_class=confidence_class,
            assessment_date=_ASSESSMENT_DATE,
        )

    return asyncio.run(_inner())


def build_requirement(
    requirement_type: str,
    description: str,
    *,
    persona_mode: str,
    required: bool = True,
) -> dict[str, object]:
    """Build a minimal evidence requirement row mapping."""

    return {
        "requirement_type": requirement_type,
        "requirement_description": description,
        "persona_mode": persona_mode,
        "required": required,
    }


def build_question(
    question_text: str,
    *,
    persona_mode: str,
    risk_category: str = "general",
) -> dict[str, object]:
    """Build a minimal verification question row mapping."""

    return {
        "question_text": question_text,
        "persona_mode": persona_mode,
        "risk_category": risk_category,
    }


@pytest.mark.asyncio
async def test_build_readiness_officer_has_more_requirements_than_exporter() -> None:
    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = [
        build_requirement(
            "certificate_of_origin",
            "Certificate of origin",
            persona_mode="system",
        ),
        build_requirement(
            "inspection_record",
            "Inspection record",
            persona_mode="officer",
        ),
    ]
    repository.get_verification_questions.return_value = [
        build_question("Has the origin claim been reviewed?", persona_mode="officer"),
        build_question("System baseline question", persona_mode="system"),
        build_question("Exporter-only question", persona_mode="exporter"),
    ]
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-123",
        persona_mode="officer",
        existing_documents=["certificate_of_origin"],
        assessment_date=_ASSESSMENT_DATE,
    )

    repository.get_requirements.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-123",
        persona_mode="officer",
        as_of_date=_ASSESSMENT_DATE,
    )
    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-123",
        risk_category=None,
        as_of_date=_ASSESSMENT_DATE,
    )
    assert isinstance(result, EvidenceReadinessResult)
    assert result.required_items == ["Certificate of origin", "Inspection record"]
    assert result.missing_items == ["Inspection record"]
    assert result.readiness_score == 0.5
    assert result.verification_questions == [
        "Has the origin claim been reviewed?",
        "System baseline question",
    ]


@pytest.mark.asyncio
async def test_build_readiness_exporter_has_fewer_requirements() -> None:
    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = [
        build_requirement(
            "certificate_of_origin",
            "Certificate of origin",
            persona_mode="system",
        ),
    ]
    repository.get_verification_questions.return_value = [
        build_question("Exporter declaration on file?", persona_mode="exporter"),
        build_question("Officer inspection complete?", persona_mode="officer"),
    ]
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="corridor",
        entity_key="CORRIDOR:GHA:NGA:110311",
        persona_mode="exporter",
        existing_documents=[],
    )

    assert result.required_items == ["Certificate of origin"]
    assert result.missing_items == ["Certificate of origin"]
    assert result.readiness_score == 0.0
    assert result.verification_questions == ["Exporter declaration on file?"]


@pytest.mark.asyncio
async def test_build_readiness_with_no_existing_documents_marks_all_required_missing() -> None:
    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = [
        build_requirement(
            "certificate_of_origin",
            "Certificate of origin",
            persona_mode="system",
        ),
        build_requirement(
            "supplier_declaration",
            "Supplier declaration",
            persona_mode="system",
        ),
    ]
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-123",
        persona_mode="exporter",
        existing_documents=[],
    )

    assert result.missing_items == ["Certificate of origin", "Supplier declaration"]
    assert result.readiness_score == 0.0
    assert result.completeness_ratio == 0.0


@pytest.mark.asyncio
async def test_build_readiness_with_all_documents_present_scores_one() -> None:
    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = [
        build_requirement(
            "certificate_of_origin",
            "Certificate of origin",
            persona_mode="system",
        ),
        build_requirement(
            "supplier_declaration",
            "Supplier declaration",
            persona_mode="exporter",
        ),
    ]
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-456",
        persona_mode="exporter",
        existing_documents=["certificate_of_origin", "supplier_declaration"],
    )

    assert result.missing_items == []
    assert result.readiness_score == 1.0
    assert result.completeness_ratio == 1.0


@pytest.mark.asyncio
async def test_build_readiness_with_no_requirements_returns_empty_and_complete() -> None:
    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="corridor",
        entity_key="CORRIDOR:CMR:NGA:040630",
        persona_mode="analyst",
        existing_documents=[],
    )

    assert result.required_items == []
    assert result.missing_items == []
    assert result.verification_questions == []
    assert result.readiness_score == 1.0
    assert result.completeness_ratio == 1.0


@pytest.mark.asyncio
async def test_build_readiness_without_assessment_date_emits_warning_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Callers without assessment_date keep working but must emit an explicit warning."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    with caplog.at_level(logging.WARNING, logger="app.evidence"):
        await service.build_readiness(
            entity_type="pathway",
            entity_key="PATHWAY:pathway-999",
            persona_mode="exporter",
            existing_documents=[],
            assessment_date=None,
        )

    assert (
        "evidence_service called without assessment_date — snapshot isolation relies on caller transaction boundary"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_build_readiness_passes_assessment_date_to_repository_calls() -> None:
    """The service should forward assessment_date to both repository lookups."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)
    assessment_date = date(2025, 1, 1)

    await service.build_readiness(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-999",
        persona_mode="exporter",
        existing_documents=[],
        assessment_date=assessment_date,
    )

    repository.get_requirements.assert_awaited_once_with(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-999",
        persona_mode="exporter",
        as_of_date=assessment_date,
    )
    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-999",
        risk_category=None,
        as_of_date=assessment_date,
    )


@pytest.mark.asyncio
async def test_build_readiness_for_targets_returns_first_target_with_content() -> None:
    """Batch target lookup should stop on the first target that yields actual evidence content."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_readiness_inputs_for_targets.return_value = [
        {
            "entity_type": "pathway",
            "entity_key": "PATHWAY:pathway-empty",
            "requirements": [],
            "questions": [],
        },
        {
            "entity_type": "hs6_rule",
            "entity_key": "HS6_RULE:psr-populated",
            "requirements": [
                build_requirement(
                    "certificate_of_origin",
                    "Certificate of origin",
                    persona_mode="system",
                )
            ],
            "questions": [
                build_question(
                    "Origin evidence reviewed?",
                    persona_mode="system",
                    risk_category="general",
                )
            ],
        },
    ]
    service = EvidenceService(repository)

    result = await service.build_readiness_for_targets(
        [
            ("pathway", "PATHWAY:pathway-empty"),
            ("hs6_rule", "HS6_RULE:psr-populated"),
        ],
        persona_mode="exporter",
        existing_documents=[],
        confidence_class="complete",
        assessment_date=_ASSESSMENT_DATE,
    )

    repository.get_readiness_inputs_for_targets.assert_awaited_once_with(
        [
            ("pathway", "PATHWAY:pathway-empty"),
            ("hs6_rule", "HS6_RULE:psr-populated"),
        ],
        persona_mode="exporter",
        risk_category=None,
        as_of_date=_ASSESSMENT_DATE,
    )
    assert result.required_items == ["Certificate of origin"]
    assert result.verification_questions == ["Origin evidence reviewed?"]


def build_windowed_requirement(
    requirement_type: str,
    description: str,
    *,
    persona_mode: str,
    required: bool = True,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> dict[str, object]:
    """Build a requirement row with optional effective date bounds."""

    row = build_requirement(
        requirement_type,
        description,
        persona_mode=persona_mode,
        required=required,
    )
    row["effective_from"] = effective_from
    row["effective_to"] = effective_to
    return row


class WindowFilteringRepository:
    """Fake repository that applies the same effective-date rules as the SQL layer."""

    def __init__(self, requirements: list[dict[str, object]]) -> None:
        self._requirements = requirements

    async def get_requirements(
        self,
        *,
        entity_type: str,
        entity_key: str,
        persona_mode: str,
        as_of_date: date | None = None,
    ) -> list[dict[str, object]]:
        assert entity_type == "hs6_rule"
        assert entity_key == "HS6_RULE:psr-windowed"
        assert persona_mode == "exporter"
        if as_of_date is None:
            return list(self._requirements)
        return [
            row
            for row in self._requirements
            if (row["effective_from"] is None or row["effective_from"] <= as_of_date)
            and (row["effective_to"] is None or row["effective_to"] >= as_of_date)
        ]

    async def get_verification_questions(
        self,
        *,
        entity_type: str,
        entity_key: str,
        risk_category: str | None,
        as_of_date: date | None = None,
    ) -> list[dict[str, object]]:
        assert entity_type == "hs6_rule"
        assert entity_key == "HS6_RULE:psr-windowed"
        assert risk_category is None
        return []


@pytest.mark.asyncio
async def test_build_readiness_excludes_rows_expired_before_assessment_date() -> None:
    repository = WindowFilteringRepository(
        [
            build_windowed_requirement(
                "certificate_of_origin",
                "Expired certificate of origin",
                persona_mode="system",
                effective_to=date(2024, 12, 31),
            )
        ]
    )
    service = EvidenceService(repository)  # type: ignore[arg-type]

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-windowed",
        persona_mode="exporter",
        existing_documents=[],
        assessment_date=date(2025, 1, 1),
    )

    assert result.required_items == []


@pytest.mark.asyncio
async def test_build_readiness_excludes_rows_not_yet_effective_after_assessment_date() -> None:
    repository = WindowFilteringRepository(
        [
            build_windowed_requirement(
                "supplier_declaration",
                "Future supplier declaration",
                persona_mode="system",
                effective_from=date(2025, 2, 1),
            )
        ]
    )
    service = EvidenceService(repository)  # type: ignore[arg-type]

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-windowed",
        persona_mode="exporter",
        existing_documents=[],
        assessment_date=date(2025, 1, 1),
    )

    assert result.required_items == []


@pytest.mark.asyncio
async def test_build_readiness_includes_unbounded_rows_for_any_assessment_date() -> None:
    repository = WindowFilteringRepository(
        [
            build_windowed_requirement(
                "invoice",
                "Always-valid invoice",
                persona_mode="system",
                effective_from=None,
                effective_to=None,
            )
        ]
    )
    service = EvidenceService(repository)  # type: ignore[arg-type]

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-windowed",
        persona_mode="exporter",
        existing_documents=[],
        assessment_date=date(2025, 1, 1),
    )

    assert result.required_items == ["Always-valid invoice"]
    assert result.missing_items == ["Always-valid invoice"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("confidence_class", "expected_risk"),
    [
        ("complete", None),
        ("provisional", None),
        (None, None),
    ],
)
async def test_build_readiness_skips_risk_filter_for_unfiltered_confidence_classes(
    confidence_class: str | None,
    expected_risk: str | None,
) -> None:
    """Complete and provisional confidence do not narrow verification questions by risk."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-risk",
        persona_mode="exporter",
        existing_documents=[],
        confidence_class=confidence_class,
        assessment_date=_ASSESSMENT_DATE,
    )

    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-risk",
        risk_category=expected_risk,
        as_of_date=_ASSESSMENT_DATE,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("confidence_class", "expected_risk"),
    [
        ("incomplete", "documentary_gap"),
        ("insufficient", "origin_claim"),
    ],
)
async def test_build_readiness_maps_confidence_class_to_seeded_risk_category(
    confidence_class: str,
    expected_risk: str,
) -> None:
    """Confidence classes that imply evidence risk must use the DB-backed category names."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-risk",
        persona_mode="exporter",
        existing_documents=[],
        confidence_class=confidence_class,
        assessment_date=_ASSESSMENT_DATE,
    )

    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-risk",
        risk_category=expected_risk,
        as_of_date=_ASSESSMENT_DATE,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("confidence_class", "expected_questions"),
    [
        ("incomplete", ["Documentary gap check"]),
        ("insufficient", ["Origin claim check"]),
    ],
)
async def test_build_readiness_excludes_questions_outside_resolved_risk_category(
    confidence_class: str,
    expected_questions: list[str],
) -> None:
    """The repository risk filter should remove questions from non-matching categories."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    all_questions = [
        build_question(
            "General documentary check",
            persona_mode="system",
            risk_category="general",
        ),
        build_question(
            "Documentary gap check",
            persona_mode="system",
            risk_category="documentary_gap",
        ),
        build_question(
            "Origin claim check",
            persona_mode="system",
            risk_category="origin_claim",
        ),
        build_question(
            "Valuation support check",
            persona_mode="system",
            risk_category="valuation_risk",
        ),
        build_question(
            "Officer-only documentary check",
            persona_mode="officer",
            risk_category="general",
        ),
    ]

    async def get_verification_questions(
        *,
        entity_type: str,
        entity_key: str,
        risk_category: str | None,
        as_of_date: date | None = None,
    ) -> list[dict[str, object]]:
        assert entity_type == "hs6_rule"
        assert entity_key == "HS6_RULE:psr-risk"
        assert as_of_date == _ASSESSMENT_DATE
        return [
            question
            for question in all_questions
            if risk_category is None or question["risk_category"] == risk_category
        ]

    repository.get_verification_questions.side_effect = get_verification_questions
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-risk",
        persona_mode="exporter",
        existing_documents=[],
        confidence_class=confidence_class,
        assessment_date=_ASSESSMENT_DATE,
    )

    assert result.verification_questions == expected_questions


@pytest.mark.asyncio
async def test_incomplete_confidence_routes_to_documentary_gap() -> None:
    """confidence_class='incomplete' must route get_verification_questions to documentary_gap.

    Asserts the repository is called with risk_category='documentary_gap' and that
    the returned verification_questions list is non-empty when the repository returns data.
    """
    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = [
        build_question(
            "Is the documentary evidence package complete and consistent?",
            persona_mode="officer",
            risk_category="documentary_gap",
        ),
    ]
    service = EvidenceService(repository)

    result = await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-docgap",
        persona_mode="officer",
        existing_documents=[],
        confidence_class="incomplete",
        assessment_date=_ASSESSMENT_DATE,
    )

    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-docgap",
        risk_category="documentary_gap",
        as_of_date=_ASSESSMENT_DATE,
    )
    assert result.verification_questions


@pytest.mark.asyncio
async def test_complete_confidence_skips_risk_filter() -> None:
    """confidence_class='complete' must call get_verification_questions with risk_category=None."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    await service.build_readiness(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-complete",
        persona_mode="officer",
        existing_documents=[],
        confidence_class="complete",
        assessment_date=_ASSESSMENT_DATE,
    )

    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-complete",
        risk_category=None,
        as_of_date=_ASSESSMENT_DATE,
    )


def test_evidence_readiness_request_uses_existing_documents_vocabulary() -> None:
    """Evidence request schema should keep the shared existing_documents field name."""

    request = EvidenceReadinessRequest(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-123",
        persona_mode="exporter",
        existing_documents=["certificate_of_origin"],
    )

    assert request.existing_documents == ["certificate_of_origin"]


def test_evidence_readiness_request_accepts_as_of_date_alias() -> None:
    """Evidence request schema should accept as_of_date as an input alias."""

    request = EvidenceReadinessRequest(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-123",
        persona_mode="exporter",
        as_of_date="2025-01-01",
    )

    assert request.assessment_date == date(2025, 1, 1)


# ---------------------------------------------------------------------------
# Property-based tests — readiness score invariants
# ---------------------------------------------------------------------------


@given(
    requirements=st.lists(_requirement_strategy, min_size=0, max_size=8),
    documents=st.lists(
        st.sampled_from(_DOC_TYPES + ["unrecognised_doc"]), max_size=6
    ),
)
@settings(max_examples=200)
def test_readiness_score_is_always_in_unit_interval(
    requirements: list[dict], documents: list[str]
) -> None:
    """readiness_score ∈ [0.0, 1.0] for every combination of requirements and documents.

    Catches: division by len(required_map) when the map is empty (ZeroDivisionError
    or NaN), or a provided_count that exceeds total_required due to a counting error.
    """
    result = _run_readiness(requirements, documents)
    assert 0.0 <= result.readiness_score <= 1.0


@given(
    requirements=st.lists(_requirement_strategy, min_size=0, max_size=8),
    documents=st.lists(st.sampled_from(_DOC_TYPES), max_size=6),
)
@settings(max_examples=200)
def test_readiness_score_always_equals_completeness_ratio(
    requirements: list[dict], documents: list[str]
) -> None:
    """readiness_score and completeness_ratio must be identical on every call.

    Catches: a future refactor that updates one field but forgets the other,
    or a copy-paste bug that uses a different expression for each field.
    """
    result = _run_readiness(requirements, documents)
    assert result.readiness_score == result.completeness_ratio


@given(
    requirements=st.lists(_requirement_strategy, min_size=1, max_size=6),
    base_docs=st.frozensets(st.sampled_from(_DOC_TYPES), min_size=0, max_size=3),
    extra_docs=st.frozensets(st.sampled_from(_DOC_TYPES), min_size=1, max_size=3),
)
@settings(max_examples=200)
def test_providing_more_documents_never_decreases_readiness_score(
    requirements: list[dict],
    base_docs: frozenset[str],
    extra_docs: frozenset[str],
) -> None:
    """Readiness score is monotonically non-decreasing as more documents are provided.

    Catches: a set-difference bug that computes missing items using the wrong
    operand order, causing extra documents to appear as gaps rather than
    reducing the missing count.
    """
    base_score = _run_readiness(requirements, list(base_docs)).readiness_score
    extended_score = _run_readiness(requirements, list(base_docs | extra_docs)).readiness_score
    assert extended_score >= base_score


@given(
    requirements=st.lists(_requirement_strategy, min_size=0, max_size=8),
    documents=st.lists(st.sampled_from(_DOC_TYPES), max_size=6),
)
@settings(max_examples=200)
def test_score_is_consistent_with_required_and_missing_item_counts(
    requirements: list[dict], documents: list[str]
) -> None:
    """readiness_score == (required - missing) / required, or 1.0 when required == 0.

    Catches: an off-by-one in provided_count, a double-count of duplicate
    requirement types, or a score computed from a different denominator than
    the one used to build required_items and missing_items.
    """
    result = _run_readiness(requirements, documents)
    total = len(result.required_items)
    missing = len(result.missing_items)

    if total == 0:
        assert result.readiness_score == 1.0
    else:
        expected = (total - missing) / total
        assert abs(result.readiness_score - expected) < 1e-12
