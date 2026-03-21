Below is an **updated implementation-grade blueprint** for an **AfCFTA intelligence system** that goes beyond RAG.

This version incorporates the stronger UVP:

* **decision support**, not just retrieval,
* **eligibility assessment**, not just rule display,
* **corridor intelligence**, not just generic AfCFTA text,
* **status-aware outputs**, not false certainty,
* **evidence readiness**, not just legal citations,
* **role-specific modes** for officers, analysts, and exporters.

---

# 1) Product definition

## 1.1 Working product concept

Build an **AfCFTA Legal + Trade Decision Engine** with six major capabilities:

1. **Rule Lookup**
2. **Tariff Corridor Query**
3. **Policy / Legal Q&A**
4. **Transition & Pending Rule Tracking**
5. **Eligibility / Failure Analysis**
6. **Evidence Readiness & Verification Support**

## 1.2 User personas

The system should support three primary personas with different output modes:

### A. Competent Authority Officer

Needs:

* exact legal text,
* verification procedures,
* discrepancy checks,
* evidence sufficiency guidance,
* risk flags,
* case memo support.

### B. Policy Analyst

Needs:

* transition maps,
* unresolved-rule tracking,
* corridor maturity,
* sector-level friction analysis,
* implementation trends.

### C. Potential Exporter

Needs:

* likely qualification path,
* tariff savings visibility,
* evidence checklist,
* likely rejection points,
* what to change to qualify.

## 1.3 Product promise

The system should answer not only:

* “What does the law say?”

but also:

* “Does this claim likely pass?”
* “Why might it fail?”
* “What evidence is missing?”
* “Is this corridor actually usable now?”
* “Is the rule agreed, provisional, or pending?”
* “What sourcing or process change would improve qualification odds?”

---

# 2) System architecture

Use a **five-layer architecture**.

## 2.1 Layer A — Canonical Source Store

Purpose:

* preserve originals,
* track provenance,
* support audit and versioning.

Contents:

* legal PDFs,
* schedules,
* appendices,
* circulars,
* notices,
* guidance notes,
* negotiation status files,
* e-Tariff Book exports,
* national implementation documents.

## 2.2 Layer B — Retrieval Index

Purpose:

* semantic and lexical retrieval for narrative/legal Q&A.

Contains:

* chunked legal text,
* operational guidance chunks,
* ministerial decision chunks,
* negotiation-status chunks,
* embeddings,
* BM25/full-text index.

## 2.3 Layer C — Structured Knowledge Layer

Purpose:

* deterministic query answering.

Contains:

* product-specific rules,
* tariff schedules by year,
* legal provisions by topic,
* status assertions,
* evidence requirements,
* corridor readiness records.

## 2.4 Layer D — Reasoning / Decision Layer

Purpose:

* apply rules to case facts.

Contains:

* eligibility engine,
* failure mode analyzer,
* evidence sufficiency engine,
* corridor risk engine,
* counterfactual recommender.

## 2.5 Layer E — Application / API Layer

Purpose:

* expose outputs per user role.

Interfaces:

* officer UI,
* analyst dashboard,
* exporter workflow,
* internal APIs,
* batch analytics pipeline.

---

# 3) Capability modules

## 3.1 Core retrieval modules

* legal provision retrieval
* rule lookup
* tariff schedule lookup
* status / transition retrieval

## 3.2 Decision-support modules

* origin eligibility assessment
* failure mode analyzer
* evidence readiness generator
* verification checklist generator
* tariff savings calculator
* counterfactual sourcing advisor

## 3.3 Analytics modules

* corridor maturity scoring
* restrictiveness / friction index
* pending-rule heatmap
* schedule phase-down tracker
* change detection / alerting

---

# 4) Source inventory

The corpus should be divided into **authority tiers** and **functional source groups**.

## 4.1 Tier 1 — Binding and quasi-binding sources

These are the highest-priority ingest sources.

### A. Continental legal texts

