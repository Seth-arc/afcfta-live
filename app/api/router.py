"""Root API router for versioned endpoint registration."""

from fastapi import APIRouter, Depends

from app.api.deps import (
	require_authenticated_principal,
	require_default_rate_limit,
)
from app.api.v1 import (
	assessments,
	audit,
	cases,
	evidence,
	health,
	intelligence,
	rules,
	sources,
	tariffs,
)

api_router = APIRouter()
api_router.include_router(health.router)

protected_router = APIRouter(
	dependencies=[
		Depends(require_authenticated_principal),
		Depends(require_default_rate_limit),
	]
)
protected_router.include_router(cases.router)
protected_router.include_router(audit.router)
protected_router.include_router(evidence.router)
protected_router.include_router(rules.router)
protected_router.include_router(sources.router)
protected_router.include_router(tariffs.router)
protected_router.include_router(intelligence.router)

assessment_router = APIRouter(
	dependencies=[Depends(require_authenticated_principal)]
)
assessment_router.include_router(assessments.router)

api_router.include_router(protected_router)
api_router.include_router(assessment_router)
