"""Domain exception hierarchy for the AfCFTA Intelligence System."""

from __future__ import annotations

from typing import Any


class AISBaseException(Exception):
    """Base class for domain-level engine errors."""

    code = "AIS_ERROR"

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ClassificationError(AISBaseException):
    """Raised when an HS code cannot be resolved to the canonical HS6 backbone."""

    code = "CLASSIFICATION_ERROR"


class RuleNotFoundError(AISBaseException):
    """Raised when no applicable PSR rule exists for the resolved HS6."""

    code = "RULE_NOT_FOUND"


class TariffNotFoundError(AISBaseException):
    """Raised when no tariff schedule exists for the requested corridor and HS6."""

    code = "TARIFF_NOT_FOUND"


class StatusUnknownError(AISBaseException):
    """Raised when no current status assertion can be found for an entity key."""

    code = "STATUS_UNKNOWN"


class AuditTrailNotFoundError(AISBaseException):
    """Raised when no persisted evaluation trail exists for the requested identifier."""

    code = "AUDIT_TRAIL_NOT_FOUND"


class AuthenticationError(AISBaseException):
    """Raised when a request to a protected API route lacks valid credentials."""

    code = "AUTHENTICATION_ERROR"


class RateLimitExceededError(AISBaseException):
    """Raised when a caller exceeds the configured API rate limit."""

    code = "RATE_LIMIT_EXCEEDED"


class ReadinessCheckError(AISBaseException):
    """Raised when a dependency readiness probe fails."""

    code = "READINESS_CHECK_FAILED"


class EvaluationPersistenceError(AISBaseException):
    """Raised when an interface assessment cannot guarantee replay-safe persistence."""

    code = "EVALUATION_PERSISTENCE_ERROR"


class CaseNotFoundError(AISBaseException):
    """Raised when a referenced case_id cannot be resolved to a stored case."""

    code = "CASE_NOT_FOUND"


class ExpressionEvaluationError(AISBaseException):
    """Raised when the safe expression evaluator cannot evaluate a rule expression."""

    code = "EXPRESSION_EVALUATION_ERROR"


class InsufficientFactsError(AISBaseException):
    """Raised when required production facts are absent for a deterministic assessment."""

    code = "INSUFFICIENT_FACTS"


class CorridorNotSupportedError(AISBaseException):
    """Raised when a country pair falls outside the locked v0.1 corridor scope."""

    code = "CORRIDOR_NOT_SUPPORTED"
