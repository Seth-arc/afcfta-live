"""Thin route handlers for persisted evaluation-trace retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_audit_service
from app.schemas.audit import AuditTrail
from app.schemas.evaluations import EligibilityEvaluationResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/audit/evaluations/{evaluation_id}", response_model=AuditTrail)
async def get_evaluation_audit_trail(
    evaluation_id: str,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditTrail:
    """Return the full decision trace for one persisted evaluation id."""

    return await audit_service.get_decision_trace(evaluation_id=evaluation_id)


@router.get(
    "/audit/cases/{case_id}/evaluations",
    response_model=list[EligibilityEvaluationResponse],
)
async def list_case_evaluations(
    case_id: str,
    audit_service: AuditService = Depends(get_audit_service),
) -> list[EligibilityEvaluationResponse]:
    """Return all persisted evaluations stored for one case id."""

    return await audit_service.get_evaluations_for_case(case_id)


@router.get("/audit/cases/{case_id}/latest", response_model=AuditTrail)
async def get_latest_case_audit_trail(
    case_id: str,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditTrail:
    """Compatibility alias for GET /api/v1/cases/{case_id}/latest."""

    return await audit_service.get_latest_decision_trace(case_id)
