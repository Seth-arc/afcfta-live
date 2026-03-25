"""Dependency wiring for repository-backed and stateless services used by API handlers."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import compare_digest
from threading import Lock
from time import monotonic

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.logging import update_request_log_context
from app.db.session import get_assessment_db, get_db
from app.core.exceptions import AuthenticationError, RateLimitExceededError
from app.repositories.cases_repository import CasesRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.evaluations_repository import EvaluationsRepository
from app.repositories.hs_repository import HSRepository
from app.repositories.intelligence_repository import IntelligenceRepository
from app.repositories.rules_repository import RulesRepository
from app.repositories.sources_repository import SourcesRepository
from app.repositories.status_repository import StatusRepository
from app.repositories.tariffs_repository import TariffsRepository
from app.services.audit_service import AuditService
from app.services.classification_service import ClassificationService
from app.services.eligibility_service import EligibilityService
from app.services.evidence_service import EvidenceService
from app.services.expression_evaluator import ExpressionEvaluator
from app.services.fact_normalization_service import FactNormalizationService
from app.services.general_origin_rules_service import GeneralOriginRulesService
from app.services.intelligence_service import IntelligenceService
from app.services.rule_resolution_service import RuleResolutionService
from app.services.status_service import StatusService
from app.services.tariff_resolution_service import TariffResolutionService


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Authenticated caller metadata stored on request state for later logging reuse."""

    principal_id: str
    auth_scheme: str = "api_key"


@dataclass(frozen=True)
class RateLimitPolicy:
    """Concrete fixed-window rate limit policy for one route group."""

    policy_name: str
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Minimal fixed-window in-memory limiter suitable for single-process deployments."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}

    def check(self, *, subject: str, policy: RateLimitPolicy) -> dict[str, int | bool]:
        """Consume one slot from the caller's bucket or report retry timing."""

        now = monotonic()
        window_start = now - policy.window_seconds
        bucket_key = (subject, policy.policy_name)

        with self._lock:
            started_at, count = self._buckets.get(bucket_key, (now, 0))
            if started_at <= window_start:
                started_at, count = now, 0

            if count >= policy.max_requests:
                retry_after = max(1, int(policy.window_seconds - (now - started_at)))
                return {
                    "allowed": False,
                    "retry_after_seconds": retry_after,
                    "remaining": 0,
                }

            count += 1
            self._buckets[bucket_key] = (started_at, count)
            return {
                "allowed": True,
                "retry_after_seconds": 0,
                "remaining": max(policy.max_requests - count, 0),
            }


async def require_authenticated_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthenticatedPrincipal:
    """Authenticate protected API calls with a configured API key.

    The authenticated principal is sourced from Settings.API_AUTH_PRINCIPAL and is
    written to request.state.authenticated_principal so later logging middleware and
    services can reuse the same canonical caller identity without reparsing headers.
    """

    provided_key = request.headers.get(settings.API_AUTH_HEADER_NAME)
    if not provided_key:
        raise AuthenticationError(
            "Authentication is required for this route",
            detail={
                "auth_scheme": "api_key",
                "header_name": settings.API_AUTH_HEADER_NAME,
                "reason": "missing_api_key",
            },
        )

    if not compare_digest(provided_key, settings.API_AUTH_KEY):
        raise AuthenticationError(
            "Authentication failed for this route",
            detail={
                "auth_scheme": "api_key",
                "header_name": settings.API_AUTH_HEADER_NAME,
                "reason": "invalid_api_key",
            },
        )

    principal = AuthenticatedPrincipal(principal_id=settings.API_AUTH_PRINCIPAL)
    request.state.authenticated_principal = principal.principal_id
    request.state.authenticated_auth_scheme = principal.auth_scheme
    update_request_log_context(
        authenticated_principal=principal.principal_id,
        auth_scheme=principal.auth_scheme,
    )
    return principal


