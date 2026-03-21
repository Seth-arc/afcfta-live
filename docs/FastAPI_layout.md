Below is the **production-ready FastAPI layout** for the v0.1 system: routes, Pydantic models, service boundaries, and file structure.

It is aligned to the locked scope, HS6 backbone, deterministic engine flow, and structured storage model already defined.

# 1. Repo structure

```text
afcfta-intelligence/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── models/
│   │   │   ├── hs.py
│   │   │   ├── rules.py
│   │   │   ├── tariffs.py
│   │   │   ├── status.py
│   │   │   ├── evidence.py
│   │   │   ├── cases.py
│   │   │   └── evaluations.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── hs.py
│   │   ├── rules.py
│   │   ├── tariffs.py
│   │   ├── status.py
│   │   ├── evidence.py
│   │   ├── cases.py
│   │   └── assessments.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── v1/
│   │       ├── rules.py
│   │       ├── tariffs.py
│   │       ├── cases.py
│   │       ├── assessments.py
│   │       ├── evidence.py
│   │       └── health.py
│   ├── services/
│   │   ├── classification_service.py
│   │   ├── rule_resolution_service.py
│   │   ├── tariff_resolution_service.py
│   │   ├── status_service.py
│   │   ├── evidence_service.py
│   │   ├── fact_normalization_service.py
│   │   ├── expression_evaluator.py
│   │   ├── general_origin_rules_service.py
│   │   ├── eligibility_service.py
│   │   └── audit_service.py
│   ├── repositories/
│   │   ├── hs_repository.py
│   │   ├── rules_repository.py
│   │   ├── tariffs_repository.py
│   │   ├── status_repository.py
│   │   ├── evidence_repository.py
│   │   ├── cases_repository.py
│   │   └── evaluations_repository.py
│   ├── core/
│   │   ├── enums.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── utils.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
├── alembic/
├── scripts/
├── docs/
└── pyproject.toml
```

# 2. Service boundaries

Keep handlers thin.

## `classification_service`

Responsibilities:

* normalize raw HS input
* resolve `hs_version + hs6_code`
* return canonical product

## `rule_resolution_service`

Responsibilities:

* resolve applicable PSR through `hs6_psr_applicability`
* fetch components
* fetch executable pathways

## `tariff_resolution_service`

Responsibilities:

* resolve corridor schedule line
* resolve year-specific rate
* expose tariff status cleanly

## `status_service`

Responsibilities:

* gather all applicable `status_assertion`
* reduce into actionable blockers/warnings

## `fact_normalization_service`

Responsibilities:

* turn raw case facts into normalized structure
* compute helper maps for input headings, origins, process flags

## `expression_evaluator`

Responsibilities:

* execute pathway `expression_json`
* emit atomic checks

## `general_origin_rules_service`

Responsibilities:

* insufficient operations
* cumulation
* direct transport
* territoriality
* documentary gates where applicable

## `evidence_service`

Responsibilities:

* fetch applicable evidence rules
* compare with case facts
* output present / missing / conditional

## `eligibility_service`

Responsibilities:

* orchestrate full deterministic pipeline
* persist evaluation and checks

## `audit_service`

Responsibilities:

* reconstruct evaluation trail
* expose full evidence for case memo / officer UI

# 3. Core enums

```python
# app/core/enums.py
from enum import Enum

class PersonaMode(str, Enum):
    OFFICER = "officer"
    ANALYST = "analyst"
    EXPORTER = "exporter"
    SYSTEM = "system"

class LegalOutcome(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNCERTAIN = "uncertain"
    NOT_YET_OPERATIONAL = "not_yet_operational"
    INSUFFICIENT_INFORMATION = "insufficient_information"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class CheckSeverity(str, Enum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"

class CheckGroup(str, Enum):
    STATUS = "status"
    RULE = "rule"
    PROCEDURE = "procedure"
    EVIDENCE = "evidence"
    CORRIDOR = "corridor"

class ScheduleStatus(str, Enum):
    OFFICIAL = "official"
    PROVISIONAL = "provisional"
    GAZETTED = "gazetted"
    SUPERSEDED = "superseded"
    DRAFT = "draft"
```

# 4. Common response schemas

```python
# app/schemas/common.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Optional

class Meta(BaseModel):
    request_id: str
    timestamp: datetime

class ApiResponse(BaseModel):
    data: Any
    meta: Meta

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
    meta: Meta
```