* Agreement Establishing the AfCFTA
* Protocol on Trade in Goods
* Compiled annexes
* Annex 1: Tariff concessions
* Annex 2: Rules of Origin
* Annex 3: Customs cooperation
* Annex 4: Trade facilitation
* Annex 5: NTBs
* Annex 8: Transit
* Annex 10: Trade remedies
* Appendices under Annex 2, especially Appendix IV

### B. Official tariff schedule sources

* State Party schedules
* customs union schedules
* provisional schedules
* schedule amendments
* gazetted implementing tariff notices

### C. Official status and negotiation sources

* Council / ministerial decisions
* committee communiqués
* official negotiation updates
* official implementation directives

## 4.2 Tier 2 — Official operational sources

* e-Tariff Book exports
* Secretariat guidance
* customs circulars
* implementation notes
* origin certification procedures
* verification procedure guidance
* official domestic customs notices

## 4.3 Tier 3 — Interpretive support

* Rules of Origin manuals
* implementation guides
* structured explainers
* operational notes useful for normalization

## 4.4 Tier 4 — Analytic enrichment sources

Not binding, but useful for policy and risk context.

* corridor performance statistics
* customs administration readiness indicators
* border delay datasets
* trade volume baselines
* partner-state implementation trackers

These should never override legal truth, but can enhance UVP for analysts and exporters.

---

# 5) Functional data domains

The structured system should be built around seven domains.

## 5.1 Legal domain

Stores the legal text and provision ontology.

## 5.2 Origin-rule domain

Stores Appendix IV rules and generalized origin logic.

## 5.3 Tariff domain

Stores schedules, year-by-year rates, categories, and corridor materializations.

## 5.4 Status domain

Stores pending, provisional, transitional, review, and effective-date logic.

## 5.5 Evidence domain

Stores documents, proof requirements, officer verification points, and exporter readiness checklists.

## 5.6 Case assessment domain

Stores input facts, assessment logic, failure modes, and decisions.

## 5.7 Intelligence domain

Stores corridor maturity, restrictiveness scores, change logs, and alerts.

---

# 6) Repository and data layout

```text
afcfta-intelligence/
  data/
    raw/
      tier1_binding/
        legal/
        annexes/
        appendices/
        tariff_schedules/
        ministerial_decisions/
        status_decisions/
      tier2_operational/
        e_tariff_book/
        customs_circulars/
        guidance/
        implementation_notes/
      tier3_support/
        manuals/
        guides/
      tier4_analytics/
        corridor_metrics/
        customs_readiness/
        trade_baselines/
    staged/
      extracted_text/
      extracted_tables/
      ocr/
      metadata/
      normalized/
    processed/
      chunks/
      entities/
      provisions/
      rules/
      tariffs/
      statuses/
      evidence/
      cases/
      analytics/
  schemas/
    sql/
    json/
    contracts/
  pipelines/
    acquire/
    parse/
    normalize/
    enrich/
    assess/
    index/
    alerts/
    qa/
  eval/
    gold_sets/
    benchmarks/
    regression/
  docs/
    source_registry/
    ontology/
    parser_notes/
    governance/
```

---

# 7) Source registry schema

Create a `source_registry` table for every source file.

## 7.1 `source_registry`

Fields:

* `source_id`
* `title`
* `short_title`
* `source_group`
* `source_type`
* `authority_tier`
* `issuing_body`
* `jurisdiction_scope`
* `country_code`
* `customs_union_code`
* `publication_date`
* `effective_date`
* `expiry_date`
* `version_label`
* `status`
* `language`
* `hs_version`
* `file_path`
* `mime_type`
* `source_url`
* `checksum_sha256`
* `supersedes_source_id`
* `superseded_by_source_id`
* `citation_preferred`
* `ingested_at`
* `notes`

## 7.2 `source_attachment`

For cases where one document contains multiple extractable artifacts.
Fields:

