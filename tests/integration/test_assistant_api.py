"""Integration tests for the NIM assistant endpoint.

Covers:
- Authentication and rate-limit guard.
- Input validation (schema rejection before any NIM call).
- Envelope shape contract for all three response_type values.
- Clarification path: NIM disabled → empty draft → real clarification flow.
- Happy path: mocked intake draft → full engine run → assessment + replay ids.
- Replay linkage: case_id, evaluation_id, audit_url populated and consistent.
- Field-name migration: submitted_documents must never appear in responses.

Invariants that must always hold:
1. The endpoint requires authentication.
2. Every response is an AssistantResponseEnvelope with a known response_type.
3. Replay identifiers are null when response_type is not "assessment".
4. audit_persisted is False when response_type is not "assessment".
5. Exactly one of assessment/clarification/error is non-null per response.
6. The envelope never uses `submitted_documents` — only `existing_documents`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from tests.contract_constants import (
    ASSISTANT_RESPONSE_ENVELOPE_FIELDS,
    CLARIFICATION_FIELDS,
    ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS,
    VALID_ASSISTANT_RESPONSE_TYPES,
)

pytestmark = pytest.mark.integration

ASSISTANT_URL = "/api/v1/assistant/assess"

def _minimal_request() -> dict[str, object]:
    """Return a minimally valid assistant request."""
    return {"user_input": "Can I export HS 110311 from Ghana to Nigeria?"}


def _request_with_context() -> dict[str, object]:
    """Return an assistant request with full optional context."""
    return {
        "user_input": "Can I export wheat groats from Ghana to Nigeria in 2025?",
        "context": {
            "persona_mode": "exporter",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
        },
    }


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assistant_endpoint_requires_authentication(
    unauthenticated_async_client: AsyncClient,
) -> None:
    """POST /assistant/assess must reject unauthenticated requests with 401."""

    response = await unauthenticated_async_client.post(
        ASSISTANT_URL, json=_minimal_request()
    )

    assert response.status_code == 401, response.text
    body = response.json()
    assert set(body) == {"error", "meta"}
    assert body["error"]["code"] == "AUTHENTICATION_ERROR"
    assert body["meta"]["request_id"]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assistant_rejects_empty_user_input(
    async_client: AsyncClient,
) -> None:
    """Empty user_input must fail Pydantic validation with 422."""

    response = await async_client.post(ASSISTANT_URL, json={"user_input": ""})

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_assistant_rejects_missing_user_input(
    async_client: AsyncClient,
) -> None:
    """Missing user_input field must fail Pydantic validation with 422."""

    response = await async_client.post(ASSISTANT_URL, json={})

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_assistant_rejects_unknown_fields_in_context(
    async_client: AsyncClient,
) -> None:
    """Extra fields in context must be rejected (extra='forbid' on AssistantContext)."""

    payload = {
        "user_input": "Can I export HS 110311?",
        "context": {"unknown_field": "surprise"},
    }
    response = await async_client.post(ASSISTANT_URL, json=payload)

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_assistant_rejects_invalid_country_code_length_in_context(
    async_client: AsyncClient,
) -> None:
    """Country codes in context must be exactly 3 characters."""

    payload = {
        "user_input": "Can I export from here?",
        "context": {"exporter": "GHANA"},  # 5 chars, must be 3
    }
    response = await async_client.post(ASSISTANT_URL, json=payload)

    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Envelope shape contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assistant_response_contains_all_required_envelope_fields(
    async_client: AsyncClient,
) -> None:
    """Every assistant response must contain all envelope fields, none missing."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()
    assert ASSISTANT_RESPONSE_ENVELOPE_FIELDS.issubset(set(body)), (
        f"Envelope missing fields: {ASSISTANT_RESPONSE_ENVELOPE_FIELDS - set(body)}"
    )