# 5. HS schemas

```python
# app/schemas/hs.py
from pydantic import BaseModel, Field

class HSResolveResponse(BaseModel):
    hs6_id: str
    hs_version: str
    hs6_code: str
    hs6_display: str
    subheading_title: str
```

# 6. Rule schemas

```python
# app/schemas/rules.py
from pydantic import BaseModel
from typing import Any, Optional, List

class PSRComponentOut(BaseModel):
    component_id: str
    component_type: str
    operator_type: str
    threshold_percent: Optional[float] = None
    threshold_basis: Optional[str] = None
    tariff_shift_level: Optional[str] = None
    specific_process_text: Optional[str] = None
    component_text_verbatim: str
    normalized_expression: Optional[Any] = None
    component_order: int

class RulePathwayOut(BaseModel):
    pathway_id: str
    pathway_code: str
    pathway_label: str
    pathway_type: str
    expression_json: dict
    priority_rank: int

class RuleLookupResponse(BaseModel):
    hs6_id: str
    hs_version: str
    hs6_code: str
    product_description: str
    psr_id: str
    rule_scope: str
    rule_status: str
    legal_rule_text_verbatim: str
    legal_rule_text_normalized: Optional[str] = None
    applicability_type: str
    components: List[PSRComponentOut]
    pathways: List[RulePathwayOut]
    source_id: Optional[str] = None
    page_ref: Optional[int] = None
    row_ref: Optional[str] = None
```

# 7. Tariff schemas

```python
# app/schemas/tariffs.py
from pydantic import BaseModel
from typing import Optional

class TariffQueryParams(BaseModel):
    exporter_state: str
    importer_state: str
    hs_version: str = "HS2017"
    hs6_code: str
    year: int

class TariffOutcomeResponse(BaseModel):
    schedule_id: str
    schedule_line_id: str
    importer_state: str
    exporter_state: str
    hs6_code: str
    product_description: str
    tariff_category: Optional[str] = None
    mfn_base_rate: Optional[float] = None
    preferential_rate: Optional[float] = None
    target_rate: Optional[float] = None
    target_year: Optional[int] = None
    schedule_status: str
    rate_status: Optional[str] = None
```

# 8. Case and fact schemas

Use a flexible fact model because pathway fact requirements vary by rule type. The deterministic engine spec depends on normalized facts rather than prose. 

```python
# app/schemas/cases.py
from pydantic import BaseModel, Field
from typing import Optional, Any, List

class CaseFactIn(BaseModel):
    fact_type: str
    fact_value_text: Optional[str] = None
    fact_value_number: Optional[float] = None
    fact_value_boolean: Optional[bool] = None
    fact_value_json: Optional[Any] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None

class CaseCreateRequest(BaseModel):
    case_external_ref: str
    exporter_state: str
    importer_state: str
    hs_version: str = "HS2017"
    hs6_code: str
    persona_mode: str
    facts: List[CaseFactIn]

class CaseCreateResponse(BaseModel):
    case_id: str
    case_external_ref: str
    hs6_code: str
    exporter_state: str
    importer_state: str
```

# 9. Assessment schemas

```python
# app/schemas/assessments.py
from pydantic import BaseModel
from typing import Optional, List, Any

class AssessmentRequest(BaseModel):
    case_id: str
    assessment_date: str

class AtomicCheckOut(BaseModel):
    check_code: str
    check_group: str
    passed: Optional[bool] = None
    severity: str
    expected_value: Optional[str] = None
    observed_value: Optional[str] = None
    explanation: str
    linked_provision_id: Optional[str] = None
    linked_rule_component_id: Optional[str] = None

class EvidenceReadinessOut(BaseModel):
    required_items: List[str]
    missing_items: List[str]
    completeness_ratio: float

class AssessmentResponse(BaseModel):
    case_id: str
    hs6_code: str
    legal_outcome: str
    confidence_level: str
    pathway_used: Optional[str] = None
    rule_status: str
    tariff_outcome: Optional[dict] = None
    failures: List[AtomicCheckOut]
    checks: List[AtomicCheckOut]
    evidence: EvidenceReadinessOut
```

# 10. Repository pattern

Keep SQL in repositories.

Example:

