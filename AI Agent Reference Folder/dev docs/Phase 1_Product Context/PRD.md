# **AfCFTA Intelligence System — Product Requirements Document (PRD v0.1)**

---

# **1. Product Definition**

## **1.1 Product Name (Working)**

**AfCFTA Intelligence System (AIS)**

## **1.2 Product Type**

Deterministic **RegTech decision-support platform** for:

* Competent Authority Officers
* Policy Analysts
* Exporters

## **1.3 Core Value Proposition**

Not retrieval → **decision execution**

* Structured PSR interpretation
* Deterministic eligibility outcomes
* Corridor-aware tariff intelligence
* Evidence readiness + audit trace

→ No ambiguity, no hallucination, no “best guess” outputs 

---

# **2. Objectives**

## **2.1 Primary Objective**

Enable users to answer:

* Can this product qualify under AfCFTA?
* Under which legal pathway?
* What tariff applies?
* What documentation is required?
* What legal/status constraints exist?

## **2.2 Non-Negotiables**

* Deterministic outputs only
* Fully auditable logic
* Verbatim legal traceability
* Status-aware responses

---

# **3. Scope (v0.1 Locked)**

## **3.1 Countries**

* Nigeria
* Ghana
* Côte d’Ivoire
* Senegal
* Kenya

## **3.2 Product Resolution**

* **HS6 canonical only**
* HS8/10 stored but NOT computed

## **3.3 Capabilities**

1. Rule lookup
2. Tariff lookup
3. Eligibility engine
4. Evidence readiness
5. Status-aware outputs

---

# **4. Users & Personas**

## **4.1 Competent Authority Officer**

* Needs: legal defensibility, audit trails
* Behavior: case-by-case validation
* Output: structured + evidentiary

## **4.2 Policy Analyst**

* Needs: system-level insight
* Behavior: comparative + scenario modeling
* Output: rule + tariff + status overlays

## **4.3 Exporter**

* Needs: actionable clarity
* Behavior: pre-shipment validation
* Output: pass/fail + checklist

---

# **5. Core Features**

---

## **5.1 Rule Lookup Engine**

### Input

* HS6 code

### Output

* PSR rule(s)
* Components (WO, VNM, CTH, etc.)
* Thresholds
* Legal text (verbatim)
* Rule status

### Data Dependencies

* `psr_rule`
* `psr_rule_component`
* `eligibility_rule_pathway` 

---

## **5.2 Tariff Engine**

### Input

* exporter_country
* importer_country
* HS6

### Output

* MFN base rate
* Preferential rate
* Staging year
* Tariff status

### Data Dependencies

* `tariff_schedule_line`
* `tariff_schedule_rate_by_year`

---

## **5.3 Eligibility Engine (Core IP)**

### Input

* HS6
* production facts

### Output

* eligible / not eligible
* pathway used
* failure codes
* counterfactuals
* missing inputs

### Logic

* deterministic expression execution
* AND/OR pathway evaluation
* general rules applied separately

### Derived Variables

* VNM %
* VA %

### Execution Flow

```
HS6 → PSR → Pathways → Evaluate → Apply general rules → Status → Tariff
```



---

## **5.4 Evidence Readiness Engine**

### Output

* required documents
* missing documents
* verification questions

### Data Dependencies

* `evidence_requirement`
* `verification_question`
* `document_readiness_template`

---

## **5.5 Status Layer (Critical)**

Every output must include:

* rule_status
* tariff_status
* legal_basis
* confidence_class

→ prevents false certainty

---

# **6. System Architecture**

## **6.1 Data Layers**

| Layer        | Tables                                                       |
| ------------ | ------------------------------------------------------------ |
| Backbone     | `hs6_product`                                                |
| Rules        | `psr_rule`, `psr_rule_component`, `eligibility_rule_pathway` |
| Tariffs      | `tariff_schedule_*`                                          |
| Status       | `status_assertion`, `transition_clause`                      |
| Evidence     | `evidence_requirement`, `verification_question`              |
| Decision     | `case_file`, `case_input_fact`                               |
| Intelligence | `corridor_profile`, `alert_event`                            |



---

## **6.2 Core Services**

* classification_service
* rule_resolution_service
* tariff_resolution_service
* eligibility_service
* evidence_service
* audit_service



---

## **6.3 Join Principle**

All joins resolve via:

```
hs_version + hs6_id
```

→ single canonical spine
→ eliminates ambiguity



---

# **7. API Contract**

## **7.1 Rule Lookup**

```
GET /v1/rules/{hs6}
```

## **7.2 Tariff Query**

```
GET /v1/tariffs?exporter=&importer=&hs6=&year=
```

## **7.3 Case Creation**

```
POST /v1/cases
```

## **7.4 Eligibility Assessment**

```
POST /v1/assessments
```

---

## **7.5 Sample Response**

```json
{
  "hs6_code": "040630",
  "eligible": true,
  "pathway_used": "VNM<=40",
  "rule_status": "agreed",
  "tariff_outcome": {
    "preferential_rate": 0,
    "base_rate": 20,
    "status": "provisional"
  },
  "failures": [],
  "missing_facts": [],
  "evidence_required": ["invoice", "origin_declaration"],
  "confidence_class": "complete"
}
```



---

# **8. Data Ingestion Requirements**

## **8.1 Sources**

* AfCFTA Agreement + Appendix IV
* e-Tariff schedules
* WCO / AfCFTA manuals
* Corridor datasets

## **8.2 Parser Requirements**

* preserve verbatim legal text
* normalize into components
* generate executable expressions
* attach provenance
* flag ambiguity

---

# **9. Evaluation & QA**

## **9.1 Deterministic Validation**

* unit tests per HS6 rule
* pathway execution tests
* counterfactual validation

## **9.2 Failure Modes**

* incorrect rule inheritance
* missing status flags
* ambiguous parsing
* incomplete tariff schedules

---

# **10. Success Metrics**

## **10.1 Product Metrics**

* % HS6 coverage (PSR parsed)
* % tariff corridor coverage
* % deterministic evaluations completed

## **10.2 Accuracy Metrics**

* rule extraction accuracy
* pathway execution correctness
* false-positive eligibility rate (must → ~0)

---

# **11. Risks**

## **11.1 Structural**

* incomplete tariff schedules
* pending PSR rules

## **11.2 Technical**

* parser ambiguity
* incorrect inheritance logic

## **11.3 Legal**

* misinterpretation of status
  → mitigated via `status_assertion`

---

# **12. Roadmap (Post v0.1)**

## **v0.2**

* HS8/10 expansion
* More countries
* Cumulation intelligence

## **v0.3**

* Trade anomaly detection (CTAD integration)
* Corridor risk scoring
* Predictive compliance

## **v1.0**

* Full Africa coverage
* API monetization layer
* Embedded compliance engine for ERP/logistics

---

# **13. Strategic Insight (Non-obvious)**

Your moat is NOT:

* rules
* tariffs
* documents

Your moat is:

→ **execution layer + structured normalization + deterministic audit trail**

Everything else is commoditized.

---
