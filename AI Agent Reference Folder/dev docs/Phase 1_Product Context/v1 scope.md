Here is your **Tight v0.1 Scope — Updated (Cameroon swap)**, cleaned and structured as a **developer handover reference doc**.

---

# **AfCFTA Intelligence System — Tight v0.1 Scope (Revised)**

---

# **1. Objective (Non-Negotiable)**

Build a **deterministic AfCFTA decision-support system** that answers:

* Qualification → *Can this product qualify?*
* Pathway → *Under which rule?*
* Outcome → *What tariff applies?*
* Burden → *What evidence is required?*
* Constraint → *What legal/status limits apply?*

**Hard constraints**

* No RAG-only answers
* No probabilistic outputs
* No silent inference

**All outputs must be**

* Structured
* Auditable
* Reproducible

---

# **2. Locked v0.1 Scope**

## **2.1 Countries (FINAL)**

* Nigeria
* Ghana
* Côte d’Ivoire
* Senegal
* **Cameroon (replaces Kenya)**

### Why Cameroon (vs Kenya)

**System impact (important):**

* Introduces **ECCAS + CEMAC logic**
* Forces **Francophone-heavy legal parsing**
* Adds **weaker digitization → stress-tests missing data handling**
* Enables **Central Africa corridor modeling (non-trivial edge case)**

**Tradeoff vs Kenya**

* Less clean procedural data
* More ambiguity → **good for robustness, worse for demos**

---

## **2.2 Product Resolution**

* **HS6 ONLY (canonical backbone)**

Rules:

* All joins resolve at HS6
* HS8/10 stored but ignored in logic
* All rule evaluation anchored at HS6

---

## **2.3 Core Capabilities (v0.1)**

### **1. Rule Lookup**

Input: `hs6`

Output:

* PSR pathways (WO / VNM / CTH / etc.)
* thresholds
* legal text (verbatim)
* rule status

---

### **2. Tariff Lookup**

Input:

* exporter_country
* importer_country
* hs6

Output:

* base_rate
* preferential_rate
* staging_year
* tariff_status

---

### **3. Eligibility Engine (Core)**

Input:

* HS6
* production facts

Output:

* eligible / not eligible
* pathway satisfied
* failure codes
* missing facts

---

### **4. Evidence Readiness**

Output:

* required documents
* missing documents
* verification questions

---

### **5. Status-Aware Output (MANDATORY)**

Every response must include:

* `rule_status`
* `tariff_status`
* `legal_basis`
* `confidence_class` (structural completeness, not probability)

---

# **3. Architecture (Minimal Build)**

## **3.1 Data Layers**

### **L1 — Backbone**

* `hs6_product`

---

### **L2 — Rules**

* `psr_rule`
* `psr_rule_component`
* `eligibility_rule_pathway`

→ Appendix IV normalized 

---

### **L3 — Tariffs**

* `tariff_schedule_header`
* `tariff_schedule_line`
* `tariff_schedule_rate_by_year`

---

### **L4 — Status**

* `status_assertion`
* `transition_clause`

---

### **L5 — Evidence**

* `evidence_requirement`
* `verification_question`
* `document_readiness_template`

---

### **L6 — Decision Layer**

* `case_file`
* `case_input_fact`
* `case_failure_mode`
* `case_counterfactual`

---

### **L7 — Intelligence Layer**

* `corridor_profile`
* `alert_event`

---

# **4. Deterministic Engine**

## **4.1 Execution Order (Strict)**

```
1. Resolve HS6
2. Fetch PSR(s)
3. Expand pathways (AND/OR)
4. Evaluate expressions
5. Apply general rules:
   - insufficient operations
   - cumulation
   - direct transport
6. Apply status constraints
7. Compute tariff
8. Generate evidence requirements
```

---

## **4.2 Rule Execution Model**

```
INPUT (facts)
↓
DERIVED VARIABLES
↓
BOOLEAN EXPRESSION
↓
PASS / FAIL + FAILURE CODES
```

---

## **4.3 Derived Variables**

```
vnom_percent = non_originating / ex_works * 100
va_percent   = (ex_works - non_originating) / ex_works * 100
```

---

## **4.4 Critical Separation**

