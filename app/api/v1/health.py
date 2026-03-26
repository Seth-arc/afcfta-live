"""Health endpoints for lightweight liveness and dependency readiness."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Request

from app.config import get_settings
from app.core.exceptions import AISBaseException, ReadinessCheckError
from app.db.base import check_database_readiness, get_pool_stats

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return API liveness information."""

    settings = get_settings()
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/health/ready")
async def readiness_check(request: Request) -> dict[str, object]:
    """Return dependency readiness information for operators and container probes.

    Pool stats are included only for authenticated callers.  Unauthenticated
    container probes receive the same ``status`` and ``checks`` fields as before
    so existing health-check tooling is unaffected.
    """

    from app.api.deps import require_authenticated_principal

    settings = get_settings()

    # Collect pool stats before the probe so the readiness query itself does
    # not perturb the counters returned to authenticated operators.
    pool_stats: dict[str, object] | None = None
    try:
        await require_authenticated_principal(request, settings)
        pool_stats = get_pool_stats()
    except AISBaseException:
        pass

    try:
        await check_database_readiness()
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", exc)
        raise ReadinessCheckError(
            "Service dependencies are not ready",
            detail={
                "status": "degraded",
                "checks": {"database": "unavailable"},
            },
        ) from exc

    result: dict[str, object] = {
        "status": "ok",
        "version": settings.APP_VERSION,
        "checks": {"database": "ok"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if pool_stats is not None:
        result["pool_stats"] = pool_stats
    return result
