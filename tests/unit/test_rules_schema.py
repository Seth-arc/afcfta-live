"""Unit tests for PSR rule lookup schema flattening and provenance normalization."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.core.enums import HsLevelEnum, RuleStatusEnum
from app.schemas.rules import PSRRuleResolvedOut, RuleLookupResponse


def _rule_payload(*, hs6_code: str = "110311") -> dict[str, object]:
    return {
        "psr_id": uuid4(),
        "source_id": uuid4(),
        "appendix_version": "appendix-iv",
        "hs_version": "HS2017",
        "hs6_code": hs6_code,
        "hs_level": HsLevelEnum.SUBHEADING,
        "product_description": "Groats and meal of cereals",
        "legal_rule_text_verbatim": "CTH or VNM 40%",
        "rule_status": RuleStatusEnum.AGREED,
        "effective_date": date(2025, 1, 1),
    }


def test_psr_rule_resolved_out_populates_provenance_ids_from_dict_source_id() -> None:
    payload = _rule_payload()

    rule = PSRRuleResolvedOut.model_validate(payload)

    assert rule.provenance_ids == [payload["source_id"]]


def test_psr_rule_resolved_out_populates_provenance_ids_from_model_dump_source() -> None:
    payload = _rule_payload()
    model_like = SimpleNamespace(model_dump=lambda mode="python": dict(payload))

    rule = PSRRuleResolvedOut.model_validate(model_like)

    assert rule.provenance_ids == [payload["source_id"]]


def test_psr_rule_resolved_out_populates_provenance_ids_from_mapping_source() -> None:
    payload = _rule_payload()
    mapping_like = SimpleNamespace(_mapping=dict(payload))

    rule = PSRRuleResolvedOut.model_validate(mapping_like)

    assert rule.provenance_ids == [payload["source_id"]]


def test_psr_rule_resolved_out_preserves_existing_provenance_ids() -> None:
    payload = _rule_payload()
    provenance_id = uuid4()
    payload["provenance_ids"] = [provenance_id]

    rule = PSRRuleResolvedOut.model_validate(payload)

    assert rule.provenance_ids == [provenance_id]


def test_psr_rule_resolved_out_accepts_hs_code_alias() -> None:
    payload = _rule_payload()
    payload["hs_code"] = payload.pop("hs6_code")

    rule = PSRRuleResolvedOut.model_validate(payload)

    assert rule.hs6_code == "110311"


def test_psr_rule_resolved_out_normalizer_passthroughs_none() -> None:
    assert PSRRuleResolvedOut.normalize_provenance_ids(None) is None


def test_psr_rule_resolved_out_normalizer_passthroughs_unknown_object() -> None:
    value = object()

    assert PSRRuleResolvedOut.normalize_provenance_ids(value) is value


def test_rule_lookup_response_flattens_nested_rule_resolution_result() -> None:
    payload = {
        "psr_rule": _rule_payload(),
        "components": [],
        "pathways": [],
        "applicability_type": "direct",
    }

    response = RuleLookupResponse.model_validate(payload)

    assert response.hs6_code == "110311"
    assert response.applicability_type == "direct"
    assert response.provenance_ids == [payload["psr_rule"]["source_id"]]


def test_rule_lookup_response_flattens_rule_bundle_and_uses_product_hs6_code() -> None:
    nested_rule = _rule_payload(hs6_code="999999")
    nested_rule.pop("hs6_code")
    nested_rule["hs_code"] = "999999"
    payload = {
        "rule_bundle": {
            "psr_rule": nested_rule,
            "components": [],
            "pathways": [],
            "applicability_type": "direct",
        },
        "product": {"hs6_code": "110311"},
    }

    response = RuleLookupResponse.model_validate(payload)

    assert response.hs6_code == "999999"
    assert response.applicability_type == "direct"


def test_rule_lookup_response_flattens_result_key_and_fills_missing_hs6_from_product() -> None:
    nested_rule = _rule_payload()
    nested_rule.pop("hs6_code")
    payload = {
        "result": {
            "psr_rule": nested_rule,
            "components": [],
            "pathways": [],
            "applicability_type": "range",
        },
        "product": {"hs6_code": "110311"},
    }

    response = RuleLookupResponse.model_validate(payload)

    assert response.hs6_code == "110311"
    assert response.applicability_type == "range"


def test_rule_lookup_response_accepts_flat_payload_with_hs_code_alias() -> None:
    payload = _rule_payload()
    payload["hs_code"] = payload.pop("hs6_code")
    payload["applicability_type"] = "direct"

    response = RuleLookupResponse.model_validate(payload)

    assert response.hs6_code == "110311"
    assert response.applicability_type == "direct"


def test_rule_lookup_response_coerce_to_dict_supports_mapping_objects() -> None:
    payload = _rule_payload()
    coerced = RuleLookupResponse._coerce_to_dict(SimpleNamespace(_mapping=payload))

    assert coerced == payload


def test_rule_lookup_response_coerce_to_dict_supports_model_dump_objects() -> None:
    payload = _rule_payload()
    coerced = RuleLookupResponse._coerce_to_dict(
        SimpleNamespace(model_dump=lambda mode="python": payload)
    )

    assert coerced == payload


def test_rule_lookup_response_coerce_to_dict_passthroughs_unknown_object() -> None:
    value = object()

    assert RuleLookupResponse._coerce_to_dict(value) is value
