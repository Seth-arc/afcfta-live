Below is the **production-grade join model, query patterns, and execution pseudocode** for the v0.1 system, assuming the locked scope in the handover doc and the HS6-centered architecture already defined.

# 1. Join strategy

## 1.1 Canonical principle

Everything operational joins on:

`hs_version + hs6_id`

Not raw HS text. Not product description. The HS6 layer is the stable spine because Appendix IV rules apply at chapter, heading, and subheading levels, while the e-Tariff workflow also centers product lookup on 2/4/6-digit HS structures.

## 1.2 Core relational path

```text
hs6_product
  ← hs6_psr_applicability → psr_rule → psr_rule_component
                                   → eligibility_rule_pathway
  ← tariff_schedule_line ← tariff_schedule_header
                         ← tariff_schedule_rate_by_year
  ← case_file → case_input_fact
  ← evidence_requirement
  ← status_assertion
```

## 1.3 Required join keys by table

### `hs6_product`

Primary canonical product table. 

### `psr_rule`

Join with:

* `psr_rule.hs6_id = hs6_product.hs6_id` when exact
* otherwise through `hs6_psr_applicability`

### `hs6_psr_applicability`

Materialized resolver for inherited PSR coverage:

* direct HS6
* inherited from heading
* inherited from chapter. 

### `eligibility_rule_pathway`

Join:

* `eligibility_rule_pathway.psr_id = psr_rule.psr_id`

### `tariff_schedule_header`

Join on corridor context:

* `importing_state`
* `exporting_scope`
* `schedule_status`
* `effective_date`

### `tariff_schedule_line`

Join:

* `tariff_schedule_line.schedule_id = tariff_schedule_header.schedule_id`
* `tariff_schedule_line.hs6_id = hs6_product.hs6_id`

### `tariff_schedule_rate_by_year`

Join:

* `tariff_schedule_rate_by_year.schedule_line_id = tariff_schedule_line.schedule_line_id`

### `case_file`

Join:

* `case_file.hs6_id = hs6_product.hs6_id`

### `case_input_fact`

Join:

* `case_input_fact.case_id = case_file.case_id`

### `status_assertion`

Generic join:

* `entity_type`
* `entity_key`

Recommended entity keys:

* `PSR:<psr_id>`
* `SCHEDULE:<schedule_id>`
* `SCHEDULE_LINE:<schedule_line_id>`
* `CORRIDOR:<exporter>:<importer>:<hs6_code>`
* `COUNTRY:<iso3>`

### `evidence_requirement`

Recommended entity patterns:

* `entity_type = 'hs6_rule'`, `entity_key = <psr_id>`
* `entity_type = 'corridor'`, `entity_key = <exporter>:<importer>:<hs6_code>`
* `entity_type = 'pathway'`, `entity_key = <pathway_id>`

# 2. Exact DB joins

## 2.1 Resolve applicable PSR for an HS6

Use the applicability table, not live inheritance logic. That was the point of materializing applicability. 

```sql
SELECT
  hp.hs6_id,
  hp.hs_version,
  hp.hs6_code,
  hp.hs6_display,
  pa.psr_id,
  pa.applicability_type,
  pa.priority_rank,
  pr.rule_scope,
  pr.product_description,
  pr.legal_rule_text_verbatim,
  pr.legal_rule_text_normalized,
  pr.rule_status,
  pr.page_ref,
  pr.row_ref,
  pr.source_id
FROM hs6_product hp
JOIN hs6_psr_applicability pa
  ON pa.hs6_id = hp.hs6_id
JOIN psr_rule pr
  ON pr.psr_id = pa.psr_id
WHERE hp.hs_version = $1
  AND hp.hs6_code = $2
  AND (pa.effective_date IS NULL OR pa.effective_date <= $3::date)
  AND (pa.expiry_date IS NULL OR pa.expiry_date >= $3::date)
ORDER BY pa.priority_rank ASC, pr.updated_at DESC
LIMIT 1;
```

Inputs:

* `$1 = 'HS2017'`
* `$2 = '040630'`
* `$3 = assessment_date`

## 2.2 Fetch all PSR components for the resolved rule

