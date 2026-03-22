"""Root API router for versioned endpoint registration."""

from fastapi import APIRouter

from app.api.v1 import health, rules, tariffs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(rules.router)
api_router.include_router(tariffs.router)
