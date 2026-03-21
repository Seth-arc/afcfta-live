1) Canonical corpus you absolutely need

These are the documents I would treat as authoritative for answering users.

A. Core AfCFTA legal texts

Agreement Establishing the AfCFTA

Protocol on Trade in Goods

Compiled Annexes to the AfCFTA Agreement, especially:

Annex 1: Schedules of Tariff Concessions

Annex 2: Rules of Origin

Annex 3: Customs Cooperation and Mutual Administrative Assistance

Annex 4: Trade Facilitation

Annex 5: Non-Tariff Barriers

Annex 8: Transit

Annex 10: Trade Remedies
The WCO’s AfCFTA implementation guide explicitly lays out this Protocol-on-Trade-in-Goods annex stack, and the compiled annexes are where the operative legal text sits.

B. Rules of Origin source set

Annex 2 on Rules of Origin

Appendix I to Annex 2 — Certificate of Origin specimen

Appendix II to Annex 2 — Origin declaration text

Appendix III to Annex 2 — Supplier declaration

Appendix IV to Annex 2 — Product-Specific Rules (PSRs) by HS chapter/heading/subheading
This is the core source for your Rule Lookup use case. The compiled annexes state that goods listed in Appendix IV qualify only if they satisfy the specific rules set out there, and the AfCFTA Rules of Origin Manual confirms Appendix IV contains the hybrid/general plus product-specific rules by HS structure.

C. Tariff schedule source set

AfCFTA e-Tariff Book dataset/export

State Party Schedules of Tariff Concessions, including:

national or customs-union schedules

provisional schedules where applicable

gazetted/domesticated versions where published

Ministerial directives or decisions on provisional schedules / application of tariff concessions
The AfCFTA Secretariat and WCO describe the e-Tariff Book as the key operational source for tariff concessions and rules-of-origin access; tralac also notes that provisional schedules are available there and used under the Guided Trade Initiative.

2) Documents needed for each use case
01 — Rule Lookup

For “query HS code and return exact Appendix IV rule, tags, thresholds, status, verbatim legal text” you need:

Annex 2 on Rules of Origin

Appendix IV to Annex 2

Any updated agreed PSR compilations / corrigenda / amendment decisions

AfCFTA Rules of Origin Manual for interpretive mapping and implementation logic

WCO Practical Guide for the Implementation of the AfCFTA Rules of Origin for operational interpretation, but not as the source of law
The legal rule comes from Annex 2 + Appendix IV; the manual and WCO guide help normalize concepts like WO, value-added, non-originating material content, CTH/CTSH, and specific processes. The WCO guide is explicit that it does not replace the legal texts.

You should also ingest:

HS nomenclature reference table for the exact HS version used by AfCFTA source documents

Crosswalk tables if some schedules or rule sets use different HS vintages

02 — Schedule Query

For “preferential tariff between any two member states, phase-in timeline, MFN baseline, current rate, target year” you need:

Annex 1: Schedules of Tariff Concessions

AfCFTA e-Tariff Book data

Each State Party’s tariff offer / schedule

Provisional schedule directives

National gazettes or customs notices implementing the AfCFTA rates

MFN tariff baseline source for each importing state, ideally the baseline embedded in the schedule and, where needed, the national tariff book or customs tariff reference
The e-Tariff Book is specifically designed to surface tariff concessions, and commentary around it explains these schedules are year-by-year reductions from the MFN rate toward the liberalised rate.

03 — Policy Q&A

For “valuation methodology, de minimis, proof of origin, cumulation, verification procedures” you need:

Annex 2 on Rules of Origin

Appendices I–III under Annex 2

Annex 3: Customs Cooperation and Mutual Administrative Assistance

Protocol on Trade in Goods

Guidelines, manuals, and implementation notes issued by AfCFTA Secretariat

WCO Practical Guide

National implementing regulations / customs circulars for state-level operational differences
This is where your citation discipline matters: the answer engine should prefer the legal text first, then use the manuals only to explain the legal provision. The WCO guide directly references verification, penalties, appendices, and institutional arrangements around Annex 2.

04 — Transition Analysis

For “which PSRs are pending, which tariff lines are phased, where transition language appears” you need:

Latest agreed Appendix IV / PSR compilation

Negotiation status tables or official lists of pending RoO

Council of Ministers decisions / directives / communiqués on unresolved rules

Tariff schedules with phase-down categories

Modalities documents for tariff liberalisation

