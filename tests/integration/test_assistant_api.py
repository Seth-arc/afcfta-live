"""Integration tests for the NIM assistant endpoint contract.

These tests pin the assistant-facing response shape and guard against
contract drift between the NIM orchestration layer and the deterministic
engine. They do NOT test model-calling logic (which is not yet wired).

Invariants that must always hold:
1. The endpoint requires authentication.
2. Every response is an AssistantResponseEnvelope with a known response_type.
3. Replay identifiers are null when response_type is not "assessment".
4. audit_persisted is False when response_type is not "assessment".
5. Exactly one of assessment/clarification/error is non-null per response.
6. The envelope never uses `submitted_documents` — only `existing_documents`.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

ASSISTANT_URL = "/api/v1/assistant/assess"

REQUIRED_ENVELOPE_FIELDS = {
    "response_type",
    "case_id",
    "evaluation_id",
    "audit_url",
    "audit_persisted",
    "assessment",
    "clarification",
    "explanation",
    "error",
}

REQUIRED_CLARIFICATION_FIELDS = {"question", "missing_facts", "missing_evidence"}

REQUIRED_ASSESSMENT_FIELDS = {
    "hs6_code",
    "eligible",
    "pathway_used",
    "rule_status",
    "tariff_outcome",
    "failures",
    "missing_facts",
    "evidence_required",
    "missing_evidence",
    "confidence_class",
    "audit_persisted",
}


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
    assert REQUIRED_ENVELOPE_FIELDS.issubset(set(body)), (
        f"Envelope missing fields: {REQUIRED_ENVELOPE_FIELDS - set(body)}"
    )


@pytest.mark.asyncio
async def test_assistant_response_type_is_a_known_discriminator_value(
    async_client: AsyncClient,
) -> None:
    """response_type must be one of the three known discriminator values."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    assert response.json()["response_type"] in {"clarification", "assessment", "error"}


@pytest.mark.asyncio
async def test_assistant_response_with_context_returns_valid_envelope(
    async_client: AsyncClient,
) -> None:
    """Requests with full context hints must also produce a valid envelope."""

    response = await async_client.post(ASSISTANT_URL, json=_request_with_context())

    assert response.status_code == 200, response.text
    body = response.json()
    assert REQUIRED_ENVELOPE_FIELDS.issubset(set(body))
    assert body["response_type"] in {"clarification", "assessment", "error"}


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
        assert REQUIRED_CLARIFICATION_FIELDS.issubset(set(clr)), (
            f"Clarification missing fields: {REQUIRED_CLARIFICATION_FIELDS - set(clr)}"
        )
        assert isinstance(clr["question"], str) and len(clr["question"]) > 0
        assert isinstance(clr["missing_facts"], list)
        assert isinstance(clr["missing_evidence"], list)


@pytest.mark.asyncio
async def test_harness_stub_returns_clarification(
    async_client: AsyncClient,
) -> None:
    """The contract harness must return clarification (no NIM model is wired yet)."""

    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response_type"] == "clarification", (
        "Harness stub must return clarification until NIM intake service is wired"
    )
    assert body["clarification"] is not None
    assert len(body["clarification"]["missing_facts"]) > 0


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
        assert REQUIRED_ASSESSMENT_FIELDS.issubset(set(asmnt)), (
            f"Assessment missing fields: {REQUIRED_ASSESSMENT_FIELDS - set(asmnt)}"
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
