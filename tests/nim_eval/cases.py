"""Seed evaluation cases for the mocked NIM regression harness.

These cases are derived from the locked golden corpus so future NIM tuning
stays anchored to supported v0.1 corridors and HS6 products.
"""

from __future__ import annotations

from tests.fixtures.golden_cases import GOLDEN_CASES


def _golden_case(name: str) -> dict[str, object]:
    for case in GOLDEN_CASES:
        if case["name"] == name:
            return case
    raise ValueError(f"Golden case not found: {name}")


_GROATS_CASE = _golden_case("GHA->NGA groats CTH pass")
_APPAREL_CASE = _golden_case("CIV->NGA apparel WO pass")


NIM_EVAL_CASES: list[dict[str, object]] = [
    {
        "name": "GHA->NGA groats complete parse",
        "user_input": (
            "Can I export wheat groats HS 110311 from Ghana to Nigeria in 2025 "
            "under AfCFTA?"
        ),
        "expected_fields": {
            "hs6_code": _GROATS_CASE["input"]["hs6_code"],
            "exporter": _GROATS_CASE["input"]["exporter"],
            "importer": _GROATS_CASE["input"]["importer"],
            "year": _GROATS_CASE["input"]["year"],
            "persona_mode": "exporter",
        },
        "expected_clarification": False,
    },
    {
        "name": "CIV->NGA apparel officer parse",
        "user_input": (
            "I am a customs officer reviewing infant garments HS 620910 from "
            "Cote d'Ivoire to Nigeria for 2025. Does the AfCFTA route apply?"
        ),
        "expected_fields": {
            "hs6_code": _APPAREL_CASE["input"]["hs6_code"],
            "exporter": _APPAREL_CASE["input"]["exporter"],
            "importer": _APPAREL_CASE["input"]["importer"],
            "year": _APPAREL_CASE["input"]["year"],
            "persona_mode": "officer",
        },
        "expected_clarification": False,
    },
    {
        "name": "CMR->NGA petroleum clarification required",
        "user_input": (
            "Need AfCFTA guidance for the Cameroon to Nigeria petroleum shipment."
        ),
        "expected_fields": {
            "hs6_code": None,
            "exporter": None,
            "importer": None,
            "year": None,
            "persona_mode": None,
        },
        "expected_clarification": True,
    },
]
