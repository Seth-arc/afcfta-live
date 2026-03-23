"""Thin route handlers for case creation and retrieval."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder

from app.api.deps import get_cases_repository
from app.core.exceptions import CaseNotFoundError
from app.repositories.cases_repository import CasesRepository
from app.schemas.cases import CaseCreateRequest, CaseCreateResponse, CaseDetailResponse, CaseSummaryResponse

router = APIRouter()


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
