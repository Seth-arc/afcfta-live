"""Unit tests for post-PSR general origin rule checks."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.general_origin_rules_service import GeneralOriginRulesService


def build_pathway(*, allows_cumulation: bool) -> SimpleNamespace:
    """Build a minimal selected pathway object for general-rule tests."""

    return SimpleNamespace(allows_cumulation=allows_cumulation)


def test_general_origin_checks_all_pass() -> None:
    service = GeneralOriginRulesService()
    facts = {
        "simple_operation_flag": False,
        "cumulation_claimed": True,
        "cumulation_partner_states": ["GHA", "NGA"],
        "direct_transport": True,
    }

    result = service.evaluate(facts, build_pathway(allows_cumulation=True))

    assert result.insufficient_operations_check == "pass"
    assert result.cumulation_check == "pass"
    assert result.direct_transport_check == "pass"
    assert result.general_rules_passed is True
    assert result.failure_codes == []


def test_general_origin_checks_fail_for_insufficient_operations() -> None:
    service = GeneralOriginRulesService()
    facts = {
        "simple_operation_flag": True,
        "cumulation_claimed": False,
        "direct_transport": True,
    }

    result = service.evaluate(facts, build_pathway(allows_cumulation=True))

    assert result.insufficient_operations_check == "fail"
    assert result.general_rules_passed is False
    assert "FAIL_INSUFFICIENT_OPERATIONS" in result.failure_codes


def test_general_origin_checks_fail_for_direct_transport() -> None:
    service = GeneralOriginRulesService()
    facts = {
        "simple_operation_flag": False,
        "cumulation_claimed": False,
        "direct_transport": False,
    }

    result = service.evaluate(facts, build_pathway(allows_cumulation=True))

    assert result.direct_transport_check == "fail"
    assert result.general_rules_passed is False
    assert "FAIL_DIRECT_TRANSPORT" in result.failure_codes


def test_general_origin_checks_flag_missing_direct_transport_without_defaulting() -> None:
    service = GeneralOriginRulesService()
    facts = {
        "simple_operation_flag": False,
        "cumulation_claimed": False,
    }

    result = service.evaluate(facts, build_pathway(allows_cumulation=True))

    assert result.direct_transport_check == "not_checked"
    assert result.general_rules_passed is False
    assert result.failure_codes == []
    assert result.checks[-1].passed is None


def test_general_origin_checks_fail_when_cumulation_claimed_but_pathway_disallows() -> None:
    service = GeneralOriginRulesService()
    facts = {
        "simple_operation_flag": False,
        "cumulation_claimed": True,
        "cumulation_partner_states": ["GHA"],
        "direct_transport": True,
    }

    result = service.evaluate(facts, build_pathway(allows_cumulation=False))

    assert result.cumulation_check == "fail"
    assert result.general_rules_passed is False
    assert "FAIL_CUMULATION_INVALID" in result.failure_codes


def test_general_origin_checks_mark_cumulation_not_applicable_when_not_claimed() -> None:
    service = GeneralOriginRulesService()
    facts = {
        "simple_operation_flag": False,
        "cumulation_claimed": False,
        "direct_transport": True,
    }

    result = service.evaluate(facts, build_pathway(allows_cumulation=True))

    assert result.cumulation_check == "not_applicable"
    assert result.general_rules_passed is True