def _rate_limit_policy(policy_name: str, settings: Settings) -> RateLimitPolicy:
    """Resolve one named rate-limit policy from application settings."""

    if policy_name == "assessments":
        return RateLimitPolicy(
            policy_name="assessments",
            max_requests=settings.RATE_LIMIT_ASSESSMENTS_MAX_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )

    return RateLimitPolicy(
        policy_name="default",
        max_requests=settings.RATE_LIMIT_DEFAULT_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    )


def require_rate_limit(policy_name: str):
    """Build a dependency that enforces one configured rate-limit policy."""

    async def _enforce_rate_limit(
        request: Request,
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        principal_id = getattr(request.state, "authenticated_principal", None)
        if principal_id is None:
            principal_id = request.client.host if request.client is not None else "anonymous"

        policy = _rate_limit_policy(policy_name, settings)
        limiter = request.app.state.rate_limiter
        result = limiter.check(subject=principal_id, policy=policy)
        if bool(result["allowed"]):
            request.state.rate_limit_policy = policy.policy_name
            request.state.rate_limit_remaining = result["remaining"]
            return

        raise RateLimitExceededError(
            "Rate limit exceeded for this route",
            detail={
                "policy_name": policy.policy_name,
                "max_requests": policy.max_requests,
                "window_seconds": policy.window_seconds,
                "retry_after_seconds": result["retry_after_seconds"],
                "principal_id": principal_id,
            },
        )

    return _enforce_rate_limit


require_default_rate_limit = require_rate_limit("default")
require_assessment_rate_limit = require_rate_limit("assessments")


def _build_eligibility_service(session: AsyncSession) -> EligibilityService:
    """Create the assessment orchestrator bound to one database session."""

    return EligibilityService(
        classification_service=ClassificationService(HSRepository(session)),
        rule_resolution_service=RuleResolutionService(
            hs_repository=HSRepository(session),
            rules_repository=RulesRepository(session),
        ),
        tariff_resolution_service=TariffResolutionService(TariffsRepository(session)),
        status_service=StatusService(StatusRepository(session)),
        evidence_service=EvidenceService(EvidenceRepository(session)),
        fact_normalization_service=FactNormalizationService(),
        expression_evaluator=ExpressionEvaluator(),
        general_origin_rules_service=GeneralOriginRulesService(),
        cases_repository=CasesRepository(session),
        evaluations_repository=EvaluationsRepository(session),
        intelligence_service=IntelligenceService(IntelligenceRepository(session)),
        audit_service=AuditService(
            evaluations_repository=EvaluationsRepository(session),
            cases_repository=CasesRepository(session),
            sources_repository=SourcesRepository(session),
        ),
    )


async def get_cases_repository(
    session: AsyncSession = Depends(get_db),
) -> CasesRepository:
    """Return a cases repository bound to the current request session."""

    return CasesRepository(session)


async def get_sources_repository(
    session: AsyncSession = Depends(get_db),
) -> SourcesRepository:
    """Return a sources repository bound to the current request session."""

    return SourcesRepository(session)


async def get_intelligence_repository(
    session: AsyncSession = Depends(get_db),
) -> IntelligenceRepository:
    """Return an intelligence repository bound to the current request session."""

    return IntelligenceRepository(session)


async def get_audit_service(
    session: AsyncSession = Depends(get_db),
) -> AuditService:
    """Return an audit service bound to the current request session."""

    return AuditService(
        evaluations_repository=EvaluationsRepository(session),
        cases_repository=CasesRepository(session),
        sources_repository=SourcesRepository(session),
    )


async def get_classification_service(
    session: AsyncSession = Depends(get_db),
) -> ClassificationService:
    """Return a classification service bound to the current request session."""

    return ClassificationService(HSRepository(session))


async def get_rule_resolution_service(
    session: AsyncSession = Depends(get_db),
) -> RuleResolutionService:
    """Return a rule-resolution service bound to the current request session."""

    return RuleResolutionService(
        hs_repository=HSRepository(session),
        rules_repository=RulesRepository(session),
    )


async def get_tariff_resolution_service(
    session: AsyncSession = Depends(get_db),
) -> TariffResolutionService:
    """Return a tariff-resolution service bound to the current request session."""

    return TariffResolutionService(TariffsRepository(session))


async def get_status_service(
    session: AsyncSession = Depends(get_db),
) -> StatusService:
    """Return a status service bound to the current request session."""

    return StatusService(StatusRepository(session))


async def get_evidence_service(
    session: AsyncSession = Depends(get_db),
) -> EvidenceService:
    """Return an evidence service bound to the current request session."""

    return EvidenceService(EvidenceRepository(session))


async def get_fact_normalization_service(
    _session: AsyncSession = Depends(get_db),
) -> FactNormalizationService:
    """Return the stateless fact-normalization service."""

    return FactNormalizationService()


async def get_expression_evaluator(
    _session: AsyncSession = Depends(get_db),
) -> ExpressionEvaluator:
    """Return the stateless expression evaluator."""

    return ExpressionEvaluator()


async def get_general_origin_rules_service(
    _session: AsyncSession = Depends(get_db),
) -> GeneralOriginRulesService:
    """Return the stateless general-origin-rules service."""

    return GeneralOriginRulesService()


async def get_eligibility_service(
    session: AsyncSession = Depends(get_db),
) -> EligibilityService:
    """Return the orchestration service with all dependencies bound to one session."""

    return _build_eligibility_service(session)


async def get_assessment_eligibility_service(
    session: AsyncSession = Depends(get_assessment_db),
) -> EligibilityService:
    """Return the assessment orchestrator bound to a repeatable-read session."""

    return _build_eligibility_service(session)


def assessment_eligibility_service_context():
    """Return an async context manager that yields an EligibilityService bound
    to a REPEATABLE READ session.

    Unlike ``get_assessment_eligibility_service`` (which is a FastAPI
    ``Depends`` and opens the DB connection eagerly for every request),
    this helper creates the DB connection only when the ``async with`` block
    is entered. The assistant handler enters it only on the assessment path,
    so clarification and 422 responses are served without any DB access.

    Usage::

        async with assessment_eligibility_service_context() as eligibility_svc:
            result = await eligibility_svc.assess_interface_request(request)
    """
    from contextlib import asynccontextmanager

    from app.db.session import assessment_session_context

    @asynccontextmanager
    async def _ctx():
        async with assessment_session_context() as session:
            yield _build_eligibility_service(session)

    return _ctx()


# ---------------------------------------------------------------------------
# NIM service factories
# ---------------------------------------------------------------------------


def get_nim_client(settings: Settings = Depends(get_settings)) -> "NimClient":
    """Return a NimClient configured from application settings.

    When NIM_ENABLED is False (the default), the client is constructed but
    generate_json() returns None immediately, so all NIM services fall back
    to their deterministic paths without making any HTTP calls.
    """
    from app.services.nim.client import NimClient

    return NimClient(
        base_url=settings.NIM_BASE_URL,
        api_key=settings.NIM_API_KEY,
        model=settings.NIM_MODEL,
        enabled=settings.NIM_ENABLED,
        timeout_seconds=settings.NIM_TIMEOUT_SECONDS,
        max_retries=settings.NIM_MAX_RETRIES,
    )


def get_intake_service(
    nim_client: "NimClient" = Depends(get_nim_client),
) -> "IntakeService":
    """Return an IntakeService bound to the request-scoped NimClient."""
    from app.services.nim.intake_service import IntakeService

    return IntakeService(nim_client)


def get_clarification_service(
    nim_client: "NimClient" = Depends(get_nim_client),
) -> "ClarificationService":
    """Return a ClarificationService bound to the request-scoped NimClient."""
    from app.services.nim.clarification_service import ClarificationService

    return ClarificationService(nim_client)


def get_explanation_service(
    nim_client: "NimClient" = Depends(get_nim_client),
) -> "ExplanationService":
    """Return an ExplanationService bound to the request-scoped NimClient."""
    from app.services.nim.explanation_service import ExplanationService

    return ExplanationService(nim_client)