```sql
SELECT
  prc.component_id,
  prc.component_type,
  prc.operator_type,
  prc.threshold_percent,
  prc.threshold_basis,
  prc.tariff_shift_level,
  prc.specific_process_text,
  prc.component_text_verbatim,
  prc.normalized_expression,
  prc.component_order,
  prc.confidence_score
FROM psr_rule_component prc
WHERE prc.psr_id = $1
ORDER BY prc.component_order ASC;
```

## 2.3 Fetch executable pathways for the resolved rule

```sql
SELECT
  erp.pathway_id,
  erp.pathway_code,
  erp.pathway_label,
  erp.pathway_type,
  erp.expression_json,
  erp.threshold_percent,
  erp.threshold_basis,
  erp.tariff_shift_level,
  erp.required_process_text,
  erp.allows_cumulation,
  erp.allows_tolerance,
  erp.priority_rank
FROM eligibility_rule_pathway erp
WHERE erp.psr_id = $1
  AND (erp.effective_date IS NULL OR erp.effective_date <= $2::date)
  AND (erp.expiry_date IS NULL OR erp.expiry_date >= $2::date)
ORDER BY erp.priority_rank ASC;
```

## 2.4 Resolve tariff line for corridor + HS6

The e-Tariff Book is operationally useful but the legal authority remains submitted schedules and gazetted national rates, so statuses must remain visible in the query result.

```sql
SELECT
  tsh.schedule_id,
  tsh.importing_state,
  tsh.exporting_scope,
  tsh.schedule_status,
  tsh.effective_date,
  tsh.expiry_date,
  tsl.schedule_line_id,
  tsl.hs6_id,
  tsl.hs_code,
  tsl.product_description,
  tsl.tariff_category,
  tsl.mfn_base_rate,
  tsl.base_year,
  tsl.target_rate,
  tsl.target_year,
  tsl.staging_type
FROM tariff_schedule_header tsh
JOIN tariff_schedule_line tsl
  ON tsl.schedule_id = tsh.schedule_id
JOIN hs6_product hp
  ON hp.hs6_id = tsl.hs6_id
WHERE tsh.importing_state = $1
  AND tsh.exporting_scope = $2
  AND hp.hs_version = $3
  AND hp.hs6_code = $4
  AND (tsh.effective_date IS NULL OR tsh.effective_date <= $5::date)
  AND (tsh.expiry_date IS NULL OR tsh.expiry_date >= $5::date)
ORDER BY
  CASE tsh.schedule_status
    WHEN 'gazetted' THEN 1
    WHEN 'official' THEN 2
    WHEN 'provisional' THEN 3
    ELSE 9
  END,
  tsh.updated_at DESC
LIMIT 1;
```

## 2.5 Resolve year-specific rate

```sql
SELECT
  tsry.year_rate_id,
  tsry.calendar_year,
  tsry.preferential_rate,
  tsry.rate_status,
  tsry.source_id
FROM tariff_schedule_rate_by_year tsry
WHERE tsry.schedule_line_id = $1
  AND tsry.calendar_year = $2;
```

Fallback if missing year rate:

* use target/base fields from `tariff_schedule_line`
* mark `tariff_status = incomplete`

## 2.6 Fetch relevant status assertions

```sql
SELECT
  sa.status_assertion_id,
  sa.entity_type,
  sa.entity_key,
  sa.status_type,
  sa.status_text_verbatim,
  sa.effective_from,
  sa.effective_to,
  sa.page_ref,
  sa.clause_ref,
  sa.confidence_score,
  sa.source_id
FROM status_assertion sa
WHERE (
    (sa.entity_type = 'psr' AND sa.entity_key = $1)
 OR (sa.entity_type = 'schedule' AND sa.entity_key = $2)
 OR (sa.entity_type = 'schedule_line' AND sa.entity_key = $3)
 OR (sa.entity_type = 'corridor' AND sa.entity_key = $4)
)
AND (sa.effective_from IS NULL OR sa.effective_from <= $5::date)
AND (sa.effective_to IS NULL OR sa.effective_to >= $5::date)
ORDER BY sa.confidence_score DESC, sa.updated_at DESC;
```

## 2.7 Fetch evidence requirements