* `attachment_id`
* `source_id`
* `artifact_type`
* `artifact_name`
* `page_start`
* `page_end`
* `artifact_path`

---

# 8) Core structured schemas

## 8.1 Legal provision schema

### `legal_provision`

Fields:

* `provision_id`
* `source_id`
* `instrument_name`
* `instrument_type`
* `article_ref`
* `annex_ref`
* `appendix_ref`
* `section_ref`
* `subsection_ref`
* `page_start`
* `page_end`
* `topic_primary`
* `topic_secondary`
* `provision_text_verbatim`
* `provision_text_normalized`
* `effective_date`
* `expiry_date`
* `status`
* `cross_reference_refs`
* `authority_weight`

### `legal_topic_map`

Fields:

* `topic_id`
* `topic_name`
* `parent_topic`
* `description`
* `keywords`
* `example_queries`

Examples:

* valuation
* de minimis
* cumulation
* proof of origin
* verification
* penalties
* documentary requirements
* transit
* customs cooperation

---

## 8.2 Product-specific rules schema

### `psr_rule`

Fields:

* `psr_id`
* `source_id`
* `appendix_version`
* `hs_version`
* `hs_code`
* `hs_code_start`
* `hs_code_end`
* `hs_level`
* `product_description`
* `legal_rule_text_verbatim`
* `legal_rule_text_normalized`
* `rule_status`
* `effective_date`
* `page_ref`
* `table_ref`
* `row_ref`

### `psr_rule_component`

Fields:

* `component_id`
* `psr_id`
* `component_type`
* `operator_type`
* `threshold_percent`
* `threshold_basis`
* `tariff_shift_level`
* `specific_process_text`
* `component_text_verbatim`
* `normalized_expression`
* `confidence_score`

### `psr_status_event`

Fields:

* `status_event_id`
* `psr_id`
* `status`
* `event_date`
* `source_id`
* `page_ref`
* `note`

---

## 8.3 Tariff schedule schema

### `tariff_schedule_header`

Fields:

* `schedule_id`
* `source_id`
* `importing_state`
* `exporting_scope`
* `schedule_status`
* `publication_date`
* `effective_date`
* `expiry_date`
* `hs_version`
* `category_system`
* `notes`

### `tariff_schedule_line`

Fields:

* `schedule_line_id`
* `schedule_id`
* `hs_code`
* `product_description`
* `tariff_category`
* `mfn_base_rate`
* `base_year`
* `target_rate`
* `target_year`
* `staging_type`
* `page_ref`
* `table_ref`
* `row_ref`

### `tariff_schedule_rate_by_year`

Fields:

* `year_rate_id`
* `schedule_line_id`
* `calendar_year`
* `preferential_rate`
* `rate_status`
* `source_id`
* `page_ref`

### `corridor_tariff_view`

Materialized view or table:

* `corridor_id`
* `exporter_state`
* `importer_state`
* `hs_code`
* `calendar_year`
* `mfn_base_rate`
* `preferential_rate`
* `target_rate`
* `target_year`
* `schedule_status`
* `evidence_source_ids`

---

## 8.4 Status and transition schema

### `status_assertion`

Fields:

* `status_assertion_id`
* `source_id`
* `entity_type`
* `entity_key`
* `status_type`
* `status_text_verbatim`
* `effective_from`
* `effective_to`
* `page_ref`
* `clause_ref`
* `confidence_score`

### `transition_clause`

Fields:

* `transition_id`
* `source_id`
* `entity_type`
* `entity_key`
* `transition_type`
* `transition_text_verbatim`
* `start_date`
* `end_date`
* `review_trigger`
* `page_ref`

Status types:

* agreed
* pending
* provisional
* under_review
* transitional
* superseded
* in_force
* not_yet_operational

---

## 8.5 Evidence and verification schema

### `evidence_requirement`

Fields:

* `evidence_id`
* `entity_type`
* `entity_key`
* `persona_mode`
* `requirement_type`
* `requirement_description`
* `legal_basis_provision_id`
* `required`
* `conditional_on`
* `priority_level`

