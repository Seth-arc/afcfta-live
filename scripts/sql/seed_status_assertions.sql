-- Step 4 of the AIS Quick Slice build: seed manual status_assertion rows for
-- the demo corridor and pending PSR status overlays. This script is idempotent
-- via NOT EXISTS checks because status_assertion has no unique constraint.

\echo 'Step 4: Seeding status assertions for GHA:CMR, CMR:GHA, and pending motor vehicles PSR'

-- Verify status_type values are drawn from status_type_enum.
-- Required values used here: in_force, pending.

INSERT INTO status_assertion (
  status_assertion_id,
  source_id,
  entity_type,
  entity_key,
  status_type,
  status_text_verbatim,
  effective_from,
  confidence_score
)
SELECT
  uuid_generate_v4(),
  'a0000000-0000-0000-0000-000000000001',
  'corridor',
  'GHA:CMR',
  'in_force',
  'Ghana-Cameroon trade corridor under AfCFTA preferential treatment.',
  DATE '2021-01-01',
  0.800
WHERE NOT EXISTS (
  SELECT 1
  FROM status_assertion sa
  WHERE sa.source_id = 'a0000000-0000-0000-0000-000000000001'
    AND sa.entity_type = 'corridor'
    AND sa.entity_key = 'GHA:CMR'
    AND sa.status_type = 'in_force'
    AND sa.effective_from = DATE '2021-01-01'
);

INSERT INTO status_assertion (
  status_assertion_id,
  source_id,
  entity_type,
  entity_key,
  status_type,
  status_text_verbatim,
  effective_from,
  confidence_score
)
SELECT
  uuid_generate_v4(),
  'a0000000-0000-0000-0000-000000000001',
  'corridor',
  'CMR:GHA',
  'in_force',
  'Cameroon-Ghana trade corridor under AfCFTA preferential treatment.',
  DATE '2021-01-01',
  0.800
WHERE NOT EXISTS (
  SELECT 1
  FROM status_assertion sa
  WHERE sa.source_id = 'a0000000-0000-0000-0000-000000000001'
    AND sa.entity_type = 'corridor'
    AND sa.entity_key = 'CMR:GHA'
    AND sa.status_type = 'in_force'
    AND sa.effective_from = DATE '2021-01-01'
);

INSERT INTO status_assertion (
  status_assertion_id,
  source_id,
  entity_type,
  entity_key,
  status_type,
  status_text_verbatim,
  confidence_score
)
SELECT
  uuid_generate_v4(),
  'a0000000-0000-0000-0000-000000000001',
  'psr',
  'b0000000-0000-0000-0000-000000000015',
  'pending',
  'Motor vehicles PSR (HS 87) - yet to be agreed by State Parties.',
  0.900
WHERE NOT EXISTS (
  SELECT 1
  FROM status_assertion sa
  WHERE sa.source_id = 'a0000000-0000-0000-0000-000000000001'
    AND sa.entity_type = 'psr'
    AND sa.entity_key = 'b0000000-0000-0000-0000-000000000015'
    AND sa.status_type = 'pending'
);

\echo 'Validation: status_assertion rows seeded by this script'
SELECT entity_type, entity_key, status_type, effective_from, confidence_score
FROM status_assertion
WHERE source_id = 'a0000000-0000-0000-0000-000000000001'
  AND (
    (entity_type = 'corridor' AND entity_key IN ('GHA:CMR', 'CMR:GHA'))
    OR (entity_type = 'psr' AND entity_key = 'b0000000-0000-0000-0000-000000000015')
  )
ORDER BY entity_type, entity_key, status_type;