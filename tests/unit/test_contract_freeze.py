"""Schema-level freeze tests for the public assessment and assistant contracts."""

from __future__ import annotations

import json

from app.schemas.assessments import (
    CaseAssessmentRequest,
    EligibilityAssessmentResponse,
    EligibilityRequest,
    TariffOutcomeResponse,
)
from app.schemas.cases import (
    CaseCreateAssessmentOptions,
    CaseCreateRequest,
    CaseCreateResponse,
)
from app.schemas.rules import RuleLookupResponse
from app.schemas.tariffs import TariffResolutionResult
from app.schemas.nim.assistant import (
    AssistantContext,
    AssistantError,
    AssistantRequest,
    AssistantResponseEnvelope,
    ClarificationResponse,
)
from tests.contract_constants import (
    ASSISTANT_CONTEXT_FIELD_ORDER,
    ASSISTANT_ERROR_FIELDS,
    ASSISTANT_REQUEST_FIELD_ORDER,
    ASSISTANT_RESPONSE_ENVELOPE_FIELDS,
    ASSESSMENT_REQUEST_FIELD_ORDER,
    CASE_CREATE_ASSESSMENT_OPTIONS_FIELD_ORDER,
    CASE_CREATE_REQUEST_FIELD_ORDER,
    CASE_CREATE_RESPONSE_FIELDS,
    CASE_ASSESSMENT_REQUEST_FIELD_ORDER,
    CLARIFICATION_FIELDS,
    ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS,
    TARIFF_OUTCOME_FIELDS,
)


def _field_order(model: type) -> tuple[str, ...]:
    return tuple(model.model_fields.keys())


def _schema_properties(model: type) -> set[str]:
    schema = model.model_json_schema()
    return set(schema.get("properties", {}))


def _schema_text(model: type) -> str:
    return json.dumps(model.model_json_schema(), sort_keys=True)


def test_eligibility_request_contract_is_frozen() -> None:
    assert _field_order(EligibilityRequest) == ASSESSMENT_REQUEST_FIELD_ORDER
    assert _schema_properties(EligibilityRequest) == set(ASSESSMENT_REQUEST_FIELD_ORDER)
    assert "submitted_documents" not in _schema_text(EligibilityRequest)


def test_case_assessment_request_contract_is_frozen() -> None:
    assert _field_order(CaseAssessmentRequest) == CASE_ASSESSMENT_REQUEST_FIELD_ORDER
    assert _schema_properties(CaseAssessmentRequest) == set(CASE_ASSESSMENT_REQUEST_FIELD_ORDER)
    assert "submitted_documents" not in _schema_text(CaseAssessmentRequest)


def test_case_create_assessment_options_contract_is_frozen() -> None:
    assert (
        _field_order(CaseCreateAssessmentOptions)
        == CASE_CREATE_ASSESSMENT_OPTIONS_FIELD_ORDER
    )
    assert _schema_properties(CaseCreateAssessmentOptions) == set(
        CASE_CREATE_ASSESSMENT_OPTIONS_FIELD_ORDER
    )
    assert "submitted_documents" not in _schema_text(CaseCreateAssessmentOptions)


def test_case_create_request_contract_is_frozen() -> None:
    assert _field_order(CaseCreateRequest) == CASE_CREATE_REQUEST_FIELD_ORDER
    assert _schema_properties(CaseCreateRequest) == set(CASE_CREATE_REQUEST_FIELD_ORDER)
    assert "submitted_documents" not in _schema_text(CaseCreateRequest)


def test_case_create_response_contract_is_frozen() -> None:
    assert _schema_properties(CaseCreateResponse) == CASE_CREATE_RESPONSE_FIELDS


def test_tariff_outcome_contract_is_frozen() -> None:
    assert _schema_properties(TariffOutcomeResponse) == TARIFF_OUTCOME_FIELDS


def test_rule_lookup_contract_exposes_provenance_ids() -> None:
    assert "provenance_ids" in _schema_properties(RuleLookupResponse)


def test_tariff_resolution_contract_exposes_provenance_ids() -> None:
    assert "provenance_ids" in _schema_properties(TariffResolutionResult)


def test_eligibility_assessment_response_contract_is_frozen() -> None:
    assert (
        _schema_properties(EligibilityAssessmentResponse)
        == ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS
    )
    assert "submitted_documents" not in _schema_text(EligibilityAssessmentResponse)


def test_assistant_context_contract_is_frozen() -> None:
    assert _field_order(AssistantContext) == ASSISTANT_CONTEXT_FIELD_ORDER
    assert _schema_properties(AssistantContext) == set(ASSISTANT_CONTEXT_FIELD_ORDER)


def test_assistant_request_contract_is_frozen() -> None:
    assert _field_order(AssistantRequest) == ASSISTANT_REQUEST_FIELD_ORDER
    assert _schema_properties(AssistantRequest) == set(ASSISTANT_REQUEST_FIELD_ORDER)
    assert "submitted_documents" not in _schema_text(AssistantRequest)


def test_clarification_contract_is_frozen() -> None:
    assert _schema_properties(ClarificationResponse) == CLARIFICATION_FIELDS


def test_assistant_error_contract_is_frozen() -> None:
    assert _schema_properties(AssistantError) == ASSISTANT_ERROR_FIELDS


def test_assistant_response_envelope_contract_is_frozen() -> None:
    assert (
        _schema_properties(AssistantResponseEnvelope)
        == ASSISTANT_RESPONSE_ENVELOPE_FIELDS
    )
    assert "submitted_documents" not in _schema_text(AssistantResponseEnvelope)