Requirement types:

* certificate_of_origin
* supplier_declaration
* process_record
* bill_of_materials
* cost_breakdown
* invoice
* transport_record
* customs_supporting_doc
* valuation_support
* inspection_record

### `verification_question`

Fields:

* `question_id`
* `entity_type`
* `entity_key`
* `persona_mode`
* `question_text`
* `purpose`
* `legal_basis_provision_id`
* `risk_category`

### `document_readiness_template`

Fields:

* `template_id`
* `hs_code`
* `corridor_scope`
* `origin_pathway_type`
* `required_docs`
* `optional_docs`
* `common_weaknesses`
* `officer_focus_points`

---

## 8.6 Case assessment schema

### `case_file`

Fields:

* `case_id`
* `created_at`
* `persona_mode`
* `exporter_state`
* `importer_state`
* `hs_code`
* `declared_origin`
* `declared_pathway`
* `submission_status`
* `notes`

### `case_input_fact`

Fields:

* `fact_id`
* `case_id`
* `fact_type`
* `fact_key`
* `fact_value`
* `unit`
* `source_type`
* `confidence_score`

Examples:

* ex_works_value
* non_originating_material_percent
* process_step
* input_origin_country
* supplier_declaration_present
* certificate_present

### `case_assessment`

Fields:

* `assessment_id`
* `case_id`
* `assessment_type`
* `decision_outcome`
* `confidence_level`
* `decision_reasoning`
* `generated_at`

### `case_failure_mode`

Fields:

* `failure_id`
* `assessment_id`
* `failure_type`
* `severity`
* `failure_reason`
* `linked_rule_component_id`
* `linked_provision_id`
* `remediation_suggestion`

### `case_counterfactual`

Fields:

* `counterfactual_id`
* `assessment_id`
* `scenario_label`
* `input_change`
* `projected_outcome`
* `projected_reasoning`

---

## 8.7 Intelligence and analytics schema

### `corridor_profile`

Fields:

* `corridor_profile_id`
* `exporter_state`
* `importer_state`
* `corridor_status`
* `schedule_maturity_score`
* `documentation_complexity_score`
* `verification_risk_score`
* `transition_exposure_score`
* `notes`

### `restrictiveness_index`

Fields:

* `index_id`
* `hs_code`
* `corridor_scope`
* `rule_complexity_score`
* `tariff_relief_speed_score`
* `documentary_burden_score`
* `pending_rule_exposure_score`
* `overall_restrictiveness_score`
* `method_version`

### `change_log`

Fields:

* `change_id`
* `entity_type`
* `entity_key`
* `change_type`
* `old_value`
* `new_value`
* `source_id`
* `detected_at`

### `alert_event`

Fields:

* `alert_id`
* `alert_type`
* `entity_type`
* `entity_key`
* `severity`
* `alert_message`
* `triggered_at`
* `status`

---

# 9) Parsing pipeline

The parsing system should branch by document type.

## 9.1 Pipeline stages

1. acquire
2. register
3. classify
4. extract text
5. extract tables
6. detect structure
7. normalize
8. enrich
9. validate
10. publish to stores
11. index
12. diff against prior version

## 9.2 Document classification classes

* `LEGAL_TEXT`
* `APPENDIX_RULE_TABLE`
* `TARIFF_SCHEDULE_TABLE`
* `STATUS_NOTICE`
* `IMPLEMENTATION_CIRCULAR`
* `GUIDANCE_DOC`
* `FORM_TEMPLATE`
* `ANALYTIC_REFERENCE`

## 9.3 Extraction strategy by class

### A. Legal text

Extract:

* full text,
* article structure,
* annex structure,
* appendix structure,
* page anchors,
* cross-references.

### B. Rule tables

Extract:

* row boundaries,
* HS fields,
* descriptions,
* legal text,
* notes,
* row references.

