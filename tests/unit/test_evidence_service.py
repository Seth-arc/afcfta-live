"""Unit tests for evidence readiness scoring and persona-aware filtering."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.evidence import EvidenceReadinessRequest, EvidenceReadinessResult
from app.services.evidence_service import EvidenceService


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
