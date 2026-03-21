"""Common API response envelopes shared across endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Meta(BaseModel):
    """Metadata returned with every API response."""

    request_id: str
    timestamp: datetime


class ApiResponse(BaseModel):
    """Standard success response envelope."""

    data: Any
    meta: Meta


class ErrorDetail(BaseModel):
    """Structured error details."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail
    meta: Meta