### C. Tariff schedules

Extract:

* schedule header,
* tariff category,
* year columns,
* rate values,
* target year,
* notes.

### D. Status notices

Extract:

* affected entity,
* status phrase,
* effective date,
* sunset / review language,
* referenced schedule/rule/provision.

### E. Circulars and guidance

Extract:

* operational procedure text,
* verification steps,
* required documents,
* submission requirements,
* officer action cues.

---

# 10) Normalization pipeline

## 10.1 HS normalization

* standardize punctuation,
* preserve original HS format,
* map to canonical code length,
* store HS version,
* support crosswalks between versions.

## 10.2 Rule normalization

Convert raw rule text into structured signals:

* wholly obtained
* value-added threshold
* max non-originating content
* tariff shift type
* specific process
* alternative pathways
* exceptions
* notes

## 10.3 Tariff normalization

Normalize:

* percentage format,
* year sequence,
* staging logic,
* category names,
* importer/exporter scope,
* official vs provisional flags.

## 10.4 Status normalization

Pattern-match and label:

* pending agreement
* subject to review
* provisional application
* in force from
* until finalization
* phased reduction
* excluded line
* sensitive product

## 10.5 Evidence normalization

Map textual requirements into standard evidence types and verification questions.

---

# 11) Chunking design

Do not use a single chunking rule.

## 11.1 Legal chunking

Chunk at:

* article,
* paragraph,
* subparagraph,
* proviso,
* footnote.

Metadata:

* `article_ref`
* `annex_ref`
* `appendix_ref`
* `page_start`
* `page_end`
* `topic_labels`
* `authority_tier`

## 11.2 Rule chunking

Primary object should be structured row extraction.
Also produce supporting retrieval chunks:

* row text,
* surrounding note text,
* adjacent explanatory text.

## 11.3 Tariff chunking

Primary object should be structured row extraction plus rate-by-year expansion.
Support with explanatory note chunks.

## 11.4 Operational chunking

For guidance and notices, chunk by:

* requirement block,
* procedure step,
* verification block,
* implementation clause.

---

# 12) Retrieval design

This system should use **router-based retrieval**, not general search first.

## 12.1 Query classifier

Classify user query into:

* rule_lookup
* tariff_query
* legal_qa
* transition_analysis
* eligibility_assessment
* evidence_readiness
* officer_verification
* policy_analytics
* counterfactual_query

## 12.2 Routing rules

### A. Rule lookup

Route to:

1. `psr_rule`
2. `psr_rule_component`
3. `psr_status_event`
4. supporting legal chunk index

### B. Tariff query

Route to:

1. `corridor_tariff_view`
2. `tariff_schedule_line`
3. `rate_by_year`
4. supporting schedule note chunks

### C. Legal Q&A

Route to:

1. `legal_provision`
2. chunk index
3. guidance layer if needed

### D. Transition analysis

Route to:

1. `status_assertion`
2. `transition_clause`
3. `psr_status_event`
4. tariff schedule status data
5. negotiation / decision chunks

### E. Eligibility assessment

Route to:

1. rule tables
2. evidence requirements
3. case facts
4. verification logic
5. supporting legal provisions

### F. Evidence readiness

Route to:

1. `evidence_requirement`
2. `document_readiness_template`
3. legal provisions
4. officer verification questions

---

# 13) Decision-support engine design

This is the main upgrade over plain RAG.

## 13.1 Eligibility engine

Inputs:

* HS code
* exporter state
* importer state
* BOM / input origins
* production steps
* ex-works value
* non-originating content
* available evidence

Outputs:

* likely qualifying pathway
* likely non-qualifying pathway
* confidence
* rule component match breakdown
* evidence sufficiency score

## 13.2 Failure mode analyzer

Outputs:

* tariff shift not achieved
* threshold not met
* missing documentary proof
* ambiguous cumulation basis
* schedule not operational
* pending rule exposure
* valuation evidence weak

## 13.3 Counterfactual advisor

