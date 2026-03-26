"""
Golden test cases for v0.1 acceptance criteria.
Each case defines exact inputs and expected outputs.
Corpus coverage after the Q2 2026 corridor expansion:
- 6 directed v0.1 corridors
- 9 HS6 chapters
"""

GOLDEN_CASES = [
    {
        "name": "GHA->NGA groats CTH pass",
        "input": {
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "1001",
                "tariff_heading_output": "1103",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "CTH",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "GHA->NGA groats CTH fail - no tariff shift",
        "input": {
            "hs6_code": "110311",
            "hs_version": "HS2017",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "1103",
                "tariff_heading_output": "1103",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_CTH_NOT_MET"],
        },
    },
    {
        "name": "CMR->NGA petroleum VNM pass",
        "input": {
            "hs6_code": "271019",
            "hs_version": "HS2017",
            "exporter": "CMR",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "ex_works": 100000,
                "non_originating": 55000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "VNM",
            "rule_status": "agreed",
        },
    },
    {
        "name": "CMR->NGA petroleum VNM fail - over threshold",
        "input": {
            "hs6_code": "271019",
            "hs_version": "HS2017",
            "exporter": "CMR",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "ex_works": 100000,
                "non_originating": 65000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_VNM_EXCEEDED"],
        },
    },
    {
        "name": "Missing facts - incomplete assessment",
        "input": {
            "hs6_code": "271019",
            "hs_version": "HS2017",
            "exporter": "CMR",
            "importer": "NGA",
            "year": 2025,
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
            "hs6_code": "610910",
            "hs_version": "HS2017",
            "exporter": "GHA",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "5208",
                "tariff_heading_output": "6109",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "CTH",
            "rule_status": "provisional",
            "confidence_class": "provisional",
        },
    },
    {
        "name": "CIV->NGA agricultural WO pass",
        "input": {
            "hs6_code": "080111",
            "hs_version": "HS2017",
            "exporter": "CIV",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "wholly_obtained": True,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "WO",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "SEN->NGA chemical VNM pass",
        "input": {
            "hs6_code": "290110",
            "hs_version": "HS2017",
            "exporter": "SEN",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "ex_works": 100000,
                "non_originating": 35000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "VNM",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "CIV->NGA machinery VNM pass",
        "input": {
            "hs6_code": "840820",
            "hs_version": "HS2017",
            "exporter": "CIV",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "ex_works": 100000,
                "non_originating": 45000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "VNM",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "CIV->NGA apparel WO pass",
        "seed": {
            "scenario_tag": "civ-nga-apparel-wo",
            "chapter": "62",
            "heading": "6209",
            "description": "Synthetic infant garments golden fixture",
            "pathway_code": "WO",
        },
        "input": {
            "hs6_code": "620910",
            "hs_version": "HS2017",
            "exporter": "CIV",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "wholly_obtained": True,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "WO",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "CIV->NGA apparel WO fail - direct transport broken",
        "seed": {
            "scenario_tag": "civ-nga-apparel-wo",
            "chapter": "62",
            "heading": "6209",
            "description": "Synthetic infant garments golden fixture",
            "pathway_code": "WO",
        },
        "input": {
            "hs6_code": "620910",
            "hs_version": "HS2017",
            "exporter": "CIV",
            "importer": "NGA",
            "year": 2025,
            "facts": {
                "wholly_obtained": True,
                "direct_transport": False,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_DIRECT_TRANSPORT"],
        },
    },
    {
        "name": "CIV->SEN coffee CTH pass",
        "seed": {
            "scenario_tag": "civ-sen-coffee-cth",
            "chapter": "09",
            "heading": "0901",
            "description": "Synthetic coffee not roasted golden fixture",
            "pathway_code": "CTH",
        },
        "input": {
            "hs6_code": "090111",
            "hs_version": "HS2017",
            "exporter": "CIV",
            "importer": "SEN",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "2101",
                "tariff_heading_output": "0901",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "CTH",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "CIV->SEN coffee CTH fail - no tariff shift",
        "seed": {
            "scenario_tag": "civ-sen-coffee-cth",
            "chapter": "09",
            "heading": "0901",
            "description": "Synthetic coffee not roasted golden fixture",
            "pathway_code": "CTH",
        },
        "input": {
            "hs6_code": "090111",
            "hs_version": "HS2017",
            "exporter": "CIV",
            "importer": "SEN",
            "year": 2025,
            "facts": {
                "tariff_heading_input": "0901",
                "tariff_heading_output": "0901",
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_CTH_NOT_MET"],
        },
    },
    {
        "name": "NGA->GHA iron VNM within threshold",
        "seed": {
            "scenario_tag": "nga-gha-iron-vnm",
            "chapter": "72",
            "heading": "7202",
            "description": "Synthetic ferro-manganese golden fixture",
            "pathway_code": "VNM",
        },
        "input": {
            "hs6_code": "720211",
            "hs_version": "HS2017",
            "exporter": "NGA",
            "importer": "GHA",
            "year": 2025,
            "facts": {
                "ex_works": 50000,
                "non_originating": 18000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": True,
            "pathway_used": "VNM",
            "rule_status": "agreed",
            "confidence_class": "complete",
            "failures": [],
            "missing_facts": [],
        },
    },
    {
        "name": "NGA->GHA iron VNM fail - over threshold",
        "seed": {
            "scenario_tag": "nga-gha-iron-vnm",
            "chapter": "72",
            "heading": "7202",
            "description": "Synthetic ferro-manganese golden fixture",
            "pathway_code": "VNM",
        },
        "input": {
            "hs6_code": "720211",
            "hs_version": "HS2017",
            "exporter": "NGA",
            "importer": "GHA",
            "year": 2025,
            "facts": {
                "ex_works": 50000,
                "non_originating": 22000,
                "direct_transport": True,
                "cumulation_claimed": False,
            },
        },
        "expected": {
            "eligible": False,
            "failure_codes": ["FAIL_VNM_EXCEEDED"],
        },
    },
]
