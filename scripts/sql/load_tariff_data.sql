-- Step 2 of the AIS Quick Slice build: load staged tariff CSVs into the tariff
-- tables in FK dependency order. Step 1 (hs6_product) must already be loaded.
-- Note: the extracted CSVs are present under data/staged/tariffs/.

\echo 'Step 2: Loading source_registry from data/staged/tariffs/source_registry.csv'
\COPY source_registry(
  source_id,
  title,
  short_title,
  source_group,
  source_type,
  authority_tier,
  issuing_body,
  jurisdiction_scope,
  country_code,
  customs_union_code,
  publication_date,
  effective_date,
  expiry_date,
  version_label,
  status,
  language,
  hs_version,
  file_path,
  mime_type,
  source_url,
  checksum_sha256,
  citation_preferred,
  notes,
  created_at,
  updated_at
)
FROM 'data/staged/tariffs/source_registry.csv' WITH (FORMAT csv, HEADER true);

\echo 'Step 2: Loading tariff_schedule_header from data/staged/tariffs/tariff_schedule_header.csv'
\COPY tariff_schedule_header(
  schedule_id,
  source_id,
  importing_state,
  exporting_scope,
  schedule_status,
  publication_date,
  effective_date,
  expiry_date,
  hs_version,
  category_system,
  notes,
  created_at,
  updated_at
)
FROM 'data/staged/tariffs/tariff_schedule_header.csv' WITH (FORMAT csv, HEADER true);

\echo 'Step 2: Loading tariff_schedule_line from data/staged/tariffs/tariff_schedule_line.csv'
\COPY tariff_schedule_line(
  schedule_line_id,
  schedule_id,
  hs_code,
  product_description,
  tariff_category,
  mfn_base_rate,
  base_year,
  target_rate,
  target_year,
  staging_type,
  page_ref,
  table_ref,
  row_ref,
  created_at,
  updated_at
)
FROM 'data/staged/tariffs/tariff_schedule_line.csv' WITH (FORMAT csv, HEADER true);

\echo 'Step 2: Loading tariff_schedule_rate_by_year from data/staged/tariffs/tariff_schedule_rate_by_year.csv'
\COPY tariff_schedule_rate_by_year(
  year_rate_id,
  schedule_line_id,
  calendar_year,
  preferential_rate,
  rate_status,
  source_id,
  page_ref,
  created_at,
  updated_at
)
FROM 'data/staged/tariffs/tariff_schedule_rate_by_year.csv' WITH (FORMAT csv, HEADER true);

\echo 'Validation 1: Row counts in loaded tariff tables'
SELECT 'source_registry' AS table_name, COUNT(*) AS row_count
FROM source_registry
UNION ALL
SELECT 'tariff_schedule_header' AS table_name, COUNT(*) AS row_count
FROM tariff_schedule_header
UNION ALL
SELECT 'tariff_schedule_line' AS table_name, COUNT(*) AS row_count
FROM tariff_schedule_line
UNION ALL
SELECT 'tariff_schedule_rate_by_year' AS table_name, COUNT(*) AS row_count
FROM tariff_schedule_rate_by_year;

\echo 'Validation 2: tariff_schedule_header rows'
SELECT schedule_id, importing_state, exporting_scope, schedule_status
FROM tariff_schedule_header
ORDER BY importing_state, exporting_scope, schedule_id;

\echo 'Validation 3: tariff_schedule_line counts per corridor'
SELECT h.importing_state, h.exporting_scope, COUNT(l.schedule_line_id) AS line_count
FROM tariff_schedule_header h
JOIN tariff_schedule_line l ON l.schedule_id = h.schedule_id
GROUP BY h.importing_state, h.exporting_scope
ORDER BY h.importing_state, h.exporting_scope;

\echo 'Validation 4: Phase-down for hs_code LIKE 010121%'
SELECT
  h.importing_state,
  h.exporting_scope,
  l.hs_code,
  l.product_description,
  l.mfn_base_rate,
  r.calendar_year,
  r.preferential_rate,
  r.rate_status
FROM tariff_schedule_line l
JOIN tariff_schedule_header h ON h.schedule_id = l.schedule_id
JOIN tariff_schedule_rate_by_year r ON r.schedule_line_id = l.schedule_line_id
WHERE l.hs_code LIKE '010121%'
ORDER BY h.importing_state, h.exporting_scope, l.hs_code, r.calendar_year;