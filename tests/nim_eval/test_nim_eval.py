"""Mocked NIM evaluation harness for regression-safe prompt and model tuning."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.nim.intake import NimAssessmentDraft
from app.services.nim.intake_service import IntakeService
from tests.nim_eval.cases import NIM_EVAL_CASES


def _mock_nim_json(expected_fields: dict[str, object]) -> str:
    return json.dumps(
        {
            "product": {
                "hs6_code": expected_fields["hs6_code"],
                "hs_version": "HS2017",
                "product_description_parsed": None,
            },
            "trade_flow": {
                "exporter": expected_fields["exporter"],
                "importer": expected_fields["importer"],
                "year": expected_fields["year"],
            },
            "context": {
                "persona_mode": expected_fields["persona_mode"],
            },
            "production_facts": {"material_inputs": []},
            "existing_documents": [],
            "nim_confidence": {
                "overall": 0.9,
                "hs6_confidence": 0.9,
                "corridor_confidence": 0.9,
                "facts_confidence": 0.9,
            },
            "nim_assumptions": [],
        }
    )


def _mock_client(expected_fields: dict[str, object]) -> MagicMock:
    client = MagicMock()
    client.generate_json = AsyncMock(return_value=_mock_nim_json(expected_fields))
    return client


@pytest.mark.nim_eval
class TestNimEvaluationHarness:
    @staticmethod
    def _assert_expected_fields(
        draft: NimAssessmentDraft,
        expected_fields: dict[str, object],
    ) -> None:
        expected_hs6 = expected_fields["hs6_code"]
        expected_exporter = expected_fields["exporter"]
        expected_importer = expected_fields["importer"]
        expected_year = expected_fields["year"]
        expected_persona = expected_fields["persona_mode"]

        actual_hs6 = draft.product.hs6_code if draft.product else None
        actual_exporter = draft.trade_flow.exporter if draft.trade_flow else None
        actual_importer = draft.trade_flow.importer if draft.trade_flow else None
        actual_year = draft.trade_flow.year if draft.trade_flow else None
        actual_persona = (
            draft.context.persona_mode.value
            if draft.context and draft.context.persona_mode is not None
            else None
        )

        assert actual_hs6 == expected_hs6
        assert actual_exporter == expected_exporter
        assert actual_importer == expected_importer
        assert actual_year == expected_year
        assert actual_persona == expected_persona

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", NIM_EVAL_CASES, ids=[case["name"] for case in NIM_EVAL_CASES])
    async def test_parse_user_input_matches_eval_case(
        self,
        case: dict[str, object],
    ) -> None:
        expected_fields = case["expected_fields"]
        client = _mock_client(expected_fields)
        service = IntakeService(client)

        draft = await service.parse_user_input(case["user_input"])

        assert isinstance(draft, NimAssessmentDraft)
        client.generate_json.assert_awaited_once()
        self._assert_expected_fields(draft, expected_fields)

        if case["expected_clarification"]:
            assert draft.product is not None
            assert draft.trade_flow is not None
            assert draft.context is not None
            assert draft.product.hs6_code is None
            assert draft.trade_flow.exporter is None
            assert draft.trade_flow.importer is None
            assert draft.trade_flow.year is None
            assert draft.context.persona_mode is None
        else:
            assert draft.missing_required_facts() == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        [case for case in NIM_EVAL_CASES if not case["expected_clarification"]],
        ids=[case["name"] for case in NIM_EVAL_CASES if not case["expected_clarification"]],
    )
    async def test_to_eligibility_request_drops_nim_only_metadata(
        self,
        case: dict[str, object],
    ) -> None:
        expected_fields = case["expected_fields"]
        service = IntakeService(_mock_client(expected_fields))

        draft = await service.parse_user_input(case["user_input"])
        request_payload = service.to_eligibility_request(draft).model_dump()

        assert "nim_confidence" not in request_payload
        assert "nim_assumptions" not in request_payload
        assert "nim_rejection_reason" not in request_payload