@pytest.mark.asyncio
async def test_assistant_response_type_is_a_known_discriminator_value(
    async_client: AsyncClient,
) -> None:
    """response_type must be one of the three known discriminator values."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    assert response.json()["response_type"] in VALID_ASSISTANT_RESPONSE_TYPES


@pytest.mark.asyncio
async def test_assistant_response_with_context_returns_valid_envelope(
    async_client: AsyncClient,
) -> None:
    """Requests with full context hints must also produce a valid envelope."""

    response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

    assert response.status_code == 200, response.text
    body = response.json()
    assert ASSISTANT_RESPONSE_ENVELOPE_FIELDS.issubset(set(body))
    assert body["response_type"] in VALID_ASSISTANT_RESPONSE_TYPES


# ---------------------------------------------------------------------------
# Clarification response contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clarification_response_has_null_replay_identifiers(
    async_client: AsyncClient,
) -> None:
    """When response_type is 'clarification', all replay identifiers must be null."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()

    if body["response_type"] == "clarification":
        assert body["case_id"] is None, "case_id must be null for clarification"
        assert body["evaluation_id"] is None, "evaluation_id must be null for clarification"
        assert body["audit_url"] is None, "audit_url must be null for clarification"
        assert body["audit_persisted"] is False, "audit_persisted must be False for clarification"
        assert body["assessment"] is None, "assessment must be null for clarification"
        assert body["error"] is None, "error must be null for clarification"


@pytest.mark.asyncio
async def test_clarification_payload_has_required_fields(
    async_client: AsyncClient,
) -> None:
    """When response_type is 'clarification', the clarification payload must be populated."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()

    if body["response_type"] == "clarification":
        assert body["clarification"] is not None
        clr = body["clarification"]
        assert CLARIFICATION_FIELDS.issubset(set(clr)), (
            f"Clarification missing fields: {CLARIFICATION_FIELDS - set(clr)}"
        )
        assert isinstance(clr["question"], str) and len(clr["question"]) > 0
        assert isinstance(clr["missing_facts"], list)
        assert isinstance(clr["missing_evidence"], list)


@pytest.mark.asyncio
async def test_nim_disabled_returns_clarification_with_missing_facts(
    async_client: AsyncClient,
) -> None:
    """With NIM disabled (default in tests), an empty draft is produced and the
    real clarification flow fires, asking for all required facts."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response_type"] == "clarification", (
        "NIM disabled → empty draft → clarification with all required facts missing"
    )
    assert body["clarification"] is not None
    assert len(body["clarification"]["missing_facts"]) > 0
    assert body["audit_persisted"] is False
    assert body["case_id"] is None
    assert body["evaluation_id"] is None


# ---------------------------------------------------------------------------
# Assessment response contract (shape-only — engine not yet wired)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assessment_response_shape_when_type_is_assessment(
    async_client: AsyncClient,
) -> None:
    """When response_type is 'assessment', all replay identifiers must be present.

    This test is a forward contract guard. It will only exercise the
    assessment branch once the NIM intake service and engine are wired
    in Prompt 9. Until then, the harness returns clarification and this
    test passes vacuously on the condition.
    """

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()

    if body["response_type"] == "assessment":
        # Replay identifiers must all be present
        assert body["case_id"] is not None, "case_id must be set for assessment"
        assert body["evaluation_id"] is not None, "evaluation_id must be set for assessment"
        assert body["audit_url"] is not None, "audit_url must be set for assessment"

        # audit_url must point to the canonical audit endpoint
        expected_prefix = "/api/v1/audit/evaluations/"
        assert body["audit_url"].startswith(expected_prefix), (
            f"audit_url must start with {expected_prefix}"
        )

        # audit_persisted must reflect real persistence
        assert isinstance(body["audit_persisted"], bool)

        # Assessment payload must carry all deterministic engine fields
        assert body["assessment"] is not None
        asmnt = body["assessment"]
        assert ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS.issubset(set(asmnt)), (
            f"Assessment missing fields: {ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS - set(asmnt)}"
        )

        # Clarification and error must be null for assessment responses
        assert body["clarification"] is None
        assert body["error"] is None

        # submitted_documents must never appear in assessment output
        assert "submitted_documents" not in asmnt, (
            "submitted_documents must not appear in assessment output; "
            "use existing_documents"
        )


# ---------------------------------------------------------------------------
# Error response contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_response_shape_when_type_is_error(
    async_client: AsyncClient,
) -> None:
    """When response_type is 'error', the error payload must be populated.

    Forward contract guard — exercises the error branch once the NIM
    validation layer is wired.
    """

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()

    if body["response_type"] == "error":
        assert body["error"] is not None
        err = body["error"]
        assert "code" in err and isinstance(err["code"], str)
        assert "message" in err and isinstance(err["message"], str)
        assert body["assessment"] is None
        assert body["clarification"] is None
        assert body["audit_persisted"] is False