```python
# app/repositories/rules_repository.py
from sqlalchemy import text

class RulesRepository:
    def __init__(self, session):
        self.session = session

    async def get_applicable_psr(self, hs6_id: str, assessment_date: str):
        sql = text("""
        SELECT pr.*, pa.applicability_type, pa.priority_rank
        FROM hs6_psr_applicability pa
        JOIN psr_rule pr ON pr.psr_id = pa.psr_id
        WHERE pa.hs6_id = :hs6_id
          AND (pa.effective_date IS NULL OR pa.effective_date <= :assessment_date)
          AND (pa.expiry_date IS NULL OR pa.expiry_date >= :assessment_date)
        ORDER BY pa.priority_rank ASC, pr.updated_at DESC
        LIMIT 1
        """)
        result = await self.session.execute(sql, {
            "hs6_id": hs6_id,
            "assessment_date": assessment_date,
        })
        return result.mappings().first()

    async def get_psr_components(self, psr_id: str):
        sql = text("""
        SELECT *
        FROM psr_rule_component
        WHERE psr_id = :psr_id
        ORDER BY component_order ASC
        """)
        result = await self.session.execute(sql, {"psr_id": psr_id})
        return result.mappings().all()

    async def get_pathways(self, psr_id: str, assessment_date: str):
        sql = text("""
        SELECT *
        FROM eligibility_rule_pathway
        WHERE psr_id = :psr_id
          AND (effective_date IS NULL OR effective_date <= :assessment_date)
          AND (expiry_date IS NULL OR expiry_date >= :assessment_date)
        ORDER BY priority_rank ASC
        """)
        result = await self.session.execute(sql, {
            "psr_id": psr_id,
            "assessment_date": assessment_date,
        })
        return result.mappings().all()
```

# 11. Service implementations

## `classification_service.py`

```python
class ClassificationService:
    def __init__(self, hs_repository):
        self.hs_repository = hs_repository

    @staticmethod
    def normalize_hs6_code(raw_code: str) -> str:
        normalized = "".join(ch for ch in raw_code if ch.isdigit())
        if len(normalized) != 6:
            raise ValueError("HS6 code must normalize to 6 digits")
        return normalized

    async def resolve_hs6(self, hs_version: str, raw_code: str):
        hs6_code = self.normalize_hs6_code(raw_code)
        product = await self.hs_repository.get_hs6_product(hs_version, hs6_code)
        if not product:
            raise LookupError("HS6 product not found")
        return product
```

## `rule_resolution_service.py`

```python
class RuleResolutionService:
    def __init__(self, rules_repository):
        self.rules_repository = rules_repository

    async def resolve_rule_bundle(self, hs6_id: str, assessment_date: str):
        psr = await self.rules_repository.get_applicable_psr(hs6_id, assessment_date)
        if not psr:
            raise LookupError("Applicable PSR not found")

        components = await self.rules_repository.get_psr_components(psr["psr_id"])
        pathways = await self.rules_repository.get_pathways(psr["psr_id"], assessment_date)

        return {
            "psr": psr,
            "components": components,
            "pathways": pathways,
        }
```

## `tariff_resolution_service.py`

```python
class TariffResolutionService:
    def __init__(self, tariffs_repository):
        self.tariffs_repository = tariffs_repository

    async def resolve_tariff_bundle(
        self,
        importer_state: str,
        exporter_state: str,
        hs_version: str,
        hs6_code: str,
        year: int,
        assessment_date: str,
    ):
        line = await self.tariffs_repository.get_tariff_line(
            importer_state=importer_state,
            exporter_state=exporter_state,
            hs_version=hs_version,
            hs6_code=hs6_code,
            assessment_date=assessment_date,
        )
        if not line:
            return {"line": None, "year_rate": None}

        year_rate = await self.tariffs_repository.get_year_rate(
            schedule_line_id=line["schedule_line_id"],
            year=year,
        )
        return {"line": line, "year_rate": year_rate}
```

## `status_service.py`

```python
class StatusService:
    def __init__(self, status_repository):
        self.status_repository = status_repository

    async def get_status_bundle(
        self,
        psr_id: str | None,
        schedule_id: str | None,
        schedule_line_id: str | None,
        corridor_key: str | None,
        assessment_date: str,
    ):
        return await self.status_repository.get_status_bundle(
            psr_id=psr_id,
            schedule_id=schedule_id,
            schedule_line_id=schedule_line_id,
            corridor_key=corridor_key,
            assessment_date=assessment_date,
        )
```

