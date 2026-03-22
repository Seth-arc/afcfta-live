"""Thin route handlers for evidence readiness lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_evidence_service
from app.schemas.evidence import EvidenceReadinessRequest, EvidenceReadinessResult
from app.services.evidence_service import EvidenceService

router = APIRouter()


@router.post("/evidence/readiness", response_model=EvidenceReadinessResult)
async def get_evidence_readiness(
    payload: EvidenceReadinessRequest,
    evidence_service: EvidenceService = Depends(get_evidence_service),
) -> EvidenceReadinessResult:
    """Return the evidence readiness summary for one entity/persona combination."""

    return await evidence_service.get_readiness(
        entity_type=payload.entity_type,
        entity_key=payload.entity_key,
        persona_mode=payload.persona_mode,
        existing_documents=payload.existing_documents,
    )