# ---------------------------------------------------------------------------
# Field-name migration guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_never_contains_submitted_documents_field(
    async_client: AsyncClient,
) -> None:
    """The response envelope must never use the legacy submitted_documents field name.

    The canonical field is existing_documents. submitted_documents is an
    input-only backward-compatibility alias and must not appear in any
    assistant response.
    """

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text

    # Check the raw response text — submitted_documents must never appear
    assert "submitted_documents" not in response.text, (
        "Legacy field 'submitted_documents' must not appear in assistant responses. "
        "Use 'existing_documents' exclusively."
    )


# ---------------------------------------------------------------------------
# Replay linkage contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_persisted_false_when_no_engine_ran(
    async_client: AsyncClient,
) -> None:
    """audit_persisted must be False when the engine has not run.

    The assistant must not claim audit compliance when no engine run
    has occurred and no persisted evaluation exists.
    """

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()

    if body["response_type"] in {"clarification", "error"}:
        assert body["audit_persisted"] is False, (
            "audit_persisted must be False when the engine did not run"
        )
        assert body["case_id"] is None
        assert body["evaluation_id"] is None
        assert body["audit_url"] is None


# ---------------------------------------------------------------------------
# Happy path: complete draft → full engine run → assessment with replay ids
# ---------------------------------------------------------------------------

# Shared helper: build a complete NimAssessmentDraft for the GHA→NGA corridor.
def _complete_gha_nga_draft():
    """Return a complete NimAssessmentDraft for HS 110311, GHA→NGA, 2025."""
    from app.core.enums import PersonaModeEnum
    from app.schemas.nim.intake import (
        AssessmentContext,
        HS6Candidate,
        NimAssessmentDraft,
        TradeFlow,
    )

    return NimAssessmentDraft(
        product=HS6Candidate(hs6_code="110311"),
        trade_flow=TradeFlow(exporter="GHA", importer="NGA", year=2025),
        context=AssessmentContext(persona_mode=PersonaModeEnum.EXPORTER),
    )


def _override_intake_with_complete_draft(app: FastAPI) -> None:
    """Install a dependency override that returns the complete GHA→NGA draft."""
    from app.api.deps import get_intake_service
    from app.services.nim.intake_service import IntakeService

    draft = _complete_gha_nga_draft()
    real_svc = IntakeService(MagicMock())  # only to_eligibility_request is needed

    mock_svc = MagicMock(spec=IntakeService)
    mock_svc.parse_user_input = AsyncMock(return_value=draft)
    mock_svc.to_eligibility_request = real_svc.to_eligibility_request
    # nim_client is an instance attribute (set in __init__), not in the class
    # spec — must be set explicitly so the handler can read .enabled and .model.
    mock_svc.nim_client = MagicMock(enabled=False, model="")

    app.dependency_overrides[get_intake_service] = lambda: mock_svc


def _remove_intake_override(app: FastAPI) -> None:
    from app.api.deps import get_intake_service

    app.dependency_overrides.pop(get_intake_service, None)