```sql
SELECT
  er.evidence_id,
  er.entity_type,
  er.entity_key,
  er.persona_mode,
  er.requirement_type,
  er.requirement_description,
  er.legal_basis_provision_id,
  er.required,
  er.conditional_on,
  er.priority_level
FROM evidence_requirement er
WHERE er.persona_mode IN ($1, 'system')
  AND (
       (er.entity_type = 'pathway' AND er.entity_key = $2)
    OR (er.entity_type = 'hs6_rule' AND er.entity_key = $3)
    OR (er.entity_type = 'corridor' AND er.entity_key = $4)
  )
ORDER BY er.priority_level ASC, er.requirement_type ASC;
```

## 2.8 Fetch case facts

```sql
SELECT
  cif.case_input_fact_id,
  cif.fact_type,
  cif.fact_value_text,
  cif.fact_value_number,
  cif.fact_value_boolean,
  cif.fact_value_json,
  cif.source_type,
  cif.source_ref,
  cif.confidence_score
FROM case_input_fact cif
WHERE cif.case_id = $1
ORDER BY cif.fact_type ASC, cif.created_at ASC;
```

# 3. Production query patterns

## 3.1 Pattern: rule lookup endpoint

Use when user asks:

* “What is the rule for HS 040630?”
* “Show Appendix IV rule for HS6”

Execution:

1. resolve HS6
2. resolve applicable PSR
3. fetch components
4. fetch pathway rows
5. attach status assertions
6. return normalized + verbatim rule

## 3.2 Pattern: tariff lookup endpoint

Use when user asks:

* “What tariff applies from Ghana to Nigeria for HS 110311?”

Execution:

1. resolve HS6
2. resolve schedule header/line
3. resolve year rate
4. attach schedule status
5. return MFN base, current rate, target rate, category

## 3.3 Pattern: eligibility assessment endpoint

Use when user asks:

* “Can Cameroon export X to Nigeria?”

Execution:

1. resolve HS6
2. get PSR + pathways
3. get tariff line
4. get statuses
5. get evidence template
6. get case facts
7. run blockers
8. run pathways
9. run general rules
10. emit outcome

## 3.4 Pattern: evidence readiness endpoint

Execution:

1. resolve applicable pathway or rule
2. fetch evidence requirements by persona + pathway + corridor
3. compare against case facts
4. emit missing / present / conditional

## 3.5 Pattern: case replay / audit

Execution:

1. fetch past `eligibility_evaluation`
2. fetch all `eligibility_check_result`
3. fetch linked legal provisions + PSR components
4. reconstruct deterministic decision trail

# 4. Indexing recommendations

These are the indexes that matter most in practice.

## 4.1 Must-have

```sql
CREATE INDEX idx_hs6_product_ver_code
ON hs6_product (hs_version, hs6_code);

CREATE INDEX idx_hs6_psr_applicability_lookup
ON hs6_psr_applicability (hs6_id, priority_rank, effective_date, expiry_date);

CREATE INDEX idx_eligibility_rule_pathway_psr
ON eligibility_rule_pathway (psr_id, priority_rank, effective_date, expiry_date);

CREATE INDEX idx_tariff_schedule_header_corridor
ON tariff_schedule_header (importing_state, exporting_scope, schedule_status, effective_date);

CREATE INDEX idx_tariff_schedule_line_hs6
ON tariff_schedule_line (schedule_id, hs6_id);

CREATE INDEX idx_tariff_rate_year_lookup
ON tariff_schedule_rate_by_year (schedule_line_id, calendar_year);

CREATE INDEX idx_case_input_fact_case_fact
ON case_input_fact (case_id, fact_type);

CREATE INDEX idx_status_assertion_entity_window
ON status_assertion (entity_type, entity_key, effective_from, effective_to);

CREATE INDEX idx_evidence_requirement_match
ON evidence_requirement (persona_mode, entity_type, entity_key, priority_level);
```

## 4.2 Useful GIN indexes

```sql
CREATE INDEX idx_case_input_fact_json
ON case_input_fact USING GIN (fact_value_json);

CREATE INDEX idx_evidence_requirement_conditional
ON evidence_requirement USING GIN (conditional_on);
```

# 5. Transaction boundaries

## 5.1 Read-only assessment request

Use one transaction with `REPEATABLE READ` so:

