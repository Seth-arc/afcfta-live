"""Dependency wiring for repository-backed and stateless services used by API handlers."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.cases_repository import CasesRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.evaluations_repository import EvaluationsRepository
from app.repositories.hs_repository import HSRepository
from app.repositories.rules_repository import RulesRepository
from app.repositories.status_repository import StatusRepository
from app.repositories.tariffs_repository import TariffsRepository
from app.services.audit_service import AuditService
from app.services.classification_service import ClassificationService
from app.services.eligibility_service import EligibilityService
from app.services.evidence_service import EvidenceService
from app.services.expression_evaluator import ExpressionEvaluator
from app.services.fact_normalization_service import FactNormalizationService
from app.services.general_origin_rules_service import GeneralOriginRulesService
from app.services.rule_resolution_service import RuleResolutionService
from app.services.status_service import StatusService
from app.services.tariff_resolution_service import TariffResolutionService


async def get_cases_repository(
    session: AsyncSession = Depends(get_db),
) -> CasesRepository:
    """Return a cases repository bound to the current request session."""

    return CasesRepository(session)


async def get_audit_service(
    session: AsyncSession = Depends(get_db),
) -> AuditService:
    """Return an audit service bound to the current request session."""

    return AuditService(
        evaluations_repository=EvaluationsRepository(session),
        cases_repository=CasesRepository(session),
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
        evaluations_repository=EvaluationsRepository(session),
        audit_service=AuditService(
            evaluations_repository=EvaluationsRepository(session),
            cases_repository=CasesRepository(session),
        ),
    )
