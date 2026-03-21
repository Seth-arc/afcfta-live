"""Resolve applicable PSRs through hs6_psr_applicability and return a typed rule bundle."""

from __future__ import annotations

from datetime import date

from app.core.exceptions import RuleNotFoundError
from app.repositories.hs_repository import HSRepository
from app.repositories.rules_repository import RulesRepository
from app.schemas.rules import (
    PSRComponentOut,
    PSRRuleResolvedOut,
    RulePathwayOut,
    RuleResolutionResult,
)


class RuleResolutionService:
    """Service for resolved PSR lookup and pathway expansion."""

    def __init__(
        self,
        hs_repository: HSRepository,
        rules_repository: RulesRepository,
    ) -> None:
        self.hs_repository = hs_repository
        self.rules_repository = rules_repository

    async def resolve_rule_bundle(
        self,
        hs_version: str,
        hs6_code: str,
        assessment_date: date | None = None,
    ) -> RuleResolutionResult:
        """Resolve the governing PSR and its OR-pathway alternatives for an HS6 code."""

        resolved_date = assessment_date or date.today()
        product = await self.hs_repository.get_by_code(hs_version, hs6_code)
        if product is None:
            raise RuleNotFoundError(
                f"No PSR found for hs_version '{hs_version}' and hs6_code '{hs6_code}'",
                detail={"hs_version": hs_version, "hs6_code": hs6_code},
            )

        resolved_psr = await self.rules_repository.resolve_applicable_psr(
            str(product.hs6_id),
            resolved_date,
        )
        if resolved_psr is None:
            raise RuleNotFoundError(
                f"No PSR found for hs_version '{hs_version}' and hs6_code '{hs6_code}'",
                detail={"hs_version": hs_version, "hs6_code": hs6_code},
            )

        psr_id = str(resolved_psr["psr_id"])
        components = await self.rules_repository.get_psr_components(psr_id)
        pathways = await self.rules_repository.get_pathways(psr_id, resolved_date)
        ordered_components = sorted(
            components,
            key=lambda component: component["component_order"],
        )
        ordered_pathways = sorted(pathways, key=lambda pathway: pathway["priority_rank"])

        return RuleResolutionResult(
            psr_rule=PSRRuleResolvedOut.model_validate(resolved_psr),
            components=[
                PSRComponentOut.model_validate(component) for component in ordered_components
            ],
            pathways=[RulePathwayOut.model_validate(pathway) for pathway in ordered_pathways],
            applicability_type=resolved_psr["applicability_type"],
        )
