"""Response schemas for health and readiness endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PoolStats(BaseModel):
    """Connection pool counters and pressure classification."""

    checked_out: int
    pool_size: int
    overflow: int
    checked_in: int
    pool_pressure: Literal["ok", "elevated", "saturated"]
