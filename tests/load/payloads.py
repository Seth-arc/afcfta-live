"""
Deterministic wire-format payloads for the AIS load test harness.

Every payload matches a seeded HS6/corridor combination that is present in the
deterministic seed slice.  Using fixed inputs means the load harness exercises
real engine paths — classification, rule resolution, tariff lookup, evidence
scoring — without depending on random or synthetic data that might not exist in
the database.

Payloads are expressed in the exact JSON shape expected by
POST /api/v1/assessments so that the harness can send them without any
conversion step.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Payload type alias: each entry is a ready-to-POST JSON-serialisable dict.
# ---------------------------------------------------------------------------

LOAD_PAYLOADS: list[dict] = [
    # ------------------------------------------------------------------
    # 1. GHA → NGA  |  HS 110311 (groats / meal)  |  CTH pathway  |  PASS
    #    Tests: classification, CTH rule evaluation, tariff lookup,
    #           evidence readiness, audit persistence.
    # ------------------------------------------------------------------
    {
        "hs6_code": "110311",
        "hs_version": "HS2017",
        "exporter": "GHA",
        "importer": "NGA",
        "year": 2025,
        "persona_mode": "exporter",
        "existing_documents": ["certificate_of_origin", "invoice"],
        "production_facts": [
            {
                "fact_type": "tariff_heading_input",
                "fact_key": "tariff_heading_input",
                "fact_value_type": "text",
                "fact_value_text": "1001",
            },
            {
                "fact_type": "tariff_heading_output",
                "fact_key": "tariff_heading_output",
                "fact_value_type": "text",
                "fact_value_text": "1103",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # 2. CMR → NGA  |  HS 271019 (petroleum)  |  VNM pathway  |  PASS
    #    Tests: VNM formula evaluation (non_originating / ex_works * 100),
    #           tariff lookup on a different corridor.
    # ------------------------------------------------------------------
    {
        "hs6_code": "271019",
        "hs_version": "HS2017",
        "exporter": "CMR",
        "importer": "NGA",
        "year": 2025,
        "persona_mode": "exporter",
        "existing_documents": ["certificate_of_origin"],
        "production_facts": [
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": "100000",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": "55000",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # 3. CIV → NGA  |  HS 080111 (coconuts)  |  WO pathway  |  PASS
    #    Tests: wholly-obtained short path — the simplest engine branch.
    #    Useful as a latency baseline because no formula computation is needed.
    # ------------------------------------------------------------------
    {
        "hs6_code": "080111",
        "hs_version": "HS2017",
        "exporter": "CIV",
        "importer": "NGA",
        "year": 2025,
        "persona_mode": "exporter",
        "existing_documents": ["certificate_of_origin"],
        "production_facts": [
            {
                "fact_type": "wholly_obtained",
                "fact_key": "wholly_obtained",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # 4. SEN → NGA  |  HS 290110 (ethylene)  |  VNM pathway  |  PASS
    #    Tests: a third corridor under load — exercises the corridor-profile
    #           and status-overlay paths independently of the GHA/CMR cases.
    # ------------------------------------------------------------------
    {
        "hs6_code": "290110",
        "hs_version": "HS2017",
        "exporter": "SEN",
        "importer": "NGA",
        "year": 2025,
        "persona_mode": "exporter",
        "existing_documents": ["certificate_of_origin", "supplier_declaration"],
        "production_facts": [
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": "100000",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": "35000",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    },
    # ------------------------------------------------------------------
    # 5. CMR → NGA  |  HS 271019 (petroleum)  |  VNM  |  FAIL (over threshold)
    #    Tests: engine failure paths under load — confirms the error envelope
    #           and 200-with-eligible=false response structure holds up.
    # ------------------------------------------------------------------
    {
        "hs6_code": "271019",
        "hs_version": "HS2017",
        "exporter": "CMR",
        "importer": "NGA",
        "year": 2025,
        "persona_mode": "exporter",
        "existing_documents": [],
        "production_facts": [
            {
                "fact_type": "ex_works",
                "fact_key": "ex_works",
                "fact_value_type": "number",
                "fact_value_number": "100000",
            },
            {
                "fact_type": "non_originating",
                "fact_key": "non_originating",
                "fact_value_type": "number",
                "fact_value_number": "65000",
            },
            {
                "fact_type": "direct_transport",
                "fact_key": "direct_transport",
                "fact_value_type": "boolean",
                "fact_value_boolean": True,
            },
            {
                "fact_type": "cumulation_claimed",
                "fact_key": "cumulation_claimed",
                "fact_value_type": "boolean",
                "fact_value_boolean": False,
            },
        ],
    },
]