* PSR rules = **product-specific**
* General rules = **separate engine layer**

→ prevents false qualification
→ aligns with AfCFTA legal structure

---

# **5. Parser Layer (Critical Dependency)**

## **Responsibilities**

Parser must:

1. Preserve verbatim legal text
2. Normalize → structured schema
3. Attach provenance
4. Generate executable expressions
5. Flag ambiguity (never infer)

---

## **Source Priority**

| Tier | Source                  | Role         |
| ---- | ----------------------- | ------------ |
| 1    | Agreement + Appendix IV | Binding      |
| 2    | Tariff schedules        | Operational  |
| 3    | Manuals                 | Interpretive |
| 4    | Corridor data           | Enrichment   |

---

## **Parser Outputs (Required)**

* `psr_rule`
* `psr_rule_component`
* `eligibility_rule_pathway`
* `tariff_schedule_line`
* `status_assertion`
* `evidence_requirement`

---

# **6. Eligibility Engine (v0.1 Logic)**

## **Pathway Logic**

* `AND` → all conditions required
* `OR` → alternative pathways

Appendix IV semantics:

* “or” = alternative eligibility routes
* combined rules = cumulative

---

## **Supported Rule Types**

* WO
* CTH / CTSH
* VNM
* VA
* PROCESS

---

# **7. API Output Contract**

## **7.1 Success**

```json
{
  "hs6_code": "110311",
  "eligible": true,
  "pathway_used": "CTH",
  "rule_status": "agreed",
  "tariff_outcome": {
    "preferential_rate": 0,
    "base_rate": 15,
    "status": "provisional"
  },
  "failures": [],
  "missing_facts": [],
  "evidence_required": ["certificate_of_origin"],
  "confidence_class": "complete"
}
```

---

## **7.2 Failure**

```json
{
  "eligible": false,
  "failure_codes": ["FAIL_CTH_NOT_MET"],
  "counterfactual": {
    "required_condition": "change in tariff heading",
    "observed_condition": "no tariff shift"
  }
}
```

---

# **8. Corridor Intelligence (v0.1)**

## **Minimal Model**

```json
{
  "corridor_id": "CMR-NGA",
  "route_type": "road",
  "avg_border_delay_hours": 48,
  "risk_flags": ["customs_delay", "informal_checks"]
}
```

---

## **New Insight (Cameroon effect)**

You now unlock:

* **Nigeria ↔ Cameroon = high-friction corridor**
* **Francophone ↔ Anglophone trade interface**
* **CEMAC vs ECOWAS regulatory mismatch**

→ This is **far more valuable for anomaly detection (CTAD synergy)** than Kenya

---

# **9. Constraints (Hard Limits)**

## **Not in v0.1**

* HS8/10 computation
* ML / probabilistic scoring
* auto HS classification
* full Africa coverage
* real-time legal updates

---

## **Allowed Simplifications**

* Partial tariff schedules OK
* Missing data → explicit flags
* Evidence = template-based
* Corridor data = coarse

---

# **10. v0.1 Success Criteria**

System is complete when it can:

1. Evaluate **≥5 HS6 products end-to-end**

2. Run **≥2 corridors (e.g., GHA→NGA, CMR→NGA)**

3. Produce:

   * eligibility decision
   * tariff outcome
   * failure reasoning
   * evidence checklist

4. Handle:

   * missing facts
   * ambiguous rules
   * status variability

---

# **11. Strategic Positioning (Important)**

This v0.1 is NOT a product.

It is:

> **A deterministic trade reasoning engine prototype**

What it proves:

* Rules can be executed, not read
* Compliance can be computed, not interpreted
* Trade decisions can be simulated pre-export

---

# **Non-obvious upgrade unlocked by Cameroon**

You now have:

> **A “messy corridor” test environment**

This is critical because:

* Real AfCFTA usage ≠ clean Kenya-style systems
* Most value comes from **uncertainty handling**

---

# **Next move (don’t skip)**

You should now:

→ **Lock HS6 canonical schema + joins across:**

* `psr_rule`
* `tariff_schedule_line`
* `eligibility_rule_pathway`

That becomes your **true system backbone**.

---

If you want, next step I can give you:

→ **Exact DB joins + query patterns + execution pseudocode (production-grade)**