## `expression_evaluator.py`

Use the exact pathway DSL model already specified for `expression_json`. 

```python
class ExpressionEvaluator:
    def compute_variables(self, variable_defs: list[dict], facts: dict) -> dict:
        out = {}
        for var in variable_defs:
            formula = var["formula"]
            safe_locals = dict(facts)
            out[var["name"]] = eval(formula, {"__builtins__": {}}, safe_locals)
        return out

    def evaluate(self, expression_json: dict, facts: dict):
        variables = self.compute_variables(expression_json.get("variables", []), facts)
        return self._eval_node(expression_json["expression"], facts, variables)

    def _eval_node(self, node: dict, facts: dict, variables: dict):
        op = node["op"]

        if op == "all":
            checks = []
            passed = True
            for child in node["args"]:
                child_passed, child_checks = self._eval_node(child, facts, variables)
                passed = passed and child_passed
                checks.extend(child_checks)
            return passed, checks

        if op == "any":
            checks = []
            passed = False
            for child in node["args"]:
                child_passed, child_checks = self._eval_node(child, facts, variables)
                passed = passed or child_passed
                checks.extend(child_checks)
            return passed, checks

        if op == "formula_lte":
            actual = variables[node["formula"]]
            expected = node["value"]
            passed = actual <= expected
            return passed, [{
                "check_code": "FORMULA_LTE",
                "check_group": "rule",
                "passed": passed,
                "severity": "major" if not passed else "info",
                "expected_value": str(expected),
                "observed_value": str(actual),
                "explanation": f"{node['formula']} <= {expected}"
            }]

        if op == "fact_eq":
            actual = facts.get(node["fact"])
            expected = node["value"]
            passed = actual == expected
            return passed, [{
                "check_code": "FACT_EQ",
                "check_group": "rule",
                "passed": passed,
                "severity": "major" if not passed else "info",
                "expected_value": str(expected),
                "observed_value": str(actual),
                "explanation": f"{node['fact']} == {expected}"
            }]

        raise ValueError(f"Unsupported op: {op}")
```

## `general_origin_rules_service.py`

The PSR is not the whole origin regime; general origin conditions must be checked separately.

```python
class GeneralOriginRulesService:
    def evaluate(self, facts: dict, selected_pathway: dict):
        checks = []

        if facts.get("simple_operation_flag") is True:
            checks.append({
                "check_code": "INSUFFICIENT_OPERATION",
                "check_group": "procedure",
                "passed": False,
                "severity": "major",
                "expected_value": "substantial transformation",
                "observed_value": "simple operations only",
                "explanation": "Only simple operations were indicated"
            })

        if facts.get("direct_transport_confirmed") is False:
            checks.append({
                "check_code": "DIRECT_TRANSPORT_FAIL",
                "check_group": "procedure",
                "passed": False,
                "severity": "major",
                "expected_value": "true",
                "observed_value": "false",
                "explanation": "Direct transport condition not satisfied"
            })

        return checks
```

## `evidence_service.py`

```python
class EvidenceService:
    def __init__(self, evidence_repository):
        self.evidence_repository = evidence_repository

    async def build_readiness(
        self,
        persona_mode: str,
        pathway_id: str | None,
        psr_id: str,
        corridor_key: str,
        facts: dict,
    ):
        rules = await self.evidence_repository.get_evidence_bundle(
            persona_mode=persona_mode,
            pathway_id=pathway_id,
            psr_id=psr_id,
            corridor_key=corridor_key,
        )

        required_items = []
        missing_items = []

        for rule in rules:
            req_type = rule["requirement_type"]
            required_items.append(req_type)
            fact_key = f"{req_type}_present"
            if facts.get(fact_key) is not True and rule["required"] is True:
                missing_items.append(req_type)

        total = len(required_items)
        completeness_ratio = 1.0 if total == 0 else (total - len(missing_items)) / total

        checks = [{
            "check_code": "MISSING_EVIDENCE",
            "check_group": "evidence",
            "passed": len(missing_items) == 0,
            "severity": "minor" if missing_items else "info",
            "expected_value": "all required documents present",
            "observed_value": ", ".join(missing_items) if missing_items else "complete",
            "explanation": "Evidence readiness evaluation completed"
        }]

        return {
            "required_items": required_items,
            "missing_items": missing_items,
            "completeness_ratio": completeness_ratio,
            "checks": checks,
        }
```

