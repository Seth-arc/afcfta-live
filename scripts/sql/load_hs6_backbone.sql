-- Step 1 of the AIS Quick Slice build: load the HS6 backbone CSV into hs6_product
-- and run validation queries to confirm the backbone loaded correctly.

\echo 'Step 1: Loading hs6_product from data/staged/hs6_product.csv'

\COPY hs6_product(hs6_id, hs_version, hs6_code, hs6_display, chapter, heading, description)
FROM 'data/staged/hs6_product.csv' WITH (FORMAT csv, HEADER true);

\echo 'Validation 1: Total hs6_product row count'
SELECT COUNT(*) AS hs6_product_count
FROM hs6_product;

\echo 'Validation 2: Spot check for HS6 codes 010121, 010129, 180100'
SELECT hs6_code, hs6_display, description
FROM hs6_product
WHERE hs6_code IN ('010121', '010129', '180100')
ORDER BY hs6_code;

\echo 'Validation 3: Duplicate check on (hs_version, hs6_code)'
SELECT hs_version, hs6_code, COUNT(*) AS duplicate_count
FROM hs6_product
GROUP BY hs_version, hs6_code
HAVING COUNT(*) > 1
ORDER BY hs_version, hs6_code;

\echo 'Validation 4: Distinct chapters loaded'
SELECT DISTINCT chapter
FROM hs6_product
ORDER BY chapter;