* PSR
* tariff
* statuses
* evidence
  are all resolved against the same snapshot.

## 5.2 Persisted evaluation

Use:

1. begin transaction
2. lock case row if needed
3. insert `eligibility_evaluation`
4. insert `eligibility_check_result` rows
5. update `case_assessment`
6. commit

This prevents drift between displayed result and stored audit trail.

# 6. Execution pseudocode

## 6.1 Main assessment service

```python
def assess_case(
    db,
    hs_version: str,
    hs6_code: str,
    exporter_state: str,
    importer_state: str,
    persona_mode: str,
    assessment_date: date,
    case_id: str,
) -> dict:
    with db.transaction(isolation="repeatable_read"):
        product = resolve_hs6(db, hs_version, hs6_code)
        if not product:
            return fail("UNKNOWN_HS6", "HS6 code could not be resolved")

        psr = resolve_applicable_psr(db, product.hs6_id, assessment_date)
        if not psr:
            return fail("NO_PSR_FOUND", "No applicable PSR resolved")

        pathways = get_rule_pathways(db, psr.psr_id, assessment_date)
        components = get_psr_components(db, psr.psr_id)

        tariff_line = resolve_tariff_line(
            db, importer_state, exporter_state, hs_version, hs6_code, assessment_date
        )

        tariff_year = None
        if tariff_line:
            tariff_year = get_year_rate(db, tariff_line.schedule_line_id, assessment_date.year)

        statuses = get_status_bundle(
            db=db,
            psr_id=psr.psr_id,
            schedule_id=tariff_line.schedule_id if tariff_line else None,
            schedule_line_id=tariff_line.schedule_line_id if tariff_line else None,
            corridor_key=f"{exporter_state}:{importer_state}:{hs6_code}",
            assessment_date=assessment_date,
        )

        evidence_rules = get_evidence_bundle(
            db=db,
            persona_mode=persona_mode,
            pathway_ids=[p.pathway_id for p in pathways],
            psr_id=psr.psr_id,
            corridor_key=f"{exporter_state}:{importer_state}:{hs6_code}",
        )

        facts = load_case_facts(db, case_id)
        normalized_facts = normalize_case_facts(facts)

        blocker_results = run_blocker_checks(
            psr=psr,
            tariff_line=tariff_line,
            tariff_year=tariff_year,
            statuses=statuses,
            pathways=pathways,
            facts=normalized_facts,
        )
        if any(x.severity == "blocker" and x.passed is False for x in blocker_results):
            return persist_and_return_blocked(
                db=db,
                case_id=case_id,
                product=product,
                psr=psr,
                tariff_line=tariff_line,
                blocker_results=blocker_results,
                evidence_rules=evidence_rules,
            )

        pathway_results = []
        for pathway in pathways:
            required = get_fact_requirements_for_pathway(db, pathway.pathway_id)
            completeness = check_fact_completeness(required, normalized_facts)
            if not completeness.complete:
                pathway_results.append(
                    make_incomplete_pathway_result(pathway, completeness.missing_fact_types)
                )
                continue

            eval_result = evaluate_expression_json(
                expression_json=pathway.expression_json,
                facts=normalized_facts,
            )
            pathway_results.append(eval_result)

        selected = choose_best_pathway_result(pathway_results)

        general_rule_checks = run_general_origin_checks(
            facts=normalized_facts,
            psr=psr,
            selected_pathway=selected,
            statuses=statuses,
        )

        evidence_result = evaluate_evidence_readiness(
            evidence_rules=evidence_rules,
            facts=normalized_facts,
        )

        final_result = combine_results(
            selected_pathway=selected,
            blocker_results=blocker_results,
            general_rule_checks=general_rule_checks,
            evidence_result=evidence_result,
            tariff_line=tariff_line,
            tariff_year=tariff_year,
            statuses=statuses,
            psr=psr,
        )

        persist_assessment(
            db=db,
            case_id=case_id,
            product=product,
            psr=psr,
            tariff_line=tariff_line,
            final_result=final_result,
            all_checks=blocker_results + selected.checks + general_rule_checks + evidence_result.checks,
        )

        return final_result
```

## 6.2 Resolve HS6

