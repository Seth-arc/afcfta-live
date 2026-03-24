"""HTTP status mappings for domain exceptions without application startup side effects."""

from __future__ import annotations

from app.core.exceptions import (
    AISBaseException,
    AuthenticationError,
    AuditTrailNotFoundError,
    CaseNotFoundError,
    ClassificationError,
    CorridorNotSupportedError,
    EvaluationPersistenceError,
    ExpressionEvaluationError,
    InsufficientFactsError,
    ReadinessCheckError,
    RateLimitExceededError,
    RuleNotFoundError,
    StatusUnknownError,
    TariffNotFoundError,
)


DOMAIN_STATUS_CODES: dict[type[AISBaseException], int] = {
    AuthenticationError: 401,
    RateLimitExceededError: 429,
    ReadinessCheckError: 503,
    ClassificationError: 404,
    RuleNotFoundError: 404,
    TariffNotFoundError: 404,
    StatusUnknownError: 404,
    AuditTrailNotFoundError: 404,
    CaseNotFoundError: 404,
    CorridorNotSupportedError: 422,
    InsufficientFactsError: 422,
    ExpressionEvaluationError: 500,
    EvaluationPersistenceError: 500,
}