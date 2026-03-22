-- Step 5 of the AIS Quick Slice build: seed template evidence requirements for
-- rule types WO, CTH, VNM plus corridor-level transport records.
-- Note: the current evidence_requirement table does not include source_id, so
-- provenance cannot be stored directly in this table with the live schema.

\echo 'Step 5: Seeding evidence_requirement templates for WO, CTH, VNM, and corridor transport records'

-- WO requirements
INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'WO',
  'system',
  'certificate_of_origin',
  'AfCFTA Certificate of Origin (Annex 2, Appendix I)',
  NULL,
  true,
  NULL,
  1
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'WO'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'certificate_of_origin'
);

INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'WO',
  'system',
  'supplier_declaration',
  'Supplier declaration confirming wholly obtained status',
  NULL,
  true,
  NULL,
  2
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'WO'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'supplier_declaration'
);

-- CTH requirements
INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'CTH',
  'system',
  'certificate_of_origin',
  'AfCFTA Certificate of Origin (Annex 2, Appendix I)',
  NULL,
  true,
  NULL,
  1
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'CTH'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'certificate_of_origin'
);

INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'CTH',
  'system',
  'bill_of_materials',
  'Bill of materials showing HS codes of all inputs',
  NULL,
  true,
  NULL,
  2
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'CTH'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'bill_of_materials'
);

INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'CTH',
  'system',
  'invoice',
  'Commercial invoice with HS classification of inputs',
  NULL,
  true,
  NULL,
  3
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'CTH'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'invoice'
);

-- VNM requirements
INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'VNM',
  'system',
  'certificate_of_origin',
  'AfCFTA Certificate of Origin (Annex 2, Appendix I)',
  NULL,
  true,
  NULL,
  1
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'VNM'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'certificate_of_origin'
);

INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'VNM',
  'system',
  'cost_breakdown',
  'Cost breakdown showing originating and non-originating content',
  NULL,
  true,
  NULL,
  2
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'VNM'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'cost_breakdown'
);

INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'rule_type',
  'VNM',
  'system',
  'valuation_support',
  'Valuation documentation supporting materials calculation',
  NULL,
  true,
  NULL,
  3
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'rule_type'
    AND er.entity_key = 'VNM'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'valuation_support'
);

-- Corridor requirements
INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'corridor',
  'GHA:CMR',
  'system',
  'transport_record',
  'Through bill of lading demonstrating direct consignment',
  NULL,
  true,
  NULL,
  1
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'corridor'
    AND er.entity_key = 'GHA:CMR'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'transport_record'
);

INSERT INTO evidence_requirement (
  evidence_id,
  entity_type,
  entity_key,
  persona_mode,
  requirement_type,
  requirement_description,
  legal_basis_provision_id,
  required,
  conditional_on,
  priority_level
)
SELECT
  uuid_generate_v4(),
  'corridor',
  'CMR:GHA',
  'system',
  'transport_record',
  'Through bill of lading demonstrating direct consignment',
  NULL,
  true,
  NULL,
  1
WHERE NOT EXISTS (
  SELECT 1
  FROM evidence_requirement er
  WHERE er.entity_type = 'corridor'
    AND er.entity_key = 'CMR:GHA'
    AND er.persona_mode = 'system'
    AND er.requirement_type = 'transport_record'
);

\echo 'Validation: seeded evidence requirements'
SELECT entity_type, entity_key, persona_mode, requirement_type, priority_level
FROM evidence_requirement
WHERE (entity_type = 'rule_type' AND entity_key IN ('WO', 'CTH', 'VNM'))
   OR (entity_type = 'corridor' AND entity_key IN ('GHA:CMR', 'CMR:GHA'))
ORDER BY entity_type, entity_key, priority_level, requirement_type;