## `eligibility_service.py`

```python
class EligibilityService:
    def __init__(
        self,
        classification_service,
        rule_resolution_service,
        tariff_resolution_service,
        status_service,
        evidence_service,
        fact_normalization_service,
        expression_evaluator,
        general_origin_rules_service,
        evaluations_repository,
        cases_repository,
    ):
        self.classification_service = classification_service
        self.rule_resolution_service = rule_resolution_service
        self.tariff_resolution_service = tariff_resolution_service
        self.status_service = status_service
        self.evidence_service = evidence_service
        self.fact_normalization_service = fact_normalization_service
        self.expression_evaluator = expression_evaluator
        self.general_origin_rules_service = general_origin_rules_service
        self.evaluations_repository = evaluations_repository
        self.cases_repository = cases_repository

    async def assess(self, case_id: str, assessment_date: str):
        case = await self.cases_repository.get_case(case_id)
        facts_raw = await self.cases_repository.get_case_facts(case_id)
        facts = self.fact_normalization_service.normalize(facts_raw)

        product = await self.classification_service.resolve_hs6(case["hs_version"], case["hs6_code"])
        rule_bundle = await self.rule_resolution_service.resolve_rule_bundle(product["hs6_id"], assessment_date)

        tariff_bundle = await self.tariff_resolution_service.resolve_tariff_bundle(
            importer_state=case["importer_state"],
            exporter_state=case["exporter_state"],
            hs_version=case["hs_version"],
            hs6_code=case["hs6_code"],
            year=int(assessment_date[:4]),
            assessment_date=assessment_date,
        )

        statuses = await self.status_service.get_status_bundle(
            psr_id=rule_bundle["psr"]["psr_id"],
            schedule_id=tariff_bundle["line"]["schedule_id"] if tariff_bundle["line"] else None,
            schedule_line_id=tariff_bundle["line"]["schedule_line_id"] if tariff_bundle["line"] else None,
            corridor_key=f"{case['exporter_state']}:{case['importer_state']}:{case['hs6_code']}",
            assessment_date=assessment_date,
        )

        selected_pathway = None
        all_checks = []

        for pathway in rule_bundle["pathways"]:
            passed, checks = self.expression_evaluator.evaluate(pathway["expression_json"], facts)
            all_checks.extend(checks)
            if passed and selected_pathway is None:
                selected_pathway = pathway

        general_checks = self.general_origin_rules_service.evaluate(
            facts=facts,
            selected_pathway=selected_pathway,
        )
        all_checks.extend(general_checks)

        evidence = await self.evidence_service.build_readiness(
            persona_mode=case["persona_mode"],
            pathway_id=selected_pathway["pathway_id"] if selected_pathway else None,
            psr_id=rule_bundle["psr"]["psr_id"],
            corridor_key=f"{case['exporter_state']}:{case['importer_state']}:{case['hs6_code']}",
            facts=facts,
        )
        all_checks.extend(evidence["checks"])

        legal_outcome = "eligible" if selected_pathway else "not_eligible"
        confidence_level = "high" if evidence["completeness_ratio"] >= 0.9 else "medium"

        result = {
            "case_id": case_id,
            "hs6_code": case["hs6_code"],
            "legal_outcome": legal_outcome,
            "confidence_level": confidence_level,
            "pathway_used": selected_pathway["pathway_code"] if selected_pathway else None,
            "rule_status": rule_bundle["psr"]["rule_status"],
            "tariff_outcome": None if not tariff_bundle["line"] else {
                "mfn_base_rate": tariff_bundle["line"]["mfn_base_rate"],
                "preferential_rate": tariff_bundle["year_rate"]["preferential_rate"] if tariff_bundle["year_rate"] else None,
                "schedule_status": tariff_bundle["line"]["schedule_status"],
            },
            "failures": [c for c in all_checks if c["passed"] is False],
            "checks": all_checks,
            "evidence": {
                "required_items": evidence["required_items"],
                "missing_items": evidence["missing_items"],
                "completeness_ratio": evidence["completeness_ratio"],
            },
        }

        await self.evaluations_repository.persist_assessment(case_id, product, rule_bundle, tariff_bundle, result)
        return result
```