Guided Trade Initiative implementation notes, where they identify what can and cannot trade because rules are finalised or pending
Public AfCFTA commentary still notes that not all rules of origin and tariff negotiations are completed; tralac’s December 2025 summary says agreed RoO cover 92.4% of tariff lines, and earlier implementation material notes some products remain outside trade because rules are not yet agreed.

3) The actual ingest list I would prepare

I would organize the ingest into six folders.

Folder 1 — 01_primary_law

Agreement Establishing the AfCFTA

Protocol on Trade in Goods

Compiled Annexes

Any official corrigenda or amendments

Council / Assembly decisions that change interpretation or application

Folder 2 — 02_rules_of_origin

Annex 2 full text

Appendix I–IV

Agreed RoO compilations

Pending-RoO status lists

RoO amendment decisions

AfCFTA Rules of Origin Manual

WCO Practical Guide

Folder 3 — 03_tariff_schedules

Annex 1

e-Tariff Book export

State Party schedules

customs-union schedules where relevant

provisional schedules

gazetted domestic schedules

schedule update notices

Folder 4 — 04_operational_customs

Annex 3

Customs cooperation guidance

certificate issuance guidance

verification procedures

national customs circulars

proof-of-origin administrative templates

Folder 5 — 05_status_and_transition

negotiation status reports

ministerial directives

committee communiqués

GTI notes

implementation bulletins

change logs showing when a rule moved from pending to agreed

Folder 6 — 06_reference_data

HS nomenclature tables

HS-version crosswalks

ISO country codes / AfCFTA State Party codes

tariff category flags: Category A / sensitive / excluded

LDC vs non-LDC treatment flags

calendar table for phase-in years

4) What you should extract from each document

Do not rely on vector search alone. Extract structured fields.

For Appendix IV / PSRs

Per tariff line:

HS code

HS version

chapter / heading / subheading

legal rule text

normalized rule tags: WO, VA, VNM, CTH, CTSH, PROCESS

threshold percentage

threshold basis

exceptions / notes

rule status: agreed, pending, partially agreed

source doc

page

paragraph / table row

effective date

superseded-by

For tariff schedules

Per corridor and tariff line:

exporter state

importer state

HS code

MFN base rate

category

start year

phase-down schedule by year

current preferential rate

target liberalised rate

target year

schedule status: provisional, approved, gazetted

source doc

page / table reference

For legal Q&A provisions

Per provision:

topic label: valuation, cumulation, de minimis, proof of origin, verification, penalties

instrument

article / annex / appendix / page

verbatim text

short machine summary

cross-references to related articles

jurisdictional applicability note if national implementation varies

5) Minimum viable corpus vs production-grade corpus
Minimum viable

If you want a serious v1:

Agreement

Protocol on Trade in Goods

Compiled Annexes

Annex 2 + Appendix IV

AfCFTA Rules of Origin Manual

WCO Practical Guide

e-Tariff Book export

available State Party tariff schedules

latest pending/agreed RoO status list

Production-grade

For a model meant for competent authorities and policy analysts:

everything above, plus

national gazettes / customs notices

ministerial decisions

negotiation status documents

version history / amendment tracking

HS crosswalks

national customs procedures for certificate issuance and verification

6) My recommendation on source priority

Use a strict ranking:

Tier 1 — binding / canonical

Agreement

Protocol on Trade in Goods

Annexes

Appendices

official schedules

official ministerial decisions / directives

Tier 2 — authoritative operational

AfCFTA Secretariat manuals

e-Tariff Book data

official customs notices

gazetted schedules

Tier 3 — interpretive support

WCO practical guide

tralac summaries

implementation explainers

That ranking matters because the WCO guide itself says it is a guide and does not replace the AfCFTA legal documents.

7) One thing most people miss

You do not just need documents. You need three parallel stores:

A legal text store for verbatim citation and page retrieval

A structured PSR database for HS-based rule lookup

A structured tariff schedule database for corridor/time-based tariff answers

Without the structured stores, your model will hallucinate rule status, percentages, and tariff years.

8) Best-practice additions

I would also ingest:

a change log of every document version

effective date metadata

status flags for “pending,” “provisional,” “agreed,” “gazetted,” “superseded”

member-state readiness metadata for whether a corridor is operational in practice

That last point matters because public AfCFTA materials still note incomplete tariff offers and incomplete RoO coverage, so a trustworthy system must know when to answer “not yet operational” rather than pretending certainty.