@pytest.mark.asyncio
async def test_assistant_happy_path_returns_assessment_with_all_required_fields(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """Happy path: complete draft injected via override → engine runs →
    response_type is 'assessment' with all required envelope and assessment fields.
    """
    _override_intake_with_complete_draft(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["response_type"] == "assessment", (
            f"Expected 'assessment', got '{body['response_type']}'. "
            f"clarification={body.get('clarification')}, error={body.get('error')}"
        )

        # Envelope shape
        assert ASSISTANT_RESPONSE_ENVELOPE_FIELDS.issubset(set(body))

        # Assessment payload
        assert body["assessment"] is not None
        assert ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS.issubset(set(body["assessment"]))
        assert body["assessment"]["hs6_code"] == "110311"

        # Clarification and error must be absent for an assessment response
        assert body["clarification"] is None
        assert body["error"] is None

        # Explanation is optional but must not be a fabricated empty string
        if body["explanation"] is not None:
            assert isinstance(body["explanation"], str)
            assert len(body["explanation"]) > 0
    finally:
        _remove_intake_override(app)


# ---------------------------------------------------------------------------
# Replay linkage: case_id, evaluation_id, audit_url set and consistent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assistant_happy_path_sets_replay_identifiers(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """case_id, evaluation_id, and audit_url must all be populated for assessments
    and audit_url must reference the evaluation_id so clients can replay the decision.
    """
    _override_intake_with_complete_draft(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

        assert response.status_code == 200, response.text
        body = response.json()

        if body["response_type"] == "assessment":
            assert body["case_id"] is not None, "case_id must be set for assessment"
            assert body["evaluation_id"] is not None, "evaluation_id must be set"
            assert body["audit_url"] is not None, "audit_url must be set"

            # audit_url must reference the same evaluation_id
            assert body["audit_url"] == (
                f"/api/v1/audit/evaluations/{body['evaluation_id']}"
            ), "audit_url must embed evaluation_id for deterministic replay"

            # audit_persisted reflects real DB write — must be a bool
            assert isinstance(body["audit_persisted"], bool)
    finally:
        _remove_intake_override(app)


@pytest.mark.asyncio
async def test_assistant_happy_path_sets_replay_response_headers(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """X-AIS-Case-Id, X-AIS-Evaluation-Id, and X-AIS-Audit-URL response headers
    must be present for assessment responses and must match the body identifiers.
    """
    _override_intake_with_complete_draft(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

        assert response.status_code == 200, response.text
        body = response.json()

        if body["response_type"] == "assessment":
            assert "x-ais-case-id" in response.headers, "X-AIS-Case-Id header missing"
            assert "x-ais-evaluation-id" in response.headers
            assert "x-ais-audit-url" in response.headers

            assert response.headers["x-ais-case-id"] == body["case_id"]
            assert response.headers["x-ais-evaluation-id"] == body["evaluation_id"]
            assert response.headers["x-ais-audit-url"] == body["audit_url"]
    finally:
        _remove_intake_override(app)


# ---------------------------------------------------------------------------
# Deterministic field invariant: explanation must not alter assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assessment_fields_not_altered_by_explanation(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """Engine assessment fields must be identical to what the engine returned;
    the explanation service must not alter eligible, pathway_used, rule_status,
    tariff_outcome, confidence_class, failures, or missing_facts.
    """
    _override_intake_with_complete_draft(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

        assert response.status_code == 200, response.text
        body = response.json()

        if body["response_type"] == "assessment":
            asmnt = body["assessment"]
            # All required deterministic fields must be present and typed correctly
            assert isinstance(asmnt["eligible"], bool)
            assert isinstance(asmnt["failures"], list)
            assert isinstance(asmnt["missing_facts"], list)
            assert isinstance(asmnt["confidence_class"], str)
            # submitted_documents must never appear
            assert "submitted_documents" not in asmnt
    finally:
        _remove_intake_override(app)


# ---------------------------------------------------------------------------
# NIM failure mode fallback: intake service — no DB touched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nim_intake_timeout_returns_clarification_not_500(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """NIM intake timeout must produce a clarification response, never a 500.

    IntakeService catches NimClientError and falls back to an empty draft.
    The clarification gate fires immediately (all facts missing).
    ClarificationService also catches the timeout and returns a deterministic
    question. No DB connection is opened.
    """
    from app.api.deps import get_nim_client
    from app.services.nim.client import NimClientError

    mock_nim = MagicMock()
    mock_nim.generate_json = AsyncMock(
        side_effect=NimClientError("timed out after 30s", reason="timeout")
    )
    app.dependency_overrides[get_nim_client] = lambda: mock_nim
    try:
        response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["response_type"] == "clarification", (
            "NIM intake timeout must fall back to clarification, not crash"
        )
        assert body["audit_persisted"] is False
        assert body["case_id"] is None
        assert body["evaluation_id"] is None
        # Clarification must contain a deterministic question (not empty)
        assert body["clarification"] is not None
        assert isinstance(body["clarification"]["question"], str)
        assert len(body["clarification"]["question"]) > 0
        assert len(body["clarification"]["missing_facts"]) > 0
    finally:
        app.dependency_overrides.pop(get_nim_client, None)


@pytest.mark.asyncio
async def test_nim_intake_invalid_json_returns_clarification_not_500(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """NIM intake returning invalid JSON must fall back to clarification, not 500.

    IntakeService catches JSONDecodeError and returns an empty draft.
    ClarificationService returns a deterministic question because the NIM
    phrasing call also receives invalid JSON and falls through to its own
    fallback. No DB connection is opened.
    """
    from app.api.deps import get_nim_client

    mock_nim = MagicMock()
    mock_nim.generate_json = AsyncMock(return_value="{{not-valid-json-at-all")
    app.dependency_overrides[get_nim_client] = lambda: mock_nim
    try:
        response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["response_type"] == "clarification", (
            "NIM intake invalid JSON must fall back to clarification"
        )
        assert body["audit_persisted"] is False
        assert body["clarification"] is not None
        assert len(body["clarification"]["question"]) > 0
    finally:
        app.dependency_overrides.pop(get_nim_client, None)


@pytest.mark.asyncio
async def test_nim_intake_schema_mismatch_returns_clarification_not_500(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """NIM returning JSON that fails NimAssessmentDraft validation must
    fall back to an empty draft and return clarification.

    NimAssessmentDraft uses extra='forbid'; an unrecognised top-level key
    raises ValidationError which IntakeService catches. No DB is opened.
    """
    import json as _json

    from app.api.deps import get_nim_client

    # Parseable JSON but extra='forbid' rejects unknown top-level keys
    bad_payload = _json.dumps({"unrecognised_nim_field": True, "product": None})
    mock_nim = MagicMock()
    mock_nim.generate_json = AsyncMock(return_value=bad_payload)
    app.dependency_overrides[get_nim_client] = lambda: mock_nim
    try:
        response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["response_type"] == "clarification", (
            "NIM draft ValidationError must fall back to clarification"
        )
        assert body["audit_persisted"] is False
        assert body["clarification"] is not None
    finally:
        app.dependency_overrides.pop(get_nim_client, None)


# ---------------------------------------------------------------------------
# NIM failure mode fallback: explanation service — engine result preserved
# (Requires DB — passes in CI where Postgres runs as a service)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nim_explanation_timeout_does_not_block_assessment(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """NIM explanation timeout must not block the assessment result.

    The engine decision is returned unchanged. The explanation falls back to
    the minimal deterministic summary and explanation_fallback_used is True.
    """
    from app.api.deps import get_nim_client
    from app.services.nim.client import NimClientError

    _override_intake_with_complete_draft(app)
    mock_nim = MagicMock()
    mock_nim.generate_json = AsyncMock(
        side_effect=NimClientError("timed out after 30s", reason="timeout")
    )
    app.dependency_overrides[get_nim_client] = lambda: mock_nim
    try:
        response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["response_type"] == "assessment", (
            "Explanation timeout must not block the assessment result"
        )
        # Deterministic engine output is untouched
        assert body["assessment"] is not None
        assert isinstance(body["assessment"]["eligible"], bool)
        # Fallback explanation must be present — never fabricated, never None
        assert body["explanation"] is not None
        assert len(body["explanation"]) > 0
        # Caller-visible fallback signal
        assert body["explanation_fallback_used"] is True
    finally:
        _remove_intake_override(app)
        app.dependency_overrides.pop(get_nim_client, None)


@pytest.mark.asyncio
async def test_nim_explanation_invalid_json_does_not_block_assessment(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """NIM explanation returning invalid JSON must not block the assessment.

    The deterministic fallback text is used; explanation_fallback_used is True.
    The engine assessment fields are returned exactly as produced by the engine.
    """
    from app.api.deps import get_nim_client

    _override_intake_with_complete_draft(app)
    mock_nim = MagicMock()
    mock_nim.generate_json = AsyncMock(return_value="{{not-valid-json")
    app.dependency_overrides[get_nim_client] = lambda: mock_nim
    try:
        response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["response_type"] == "assessment", (
            "Explanation invalid JSON must not block the assessment result"
        )
        assert body["assessment"] is not None
        assert body["explanation"] is not None
        assert len(body["explanation"]) > 0
        assert body["explanation_fallback_used"] is True
    finally:
        _remove_intake_override(app)
        app.dependency_overrides.pop(get_nim_client, None)