# 12. API routers

## `api/router.py`

```python
from fastapi import APIRouter
from app.api.v1 import rules, tariffs, cases, assessments, evidence, health

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_router.include_router(tariffs.router, prefix="/tariffs", tags=["tariffs"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
```

## `api/v1/rules.py`

```python
from fastapi import APIRouter, Depends, Query
from app.schemas.rules import RuleLookupResponse
from app.api.deps import get_rule_resolution_service, get_classification_service

router = APIRouter()

@router.get("/{hs6_code}", response_model=RuleLookupResponse)
async def lookup_rule(
    hs6_code: str,
    hs_version: str = Query(default="HS2017"),
    assessment_date: str = Query(...),
    classification_service = Depends(get_classification_service),
    rule_resolution_service = Depends(get_rule_resolution_service),
):
    product = await classification_service.resolve_hs6(hs_version, hs6_code)
    bundle = await rule_resolution_service.resolve_rule_bundle(product["hs6_id"], assessment_date)

    return RuleLookupResponse(
        hs6_id=product["hs6_id"],
        hs_version=product["hs_version"],
        hs6_code=product["hs6_code"],
        product_description=bundle["psr"]["product_description"],
        psr_id=bundle["psr"]["psr_id"],
        rule_scope=bundle["psr"]["rule_scope"],
        rule_status=bundle["psr"]["rule_status"],
        legal_rule_text_verbatim=bundle["psr"]["legal_rule_text_verbatim"],
        legal_rule_text_normalized=bundle["psr"].get("legal_rule_text_normalized"),
        applicability_type=bundle["psr"]["applicability_type"],
        components=bundle["components"],
        pathways=bundle["pathways"],
        source_id=bundle["psr"].get("source_id"),
        page_ref=bundle["psr"].get("page_ref"),
        row_ref=bundle["psr"].get("row_ref"),
    )
```

## `api/v1/tariffs.py`

```python
from fastapi import APIRouter, Depends, Query
from app.schemas.tariffs import TariffOutcomeResponse
from app.api.deps import get_tariff_resolution_service

router = APIRouter()

@router.get("", response_model=TariffOutcomeResponse)
async def get_tariff(
    exporter_state: str = Query(...),
    importer_state: str = Query(...),
    hs6_code: str = Query(...),
    hs_version: str = Query(default="HS2017"),
    year: int = Query(...),
    assessment_date: str = Query(...),
    tariff_resolution_service = Depends(get_tariff_resolution_service),
):
    bundle = await tariff_resolution_service.resolve_tariff_bundle(
        importer_state=importer_state,
        exporter_state=exporter_state,
        hs_version=hs_version,
        hs6_code=hs6_code,
        year=year,
        assessment_date=assessment_date,
    )
    line = bundle["line"]
    rate = bundle["year_rate"]

    return TariffOutcomeResponse(
        schedule_id=line["schedule_id"],
        schedule_line_id=line["schedule_line_id"],
        importer_state=line["importing_state"],
        exporter_state=line["exporting_scope"],
        hs6_code=hs6_code,
        product_description=line["product_description"],
        tariff_category=line["tariff_category"],
        mfn_base_rate=line["mfn_base_rate"],
        preferential_rate=rate["preferential_rate"] if rate else None,
        target_rate=line["target_rate"],
        target_year=line["target_year"],
        schedule_status=line["schedule_status"],
        rate_status=rate["rate_status"] if rate else None,
    )
```

## `api/v1/cases.py`

```python
from fastapi import APIRouter, Depends
from app.schemas.cases import CaseCreateRequest, CaseCreateResponse
from app.api.deps import get_cases_repository, get_classification_service

router = APIRouter()

@router.post("", response_model=CaseCreateResponse)
async def create_case(
    payload: CaseCreateRequest,
    cases_repository = Depends(get_cases_repository),
    classification_service = Depends(get_classification_service),
):
    await classification_service.resolve_hs6(payload.hs_version, payload.hs6_code)
    case_id = await cases_repository.create_case_with_facts(payload)

    return CaseCreateResponse(
        case_id=case_id,
        case_external_ref=payload.case_external_ref,
        hs6_code=payload.hs6_code,
        exporter_state=payload.exporter_state,
        importer_state=payload.importer_state,
    )
```

