"""
Golden test cases for v0.1 acceptance criteria.
Each case defines exact inputs and expected outputs.
"""

GOLDEN_CASES = [
    {
        "name": "GHA→NGA groats CTH pass",
        "input": {
            "hs6_code": "110311", "hs_version": "HS2017",
            "exporter": "GHA", "importer": "NGA", "year": 2025,
            "facts": {
                "tariff_heading_input": "1001",
                "tariff_heading_output": "1103",
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "CTH",
            "rule_status": "agreed", "confidence_class": "complete",
            "failures": [], "missing_facts": [],
        },
    },
    {
        "name": "GHA→NGA groats CTH fail — no tariff shift",
        "input": {
            "hs6_code": "110311", "hs_version": "HS2017",
            "exporter": "GHA", "importer": "NGA", "year": 2025,
            "facts": {
                "tariff_heading_input": "1103",
                "tariff_heading_output": "1103",
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {"eligible": False, "failure_codes": ["FAIL_CTH_NOT_MET"]},
    },
    {
        "name": "CMR→NGA petroleum VNM pass",
        "input": {
            "hs6_code": "271019", "hs_version": "HS2017",
            "exporter": "CMR", "importer": "NGA", "year": 2025,
            "facts": {
                "ex_works": 100000, "non_originating": 55000,
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "VNM", "rule_status": "agreed",
        },
    },
    {
        "name": "CMR→NGA petroleum VNM fail — over threshold",
        "input": {
            "hs6_code": "271019", "hs_version": "HS2017",
            "exporter": "CMR", "importer": "NGA", "year": 2025,
            "facts": {
                "ex_works": 100000, "non_originating": 65000,
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {"eligible": False, "failure_codes": ["FAIL_VNM_EXCEEDED"]},
    },
    {
        "name": "Missing facts — incomplete assessment",
        "input": {
            "hs6_code": "271019", "hs_version": "HS2017",
            "exporter": "CMR", "importer": "NGA", "year": 2025,
            "facts": {"direct_transport": True},
        },
        "expected": {
            "eligible": False,
            "missing_facts": ["ex_works", "non_originating"],
            "confidence_class": "incomplete",
        },
    },
    {
        "name": "Provisional rule status",
        "input": {
            "hs6_code": "610910", "hs_version": "HS2017",
            "exporter": "GHA", "importer": "NGA", "year": 2025,
            "facts": {
                "tariff_heading_input": "5208",
                "tariff_heading_output": "6109",
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "CTH",
            "rule_status": "provisional", "confidence_class": "provisional",
        },
    },
    {
        "name": "CIV→NGA agricultural WO pass",
        "input": {
            "hs6_code": "080111", "hs_version": "HS2017",
            "exporter": "CIV", "importer": "NGA", "year": 2025,
            "facts": {
                "wholly_obtained": True,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "WO",
            "rule_status": "agreed", "confidence_class": "complete",
            "failures": [], "missing_facts": [],
        },
    },
    {
        "name": "SEN→NGA chemical VNM pass",
        "input": {
            "hs6_code": "290110", "hs_version": "HS2017",
            "exporter": "SEN", "importer": "NGA", "year": 2025,
            "facts": {
                "ex_works": 100000, "non_originating": 35000,
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "VNM",
            "rule_status": "agreed", "confidence_class": "complete",
            "failures": [], "missing_facts": [],
        },
    },
    {
        "name": "CIV→NGA machinery VNM pass",
        "input": {
            "hs6_code": "840820", "hs_version": "HS2017",
            "exporter": "CIV", "importer": "NGA", "year": 2025,
            "facts": {
                "ex_works": 100000, "non_originating": 45000,
                "direct_transport": True, "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True, "pathway_used": "VNM",
            "rule_status": "agreed", "confidence_class": "complete",
            "failures": [], "missing_facts": [],
        },
    },
]