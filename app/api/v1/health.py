"""Health endpoints for lightweight liveness and dependency readiness."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings
from app.core.exceptions import ReadinessCheckError
from app.db.base import check_database_readiness

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return API liveness information."""

    settings = get_settings()
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/health/ready")
async def readiness_check() -> dict[str, object]:
    """Return dependency readiness information for operators and container probes."""

    settings = get_settings()
    try:
        await check_database_readiness()
    except Exception as exc:
        raise ReadinessCheckError(
            "Service dependencies are not ready",
            detail={
                "status": "degraded",
                "checks": {"database": "unavailable"},
            },
        ) from exc

    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "checks": {"database": "ok"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