## `api/v1/assessments.py`

```python
from fastapi import APIRouter, Depends
from app.schemas.assessments import AssessmentRequest, AssessmentResponse
from app.api.deps import get_eligibility_service

router = APIRouter()

@router.post("", response_model=AssessmentResponse)
async def assess_case(
    payload: AssessmentRequest,
    eligibility_service = Depends(get_eligibility_service),
):
    return await eligibility_service.assess(
        case_id=payload.case_id,
        assessment_date=payload.assessment_date,
    )
```

## `api/v1/evidence.py`

```python
from fastapi import APIRouter, Depends, Query
from app.api.deps import get_evidence_service, get_cases_repository

router = APIRouter()

@router.get("")
async def get_evidence_readiness(
    case_id: str = Query(...),
    cases_repository = Depends(get_cases_repository),
    evidence_service = Depends(get_evidence_service),
):
    case = await cases_repository.get_case(case_id)
    facts = await cases_repository.get_case_facts(case_id)
    normalized = {f["fact_type"]: f.get("fact_value_boolean") or f.get("fact_value_text") or f.get("fact_value_number") for f in facts}

    return await evidence_service.build_readiness(
        persona_mode=case["persona_mode"],
        pathway_id=None,
        psr_id=case["linked_psr_id"],
        corridor_key=f"{case['exporter_state']}:{case['importer_state']}:{case['hs6_code']}",
        facts=normalized,
    )
```

# 13. Dependency wiring

```python
# app/api/deps.py
from app.db.session import get_session
from app.repositories.hs_repository import HSRepository
from app.repositories.rules_repository import RulesRepository
from app.repositories.tariffs_repository import TariffsRepository
from app.repositories.status_repository import StatusRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.cases_repository import CasesRepository
from app.repositories.evaluations_repository import EvaluationsRepository
from app.services.classification_service import ClassificationService
from app.services.rule_resolution_service import RuleResolutionService
from app.services.tariff_resolution_service import TariffResolutionService
from app.services.status_service import StatusService
from app.services.evidence_service import EvidenceService
from app.services.fact_normalization_service import FactNormalizationService
from app.services.expression_evaluator import ExpressionEvaluator
from app.services.general_origin_rules_service import GeneralOriginRulesService
from app.services.eligibility_service import EligibilityService

def get_classification_service(session = get_session()):
    return ClassificationService(HSRepository(session))

def get_rule_resolution_service(session = get_session()):
    return RuleResolutionService(RulesRepository(session))

def get_tariff_resolution_service(session = get_session()):
    return TariffResolutionService(TariffsRepository(session))

def get_eligibility_service(session = get_session()):
    return EligibilityService(
        classification_service=ClassificationService(HSRepository(session)),
        rule_resolution_service=RuleResolutionService(RulesRepository(session)),
        tariff_resolution_service=TariffResolutionService(TariffsRepository(session)),
        status_service=StatusService(StatusRepository(session)),
        evidence_service=EvidenceService(EvidenceRepository(session)),
        fact_normalization_service=FactNormalizationService(),
        expression_evaluator=ExpressionEvaluator(),
        general_origin_rules_service=GeneralOriginRulesService(),
        evaluations_repository=EvaluationsRepository(session),
        cases_repository=CasesRepository(session),
    )
```

# 14. `main.py`

```python
from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(
    title="AfCFTA Intelligence API",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")
```

# 15. What to build first

Build in this order:

1. `hs_repository` + `classification_service`
2. `rules_repository` + `rule_resolution_service`
3. `tariffs_repository` + `tariff_resolution_service`
4. `cases_repository`
5. `expression_evaluator`
6. `general_origin_rules_service`
7. `evidence_service`
8. `eligibility_service`
9. assessment endpoint
10. audit endpoint

That order matches the actual dependency chain in the deterministic engine spec.

# 16. Final implementation note

The cleanest production move is:

* **FastAPI + SQLAlchemy Core/2.0 style**
* async DB access
* repository/service split
* persisted atomic checks for every assessment

That gives you:

* deterministic execution
* explainability
* auditability
* future UI flexibility

Next best artifact is the one that will save the most time in implementation:

**a full starter codebase skeleton with these files populated and copy-pasteable.**
