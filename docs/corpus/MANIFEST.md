# Corpus Manifest

Inventory of files currently present in `rework/corpus`.

## Corpus Summary

| Category | Files |
|---|---:|
| Root | 3 |
| `00_data_sources` | 1 |
| `01_primary_law` | 12 |
| `02_rules_of_origin` | 9 |
| `03_tariff_schedules` | 3 |
| `04_operational_customs` | 5 |
| `05_status_and_transition` | 1 |
| `06_reference_data` | 30 |
| `07_phase_2_protocols` | 7 |
| **Total** | **71** |

## Root

| Category | Filename | Ext | Duplicate | Purpose |
|---|---|---|---|---|
| Root | `MANIFEST.md` | `md` | No | Generated inventory of corpus files and metadata |
| Root | `README.md` | `md` | No | Corpus organization guide, ingestion order, and versioning |
| Root | `INGESTION_LOG.md` | `md` | No | Timestamped record of data source ingestions and transformations |

## 00_data_sources

| Category | Filename | Ext | Source | API/Endpoint | Ingestion Script | Likely use |
|---|---|---|---|---|---|---|
| `00_data_sources` | `extract_unctad_afcfta.py` | `py` | UNCTAD | `https://afcfta-api.unctad.org/tariffseliminationnew!{reporter}&{partner}&{product}` | Automated extraction | L3 tariff_schedule tables (header, line, rate_by_year) |

## 01_primary_law

| Category | Filename | Ext | Duplicate | Likely use |
|---|---|---|---|---|
| `01_primary_law` | `36437-ax-Compiled-Annexes_AfCFTA_Agreement_English.pdf` | `pdf` | No | Full annex compilation |
| `01_primary_law` | `36437-treaty-consolidated_text_on_cfta_-_en.pdf` | `pdf` | No | Consolidated AfCFTA treaty text |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-1-26_Part I-Part IV.pdf` | `pdf` | No | Main agreement body |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-37-44_Annex_3_Customs_Cooperation.pdf` | `pdf` | Yes | Customs cooperation annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-45-61_Annex_4_Trade_Facilitation.pdf` | `pdf` | Yes | Trade facilitation annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-62-74_Annex_5_Non_Tariff_Barriers.pdf` | `pdf` | No | Non-tariff barriers annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-75-82_Annex_6_Technical_Barriers_to_Trade.pdf` | `pdf` | No | TBT annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-83-91_Annex_7_Sanitary_and_Phytosanitary.pdf` | `pdf` | No | SPS annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-92-110_Annex_8_Transit.pdf` | `pdf` | No | Transit annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-111-117_Annex_9_Trade_Remedies.pdf` | `pdf` | No | Trade remedies annex |
| `01_primary_law` | `Compiled-Annexes_AfCFTA_Agreement_English-118-124_Dispute_Settlement_Annexes.pdf` | `pdf` | No | Dispute settlement annexes |
| `01_primary_law` | `EN-AfCFTA-PROTOCOL-ON-TRADE-IN-GOODS-ocr.pdf` | `pdf` | No | OCR protocol text for trade in goods |

## 02_rules_of_origin

| Category | Filename | Ext | Duplicate | Likely use |
|---|---|---|---|---|
| `02_rules_of_origin` | `AfCFTA RULES OF ORIGIN MANUAL.pdf` | `pdf` | No | Operational rules-of-origin manual |
| `02_rules_of_origin` | `afcfta_state_parties_reference_2025.csv` | `csv` | No | State parties reference data |
| `02_rules_of_origin` | `Compiled-Annexes_AfCFTA_Agreement_English-27-31_Appendix I.pdf` | `pdf` | Yes | Appendix I certificate of origin reference |
| `02_rules_of_origin` | `Compiled-Annexes_AfCFTA_Agreement_English-32_Appendix II.pdf` | `pdf` | Yes | Appendix II origin declaration reference |
| `02_rules_of_origin` | `Compiled-Annexes_AfCFTA_Agreement_English-33-35_Appendix III.pdf` | `pdf` | Yes | Appendix III supplier declaration reference |
| `02_rules_of_origin` | `Compiled-Annexes_AfCFTA_Agreement_English-36-124.pdf` | `pdf` | No | Annex compilation including RoO sections |
| `02_rules_of_origin` | `EN-APPENDIX-IV-AS-AT-COM-12-DECEMBER-2023.pdf` | `pdf` | No | Appendix IV product-specific rules |
| `02_rules_of_origin` | `origin_compendium.pdf` | `pdf` | No | Origin reference compendium |
| `02_rules_of_origin` | `wco_practical-guide-for-the-implementation-of-afcfta-roo_en.pdf` | `pdf` | No | WCO practical implementation guide |

