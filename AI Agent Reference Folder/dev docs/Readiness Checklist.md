Here is your **implementation-grade readiness checklist**—structured for execution, not discussion.

---

# **AfCFTA Intelligence System — Readiness Checklist**

## **1. Source Corpus (Legal + Tariff + Operational)**

| Component                                        | Have | Missing                       | Owner    | Blocker                       | Next Action                       |
| ------------------------------------------------ | ---- | ----------------------------- | -------- | ----------------------------- | --------------------------------- |
| Core Legal Docs (Protocol, Annexes, Appendix IV) | ✅    | —                             | You      | None                          | Lock as canonical, version + hash |
| Rules of Origin Manual + WCO Guide               | ✅    | —                             | You      | None                          | Tag for interpretation layer      |
| e-Tariff Book (interface + guide)                | ✅    | Raw structured export         | You      | No machine-readable schedules | Build scraper/export pipeline     |
| National Tariff Schedules (gazetted)             | ❌    | Full coverage                 | Research | Fragmented availability       | Acquire top 5 countries first     |
| Negotiation Status / Pending Rules               | ❌    | Critical                      | Research | Not centralized               | Build manual status registry      |
| HS Code Crosswalks (HS2012→HS2022)               | ❌    | Required                      | Data Eng | Version mismatch risk         | Integrate WCO mappings            |
| Customs Procedures per country                   | ❌    | Required for evidence engine  | Research | Country fragmentation         | Start with 3 pilot countries      |
| Ministerial decisions / updates                  | ❌    | Required for status awareness | Research | No central API                | Build update ingestion tracker    |

---

## **2. Structured Data Layer (Critical Gap)**

| Component                          | Have | Missing         | Owner          | Blocker                  | Next Action                        |
| ---------------------------------- | ---- | --------------- | -------------- | ------------------------ | ---------------------------------- |
| PSR Schema (design)                | ✅    | —               | You            | None                     | Freeze schema                      |
| PSR Extracted Data                 | ❌    | Full dataset    | Data Eng       | PDFs not parsed          | Build parser for Appendix IV       |
| Tariff Schedule Schema             | ✅    | —               | You            | None                     | Freeze schema                      |
| Tariff Schedule Data               | ❌    | Full schedules  | Data Eng       | No structured ingestion  | Build ETL from e-Tariff + national |
| Legal Provision Index              | ❌    | Full extraction | Data Eng       | Unstructured text        | Chunk + tag legal corpus           |
| Status Flags (agreed/pending)      | ❌    | Fully populated | Policy Analyst | Missing negotiation data | Create manual tagging layer        |
| Cross-linking (HS ↔ Rule ↔ Tariff) | ❌    | Required        | Data Eng       | No unified key           | Build HS6 canonical key system     |

---

## **3. Case & Decision Engine Tables**

| Component                   | Have             | Missing        | Owner    | Blocker                | Next Action                 |
| --------------------------- | ---------------- | -------------- | -------- | ---------------------- | --------------------------- |
| case_file                   | ❌                | Full table     | Backend  | None                   | Implement immediately       |
| case_input_fact             | ❌                | Critical       | Backend  | Missing schema use     | Build ingestion UI/API      |
| verification_question       | ❌                | Full table     | Backend  | None                   | Generate from rules engine  |
| document_readiness_template | ❌                | Full templates | Policy   | Country variance       | Start generic → specialize  |
| change_log                  | ❌                | Required       | Backend  | None                   | Add audit logging           |
| case_failure_mode           | ❌                | Required       | Logic    | No failure taxonomy    | Define failure ontology     |
| case_counterfactual         | ❌                | Required       | Logic    | No simulation engine   | Build rule-modifier logic   |
| alert_event                 | ❌                | Required       | Backend  | No monitoring layer    | Add trigger system          |
| corridor_profile            | ⚠️ Partial (CSV) | Structured DB  | Data Eng | Raw CSV not normalized | Normalize corridor dataset  |

---

## **4. Retrieval + Routing Layer**

| Component                             | Have       | Missing             | Owner   | Blocker          | Next Action                  |
| ------------------------------------- | ---------- | ------------------- | ------- | ---------------- | ---------------------------- |
| Vector index (legal text)             | ❌          | Required            | ML Eng  | Not built        | Build embeddings pipeline    |
| Structured query engine (SQL-first)   | ⚠️ Partial | Full implementation | Backend | No query router  | Implement hybrid retrieval   |
| Query classifier (intent routing)     | ❌          | Required            | ML Eng  | No training data | Define 8–10 intent classes   |
| Router logic (rule vs tariff vs case) | ❌          | Required            | Backend | No orchestration | Build decision router        |
| Provenance tracking                   | ❌          | Required            | Backend | No audit layer   | Attach source IDs to outputs |

---

## **5. Decision Engine (CORE MOAT)**

