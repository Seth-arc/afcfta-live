"""Health check endpoint for service liveness."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return API liveness information."""

    settings = get_settings()
    return {"status": "ok", "version": settings.APP_VERSION}
