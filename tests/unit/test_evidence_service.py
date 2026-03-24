"""Unit tests for evidence readiness scoring and persona-aware filtering."""

from __future__ import annotations

import asyncio
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


def build_question(question_text: str, *, persona_mode: str) -> dict[str, object]:
    """Build a minimal verification question row mapping."""

    return {
        "question_text": question_text,
        "persona_mode": persona_mode,
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
    )

    repository.get_requirements.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-123",
        persona_mode="officer",
    )
    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="hs6_rule",
        entity_key="HS6_RULE:psr-123",
        risk_category=None,
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
async def test_build_readiness_uses_non_temporal_repository_contract() -> None:
    """Evidence readiness should stay date-agnostic until the schema adds date windows."""

    repository = AsyncMock(spec=EvidenceRepository)
    repository.get_requirements.return_value = []
    repository.get_verification_questions.return_value = []
    service = EvidenceService(repository)

    await service.build_readiness(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-999",
        persona_mode="exporter",
        existing_documents=[],
    )

    repository.get_requirements.assert_awaited_once_with(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-999",
        persona_mode="exporter",
    )
    repository.get_verification_questions.assert_awaited_once_with(
        entity_type="pathway",
        entity_key="PATHWAY:pathway-999",
        risk_category=None,
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