Inputs:

* case facts

Outputs:

* “if local content rises by X”
* “if input Y is sourced intra-AfCFTA”
* “if process step Z occurs domestically”
* projected qualification effect

## 13.4 Evidence readiness engine

Outputs:

* required document pack
* optional support docs
* missing items
* officer likely questions
* weak spots

## 13.5 Corridor intelligence engine

Outputs:

* current schedule maturity
* transition exposure
* documentary burden
* likely scrutiny level
* tariff benefit profile

---

# 14) Ranking policy

## 14.1 Source ranking

Authority order:

1. binding legal text
2. official schedule
3. official notice / directive
4. operational guidance
5. support guidance
6. analytic enrichment

## 14.2 Structured-over-unstructured rule

For queries answerable from structured data:

* structured record must dominate.
* narrative chunk search is supporting evidence only.

## 14.3 Status-aware rank penalties

Penalize:

* superseded documents,
* outdated provisional sources,
* ambiguous status documents.

Boost:

* latest in-force sources,
* latest status decisions,
* documents with explicit effective dates.

---

# 15) Output contracts by use case

## 15.1 Rule lookup response

Return:

* HS code
* description
* exact rule text
* normalized tags
* threshold
* status
* citation anchor
* related legal notes

## 15.2 Tariff query response

Return:

* exporter
* importer
* year
* MFN base
* current preferential rate
* target year
* category
* schedule status
* citation anchor

## 15.3 Legal Q&A response

Return:

* direct answer
* quoted legal text
* citations
* related provisions
* operational note if relevant

## 15.4 Transition analysis response

Return:

* pending items
* phased items
* transitional clauses
* source references
* implications

## 15.5 Eligibility assessment response

Return:

* likely eligible / not eligible / uncertain
* pathway match
* failure points
* confidence
* required missing evidence
* legal basis

## 15.6 Evidence readiness response

Return:

* required docs
* conditional docs
* missing docs
* likely officer questions
* review risk summary

---

# 16) Evaluation framework

You need both **retrieval evaluation** and **decision evaluation**.

## 16.1 Gold datasets

Create separate benchmark sets:

* 75 rule lookups
* 75 tariff corridor queries
* 75 legal Q&A prompts
* 50 transition analysis prompts
* 50 eligibility cases
* 50 evidence-readiness cases
* 30 counterfactual scenarios

## 16.2 Evaluation dimensions

### Retrieval metrics

* precision@k
* recall@k
* citation correctness
* authority-tier correctness
* status-source correctness

### Structured-answer metrics

* HS code match accuracy
* tariff rate accuracy
* target year accuracy
* status label accuracy
* threshold extraction accuracy

### Decision-support metrics

* eligibility outcome accuracy
* failure mode identification accuracy
* evidence checklist completeness
* counterfactual consistency
* false-confidence rate

## 16.3 Critical failure metrics

Track these explicitly:

* hallucinated rule text
* hallucinated tariff years
* wrong status flag
* wrong source precedence
* missing or wrong citation
* overconfident answer on incomplete corpus

---

# 17) QA and validation pipeline

## 17.1 Structural checks

* valid page references
* valid HS formats
* no duplicate primary entities
* year values parse correctly
* no broken foreign keys

## 17.2 Legal fidelity checks

* verbatim text matches source
* citations resolve correctly
* extracted thresholds match source row
* transition clauses are not paraphrased as settled law

## 17.3 Decision QA

* failure modes align with rule logic
* evidence requirements align with cited provisions
* counterfactual outputs do not contradict rule structure
* “not enough data” is used where appropriate

## 17.4 Regression testing

Re-run full benchmark whenever:

* a new source version is ingested,
* parser logic changes,
* normalization rules change,
* retrieval routing changes,
* scoring model changes.

---

# 18) Governance model

This system needs strong governance because it is quasi-legal and quasi-operational.

## 18.1 Governance principles

