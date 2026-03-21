"""Apply general origin rules after PSR pathway evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.countries import V01_COUNTRIES
from app.core.failure_codes import FAILURE_CODES
from app.services.expression_evaluator import AtomicCheck

CheckOutcome = Literal["pass", "fail", "not_applicable", "not_checked"]


@dataclass(slots=True)
class GeneralRulesResult:
    """Outcome of post-PSR general origin checks."""

    insufficient_operations_check: CheckOutcome
    cumulation_check: CheckOutcome
    direct_transport_check: CheckOutcome
    general_rules_passed: bool
    checks: list[AtomicCheck] = field(default_factory=list)
    failure_codes: list[str] = field(default_factory=list)


class GeneralOriginRulesService:
    """Evaluate general AfCFTA origin conditions separate from PSR logic."""

    def evaluate(
        self,
        facts: dict[str, Any],
        pathway_result: Any,
    ) -> GeneralRulesResult:
        """Run insufficient operations, cumulation, and direct transport checks."""

        checks: list[AtomicCheck] = []
        failure_codes: list[str] = []

        insufficient_operations_check = self._evaluate_insufficient_operations(
            facts,
            checks,
            failure_codes,
        )
        cumulation_check = self._evaluate_cumulation(
            facts,
            pathway_result,
            checks,
            failure_codes,
        )
        direct_transport_check = self._evaluate_direct_transport(
            facts,
            checks,
            failure_codes,
        )

        general_rules_passed = (
            insufficient_operations_check != "fail"
            and cumulation_check != "fail"
            and direct_transport_check == "pass"
        )

        return GeneralRulesResult(
            insufficient_operations_check=insufficient_operations_check,
            cumulation_check=cumulation_check,
            direct_transport_check=direct_transport_check,
            general_rules_passed=general_rules_passed,
            checks=checks,
            failure_codes=failure_codes,
        )

    def _evaluate_insufficient_operations(
        self,
        facts: dict[str, Any],
        checks: list[AtomicCheck],
        failure_codes: list[str],
    ) -> CheckOutcome:
        """Fail when only simple operations are declared."""

        simple_operation_flag = facts.get("simple_operation_flag")
        if simple_operation_flag is True:
            failure_code = "FAIL_INSUFFICIENT_OPERATIONS"
            self._append_failure(
                checks,
                failure_codes,
                check_code="INSUFFICIENT_OPERATIONS",
                expected_value="substantial transformation",
                observed_value="simple operations only",
                explanation=FAILURE_CODES[failure_code],
                failure_code=failure_code,
            )
            return "fail"

        if simple_operation_flag is False:
            checks.append(
                AtomicCheck(
                    check_code="INSUFFICIENT_OPERATIONS",
                    passed=True,
                    expected_value="not a simple operation",
                    observed_value="simple_operation_flag=false",
                    explanation="Declared operations go beyond simple or minimal operations",
                )
            )
            return "pass"

        checks.append(
            AtomicCheck(
                check_code="INSUFFICIENT_OPERATIONS",
                passed=None,
                expected_value="simple operation assessment if declared",
                observed_value="<missing>",
                explanation="No simple-operation declaration was provided",
            )
        )
        return "not_applicable"

    def _evaluate_cumulation(
        self,
        facts: dict[str, Any],
        pathway_result: Any,
        checks: list[AtomicCheck],
        failure_codes: list[str],
    ) -> CheckOutcome:
        """Validate cumulation claims separately from the selected PSR pathway."""

        if facts.get("cumulation_claimed") is not True:
            checks.append(
                AtomicCheck(
                    check_code="CUMULATION",
                    passed=None,
                    expected_value="cumulation claim when invoked",
                    observed_value="not claimed",
                    explanation="Cumulation was not claimed for this assessment",
                )
            )
            return "not_applicable"

        allows_cumulation = bool(
            self._get_pathway_value(pathway_result, "allows_cumulation", False)
        )
        if not allows_cumulation:
            failure_code = "FAIL_CUMULATION_INVALID"
            self._append_failure(
                checks,
                failure_codes,
                check_code="CUMULATION",
                expected_value="pathway allows cumulation",
                observed_value="allows_cumulation=false",
                explanation=FAILURE_CODES[failure_code],
                failure_code=failure_code,
            )
            return "fail"

        partner_states = facts.get("cumulation_partner_states")
        if not isinstance(partner_states, list) or not partner_states:
            failure_code = "FAIL_CUMULATION_INVALID"
            self._append_failure(
                checks,
                failure_codes,
                check_code="CUMULATION",
                expected_value="valid cumulation partner states",
                observed_value="<missing>",
                explanation=FAILURE_CODES[failure_code],
                failure_code=failure_code,
            )
            return "fail"

        normalized_partners = [str(partner).strip().upper() for partner in partner_states]
        invalid_partners = [
            partner for partner in normalized_partners if partner not in V01_COUNTRIES
        ]
        if invalid_partners:
            failure_code = "FAIL_CUMULATION_INVALID"
            self._append_failure(
                checks,
                failure_codes,
                check_code="CUMULATION",
                expected_value="valid v0.1 partner states",
                observed_value=", ".join(invalid_partners),
                explanation=FAILURE_CODES[failure_code],
                failure_code=failure_code,
            )
            return "fail"

        checks.append(
            AtomicCheck(
                check_code="CUMULATION",
                passed=True,
                expected_value="valid cumulation partners for an allowed pathway",
                observed_value=", ".join(normalized_partners),
                explanation="Cumulation claim is allowed and partner states are valid",
            )
        )
        return "pass"

    def _evaluate_direct_transport(
        self,
        facts: dict[str, Any],
        checks: list[AtomicCheck],
        failure_codes: list[str],
    ) -> CheckOutcome:
        """Require a direct-transport confirmation and never default it."""

        direct_transport = self._resolve_direct_transport(facts)
        if direct_transport is True:
            checks.append(
                AtomicCheck(
                    check_code="DIRECT_TRANSPORT",
                    passed=True,
                    expected_value="true",
                    observed_value="true",
                    explanation="Direct transport condition was confirmed",
                )
            )
            return "pass"

        if direct_transport is False:
            failure_code = "FAIL_DIRECT_TRANSPORT"
            self._append_failure(
                checks,
                failure_codes,
                check_code="DIRECT_TRANSPORT",
                expected_value="true",
                observed_value="false",
                explanation=FAILURE_CODES[failure_code],
                failure_code=failure_code,
            )
            return "fail"

        checks.append(
            AtomicCheck(
                check_code="DIRECT_TRANSPORT",
                passed=None,
                expected_value="true",
                observed_value="<missing>",
                explanation="Direct transport fact was not provided",
            )
        )
        return "not_checked"

    @staticmethod
    def _resolve_direct_transport(facts: dict[str, Any]) -> bool | None:
        """Prefer the normalized direct_transport fact but accept the older alias."""

        if "direct_transport" in facts:
            return facts["direct_transport"]
        return facts.get("direct_transport_confirmed")

    @staticmethod
    def _get_pathway_value(pathway_result: Any, field_name: str, default: Any = None) -> Any:
        """Read a field from a mapping or object-like selected pathway."""

        if isinstance(pathway_result, dict):
            return pathway_result.get(field_name, default)
        return getattr(pathway_result, field_name, default)

    @staticmethod
    def _append_failure(
        checks: list[AtomicCheck],
        failure_codes: list[str],
        *,
        check_code: str,
        expected_value: str,
        observed_value: str,
        explanation: str,
        failure_code: str,
    ) -> None:
        """Append a failed atomic check and deduplicated failure code."""

        checks.append(
            AtomicCheck(
                check_code=check_code,
                passed=False,
                expected_value=expected_value,
                observed_value=observed_value,
                explanation=explanation,
            )
        )
        if failure_code not in failure_codes:
            failure_codes.append(failure_code)
