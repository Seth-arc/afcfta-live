"""Thin route handlers for case creation and retrieval."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder

from app.api.deps import get_cases_repository
from app.repositories.cases_repository import CasesRepository
from app.schemas.cases import CaseCreateRequest, CaseCreateResponse

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
        [fact.model_dump(by_alias=True) for fact in payload.facts],
    )
    return CaseCreateResponse(
        case_id=case_id,
        case_external_ref=payload.case_external_ref,
        hs6_code=payload.hs6_code,
        exporter_state=payload.exporter_state,
        importer_state=payload.importer_state,
    )


@router.get("/cases/{case_id}")
async def get_case_with_facts(
    case_id: str,
    cases_repository: CasesRepository = Depends(get_cases_repository),
) -> dict[str, Any]:
    """Return the case header and all persisted facts for a case_id."""

    case_bundle = await cases_repository.get_case_with_facts(case_id)
    if case_bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' was not found",
        )

    return {
        "case": jsonable_encoder(dict(case_bundle["case"])),
        "facts": jsonable_encoder([dict(fact) for fact in case_bundle["facts"]]),
    }
