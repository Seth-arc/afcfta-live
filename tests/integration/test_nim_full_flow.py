"""End-to-end validation for the NIM-assisted eligibility assessment flow.

Covers the complete orchestration path:

  NIM intake → completeness gate → deterministic engine → audit persistence
  → NIM explanation (or deterministic fallback) → AssistantResponseEnvelope

═══════════════════════════════════════════════════════════════════════════════
DB-INDEPENDENT TESTS  (Sections 1–2)
═══════════════════════════════════════════════════════════════════════════════
Run locally without Postgres. Validate the structural contract of every
response path (clarification, error) without touching the engine.

═══════════════════════════════════════════════════════════════════════════════
DB-DEPENDENT TESTS  (Sections 3–6)
═══════════════════════════════════════════════════════════════════════════════
Require a running Postgres instance. Fail with
  OSError: [Errno 10061] Connect call failed ('127.0.0.1', 5432)
when run locally without Postgres. All pass in CI.

These tests use a dependency override that injects a complete NimAssessmentDraft
(HS 110311, GHA→NGA, 2025, exporter) so the real engine and real persistence
path run. NIM is disabled in the test environment (NIM_ENABLED=false), so the
explanation always uses the deterministic fallback.

═══════════════════════════════════════════════════════════════════════════════
DETERMINISTIC INVARIANTS PROTECTED
═══════════════════════════════════════════════════════════════════════════════
ENGINE_FIELDS
  The five engine decision fields (eligible, pathway_used, rule_status,
  tariff_outcome, confidence_class) are sourced exclusively from
  EligibilityService.assess_interface_request(). NIM cannot alter them.
  Tests verify types, allowed-values, and cross-layer consistency.

ENVELOPE_CONTRACT
  The AssistantResponseEnvelope carries exactly the set of fields declared in
  the schema. No extra key may appear (hallucination guard).

REPLAY_LINKAGE
  case_id, evaluation_id, and audit_url in the assistant envelope match the
  evaluation stored in the DB. The audit endpoint must return the same
  eligible outcome as the assessment.

PERSISTENCE_GUARANTEE
  audit_persisted is True only when the engine ran and the evaluation was
  written to the DB. It is False for every non-assessment path.

EXPLANATION_SAFETY
  The deterministic fallback explanation text correctly reflects the engine's
  eligible field without contradiction. Raw user text never appears in any
  response field.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from tests.contract_constants import (
    ALL_REQUIRED_DRAFT_FACTS,
    ASSISTANT_ERROR_FIELDS,
    ASSISTANT_RESPONSE_ENVELOPE_FIELDS,
    CLARIFICATION_FIELDS,
    ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS,
    TARIFF_OUTCOME_FIELDS,
    VALID_CONFIDENCE_CLASSES,
)

pytestmark = pytest.mark.integration

ASSISTANT_URL = "/api/v1/assistant/assess"
AUDIT_URL = "/api/v1/audit/evaluations/{evaluation_id}"

# ─── Canonical field sets for hallucination guards ──────────────────────────

KNOWN_ASSESSMENT_FIELDS = ELIGIBILITY_ASSESSMENT_RESPONSE_FIELDS
KNOWN_TARIFF_FIELDS = TARIFF_OUTCOME_FIELDS
KNOWN_ENVELOPE_FIELDS = ASSISTANT_RESPONSE_ENVELOPE_FIELDS
KNOWN_CLARIFICATION_FIELDS = CLARIFICATION_FIELDS
KNOWN_ERROR_FIELDS = ASSISTANT_ERROR_FIELDS


# ─── Shared test inputs ──────────────────────────────────────────────────────


def _minimal_request() -> dict[str, object]:
    return {"user_input": "Can I export HS 110311 from Ghana to Nigeria?"}


def _full_context_request() -> dict[str, object]:
    return {
        "user_input": "Can I export wheat groats from Ghana to Nigeria in 2025?",
        "context": {
            "persona_mode": "exporter",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
        },
    }


# ─── Intake override helpers (kept local to this file) ──────────────────────


def _complete_gha_nga_draft():
    """Return a complete NimAssessmentDraft for HS 110311, GHA→NGA, 2025, exporter."""
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


def _install_complete_draft_override(app: FastAPI) -> None:
    """Override get_intake_service to return a complete draft without calling NIM."""
    from app.api.deps import get_intake_service
    from app.services.nim.intake_service import IntakeService

    draft = _complete_gha_nga_draft()
    real_svc = IntakeService(MagicMock())
    mock_svc = MagicMock(spec=IntakeService)
    mock_svc.parse_user_input = AsyncMock(return_value=draft)
    mock_svc.to_eligibility_request = real_svc.to_eligibility_request
    mock_svc.nim_client = MagicMock(enabled=False, model="")
    app.dependency_overrides[get_intake_service] = lambda: mock_svc


def _remove_complete_draft_override(app: FastAPI) -> None:
    from app.api.deps import get_intake_service
    app.dependency_overrides.pop(get_intake_service, None)


# ═══════════════════════════════════════════════════════════════════════════
# Section 1 — Structural envelope contract (no DB)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_clarification_envelope_carries_all_declared_fields(
    async_client: AsyncClient,
) -> None:
    """Every field in AssistantResponseEnvelope must be present in a clarification
    response. Missing keys indicate a schema change that broke the contract.
    """
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response_type"] == "clarification"
    assert KNOWN_ENVELOPE_FIELDS.issubset(set(body)), (
        f"Envelope missing fields: {KNOWN_ENVELOPE_FIELDS - set(body)}"
    )


@pytest.mark.asyncio
async def test_clarification_envelope_contains_no_hallucinated_fields(
    async_client: AsyncClient,
) -> None:
    """The clarification envelope must contain exactly the declared fields — no more.

    Any key outside KNOWN_ENVELOPE_FIELDS is a schema regression or injection.
    """
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response_type"] == "clarification"
    extra = set(body.keys()) - KNOWN_ENVELOPE_FIELDS
    assert extra == set(), f"Unexpected envelope fields (hallucination guard): {extra}"


@pytest.mark.asyncio
async def test_clarification_response_object_contains_no_hallucinated_fields(
    async_client: AsyncClient,
) -> None:
    """The clarification payload must carry only the fields in ClarificationResponse."""
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    body = response.json()
    assert body["response_type"] == "clarification"
    clr = body["clarification"]
    extra = set(clr.keys()) - KNOWN_CLARIFICATION_FIELDS
    assert extra == set(), f"Unexpected clarification fields: {extra}"


@pytest.mark.asyncio
async def test_clarification_reports_all_five_required_facts_when_nim_disabled(
    async_client: AsyncClient,
) -> None:
    """With NIM disabled, the empty draft is returned and all five required facts
    must be reported as missing so the user knows exactly what to provide.
    """
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    body = response.json()
    assert body["response_type"] == "clarification"
    reported = set(body["clarification"]["missing_facts"])
    assert ALL_REQUIRED_DRAFT_FACTS.issubset(reported), (
        f"Not all required facts reported as missing: "
        f"{ALL_REQUIRED_DRAFT_FACTS - reported}"
    )


@pytest.mark.asyncio
async def test_clarification_path_invariants_hold(
    async_client: AsyncClient,
) -> None:
    """Clarification responses must satisfy all non-assessment-path invariants."""
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    body = response.json()
    assert body["response_type"] == "clarification"
    # No engine ran — audit fields must all be null / False
    assert body["audit_persisted"] is False
    assert body["case_id"] is None
    assert body["evaluation_id"] is None
    assert body["audit_url"] is None
    # Payload separation — only clarification slot is populated
    assert body["assessment"] is None
    assert body["error"] is None
    assert body["clarification"] is not None
    # explanation_fallback_used must be the default when no engine ran
    assert body["explanation_fallback_used"] is False


@pytest.mark.asyncio
async def test_clarification_question_is_non_empty_string(
    async_client: AsyncClient,
) -> None:
    """The clarification question must be a non-empty string (deterministic fallback)."""
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())

    clr = response.json()["clarification"]
    assert isinstance(clr["question"], str)
    assert len(clr["question"].strip()) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Section 2 — Error path structural contract (no DB)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_error_response_invariants_hold_when_triggered(
    async_client: AsyncClient,
) -> None:
    """When response_type is 'error', the error slot is populated and all
    persistence-claiming fields are False/None.

    This test fires vacuously on the condition (not forced to error path here)
    but guards the invariant so that if an error path is reached, it is valid.
    """
    response = await async_client.post(ASSISTANT_URL, json=_minimal_request())
    body = response.json()

    if body["response_type"] == "error":
        err = body["error"]
        assert err is not None
        assert isinstance(err.get("code"), str) and len(err["code"]) > 0
        assert isinstance(err.get("message"), str)
        extra = set(err.keys()) - KNOWN_ERROR_FIELDS
        assert extra == set(), f"Unexpected error fields: {extra}"
        assert body["audit_persisted"] is False
        assert body["case_id"] is None
        assert body["assessment"] is None
        assert body["clarification"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Section 3 — Full flow: assessment response integrity (requires DB)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_full_flow_returns_assessment_with_required_fields(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """Complete draft → engine → audit persistence → assessment response with
    all engine-output fields populated and correctly typed.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["response_type"] == "assessment", (
            f"Expected 'assessment', got '{body['response_type']}'. "
            f"clarification={body.get('clarification')}, error={body.get('error')}"
        )
        asmnt = body["assessment"]
        assert asmnt is not None
        # All declared fields must be present
        assert KNOWN_ASSESSMENT_FIELDS.issubset(set(asmnt)), (
            f"Assessment missing fields: {KNOWN_ASSESSMENT_FIELDS - set(asmnt)}"
        )
        # HS code passed through correctly
        assert asmnt["hs6_code"] == "110311"
        # Core types — engine output is never a string for these
        assert isinstance(asmnt["eligible"], bool)
        assert isinstance(asmnt["failures"], list)
        assert isinstance(asmnt["missing_facts"], list)
        assert isinstance(asmnt["evidence_required"], list)
        assert isinstance(asmnt["missing_evidence"], list)
        assert asmnt["confidence_class"] in VALID_CONFIDENCE_CLASSES
        assert isinstance(asmnt["rule_status"], str)
        # Replay identifiers populated
        assert isinstance(body["audit_persisted"], bool)
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_full_flow_assessment_envelope_contains_no_hallucinated_fields(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The assessment envelope must contain exactly the declared fields.

    Any key outside KNOWN_ENVELOPE_FIELDS is a schema regression or injection.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        extra_envelope = set(body.keys()) - KNOWN_ENVELOPE_FIELDS
        assert extra_envelope == set(), (
            f"Unexpected envelope fields (hallucination guard): {extra_envelope}"
        )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_full_flow_assessment_payload_contains_no_hallucinated_fields(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The assessment payload must contain exactly the declared engine-output fields.

    No field may appear outside KNOWN_ASSESSMENT_FIELDS.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        asmnt = body["assessment"]
        extra = set(asmnt.keys()) - KNOWN_ASSESSMENT_FIELDS
        assert extra == set(), (
            f"Unexpected assessment fields (hallucination guard): {extra}"
        )

        # Tariff outcome sub-object also guarded when present
        if asmnt["tariff_outcome"] is not None:
            tariff = asmnt["tariff_outcome"]
            extra_tariff = set(tariff.keys()) - KNOWN_TARIFF_FIELDS
            assert extra_tariff == set(), (
                f"Unexpected tariff_outcome fields: {extra_tariff}"
            )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_full_flow_submitted_documents_never_appears(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The legacy 'submitted_documents' field must never appear anywhere in the response.

    'existing_documents' is the canonical field name. This guard catches any
    serialisation regression that would leak the backward-compat alias.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        assert "submitted_documents" not in response.text, (
            "Legacy field 'submitted_documents' must not appear in any response. "
            "Use 'existing_documents' exclusively."
        )
    finally:
        _remove_complete_draft_override(app)


# ═══════════════════════════════════════════════════════════════════════════
# Section 4 — Engine field integrity: NIM must not alter deterministic fields
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_eligible_field_is_a_strict_bool_not_nim_derived(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """eligible must be a Python bool from the deterministic engine.

    If NIM somehow introduced a string like 'true' or an integer, this fails.
    The engine serialises eligible as JSON true/false; NIM text is never parsed
    back into this field.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        eligible = body["assessment"]["eligible"]
        # JSON bool parses as Python bool — must not be a string or integer
        assert isinstance(eligible, bool), (
            f"eligible must be a JSON boolean, got {type(eligible).__name__}: {eligible!r}"
        )
        assert eligible is not None
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_confidence_class_is_one_of_the_three_engine_values(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """confidence_class must be one of the three values the engine emits.

    Any other value indicates NIM injected free-form text into a deterministic slot.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        cc = body["assessment"]["confidence_class"]
        assert cc in VALID_CONFIDENCE_CLASSES, (
            f"confidence_class '{cc}' is not a valid engine value. "
            f"Expected one of {VALID_CONFIDENCE_CLASSES}. "
            "NIM must not write to this field."
        )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_rule_status_is_a_known_enum_value(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """rule_status must be a value from RuleStatusEnum — never free-form NIM text."""
    from app.core.enums import RuleStatusEnum

    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        rule_status = body["assessment"]["rule_status"]
        valid_values = {e.value for e in RuleStatusEnum}
        assert rule_status in valid_values, (
            f"rule_status '{rule_status}' is not a known RuleStatusEnum value {valid_values}. "
            "NIM must not write to this field."
        )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_hs6_code_in_response_matches_draft_code_not_nim_interpretation(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The hs6_code in the assessment must be the normalised engine input ('110311'),
    not any NIM-reinterpreted form (e.g. 'HS 110311' or '1103.11').
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        hs6 = body["assessment"]["hs6_code"]
        assert hs6 == "110311", (
            f"hs6_code should be exactly '110311', got '{hs6}'. "
            "Engine normalization must produce 6-digit clean code."
        )
    finally:
        _remove_complete_draft_override(app)


# ═══════════════════════════════════════════════════════════════════════════
# Section 5 — Replay linkage and audit persistence (requires DB)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_assessment_response_has_all_three_replay_identifiers(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """case_id, evaluation_id, and audit_url must all be non-null for assessment
    responses. These are the three handles a client needs to replay the decision.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        assert body["case_id"] is not None, "case_id must be set"
        assert body["evaluation_id"] is not None, "evaluation_id must be set"
        assert body["audit_url"] is not None, "audit_url must be set"
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_audit_url_embeds_evaluation_id_for_deterministic_replay(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """audit_url must be the canonical path that embeds evaluation_id.

    A client constructing a replay request from the envelope must be able to
    derive the exact audit URL from evaluation_id alone.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        evaluation_id = body["evaluation_id"]
        expected_url = f"/api/v1/audit/evaluations/{evaluation_id}"
        assert body["audit_url"] == expected_url, (
            f"audit_url must embed evaluation_id. "
            f"Expected '{expected_url}', got '{body['audit_url']}'"
        )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_response_headers_match_body_replay_identifiers(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """X-AIS-* response headers must match body identifiers exactly.

    The headers are the fast-path for replay tooling. Any mismatch between
    headers and body would cause silent replay failures.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        assert response.headers.get("x-ais-case-id") == body["case_id"]
        assert response.headers.get("x-ais-evaluation-id") == body["evaluation_id"]
        assert response.headers.get("x-ais-audit-url") == body["audit_url"]
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_audit_persisted_is_true_only_when_engine_ran(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """audit_persisted must be True when the engine ran and persisted the evaluation.

    This is the claim that the decision is replayable. It must not be synthetically
    set to True — it must come from the engine's own persistence flag.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        # The engine's audit_persisted bubbles up unchanged via result.response
        assert isinstance(body["audit_persisted"], bool)
        # When the engine successfully persisted, this must be True
        assert body["audit_persisted"] is True, (
            "audit_persisted must be True after a successful engine run with DB persistence. "
            "If False, the evaluation was not committed and cannot be replayed."
        )
    finally:
        _remove_complete_draft_override(app)


# ═══════════════════════════════════════════════════════════════════════════
# Section 6 — Audit trail replay via evaluation_id (requires DB)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_audit_endpoint_returns_200_for_evaluation_from_assistant(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The evaluation_id from the assistant response must resolve to a stored
    audit trail via GET /api/v1/audit/evaluations/{evaluation_id}.

    A 404 here means the engine claimed to persist but the audit layer cannot
    find it — a broken replayability guarantee.
    """
    _install_complete_draft_override(app)
    try:
        assess_resp = await async_client.post(
            ASSISTANT_URL, json=_full_context_request()
        )
        body = assess_resp.json()
        assert body["response_type"] == "assessment"
        evaluation_id = body["evaluation_id"]

        audit_resp = await async_client.get(
            AUDIT_URL.format(evaluation_id=evaluation_id)
        )
        assert audit_resp.status_code == 200, (
            f"Audit trail not found for evaluation_id '{evaluation_id}'. "
            f"Response: {audit_resp.text}"
        )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_audit_trail_evaluation_id_matches_assistant_response(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The evaluation stored in the audit trail must have the same evaluation_id
    as the one the assistant returned.

    This closes the loop: the identifier the assistant gave to the client
    actually points to the evaluation that was persisted.
    """
    _install_complete_draft_override(app)
    try:
        assess_resp = await async_client.post(
            ASSISTANT_URL, json=_full_context_request()
        )
        body = assess_resp.json()
        assert body["response_type"] == "assessment"
        evaluation_id = body["evaluation_id"]
        case_id = body["case_id"]

        audit_resp = await async_client.get(
            AUDIT_URL.format(evaluation_id=evaluation_id)
        )
        assert audit_resp.status_code == 200
        trail = audit_resp.json()

        # evaluation_id in the trail must match the assistant's evaluation_id
        assert str(trail["evaluation"]["evaluation_id"]) == evaluation_id, (
            "audit trail evaluation_id does not match assistant response evaluation_id"
        )
        # case_id in the trail must match the assistant's case_id
        assert str(trail["evaluation"]["case_id"]) == case_id, (
            "audit trail case_id does not match assistant response case_id"
        )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_audit_trail_eligible_matches_assessment_response_eligible(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The eligible outcome in the audit trail's final_decision must match the
    eligible field in the assistant's assessment response.

    This is the primary cross-layer determinism invariant:
    - The assistant returns what the engine decided.
    - The audit trail records what the engine decided.
    - They must be identical for the response to be replayable.
    """
    _install_complete_draft_override(app)
    try:
        assess_resp = await async_client.post(
            ASSISTANT_URL, json=_full_context_request()
        )
        body = assess_resp.json()
        assert body["response_type"] == "assessment"
        assessment_eligible = body["assessment"]["eligible"]
        evaluation_id = body["evaluation_id"]

        audit_resp = await async_client.get(
            AUDIT_URL.format(evaluation_id=evaluation_id)
        )
        assert audit_resp.status_code == 200
        trail = audit_resp.json()

        trail_eligible = trail["final_decision"]["eligible"]
        assert trail_eligible == assessment_eligible, (
            f"Audit trail final_decision.eligible ({trail_eligible}) does not match "
            f"assessment.eligible ({assessment_eligible}). "
            "The NIM layer must not alter the engine's persisted decision."
        )
    finally:
        _remove_complete_draft_override(app)


# ═══════════════════════════════════════════════════════════════════════════
# Section 7 — Explanation invariants (requires DB for assessment path)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_nim_disabled_produces_explanation_fallback_used_true(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """With NIM disabled (NIM_ENABLED=false, default in tests), the explanation
    must always use the deterministic fallback.

    explanation_fallback_used=True is the observable signal that the fallback
    fired. explanation must still be non-null — fallback always produces text.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        assert body["explanation_fallback_used"] is True, (
            "NIM is disabled in tests — explanation_fallback_used must be True"
        )
        assert body["explanation"] is not None, (
            "Deterministic fallback must produce explanation text, never None"
        )
        assert len(body["explanation"].strip()) > 0
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_fallback_explanation_text_reflects_engine_eligible_outcome(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The deterministic fallback explanation must correctly reflect the engine's
    eligible field.

    _build_fallback_text() produces "Assessment outcome: eligible." or
    "Assessment outcome: not eligible." — we verify the text is consistent with
    the engine output. Any mismatch would mean explanation contradicts the decision.
    """
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(ASSISTANT_URL, json=_full_context_request())
        body = response.json()
        assert body["response_type"] == "assessment"

        eligible = body["assessment"]["eligible"]
        explanation = body["explanation"] or ""

        if eligible:
            # Fallback starts "Assessment outcome: eligible."
            assert "not eligible" not in explanation.lower(), (
                "Explanation must not claim ineligibility when engine says eligible. "
                f"Got: {explanation!r}"
            )
            assert "eligible" in explanation.lower(), (
                "Fallback explanation must mention the eligible outcome. "
                f"Got: {explanation!r}"
            )
        else:
            # Fallback starts "Assessment outcome: not eligible."
            assert "not eligible" in explanation.lower(), (
                "Explanation must reflect ineligibility when engine says not eligible. "
                f"Got: {explanation!r}"
            )
    finally:
        _remove_complete_draft_override(app)


@pytest.mark.asyncio
async def test_fallback_explanation_never_contains_raw_user_input(
    app: FastAPI,
    async_client: AsyncClient,
) -> None:
    """The explanation field must never contain the raw user_input text.

    The fallback is built from engine output fields only. If user text appears
    in the explanation, a prompt-injection or echo path is leaking through.
    """
    user_input = "Can I export wheat groats from Ghana to Nigeria in 2025?"
    _install_complete_draft_override(app)
    try:
        response = await async_client.post(
            ASSISTANT_URL,
            json={
                "user_input": user_input,
                "context": {
                    "persona_mode": "exporter",
                    "exporter": "GHA",
                    "importer": "NGA",
                    "year": 2025,
                },
            },
        )
        body = response.json()
        assert body["response_type"] == "assessment"

        explanation = body["explanation"] or ""
        assert user_input not in explanation, (
            "Raw user_input must never appear in explanation. "
            "Explanation is built from engine output fields only."
        )
    finally:
        _remove_complete_draft_override(app)