```python
def resolve_hs6(db, hs_version: str, hs6_code: str):
    normalized = normalize_hs6_code(hs6_code)
    return db.fetch_one(
        """
        SELECT hs6_id, hs_version, hs6_code, hs6_display, subheading_title
        FROM hs6_product
        WHERE hs_version = %s AND hs6_code = %s
        """,
        [hs_version, normalized],
    )
```

## 6.3 Resolve PSR

```python
def resolve_applicable_psr(db, hs6_id: str, assessment_date: date):
    return db.fetch_one(
        """
        SELECT pr.*, pa.applicability_type, pa.priority_rank
        FROM hs6_psr_applicability pa
        JOIN psr_rule pr ON pr.psr_id = pa.psr_id
        WHERE pa.hs6_id = %s
          AND (pa.effective_date IS NULL OR pa.effective_date <= %s)
          AND (pa.expiry_date IS NULL OR pa.expiry_date >= %s)
        ORDER BY pa.priority_rank ASC, pr.updated_at DESC
        LIMIT 1
        """,
        [hs6_id, assessment_date, assessment_date],
    )
```

## 6.4 Blocker checks

Order matters, because the deterministic engine specification requires hard blockers first. 

```python
def run_blocker_checks(psr, tariff_line, tariff_year, statuses, pathways, facts):
    checks = []

    if psr.rule_status in {"pending", "partially_agreed"}:
        checks.append(fail_check("RULE_STATUS", "status", "blocker", "PSR not fully agreed"))

    if tariff_line is None:
        checks.append(fail_check("NO_SCHEDULE", "corridor", "blocker", "No schedule line found"))

    if tariff_line and tariff_line.schedule_status == "provisional":
        checks.append(info_check("PROVISIONAL_SCHEDULE", "corridor", "major", "Schedule is provisional"))

    for pathway in pathways:
        missing = missing_required_facts(pathway, facts)
        if missing:
            checks.append(fail_check(
                "MISSING_CORE_FACTS",
                "rule",
                "blocker",
                f"Missing facts for pathway {pathway.pathway_code}: {', '.join(missing)}"
            ))
            break

    if has_status(statuses, "not_yet_operational"):
        checks.append(fail_check(
            "NOT_OPERATIONAL",
            "status",
            "blocker",
            "Corridor or instrument not yet operational"
        ))

    return checks
```

## 6.5 Expression evaluator

Use the constrained DSL already defined for `expression_json`. 

```python
def evaluate_expression_json(expression_json: dict, facts: dict):
    variables = compute_variables(expression_json.get("variables", []), facts)
    root = expression_json["expression"]
    passed, checks = eval_node(root, facts, variables)
    return PathwayEvaluation(
        pathway_code=expression_json["pathway_code"],
        passed=passed,
        checks=checks,
    )
```

```python
def eval_node(node, facts, variables):
    op = node["op"]

    if op == "all":
        child_checks = []
        all_passed = True
        for child in node["args"]:
            passed, checks = eval_node(child, facts, variables)
            all_passed = all_passed and passed
            child_checks.extend(checks)
        return all_passed, child_checks

    if op == "any":
        all_child_checks = []
        any_passed = False
        for child in node["args"]:
            passed, checks = eval_node(child, facts, variables)
            if passed:
                any_passed = True
            all_child_checks.extend(checks)
        return any_passed, all_child_checks

    if op == "formula_lte":
        actual = variables[node["formula"]]
        expected = node["value"]
        passed = actual <= expected
        return passed, [make_check("FORMULA_LTE", passed, expected, actual)]

    if op == "fact_eq":
        actual = facts.get(node["fact"])
        expected = node["value"]
        passed = actual == expected
        return passed, [make_check("FACT_EQ", passed, expected, actual)]

    if op == "every_non_originating_input":
        test = node["test"]["op"]
        inputs = facts.get("non_originating_inputs", [])
        output_hs6 = facts["output_hs6_code"]
        passed = True
        for item in inputs:
            if test == "heading_ne_output":
                if item["hs4_code"] == output_hs6[:4]:
                    passed = False
            elif test == "subheading_ne_output":
                if item["hs6_code"] == output_hs6:
                    passed = False
        return passed, [make_check(test, passed, "all inputs differ", inputs)]

    raise ValueError(f"Unsupported op: {op}")
```