| Component                          | Have            | Missing             | Owner          | Blocker              | Next Action                    |
| ---------------------------------- | --------------- | ------------------- | -------------- | -------------------- | ------------------------------ |
| Eligibility engine (logic defined) | ⚠️ Concept only | Execution logic     | Backend        | No scoring rules     | Implement rule evaluator       |
| Confidence scoring                 | ❌               | Required            | ML/Policy      | Undefined thresholds | Define scoring formula         |
| Status-aware output logic          | ⚠️ Partial      | Full implementation | Backend        | No status DB         | Integrate negotiation flags    |
| Failure analysis engine            | ❌               | Required            | Backend        | No taxonomy          | Build failure classification   |
| Counterfactual engine              | ❌               | Required            | Backend        | No simulation logic  | Build rule perturbation engine |
| Evidence readiness engine          | ⚠️ Concept      | Full logic          | Backend/Policy | Country variation    | Start generic templates        |
| Corridor intelligence engine       | ⚠️ Data exists  | Logic missing       | Data/ML        | No scoring model     | Build corridor scoring model   |

---

## **6. Corridor Intelligence Layer**

| Component                   | Have | Missing  | Owner       | Blocker               | Next Action                     |
| --------------------------- | ---- | -------- | ----------- | --------------------- | ------------------------------- |
| Corridor dataset (raw CSV)  | ✅    | —        | You         | Not normalized        | Clean + structure               |
| Geospatial network logic    | ❌    | Required | Data Eng    | No graph model        | Build graph DB                  |
| Corridor scoring model      | ❌    | Required | Data/ML     | No metrics defined    | Define latency/cost/risk scores |
| Border friction indicators  | ❌    | Required | Policy/Data | Sparse data           | Proxy via reports               |
| Route recommendation engine | ❌    | Required | Backend     | No optimization logic | Build pathfinding layer         |

---

## **7. Evaluation & Benchmarking**

| Component                     | Have | Missing  | Owner   | Blocker              | Next Action            |
| ----------------------------- | ---- | -------- | ------- | -------------------- | ---------------------- |
| Gold test cases (eligibility) | ❌    | Required | Policy  | No dataset           | Create 50–100 cases    |
| Tariff validation set         | ❌    | Required | Data    | No ground truth      | Extract from schedules |
| Rule lookup accuracy tests    | ❌    | Required | ML      | None                 | Build automated tests  |
| Confidence calibration tests  | ❌    | Required | ML      | Undefined thresholds | Run simulation tests   |
| Regression test suite         | ❌    | Required | Backend | None                 | Build CI pipeline      |

---

## **8. Governance + Trust Layer**

| Component                          | Have | Missing  | Owner   | Blocker             | Next Action               |
| ---------------------------------- | ---- | -------- | ------- | ------------------- | ------------------------- |
| Source precedence rules            | ❌    | Required | Policy  | Conflicting sources | Define hierarchy          |
| Versioning system (legal updates)  | ❌    | Required | Backend | None                | Implement version control |
| Audit logs (decision trace)        | ❌    | Required | Backend | None                | Store reasoning steps     |
| “Uncertainty” triggers             | ❌    | Required | Logic   | No thresholds       | Define fallback rules     |
| Human-in-the-loop review           | ❌    | Required | Ops     | No workflow         | Add review interface      |
| Alert system (rule/status changes) | ❌    | Required | Backend | None                | Trigger on updates        |

---

## **9. API + Product Layer**

| Component                   | Have | Missing  | Owner   | Blocker          | Next Action                |
| --------------------------- | ---- | -------- | ------- | ---------------- | -------------------------- |
| Core API schema             | ✅    | —        | You     | None             | Freeze contract            |
| Case submission endpoint    | ❌    | Required | Backend | No case tables   | Build `/case/submit`       |
| Eligibility endpoint        | ❌    | Required | Backend | No engine        | Build `/eligibility/check` |
| Corridor query endpoint     | ❌    | Required | Backend | No scoring       | Build `/corridor/query`    |
| Evidence readiness endpoint | ❌    | Required | Backend | No templates     | Build `/evidence/ready`    |
| Role-based output modes     | ❌    | Required | Backend | No persona logic | Add role switch layer      |

---

# **Reality Check (Brutal)**

You are:

* **80% done architecturally**
* **30–40% ready to build**
* **<10% ready to deploy**

---

# **Critical Path (Do These First)**

1. **Lock v1 scope**

   * 3–5 countries
   * HS6 only
   * RoO + Tariff + Eligibility + Evidence

2. **Build structured data layer**

   * PSR extraction
   * Tariff ingestion
   * HS linking

3. **Implement case system (tables + API)**

4. **Build eligibility engine (rule evaluator + scoring)**

5. **Add status-awareness (manual if needed)**

6. **Create 50 gold test cases**

---

# **Non-Obvious Gap (Most Important)**

You do NOT yet have:

> **A deterministic adjudication policy**

Until you define:

* how decisions are scored
* when the system says “uncertain”
* how conflicts are resolved

→ you don’t have an intelligence system
→ you have a sophisticated retrieval + heuristic engine

---

If you want next step:

I can convert this into a **Notion sprint board (week-by-week build plan + repo structure + ownership)** or go straight into **SQL + backend scaffolding (FastAPI / Supabase)**.
