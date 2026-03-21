"""Domain exceptions raised by the AfCFTA Intelligence API."""

from __future__ import annotations

from typing import Any


class AISBaseException(Exception):
    """Base class for all domain exceptions."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ClassificationError(AISBaseException):
    """Raised when an HS6 code cannot be resolved."""


class RuleNotFoundError(AISBaseException):
    """Raised when no PSR is available for an HS6 code."""


class TariffNotFoundError(AISBaseException):
    """Raised when no tariff schedule exists for a corridor."""


class StatusUnknownError(AISBaseException):
    """Raised when no status assertion can be resolved."""


class ExpressionEvaluationError(AISBaseException):
    """Raised when expression evaluation fails."""


class InsufficientFactsError(AISBaseException):
    """Raised when required input facts are missing."""


class CorridorNotSupportedError(AISBaseException):
    """Raised when a country pair falls outside the locked v0.1 scope."""