## 6.6 General origin checks

The rules of origin are broader than the PSR row; general conditions such as insufficient operations, cumulation, direct transport, and procedural elements sit outside the pathway expression.

```python
def run_general_origin_checks(facts, psr, selected_pathway, statuses):
    checks = []

    if facts.get("simple_operation_flag") is True:
        checks.append(fail_check(
            "INSUFFICIENT_OPERATION",
            "procedure",
            "major",
            "Only simple operations indicated"
        ))

    if facts.get("direct_transport_confirmed") is False:
        checks.append(fail_check(
            "DIRECT_TRANSPORT_FAIL",
            "procedure",
            "major",
            "Direct transport condition not satisfied"
        ))

    if facts.get("cumulation_claimed") is True and not selected_pathway.allows_cumulation:
        checks.append(fail_check(
            "CUMULATION_NOT_ALLOWED",
            "procedure",
            "major",
            "Cumulation claimed but not allowed for pathway"
        ))

    return checks
```

## 6.7 Final result combiner

```python
def combine_results(
    selected_pathway,
    blocker_results,
    general_rule_checks,
    evidence_result,
    tariff_line,
    tariff_year,
    statuses,
    psr,
):
    all_checks = blocker_results + selected_pathway.checks + general_rule_checks + evidence_result.checks

    if any(c.severity == "blocker" and c.passed is False for c in blocker_results):
        legal_outcome = "not_yet_operational" if any(c.code == "NOT_OPERATIONAL" for c in blocker_results) else "insufficient_information"
    elif selected_pathway.passed is False:
        legal_outcome = "not_eligible"
    elif any(c.passed is False for c in general_rule_checks if c.severity in {"major", "blocker"}):
        legal_outcome = "not_eligible"
    else:
        legal_outcome = "eligible"

    confidence = derive_confidence(
        evidence_complete=evidence_result.completeness_ratio >= 0.9,
        has_provisional=tariff_line is not None and tariff_line.schedule_status == "provisional",
        has_missing_minor=evidence_result.missing_count > 0,
    )

    return {
        "legal_outcome": legal_outcome,
        "confidence_level": confidence,
        "pathway_used": selected_pathway.pathway_code,
        "rule_status": psr.rule_status,
        "tariff_outcome": None if not tariff_line else {
            "mfn_base_rate": tariff_line.mfn_base_rate,
            "preferential_rate": tariff_year.preferential_rate if tariff_year else None,
            "tariff_category": tariff_line.tariff_category,
            "schedule_status": tariff_line.schedule_status,
        },
        "failures": [serialize_check(c) for c in all_checks if c.passed is False],
        "evidence_required": evidence_result.required_items,
        "missing_evidence": evidence_result.missing_items,
    }
```

# 7. Query bundles by endpoint

## `GET /api/v1/rules/{hs6}`

Bundle:

* resolve HS6
* resolve PSR
* fetch components
* fetch pathways
* fetch PSR status assertions

## `GET /api/v1/tariffs`

Params:

* exporter
* importer
* hs6
* year

Bundle:

* resolve HS6
* resolve tariff line
* resolve year rate
* fetch schedule/corridor statuses

## `POST /api/v1/eligibility-assessments`

Body:

* corridor
* hs6
* case facts
* persona

Bundle:

* resolve HS6
* resolve PSR/pathways
* resolve tariff line/rate
* resolve statuses
* resolve evidence requirements
* evaluate + persist

## `GET /api/v1/cases/{case_id}/audit`

Bundle:

* `case_file`
* `case_input_fact`
* `eligibility_evaluation`
* `eligibility_check_result`
* linked `psr_rule`, `eligibility_rule_pathway`, `legal_provision`

# 8. Practical implementation notes

The most important production decision is this:

**Do not let API handlers assemble business logic ad hoc.**

Use four services only:

* `classification_service`
* `rule_resolution_service`
* `tariff_resolution_service`
* `eligibility_service`

And one shared:

* `status_service`

That keeps the deterministic pipeline consistent with the scope doc and engine spec.

The second most important decision:

**Persist every atomic check.**

That is what turns the system from “clever compliance software” into an auditable decision engine.