## 03_tariff_schedules

| Category | Filename | Ext | Source | Duplicate | Likely use |
|---|---|---|---|---|---|
| `03_tariff_schedules` | `EN - AfCFTA e-Tariff Book - User Guide.pdf` | `pdf` | UNCTAD | No | Tariff book usage guide |
| `03_tariff_schedules` | `Status of AfCFTA ratifications 20-01-2026.pdf` | `pdf` | AU | Yes | Ratification status sheet used with schedule context |
| `03_tariff_schedules` | `tariff_schedule_extraction_metadata.json` | `json` | UNCTAD API | No | Provenance record of automated UNCTAD extraction run |

## 04_operational_customs

| Category | Filename | Ext | Duplicate | Likely use |
|---|---|---|---|---|
| `04_operational_customs` | `Compiled-Annexes_AfCFTA_Agreement_English-27-31_Appendix I.pdf` | `pdf` | Yes | Appendix I reused for customs operations |
| `04_operational_customs` | `Compiled-Annexes_AfCFTA_Agreement_English-37-44_Annex_3_Customs_Cooperation.pdf` | `pdf` | Yes | Customs cooperation reference |
| `04_operational_customs` | `Compiled-Annexes_AfCFTA_Agreement_English-45-61_Annex_4_Trade_Facilitation.pdf` | `pdf` | Yes | Trade facilitation reference |
| `04_operational_customs` | `guidelines-on-certification.pdf` | `pdf` | No | Certification guidance |
| `04_operational_customs` | `guideWcoUPUCustomsEn.pdf` | `pdf` | No | WCO and UPU customs guide |

## 05_status_and_transition

| Category | Filename | Ext | Duplicate | Likely use |
|---|---|---|---|---|
| `05_status_and_transition` | `data-UcsVQ.csv` | `csv` | No | Status and transition dataset |

## 06_reference_data

| Category | Filename | Ext | Duplicate | Likely use |
|---|---|---|---|---|
| `06_reference_data` | `9 May_AfCFTA Booklet 13th Edition Updated May 2025.pdf` | `pdf` | No | AfCFTA reference booklet |
| `06_reference_data` | `AfCFTA Application of Provisional Schedules of Tariff Concessions Ministerial Directive 1_2021.pdf` | `pdf` | No | Ministerial directive on provisional schedules |
| `06_reference_data` | `AFCFTA Futures Report 2021 Which Value Chains for a Made in Africa Revolution.pdf` | `pdf` | No | Value-chain analysis report |
| `06_reference_data` | `AfCFTA Implementation Strategies Synthesis Report UNECA January 2024.pdf` | `pdf` | No | Implementation strategy synthesis |
| `06_reference_data` | `AfCFTA Ministerial Directive On the Implementation of State Parties Schedules of Specific Commitments (services) July 2022.pdf` | `pdf` | No | Services commitments directive |
| `06_reference_data` | `Assessing Regional Integration in Africa ARIA XI (UNECA, AU).pdf` | `pdf` | No | Regional integration assessment |
| `06_reference_data` | `AU Assembly Decision on the Progress Report on the AfCFTA February 2025.pdf` | `pdf` | No | AU Assembly decision |
| `06_reference_data` | `AU Executive Council Decision on the AfCFTA 13 February 2025.pdf` | `pdf` | No | Executive Council decision on AfCFTA progress |
| `06_reference_data` | `AU Executive Council Decision on the Report of the Implementation of the AfCFTA Secretariat February 2023.pdf` | `pdf` | No | Secretariat implementation decision |
| `06_reference_data` | `Code_Des_Douanes.pdf` | `pdf` | No | Customs code reference |
| `06_reference_data` | `Compiled-Annexes_AfCFTA_Agreement_English-27-31_Appendix I.pdf` | `pdf` | Yes | Appendix I reference copy |
| `06_reference_data` | `Compiled-Annexes_AfCFTA_Agreement_English-32_Appendix II.pdf` | `pdf` | Yes | Appendix II reference copy |
| `06_reference_data` | `Compiled-Annexes_AfCFTA_Agreement_English-33-35_Appendix III.pdf` | `pdf` | Yes | Appendix III reference copy |
| `06_reference_data` | `country_currency_registry.csv` | `csv` | No | Country and currency reference data |
| `06_reference_data` | `Economic Report on Africa 2023 UNECA.pdf` | `pdf` | No | UNECA economic report |
| `06_reference_data` | `Economic Report on Africa 2024 (UNECA).pdf` | `pdf` | No | UNECA economic report |
| `06_reference_data` | `Economic Report on Africa 2025 UNECA.pdf` | `pdf` | No | UNECA economic report focused on AfCFTA implementation |
| `06_reference_data` | `Factsheet Trading under the AfCFTA Cameroon March 2025 rev.pdf` | `pdf` | No | Cameroon trading factsheet |
| `06_reference_data` | `Factsheet Trading under the AfCFTA Nigeria updated February 2025.pdf` | `pdf` | No | Nigeria trading factsheet |
| `06_reference_data` | `Guide for Country Impact Assessments on AIDA and AfCFTA July 2024.pdf` | `pdf` | No | Country impact assessment guide |
| `06_reference_data` | `guide_de_procedures_des_exonerations_et_franchises_ivory coast.pdf` | `pdf` | No | Ivory Coast exemption procedures guide |
| `06_reference_data` | `Ministerial Regulations 1_2023 Treatment of Products from the SEZs of State Parties to the AfCFTA Agreement.pdf` | `pdf` | No | SEZ treatment regulations |
| `06_reference_data` | `Nigeria-AfCFTA-Achievements-2025.pdf` | `pdf` | No | Nigeria AfCFTA achievements note |
| `06_reference_data` | `Nigerian Customs-ACT-2023-1.pdf` | `pdf` | No | Nigerian Customs Act |
| `06_reference_data` | `Nigeria_e-Advanced Ruling Customs-Manual.pdf` | `pdf` | No | Nigeria advanced ruling manual |
| `06_reference_data` | `Nigeria_Import-and-Export-Procedure-Corrected_Final.pdf` | `pdf` | No | Nigeria import and export procedures |
| `06_reference_data` | `ordonance-phase-1-demantelement-tarifaire-signee_0.pdf` | `pdf` | No | Tariff dismantlement ordinance |
| `06_reference_data` | `Status of AfCFTA ratifications 20-01-2026.pdf` | `pdf` | Yes | Ratification status sheet |
| `06_reference_data` | `The African Continental Free Trade Area Economic and Distributional Effects World Bank 2020.pdf` | `pdf` | No | World Bank impact analysis |
| `06_reference_data` | `tralac Newsletter March 2024.pdf` | `pdf` | No | tralac newsletter reference |

