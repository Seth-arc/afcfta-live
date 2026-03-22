-- Final Quick Slice validation checklist from AIS_v01_Quick_Slice_Handbook.md
-- Section 8. Run after Steps 1-6 have completed.

\echo 'Check 1: hs6_product row count (expect 1000+)'
SELECT
  CASE WHEN COUNT(*) >= 1000 THEN 'PASS' ELSE 'FAIL' END AS hs6_check,
  COUNT(*) AS actual_count
FROM hs6_product;

\echo 'Check 2: source_registry row count (expect 2+)'
SELECT
  CASE WHEN COUNT(*) >= 2 THEN 'PASS' ELSE 'FAIL' END AS source_registry_check,
  COUNT(*) AS actual_count
FROM source_registry;

\echo 'Check 3: tariff_schedule_header rows with importing_state and exporting_scope'
SELECT
  schedule_id,
  importing_state,
  exporting_scope,
  schedule_status,
  hs_version
FROM tariff_schedule_header
ORDER BY importing_state, exporting_scope, schedule_id;

\echo 'Check 4: tariff_schedule_line row count (expect 5000+)'
SELECT
  CASE WHEN COUNT(*) >= 5000 THEN 'PASS' ELSE 'FAIL' END AS tariff_line_check,
  COUNT(*) AS actual_count
FROM tariff_schedule_line;

\echo 'Check 5: tariff_schedule_rate_by_year row count (expect 30000+)'
SELECT
  CASE WHEN COUNT(*) >= 30000 THEN 'PASS' ELSE 'FAIL' END AS tariff_rate_year_check,
  COUNT(*) AS actual_count
FROM tariff_schedule_rate_by_year;

\echo 'Check 6: psr_rule row count (expect 10-15)'
SELECT
  CASE WHEN COUNT(*) BETWEEN 10 AND 15 THEN 'PASS' ELSE 'FAIL' END AS psr_rule_check,
  COUNT(*) AS actual_count
FROM psr_rule;

\echo 'Check 7: psr_rule_component row count'
SELECT COUNT(*) AS psr_rule_component_count
FROM psr_rule_component;

\echo 'Check 8: eligibility_rule_pathway row count'
SELECT COUNT(*) AS eligibility_rule_pathway_count
FROM eligibility_rule_pathway;

\echo 'Check 9: hs6_psr_applicability distinct hs6_id count'
SELECT COUNT(DISTINCT hs6_id) AS distinct_hs6_covered
FROM hs6_psr_applicability;

\echo 'Check 10: status_assertion row count'
SELECT COUNT(*) AS status_assertion_count
FROM status_assertion;

\echo 'Check 11: evidence_requirement row count'
SELECT COUNT(*) AS evidence_requirement_count
FROM evidence_requirement;

\echo 'Check 12: psr_rule breakdown by rule_status'
SELECT
  rule_status,
  COUNT(*) AS rule_count
FROM psr_rule
GROUP BY rule_status
ORDER BY rule_status;

\echo 'Check 13: pathway count for heading 1806 (should be 2 - CTH and VNM)'
SELECT
  CASE WHEN COUNT(*) = 2 THEN 'PASS' ELSE 'FAIL' END AS heading_1806_pathway_check,
  COUNT(*) AS actual_count
FROM eligibility_rule_pathway erp
JOIN psr_rule pr ON pr.psr_id = erp.psr_id
WHERE pr.hs_code = '1806';

SELECT
  pr.hs_code,
  erp.pathway_code,
  erp.pathway_label,
  erp.priority_rank
FROM eligibility_rule_pathway erp
JOIN psr_rule pr ON pr.psr_id = erp.psr_id
WHERE pr.hs_code = '1806'
ORDER BY erp.priority_rank;

\echo 'Check 14: tariff lines with no HS6 backbone match (orphan check)'
SELECT
  CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS tariff_orphan_check,
  COUNT(*) AS orphan_count
FROM tariff_schedule_line tsl
LEFT JOIN hs6_product hp
  ON hp.hs_version = 'HS2017'
 AND hp.hs6_code = LEFT(tsl.hs_code, 6)
WHERE hp.hs6_id IS NULL;

SELECT
  tsl.schedule_line_id,
  tsl.schedule_id,
  tsl.hs_code,
  LEFT(tsl.hs_code, 6) AS hs6_code,
  tsl.product_description
FROM tariff_schedule_line tsl
LEFT JOIN hs6_product hp
  ON hp.hs_version = 'HS2017'
 AND hp.hs6_code = LEFT(tsl.hs_code, 6)
WHERE hp.hs6_id IS NULL
ORDER BY tsl.hs_code, tsl.schedule_line_id;