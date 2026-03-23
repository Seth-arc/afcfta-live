"""Seed deterministic v0.1 reference data for local testing and golden-case validation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.countries import V01_CORRIDORS
from app.core.entity_keys import make_entity_key
from app.core.enums import (
    AuthorityTierEnum,
    CorridorStatusEnum,
    HsLevelEnum,
    InstrumentTypeEnum,
    OperatorTypeEnum,
    PersonaModeEnum,
    ProvisionStatusEnum,
    RateStatusEnum,
    RequirementTypeEnum,
    RuleComponentTypeEnum,
    RuleStatusEnum,
    ScheduleStatusEnum,
    SourceStatusEnum,
    SourceTypeEnum,
    StagingTypeEnum,
    StatusTypeEnum,
    TariffCategoryEnum,
    ThresholdBasisEnum,
    VerificationRiskCategoryEnum,
)
from app.db.models.evidence import EvidenceRequirement, VerificationQuestion
from app.db.models.hs import HS6Product
from app.db.models.intelligence import CorridorProfile
from app.db.models.rules import (
    EligibilityRulePathway,
    HS6PSRApplicability,
    PSRRule,
    PSRRuleComponent,
)
from app.db.models.sources import LegalProvision, SourceRegistry
from app.db.models.status import StatusAssertion
from app.db.models.tariffs import (
    TariffScheduleHeader,
    TariffScheduleLine,
    TariffScheduleRateByYear,
)

SEED_NAMESPACE = uuid5(NAMESPACE_URL, "afcfta-intelligence/v0.1/seed-data")
HS_VERSION = "HS2017"
SEED_EFFECTIVE_DATE = date(2024, 1, 1)
SEEDED_CORRIDORS = [("GHA", "NGA"), ("CMR", "NGA"), ("CIV", "NGA"), ("SEN", "NGA")]

RULES_SOURCE_NAME = "source/rules"
TARIFF_SOURCE_NAME = "source/tariffs"
RULES_PROVISION_NAME = "provision/rules"
TARIFF_PROVISION_NAME = "provision/tariffs"

PRODUCT_SPECS: list[dict[str, object]] = [
    {
        "hs6_code": "110311",
        "description": "Groats and meal of wheat",
        "chapter": "11",
        "heading": "1103",
        "section": "II",
        "section_name": "Vegetable Products",
        "rule_status": RuleStatusEnum.AGREED,
        "legal_rule_text_verbatim": "A change to heading 11.03 from any other heading.",
        "legal_rule_text_normalized": "CTH",
        "components": [
            {
                "name": "cth",
                "component_type": RuleComponentTypeEnum.CTH,
                "operator_type": OperatorTypeEnum.STANDALONE,
                "tariff_shift_level": HsLevelEnum.HEADING,
                "component_text_verbatim": "Change in tariff heading.",
                "normalized_expression": "tariff_heading_input != tariff_heading_output",
            }
        ],
        "pathways": [
            {
                "code": "CTH",
                "label": "Change in tariff heading",
                "pathway_type": "specific",
                "expression_json": {
                    "op": "fact_ne",
                    "fact": "tariff_heading_input",
                    "ref_fact": "tariff_heading_output",
                },
                "tariff_shift_level": HsLevelEnum.HEADING,
                "priority_rank": 1,
                "allows_cumulation": True,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "15.0000",
                "target_rate": "0.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "5.0000", 2025: "0.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "15.0000",
                "target_rate": "2.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "6.0000", 2025: "2.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "14.0000",
                "target_rate": "1.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "5.0000", 2025: "1.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "16.0000",
                "target_rate": "3.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "7.0000", 2025: "3.0000"},
            },
        },
    },
    {
        "hs6_code": "271019",
        "description": "Petroleum oils and oils obtained from bituminous minerals, not crude",
        "chapter": "27",
        "heading": "2710",
        "section": "V",
        "section_name": "Mineral Products",
        "rule_status": RuleStatusEnum.AGREED,
        "legal_rule_text_verbatim": (
            "The value of non-originating materials shall not exceed 60 percent of the "
            "ex-works price."
        ),
        "legal_rule_text_normalized": "VNM<=60",
        "components": [
            {
                "name": "vnm",
                "component_type": RuleComponentTypeEnum.VNM,
                "operator_type": OperatorTypeEnum.STANDALONE,
                "threshold_percent": "60.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "component_text_verbatim": (
                    "Value of non-originating materials does not exceed 60 percent of "
                    "the ex-works price."
                ),
                "normalized_expression": "vnom_percent <= 60",
            }
        ],
        "pathways": [
            {
                "code": "VNM",
                "label": "Value of non-originating materials <= 60%",
                "pathway_type": "specific",
                "expression_json": {
                    "op": "formula_lte",
                    "formula": "vnom_percent",
                    "value": 60,
                },
                "threshold_percent": "60.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "priority_rank": 1,
                "allows_cumulation": True,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "10.0000",
                "target_rate": "6.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "8.0000", 2025: "6.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "12.0000",
                "target_rate": "5.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "7.0000", 2025: "5.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "11.0000",
                "target_rate": "5.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "7.0000", 2025: "5.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "13.0000",
                "target_rate": "6.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "8.0000", 2025: "6.0000"},
            },
        },
    },
    {
        "hs6_code": "870421",
        "description": (
            "Motor vehicles for the transport of goods, gross vehicle weight <= 5 tonnes"
        ),
        "chapter": "87",
        "heading": "8704",
        "section": "XVII",
        "section_name": "Vehicles, Aircraft, Vessels and Associated Transport Equipment",
        "rule_status": RuleStatusEnum.AGREED,
        "legal_rule_text_verbatim": (
            "A change to heading 87.04 from any other heading and the value of "
            "non-originating materials shall not exceed 60 percent of the ex-works price."
        ),
        "legal_rule_text_normalized": "CTH AND VNM<=60",
        "components": [
            {
                "name": "cth",
                "component_type": RuleComponentTypeEnum.CTH,
                "operator_type": OperatorTypeEnum.AND,
                "tariff_shift_level": HsLevelEnum.HEADING,
                "component_text_verbatim": "Change in tariff heading.",
                "normalized_expression": "tariff_heading_input != tariff_heading_output",
            },
            {
                "name": "vnm",
                "component_type": RuleComponentTypeEnum.VNM,
                "operator_type": OperatorTypeEnum.AND,
                "threshold_percent": "60.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "component_text_verbatim": (
                    "Value of non-originating materials does not exceed 60 percent of "
                    "the ex-works price."
                ),
                "normalized_expression": "vnom_percent <= 60",
            },
        ],
        "pathways": [
            {
                "code": "CTH_VNM",
                "label": "Change in tariff heading and VNM <= 60%",
                "pathway_type": "compound",
                "expression_json": {
                    "op": "all",
                    "args": [
                        {
                            "op": "fact_ne",
                            "fact": "tariff_heading_input",
                            "ref_fact": "tariff_heading_output",
                        },
                        {
                            "op": "formula_lte",
                            "formula": "vnom_percent",
                            "value": 60,
                        },
                    ],
                },
                "threshold_percent": "60.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "tariff_shift_level": HsLevelEnum.HEADING,
                "priority_rank": 1,
                "allows_cumulation": True,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "35.0000",
                "target_rate": "25.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "30.0000", 2025: "25.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "38.0000",
                "target_rate": "28.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "32.0000", 2025: "28.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "36.0000",
                "target_rate": "26.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "31.0000", 2025: "26.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "37.0000",
                "target_rate": "27.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "31.0000", 2025: "27.0000"},
            },
        },
    },
    {
        "hs6_code": "030389",
        "description": "Frozen fish, not elsewhere specified",
        "chapter": "03",
        "heading": "0303",
        "section": "I",
        "section_name": "Live Animals; Animal Products",
        "rule_status": RuleStatusEnum.PENDING,
        "legal_rule_text_verbatim": "Wholly obtained.",
        "legal_rule_text_normalized": "WO",
        "components": [
            {
                "name": "wo",
                "component_type": RuleComponentTypeEnum.WO,
                "operator_type": OperatorTypeEnum.STANDALONE,
                "component_text_verbatim": "Wholly obtained.",
                "normalized_expression": "wholly_obtained == true",
            }
        ],
        "pathways": [
            {
                "code": "WO",
                "label": "Wholly obtained",
                "pathway_type": "specific",
                "expression_json": {
                    "op": "fact_eq",
                    "fact": "wholly_obtained",
                    "value": True,
                },
                "priority_rank": 1,
                "allows_cumulation": False,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "20.0000",
                "target_rate": "5.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "10.0000", 2025: "5.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "18.0000",
                "target_rate": "4.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "9.0000", 2025: "4.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "19.0000",
                "target_rate": "4.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "8.0000", 2025: "4.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "17.0000",
                "target_rate": "3.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "7.0000", 2025: "3.0000"},
            },
        },
    },
    {
        "hs6_code": "610910",
        "description": "T-shirts, singlets and other vests, of cotton",
        "chapter": "61",
        "heading": "6109",
        "section": "XI",
        "section_name": "Textiles and Textile Articles",
        "rule_status": RuleStatusEnum.PROVISIONAL,
        "legal_rule_text_verbatim": (
            "A change to heading 61.09 from any other heading, or the value of "
            "non-originating materials shall not exceed 50 percent of the ex-works price."
        ),
        "legal_rule_text_normalized": "CTH OR VNM<=50",
        "components": [
            {
                "name": "cth",
                "component_type": RuleComponentTypeEnum.CTH,
                "operator_type": OperatorTypeEnum.OR,
                "tariff_shift_level": HsLevelEnum.HEADING,
                "component_text_verbatim": "Change in tariff heading.",
                "normalized_expression": "tariff_heading_input != tariff_heading_output",
            },
            {
                "name": "vnm",
                "component_type": RuleComponentTypeEnum.VNM,
                "operator_type": OperatorTypeEnum.OR,
                "threshold_percent": "50.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "component_text_verbatim": (
                    "Value of non-originating materials does not exceed 50 percent of "
                    "the ex-works price."
                ),
                "normalized_expression": "vnom_percent <= 50",
            },
        ],
        "pathways": [
            {
                "code": "CTH",
                "label": "Change in tariff heading",
                "pathway_type": "alternative",
                "expression_json": {
                    "op": "fact_ne",
                    "fact": "tariff_heading_input",
                    "ref_fact": "tariff_heading_output",
                },
                "tariff_shift_level": HsLevelEnum.HEADING,
                "priority_rank": 1,
                "allows_cumulation": True,
                "allows_tolerance": False,
            },
            {
                "code": "VNM",
                "label": "Value of non-originating materials <= 50%",
                "pathway_type": "alternative",
                "expression_json": {
                    "op": "formula_lte",
                    "formula": "vnom_percent",
                    "value": 50,
                },
                "threshold_percent": "50.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "priority_rank": 2,
                "allows_cumulation": True,
                "allows_tolerance": False,
            },
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "20.0000",
                "target_rate": "5.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "10.0000", 2025: "5.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "18.0000",
                "target_rate": "8.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "12.0000", 2025: "8.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "19.0000",
                "target_rate": "6.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "11.0000", 2025: "6.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "17.0000",
                "target_rate": "7.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "10.0000", 2025: "7.0000"},
            },
        },
    },
    {
        "hs6_code": "080111",
        "description": "Coconuts, desiccated",
        "chapter": "08",
        "heading": "0801",
        "section": "II",
        "section_name": "Vegetable Products",
        "rule_status": RuleStatusEnum.AGREED,
        "legal_rule_text_verbatim": "Wholly obtained.",
        "legal_rule_text_normalized": "WO",
        "components": [
            {
                "name": "wo",
                "component_type": RuleComponentTypeEnum.WO,
                "operator_type": OperatorTypeEnum.STANDALONE,
                "component_text_verbatim": "Wholly obtained.",
                "normalized_expression": "wholly_obtained == true",
            }
        ],
        "pathways": [
            {
                "code": "WO",
                "label": "Wholly obtained",
                "pathway_type": "specific",
                "expression_json": {
                    "op": "fact_eq",
                    "fact": "wholly_obtained",
                    "value": True,
                },
                "priority_rank": 1,
                "allows_cumulation": False,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "12.0000",
                "target_rate": "0.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "4.0000", 2025: "0.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "13.0000",
                "target_rate": "1.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "5.0000", 2025: "1.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "11.0000",
                "target_rate": "0.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "3.0000", 2025: "0.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.LIBERALISED,
                "base_rate": "12.0000",
                "target_rate": "1.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "4.0000", 2025: "1.0000"},
            },
        },
    },
    {
        "hs6_code": "290110",
        "description": "Saturated acyclic hydrocarbons",
        "chapter": "29",
        "heading": "2901",
        "section": "VI",
        "section_name": "Products of the Chemical or Allied Industries",
        "rule_status": RuleStatusEnum.AGREED,
        "legal_rule_text_verbatim": (
            "The value of non-originating materials shall not exceed 40 percent of the "
            "ex-works price."
        ),
        "legal_rule_text_normalized": "VNM<=40",
        "components": [
            {
                "name": "vnm",
                "component_type": RuleComponentTypeEnum.VNM,
                "operator_type": OperatorTypeEnum.STANDALONE,
                "threshold_percent": "40.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "component_text_verbatim": (
                    "Value of non-originating materials does not exceed 40 percent of "
                    "the ex-works price."
                ),
                "normalized_expression": "vnom_percent <= 40",
            }
        ],
        "pathways": [
            {
                "code": "VNM",
                "label": "Value of non-originating materials <= 40%",
                "pathway_type": "specific",
                "expression_json": {
                    "op": "formula_lte",
                    "formula": "vnom_percent",
                    "value": 40,
                },
                "threshold_percent": "40.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "priority_rank": 1,
                "allows_cumulation": True,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "10.0000",
                "target_rate": "3.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "5.0000", 2025: "3.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "11.0000",
                "target_rate": "4.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "6.0000", 2025: "4.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "9.0000",
                "target_rate": "2.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "4.0000", 2025: "2.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "10.0000",
                "target_rate": "3.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.LINEAR,
                "rates": {2024: "5.0000", 2025: "3.0000"},
            },
        },
    },
    {
        "hs6_code": "840820",
        "description": "Compression-ignition internal combustion piston engines",
        "chapter": "84",
        "heading": "8408",
        "section": "XVI",
        "section_name": "Machinery and Mechanical Appliances; Electrical Equipment",
        "rule_status": RuleStatusEnum.AGREED,
        "legal_rule_text_verbatim": (
            "The value of non-originating materials shall not exceed 55 percent of the "
            "ex-works price."
        ),
        "legal_rule_text_normalized": "VNM<=55",
        "components": [
            {
                "name": "vnm",
                "component_type": RuleComponentTypeEnum.VNM,
                "operator_type": OperatorTypeEnum.STANDALONE,
                "threshold_percent": "55.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "component_text_verbatim": (
                    "Value of non-originating materials does not exceed 55 percent of "
                    "the ex-works price."
                ),
                "normalized_expression": "vnom_percent <= 55",
            }
        ],
        "pathways": [
            {
                "code": "VNM",
                "label": "Value of non-originating materials <= 55%",
                "pathway_type": "specific",
                "expression_json": {
                    "op": "formula_lte",
                    "formula": "vnom_percent",
                    "value": 55,
                },
                "threshold_percent": "55.000",
                "threshold_basis": ThresholdBasisEnum.EX_WORKS,
                "priority_rank": 1,
                "allows_cumulation": True,
                "allows_tolerance": False,
            }
        ],
        "tariffs": {
            "GHA": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "20.0000",
                "target_rate": "10.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "14.0000", 2025: "10.0000"},
            },
            "CMR": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "21.0000",
                "target_rate": "11.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "15.0000", 2025: "11.0000"},
            },
            "CIV": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "19.0000",
                "target_rate": "9.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "13.0000", 2025: "9.0000"},
            },
            "SEN": {
                "category": TariffCategoryEnum.SENSITIVE,
                "base_rate": "20.0000",
                "target_rate": "10.0000",
                "target_year": 2025,
                "staging_type": StagingTypeEnum.STEPWISE,
                "rates": {2024: "14.0000", 2025: "10.0000"},
            },
        },
    },
]

PRODUCT_INSERT_ORDER = {
    "110311": 1,
    "271019": 2,
    "610910": 3,
    "870421": 4,
    "030389": 5,
    "080111": 6,
    "290110": 7,
    "840820": 8,
}
PRODUCT_SPECS.sort(key=lambda spec: PRODUCT_INSERT_ORDER[str(spec["hs6_code"])])


def seed_uuid(name: str) -> UUID:
    """Return a deterministic UUID5 for one seed artifact."""

    return uuid5(SEED_NAMESPACE, name)


def checksum_for(name: str) -> str:
    """Return a deterministic sha256 checksum for source_registry rows."""

    return sha256(name.encode("utf-8")).hexdigest()


def money(value: str) -> Decimal:
    """Return a stable Decimal for numeric seed values."""

    return Decimal(value)


def rule_status_text(hs6_code: str, rule_status: RuleStatusEnum) -> str:
    """Render a status_assertion verbatim string aligned to the seeded rule status."""

    if rule_status == RuleStatusEnum.PROVISIONAL:
        return f"PSR for HS6 {hs6_code} is provisional and subject to change."
    if rule_status == RuleStatusEnum.PENDING:
        return f"PSR for HS6 {hs6_code} is pending and not yet enforceable."
    return f"PSR for HS6 {hs6_code} is agreed for v0.1 seeded testing."


def rule_status_type(rule_status: RuleStatusEnum) -> StatusTypeEnum:
    """Map psr_rule.rule_status to the status_assertion enum space."""

    if rule_status == RuleStatusEnum.PROVISIONAL:
        return StatusTypeEnum.PROVISIONAL
    if rule_status == RuleStatusEnum.PENDING:
        return StatusTypeEnum.PENDING
    return StatusTypeEnum.AGREED


def question_risk_category(pathway_code: str) -> VerificationRiskCategoryEnum:
    """Pick a reasonable seeded risk category for a pathway or rule family."""

    code = pathway_code.upper()
    if code == "WO":
        return VerificationRiskCategoryEnum.ORIGIN_CLAIM
    if "VNM" in code or "VA" in code:
        return VerificationRiskCategoryEnum.VALUATION_RISK
    if "CTH" in code or "CTSH" in code:
        return VerificationRiskCategoryEnum.TARIFF_CLASSIFICATION_RISK
    return VerificationRiskCategoryEnum.GENERAL


def load_existing_hs6_ids(session: Session) -> dict[str, UUID]:
    """Return existing canonical HS6 ids keyed by hs6_code for the seeded slice."""

    seeded_codes = [str(spec["hs6_code"]) for spec in PRODUCT_SPECS]
    statement = select(HS6Product.hs6_code, HS6Product.hs6_id).where(
        HS6Product.hs_version == HS_VERSION,
        HS6Product.hs6_code.in_(seeded_codes),
    )
    rows = session.execute(statement).all()
    return {hs6_code: hs6_id for hs6_code, hs6_id in rows}


def build_seed_rows(existing_hs6_ids: dict[str, UUID] | None = None) -> dict[str, dict[str, object]]:
    """Build all seeded rows in forward FK dependency order."""

    existing_hs6_ids = existing_hs6_ids or {}
    rules_source_id = seed_uuid(RULES_SOURCE_NAME)
    tariffs_source_id = seed_uuid(TARIFF_SOURCE_NAME)
    rules_provision_id = seed_uuid(RULES_PROVISION_NAME)
    tariffs_provision_id = seed_uuid(TARIFF_PROVISION_NAME)

    sources = [
        {
            "source_id": rules_source_id,
            "title": "AfCFTA Appendix IV Rules of Origin (Seed v0.1)",
            "short_title": "Appendix IV Seed",
            "source_group": "seed_v01_rules",
            "source_type": SourceTypeEnum.APPENDIX,
            "authority_tier": AuthorityTierEnum.BINDING,
            "issuing_body": "AfCFTA Secretariat",
            "jurisdiction_scope": "AfCFTA continental",
            "publication_date": SEED_EFFECTIVE_DATE,
            "effective_date": SEED_EFFECTIVE_DATE,
            "version_label": "seed-v0.1",
            "status": SourceStatusEnum.CURRENT,
            "language": "en",
            "hs_version": HS_VERSION,
            "file_path": "seed://appendix-iv-v01",
            "mime_type": "text/plain",
            "checksum_sha256": checksum_for(RULES_SOURCE_NAME),
            "citation_preferred": "AfCFTA Appendix IV (Seed v0.1)",
            "notes": "Deterministic seed source for PSR lookup tests.",
        },
        {
            "source_id": tariffs_source_id,
            "title": "AfCFTA Preferential Tariff Schedules (Seed v0.1)",
            "short_title": "Tariff Schedules Seed",
            "source_group": "seed_v01_tariffs",
            "source_type": SourceTypeEnum.TARIFF_SCHEDULE,
            "authority_tier": AuthorityTierEnum.OFFICIAL_OPERATIONAL,
            "issuing_body": "Seeded corridor schedule registry",
            "jurisdiction_scope": "AfCFTA corridor schedules",
            "publication_date": date(2024, 1, 15),
            "effective_date": SEED_EFFECTIVE_DATE,
            "version_label": "seed-v0.1",
            "status": SourceStatusEnum.CURRENT,
            "language": "en",
            "hs_version": HS_VERSION,
            "file_path": "seed://tariff-schedules-v01",
            "mime_type": "text/plain",
            "checksum_sha256": checksum_for(TARIFF_SOURCE_NAME),
            "citation_preferred": "AfCFTA Tariff Schedules (Seed v0.1)",
            "notes": "Deterministic seed source for tariff resolution tests.",
        },
    ]

    provisions = [
        {
            "provision_id": rules_provision_id,
            "source_id": rules_source_id,
            "instrument_name": "AfCFTA Appendix IV",
            "instrument_type": InstrumentTypeEnum.APPENDIX,
            "article_ref": None,
            "annex_ref": None,
            "appendix_ref": "Appendix IV",
            "section_ref": None,
            "subsection_ref": None,
            "page_start": 1,
            "page_end": 5,
            "topic_primary": "rules_of_origin",
            "topic_secondary": ["psr", "seed"],
            "provision_text_verbatim": (
                "Seeded PSR provisions apply the pathway expressions stored for each HS6 code."
            ),
            "provision_text_normalized": (
                "Seeded PSR provisions apply the stored pathway expressions."
            ),
            "effective_date": SEED_EFFECTIVE_DATE,
            "expiry_date": None,
            "status": ProvisionStatusEnum.IN_FORCE,
            "cross_reference_refs": ["Appendix IV"],
            "authority_weight": Decimal("1.000"),
        },
        {
            "provision_id": tariffs_provision_id,
            "source_id": tariffs_source_id,
            "instrument_name": "AfCFTA Preferential Tariff Schedules",
            "instrument_type": InstrumentTypeEnum.OTHER,
            "article_ref": None,
            "annex_ref": "Schedules",
            "appendix_ref": None,
            "section_ref": None,
            "subsection_ref": None,
            "page_start": 1,
            "page_end": 4,
            "topic_primary": "tariff_schedule",
            "topic_secondary": ["corridor_rates", "seed"],
            "provision_text_verbatim": (
                "Seeded annual preferential tariff rates apply to the supported v0.1 corridors."
            ),
            "provision_text_normalized": "Seeded annual preferential tariff rates apply.",
            "effective_date": SEED_EFFECTIVE_DATE,
            "expiry_date": None,
            "status": ProvisionStatusEnum.IN_FORCE,
            "cross_reference_refs": ["Tariff Schedules"],
            "authority_weight": Decimal("0.900"),
        },
    ]

    products: list[dict[str, object]] = []
    rules: list[dict[str, object]] = []
    components: list[dict[str, object]] = []
    pathways: list[dict[str, object]] = []
    applicability: list[dict[str, object]] = []
    status_assertions: list[dict[str, object]] = []
    evidence_requirements: list[dict[str, object]] = []
    verification_questions: list[dict[str, object]] = []
    headers: list[dict[str, object]] = []
    lines: list[dict[str, object]] = []
    rates: list[dict[str, object]] = []
    corridor_profiles: list[dict[str, object]] = []

    for product_index, spec in enumerate(PRODUCT_SPECS, start=1):
        hs6_code = spec["hs6_code"]
        description = spec["description"]
        hs6_id = existing_hs6_ids.get(str(hs6_code), seed_uuid(f"hs6/{hs6_code}"))
        psr_id = seed_uuid(f"psr/{hs6_code}")

        if str(hs6_code) not in existing_hs6_ids:
            products.append(
                {
                    "hs6_id": hs6_id,
                    "hs_version": HS_VERSION,
                    "hs6_code": hs6_code,
                    "hs6_display": f"{hs6_code} - {description}",
                    "chapter": spec["chapter"],
                    "heading": spec["heading"],
                    "description": description,
                    "section": spec["section"],
                    "section_name": spec["section_name"],
                }
            )

        rules.append(
            {
                "psr_id": psr_id,
                "source_id": rules_source_id,
                "appendix_version": "seed-v0.1",
                "hs_version": HS_VERSION,
                "hs_code": hs6_code,
                "hs_level": HsLevelEnum.SUBHEADING,
                "product_description": description,
                "legal_rule_text_verbatim": spec["legal_rule_text_verbatim"],
                "legal_rule_text_normalized": spec["legal_rule_text_normalized"],
                "rule_status": spec["rule_status"],
                "effective_date": SEED_EFFECTIVE_DATE,
                "page_ref": product_index,
                "table_ref": "seed_v0_1_psr",
                "row_ref": hs6_code,
            }
        )

        status_assertions.append(
            {
                "status_assertion_id": seed_uuid(f"status/psr/{hs6_code}"),
                "source_id": rules_source_id,
                "entity_type": "psr_rule",
                "entity_key": make_entity_key("psr_rule", psr_id=str(psr_id)),
                "status_type": rule_status_type(spec["rule_status"]),
                "status_text_verbatim": rule_status_text(hs6_code, spec["rule_status"]),
                "effective_from": SEED_EFFECTIVE_DATE,
                "effective_to": None,
                "page_ref": product_index,
                "clause_ref": f"PSR-{hs6_code}",
                "confidence_score": Decimal("1.000"),
            }
        )

        evidence_requirements.extend(
            [
                {
                    "evidence_id": seed_uuid(f"evidence/hs6-rule/{hs6_code}/certificate"),
                    "entity_type": "hs6_rule",
                    "entity_key": make_entity_key("hs6_rule", psr_id=str(psr_id)),
                    "persona_mode": PersonaModeEnum.SYSTEM,
                    "requirement_type": RequirementTypeEnum.CERTIFICATE_OF_ORIGIN,
                    "requirement_description": f"Certificate of origin for HS6 {hs6_code}.",
                    "legal_basis_provision_id": rules_provision_id,
                    "required": True,
                    "priority_level": 1,
                },
                {
                    "evidence_id": seed_uuid(f"evidence/hs6-rule/{hs6_code}/supplier"),
                    "entity_type": "hs6_rule",
                    "entity_key": make_entity_key("hs6_rule", psr_id=str(psr_id)),
                    "persona_mode": PersonaModeEnum.OFFICER,
                    "requirement_type": RequirementTypeEnum.SUPPLIER_DECLARATION,
                    "requirement_description": (
                        f"Supplier declaration supporting origin inputs for HS6 {hs6_code}."
                    ),
                    "legal_basis_provision_id": rules_provision_id,
                    "required": True,
                    "priority_level": 2,
                },
            ]
        )

        verification_questions.append(
            {
                "question_id": seed_uuid(f"question/hs6-rule/{hs6_code}/officer"),
                "entity_type": "hs6_rule",
                "entity_key": make_entity_key("hs6_rule", psr_id=str(psr_id)),
                "persona_mode": PersonaModeEnum.OFFICER,
                "question_text": (
                    f"Has the supporting supplier declaration been matched to the "
                    f"claimed origin basis for HS6 {hs6_code}?"
                ),
                "purpose": "Validate the documentary support for the seeded PSR.",
                "legal_basis_provision_id": rules_provision_id,
                "risk_category": question_risk_category(spec["pathways"][0]["code"]),
                "priority_level": 1,
                "active": True,
                "question_order": 1,
            }
        )

        for component_index, component in enumerate(spec["components"], start=1):
            components.append(
                {
                    "component_id": seed_uuid(f"component/{hs6_code}/{component['name']}"),
                    "psr_id": psr_id,
                    "component_type": component["component_type"],
                    "operator_type": component["operator_type"],
                    "threshold_percent": (
                        money(component["threshold_percent"])
                        if "threshold_percent" in component
                        else None
                    ),
                    "threshold_basis": component.get("threshold_basis"),
                    "tariff_shift_level": component.get("tariff_shift_level"),
                    "component_text_verbatim": component["component_text_verbatim"],
                    "normalized_expression": component["normalized_expression"],
                    "confidence_score": Decimal("1.000"),
                    "component_order": component_index,
                }
            )

        for pathway in spec["pathways"]:
            pathway_id = seed_uuid(f"pathway/{hs6_code}/{pathway['code']}")
            pathways.append(
                {
                    "pathway_id": pathway_id,
                    "psr_id": psr_id,
                    "pathway_code": pathway["code"],
                    "pathway_label": pathway["label"],
                    "pathway_type": pathway["pathway_type"],
                    "expression_json": pathway["expression_json"],
                    "threshold_percent": (
                        money(pathway["threshold_percent"])
                        if "threshold_percent" in pathway
                        else None
                    ),
                    "threshold_basis": pathway.get("threshold_basis"),
                    "tariff_shift_level": pathway.get("tariff_shift_level"),
                    "allows_cumulation": pathway["allows_cumulation"],
                    "allows_tolerance": pathway["allows_tolerance"],
                    "priority_rank": pathway["priority_rank"],
                    "effective_date": SEED_EFFECTIVE_DATE,
                }
            )

            pathway_entity_key = make_entity_key("pathway", pathway_id=str(pathway_id))
            evidence_requirements.append(
                {
                    "evidence_id": seed_uuid(
                        f"evidence/pathway/{hs6_code}/{pathway['code']}/certificate"
                    ),
                    "entity_type": "pathway",
                    "entity_key": pathway_entity_key,
                    "persona_mode": PersonaModeEnum.SYSTEM,
                    "requirement_type": RequirementTypeEnum.CERTIFICATE_OF_ORIGIN,
                    "requirement_description": (
                        f"Certificate of origin supporting pathway {pathway['code']} "
                        f"for HS6 {hs6_code}."
                    ),
                    "legal_basis_provision_id": rules_provision_id,
                    "required": True,
                    "priority_level": 1,
                }
            )

            verification_questions.append(
                {
                    "question_id": seed_uuid(f"question/pathway/{hs6_code}/{pathway['code']}"),
                    "entity_type": "pathway",
                    "entity_key": pathway_entity_key,
                    "persona_mode": PersonaModeEnum.SYSTEM,
                    "question_text": (
                        f"Does the submitted evidence substantiate pathway {pathway['code']} "
                        f"for HS6 {hs6_code}?"
                    ),
                    "purpose": "Support seeded readiness checks for the selected pathway.",
                    "legal_basis_provision_id": rules_provision_id,
                    "risk_category": question_risk_category(pathway["code"]),
                    "priority_level": 1,
                    "active": True,
                    "question_order": 1,
                }
            )

        applicability.append(
            {
                "applicability_id": seed_uuid(f"applicability/{hs6_code}"),
                "hs6_id": hs6_id,
                "psr_id": psr_id,
                "applicability_type": "direct",
                "priority_rank": 0,
                "effective_date": SEED_EFFECTIVE_DATE,
            }
        )

    for corridor_index, (exporter, importer) in enumerate(SEEDED_CORRIDORS, start=1):
        schedule_id = seed_uuid(f"schedule/{exporter}/{importer}")
        headers.append(
            {
                "schedule_id": schedule_id,
                "source_id": tariffs_source_id,
                "importing_state": importer,
                "exporting_scope": exporter,
                "schedule_status": ScheduleStatusEnum.OFFICIAL,
                "publication_date": date(2024, 1, 15),
                "effective_date": SEED_EFFECTIVE_DATE,
                "hs_version": HS_VERSION,
                "category_system": "AfCFTA seed v0.1",
                "notes": f"Seeded tariff schedule for {exporter}->{importer}.",
            }
        )

        for spec in PRODUCT_SPECS:
            hs6_code = spec["hs6_code"]
            tariff_spec = spec["tariffs"][exporter]
            line_id = seed_uuid(f"schedule-line/{exporter}/{importer}/{hs6_code}")
            lines.append(
                {
                    "schedule_line_id": line_id,
                    "schedule_id": schedule_id,
                    "hs_code": hs6_code,
                    "product_description": spec["description"],
                    "tariff_category": tariff_spec["category"],
                    "mfn_base_rate": money(tariff_spec["base_rate"]),
                    "base_year": 2024,
                    "target_rate": money(tariff_spec["target_rate"]),
                    "target_year": tariff_spec["target_year"],
                    "staging_type": tariff_spec["staging_type"],
                    "page_ref": corridor_index,
                    "table_ref": f"seed_schedule_{exporter.lower()}_{importer.lower()}",
                    "row_ref": hs6_code,
                }
            )

            for calendar_year, preferential_rate in tariff_spec["rates"].items():
                rates.append(
                    {
                        "year_rate_id": seed_uuid(
                            f"rate/{exporter}/{importer}/{hs6_code}/{calendar_year}"
                        ),
                        "schedule_line_id": line_id,
                        "calendar_year": calendar_year,
                        "preferential_rate": money(preferential_rate),
                        "rate_status": RateStatusEnum.IN_FORCE,
                        "source_id": tariffs_source_id,
                        "page_ref": corridor_index,
                    }
                )

            status_assertions.append(
                {
                    "status_assertion_id": seed_uuid(
                        f"status/corridor/{exporter}/{importer}/{hs6_code}"
                    ),
                    "source_id": tariffs_source_id,
                    "entity_type": "corridor",
                    "entity_key": make_entity_key(
                        "corridor",
                        exporter=exporter,
                        importer=importer,
                        hs6_code=hs6_code,
                    ),
                    "status_type": StatusTypeEnum.IN_FORCE,
                    "status_text_verbatim": (
                        f"Corridor {exporter}->{importer} is operational for HS6 "
                        f"{hs6_code} in the seeded tariff schedule."
                    ),
                    "effective_from": SEED_EFFECTIVE_DATE,
                    "effective_to": None,
                    "page_ref": None,
                    "clause_ref": f"{exporter}-{importer}",
                    "confidence_score": Decimal("1.000"),
                }
            )

        corridor_profiles.append(
            {
                "corridor_profile_id": seed_uuid(f"corridor-profile/{exporter}/{importer}"),
                "exporter_state": exporter,
                "importer_state": importer,
                "corridor_status": CorridorStatusEnum.OPERATIONAL,
                "schedule_maturity_score": Decimal("85.00" if exporter == "GHA" else "78.00"),
                "documentation_complexity_score": Decimal(
                    "42.00" if exporter == "GHA" else "48.00"
                ),
                "verification_risk_score": Decimal("35.00" if exporter == "GHA" else "40.00"),
                "transition_exposure_score": Decimal("18.00" if exporter == "GHA" else "22.00"),
                "average_tariff_relief_score": Decimal("72.00" if exporter == "GHA" else "68.00"),
                "pending_rule_exposure_score": Decimal("24.00"),
                "operational_notes": (
                    f"Seeded corridor profile for {exporter}->{importer} covering the "
                    f"{len(PRODUCT_SPECS)} deterministic v0.1 products."
                ),
                "source_summary": {
                    "rule_source": str(rules_source_id),
                    "tariff_source": str(tariffs_source_id),
                    "hs6_coverage": len(PRODUCT_SPECS),
                },
                "method_version": "seed_v0.1",
                "active": True,
                "effective_from": SEED_EFFECTIVE_DATE,
            }
        )

    return {
        "source_registry": {
            "table": SourceRegistry.__table__,
            "pk": "source_id",
            "rows": sources,
        },
        "legal_provision": {
            "table": LegalProvision.__table__,
            "pk": "provision_id",
            "rows": provisions,
        },
        "hs6_product": {
            "table": HS6Product.__table__,
            "pk": "hs6_id",
            "rows": products,
        },
        "psr_rule": {
            "table": PSRRule.__table__,
            "pk": "psr_id",
            "rows": rules,
        },
        "psr_rule_component": {
            "table": PSRRuleComponent.__table__,
            "pk": "component_id",
            "rows": components,
        },
        "eligibility_rule_pathway": {
            "table": EligibilityRulePathway.__table__,
            "pk": "pathway_id",
            "rows": pathways,
        },
        "hs6_psr_applicability": {
            "table": HS6PSRApplicability.__table__,
            "pk": "applicability_id",
            "rows": applicability,
        },
        "tariff_schedule_header": {
            "table": TariffScheduleHeader.__table__,
            "pk": "schedule_id",
            "rows": headers,
        },
        "tariff_schedule_line": {
            "table": TariffScheduleLine.__table__,
            "pk": "schedule_line_id",
            "rows": lines,
        },
        "tariff_schedule_rate_by_year": {
            "table": TariffScheduleRateByYear.__table__,
            "pk": "year_rate_id",
            "rows": rates,
        },
        "status_assertion": {
            "table": StatusAssertion.__table__,
            "pk": "status_assertion_id",
            "rows": status_assertions,
        },
        "evidence_requirement": {
            "table": EvidenceRequirement.__table__,
            "pk": "evidence_id",
            "rows": evidence_requirements,
        },
        "verification_question": {
            "table": VerificationQuestion.__table__,
            "pk": "question_id",
            "rows": verification_questions,
        },
        "corridor_profile": {
            "table": CorridorProfile.__table__,
            "pk": "corridor_profile_id",
            "rows": corridor_profiles,
        },
    }


def delete_seed_rows(session: Session, seed_rows: dict[str, dict[str, object]]) -> None:
    """Delete previously seeded rows in reverse FK dependency order."""

    for seed_name in reversed(list(seed_rows)):
        table = seed_rows[seed_name]["table"]
        pk_name = seed_rows[seed_name]["pk"]
        rows = seed_rows[seed_name]["rows"]
        ids = [row[pk_name] for row in rows]
        if ids:
            session.execute(delete(table).where(table.c[pk_name].in_(ids)))


def insert_seed_rows(session: Session, seed_rows: dict[str, dict[str, object]]) -> None:
    """Insert seeded rows in forward FK dependency order."""

    for seed_name in seed_rows:
        table = seed_rows[seed_name]["table"]
        rows = seed_rows[seed_name]["rows"]
        if rows:
            session.execute(insert(table), rows)


def build_engine() -> Engine:
    """Return a synchronous SQLAlchemy engine for standalone seeding."""

    settings = get_settings()
    if not settings.DATABASE_URL_SYNC:
        raise RuntimeError(
            "DATABASE_URL_SYNC is required for scripts/seed_data.py because the seeder "
            "uses a synchronous SQLAlchemy engine."
        )
    return create_engine(settings.DATABASE_URL_SYNC, future=True, pool_pre_ping=True)


def validate_seed_scope() -> None:
    """Fail fast if the scripted corridors drift from the locked v0.1 list."""

    unsupported = [corridor for corridor in SEEDED_CORRIDORS if corridor not in V01_CORRIDORS]
    if unsupported:
        raise RuntimeError(f"Seeded corridors fall outside v0.1 scope: {unsupported}")


def print_summary(seed_rows: dict[str, dict[str, object]]) -> None:
    """Print a compact summary of the seeded row counts."""

    print("Seeded AfCFTA Intelligence v0.1 reference data:")
    for seed_name, payload in seed_rows.items():
        print(f"- {seed_name}: {len(payload['rows'])}")


def main() -> None:
    """Seed the local database with deterministic v0.1 fixture data."""

    validate_seed_scope()
    engine = build_engine()
    seed_rows: dict[str, dict[str, object]] | None = None

    with Session(engine) as session:
        with session.begin():
            existing_hs6_ids = load_existing_hs6_ids(session)
            seed_rows = build_seed_rows(existing_hs6_ids)
            delete_seed_rows(session, seed_rows)
            insert_seed_rows(session, seed_rows)

    if seed_rows is None:
        raise RuntimeError("Seed rows were not built during seeding.")
    print_summary(seed_rows)


if __name__ == "__main__":
    main()