## 07_phase_2_protocols

| Category | Filename | Ext | Duplicate | Likely use |
|---|---|---|---|---|
| `07_phase_2_protocols` | `14. JO N° 7164  DU  SAMEDI  23  FEVRIER  2019-vie-publique.pdf` | `pdf` | No | Gazette publication reference |
| `07_phase_2_protocols` | `annual-report-eu_wco-programme-2022-en.pdf` | `pdf` | No | EU-WCO annual report |
| `07_phase_2_protocols` | `ECOWAS AfCFTA Tariff Concession Schedule.xlsx` | `xlsx` | No | Tariff concession schedule spreadsheet |
| `07_phase_2_protocols` | `Protocol to the Agreement Establishing the African Continental Free Trade Area on Competition Policy.pdf` | `pdf` | No | Phase 2 competition protocol |
| `07_phase_2_protocols` | `Protocol to the Agreement Establishing the African Continental Free Trade Area on Digital Trade.pdf` | `pdf` | No | Phase 2 digital trade protocol |
| `07_phase_2_protocols` | `Protocol to the Agreement Establishing the African Continental Free Trade Area on Intellectual Property Rights.pdf` | `pdf` | No | Phase 2 IPR protocol |
| `07_phase_2_protocols` | `Protocol to the Agreement Establishing the African Continental Free Trade Area on Investment.pdf` | `pdf` | No | Phase 2 investment protocol |

## Duplicate Files

| Filename | Categories | Notes |
|---|---|---|
| `Compiled-Annexes_AfCFTA_Agreement_English-27-31_Appendix I.pdf` | `02_rules_of_origin`, `04_operational_customs`, `06_reference_data` | Certificate of origin forms — needed in multiple operational contexts |
| `Compiled-Annexes_AfCFTA_Agreement_English-32_Appendix II.pdf` | `02_rules_of_origin`, `06_reference_data` | Origin declarations — reference and operational |
| `Compiled-Annexes_AfCFTA_Agreement_English-33-35_Appendix III.pdf` | `02_rules_of_origin`, `06_reference_data` | Supplier declarations — reference and operational |
| `Compiled-Annexes_AfCFTA_Agreement_English-37-44_Annex_3_Customs_Cooperation.pdf` | `01_primary_law`, `04_operational_customs` | Foundational legal text and operational guidance |
| `Compiled-Annexes_AfCFTA_Agreement_English-45-61_Annex_4_Trade_Facilitation.pdf` | `01_primary_law`, `04_operational_customs` | Foundational legal text and operational guidance |
| `Status of AfCFTA ratifications 20-01-2026.pdf` | `03_tariff_schedules`, `06_reference_data` | Ratification status used to determine corridor operability |