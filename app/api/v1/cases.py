"""Thin route handlers for case creation, retrieval, and case-owned orchestration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.encoders import jsonable_encoder

from app.api.deps import (
    get_assessment_eligibility_service,
    get_audit_service,
    get_cases_repository,
    require_assessment_rate_limit,
)
from app.core.exceptions import CaseNotFoundError
from app.repositories.cases_repository import CasesRepository
from app.schemas.assessments import CaseAssessmentRequest, EligibilityAssessmentResponse
from app.schemas.audit import AuditTrail
from app.schemas.cases import (
    CaseCreateRequest,
    CaseCreateResponse,
    CaseDetailResponse,
    CaseSummaryResponse,
)
from app.services.audit_service import AuditService
from app.services.eligibility_service import EligibilityService

router = APIRouter()
assessment_router = APIRouter(dependencies=[Depends(require_assessment_rate_limit)])


def _set_replay_headers(response: Response, *, case_id: str, evaluation_id: str) -> None:
    """Attach deterministic replay identifiers to one assessment response."""

    response.headers["X-AIS-Case-Id"] = case_id
    response.headers["X-AIS-Evaluation-Id"] = evaluation_id
    response.headers["X-AIS-Audit-URL"] = f"/api/v1/audit/evaluations/{evaluation_id}"


@router.post("/cases", response_model=CaseCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreateRequest,
    cases_repository: CasesRepository = Depends(get_cases_repository),
) -> CaseCreateResponse:
    """Create a case_file row plus its submitted production facts."""

    case_id = await cases_repository.create_case(payload.model_dump(by_alias=True))
    await cases_repository.add_facts(
        case_id,
        [fact.model_dump(by_alias=True) for fact in payload.production_facts],
    )
    case_bundle = await cases_repository.get_case_with_facts(case_id)
    if case_bundle is None:
        raise CaseNotFoundError(
            f"Case '{case_id}' was not found after creation",
            detail={"case_id": case_id},
        )

    return CaseCreateResponse(
        case_id=case_id,
        case=CaseSummaryResponse.model_validate(case_bundle["case"]),
    )


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_with_facts(
    case_id: str,
    cases_repository: CasesRepository = Depends(get_cases_repository),
) -> CaseDetailResponse:
    """Return the case header and all persisted facts for a case_id."""

    case_bundle = await cases_repository.get_case_with_facts(case_id)
    if case_bundle is None:
        raise CaseNotFoundError(
            f"Case '{case_id}' was not found",
            detail={"case_id": case_id},
        )

    encoded_bundle = {
        "case": jsonable_encoder(dict(case_bundle["case"])),
        "facts": jsonable_encoder([dict(fact) for fact in case_bundle["facts"]]),
    }
    return CaseDetailResponse.model_validate(encoded_bundle)


@assessment_router.post(
    "/cases/{case_id}/assess",
    response_model=EligibilityAssessmentResponse,
)
async def assess_stored_case(
    case_id: str,
    payload: CaseAssessmentRequest,
    response: Response,
    eligibility_service: EligibilityService = Depends(get_assessment_eligibility_service),
) -> EligibilityAssessmentResponse:
    """Run the deterministic engine for one persisted case via the case resource."""

    assessment = await eligibility_service.assess_interface_case(case_id, payload)
    _set_replay_headers(
        response,
        case_id=assessment.case_id,
        evaluation_id=assessment.evaluation_id,
    )
    return assessment.response


@router.get("/cases/{case_id}/latest", response_model=AuditTrail)
async def get_latest_case_audit_trail(
    case_id: str,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditTrail:
    """Return the latest persisted audit replay for one case via the case resource."""

    return await audit_service.get_latest_decision_trace(case_id)
