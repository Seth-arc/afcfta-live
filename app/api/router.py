"""Root API router for versioned endpoint registration."""

from fastapi import APIRouter

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
api_router.include_router(cases.router)
api_router.include_router(assessments.router)
api_router.include_router(audit.router)
api_router.include_router(evidence.router)
api_router.include_router(rules.router)
api_router.include_router(sources.router)
api_router.include_router(tariffs.router)
api_router.include_router(intelligence.router)