* provenance first
* legal text never overwritten
* status explicit, never assumed
* structured record preferred where available
* model explains uncertainty
* every decision trace is inspectable

## 18.2 Human review layers

### Legal content review

Review:

* authority classification
* topic mapping
* status interpretation
* cross-reference accuracy

### Data engineering review

Review:

* extraction quality
* normalization logic
* schedule expansion logic
* version diffs

### Product review

Review:

* user-mode outputs
* confidence labels
* refusal behavior
* escalation behavior

## 18.3 Change control

Any update to:

* source ranking,
* status logic,
* rule parsing,
* eligibility reasoning,
* evidence mapping

should require:

* version note,
* regression pass,
* reviewer signoff.

## 18.4 Auditability requirements

For every answer, preserve:

* query
* router decision
* sources retrieved
* structured entities used
* final citations
* confidence
* decision trace

---

# 19) Security and policy controls

Even though this is not highly sensitive in the classic sense, you should still control:

* access to raw source updates,
* edit rights on structured rules,
* ability to mark a rule or schedule “current,”
* case data access if users upload commercial info,
* audit logging for officer-mode case handling.

If exporters upload BOMs or cost data, isolate case data from the shared knowledge layer.

---

# 20) Deployment stack recommendation

## 20.1 Storage

* object storage for raw sources
* PostgreSQL for relational core
* pgvector for embeddings
* Postgres full-text or OpenSearch for lexical retrieval

## 20.2 Services

* ingestion worker
* parser worker
* normalization worker
* decision engine service
* retrieval API
* alerting service
* admin governance service

## 20.3 Interfaces

* officer console
* analyst dashboard
* exporter wizard
* internal batch job runner

---

# 21) Implementation phases

## Phase 1 — Corpus and provenance

Deliverables:

* source registry
* source ingestion pipeline
* document classification
* checksum and version control

## Phase 2 — Legal and rules ingestion

Deliverables:

* legal chunk store
* `legal_provision`
* `psr_rule`
* `psr_rule_component`
* citation anchor system

## Phase 3 — Tariff ingestion

Deliverables:

* tariff schedule parsing
* yearly rate expansion
* corridor materialization
* schedule status tagging

## Phase 4 — Status intelligence

Deliverables:

* `status_assertion`
* `transition_clause`
* change log and alerts
* pending / provisional logic

## Phase 5 — Evidence and verification

Deliverables:

* `evidence_requirement`
* `verification_question`
* document readiness templates
* officer-mode checklist generation

## Phase 6 — Case assessment engine

Deliverables:

* case schema
* eligibility engine
* failure analyzer
* counterfactual engine

## Phase 7 — Analytics and scoring

Deliverables:

* corridor profile
* restrictiveness index
* policy dashboards
* analyst-mode outputs

## Phase 8 — Evaluation and hardening

Deliverables:

* benchmark suite
* confidence policy
* governance workflow
* regression testing
* admin audit tools

---

# 22) What makes this build spec different from the earlier one

The earlier blueprint focused on:

* ingest,
* chunking,
* structured legal retrieval,
* tariff and rule lookup.

This updated version adds the real product moat:

### Added layers

* evidence schema
* case-assessment schema
* failure modes
* counterfactual scenarios
* corridor maturity intelligence
* role-specific output contracts
* governance around quasi-adjudicative outputs
* change detection and alerts
* restrictiveness scoring

That is the difference between:

**“AfCFTA RAG”**

and

**“AfCFTA adjudication-grade intelligence system.”**

---

# 23) Recommended next build step

The best next step is to define the **exact SQL schema** and API contract for these tables first:

* `source_registry`
* `legal_provision`
* `psr_rule`
* `psr_rule_component`
* `tariff_schedule_header`
* `tariff_schedule_line`
* `tariff_schedule_rate_by_year`
* `status_assertion`
* `evidence_requirement`
* `case_assessment`

That will force the product into a concrete system boundary and expose where the logic is still fuzzy.
