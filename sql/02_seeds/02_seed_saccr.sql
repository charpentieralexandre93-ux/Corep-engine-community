-- =============================================================================
-- 02_seed_saccr.sql
-- Moteur SA-CCR — pondérations par type de contrepartie et paramètres dédiés.
-- =============================================================================
BEGIN;

INSERT INTO ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name, target_domain, is_active) VALUES
('CRR3_V9', 'RS_SACCR_RW', 'SACCR_RISK_WEIGHT', TRUE)
ON CONFLICT (regulatory_version_id, rule_set_name) DO UPDATE SET
    target_domain = EXCLUDED.target_domain,
    is_active = EXCLUDED.is_active;

DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_SACCR_RW'
      AND rs.regulatory_version_id = 'CRR3_V9'
);

DELETE FROM ref.ref_decision_rules
WHERE rule_set_id IN (
    SELECT rule_set_id FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_SACCR_RW'
      AND regulatory_version_id = 'CRR3_V9'
);

INSERT INTO ref.ref_decision_rules (rule_set_id, priority, result_key, result_value)
SELECT rs.rule_set_id, v.priority, 'RISK_WEIGHT', v.result_value
FROM (VALUES
    (10, '0.00'),
    (20, '0.20'),
    (30, '0.20'),
    (40, '0.50'),
    (50, '0.65'),
    (60, '1.00'),
    (70, '0.75')
) AS v(priority, result_value)
JOIN ref.ref_decision_rule_sets rs
  ON rs.rule_set_name = 'RS_SACCR_RW'
 AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT r.rule_id, 'counterparty_type', '=', v.ct
FROM ref.ref_decision_rules r
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = r.rule_set_id
CROSS JOIN (VALUES
    (10,'CENTRAL_GOVT'), (10,'SOVEREIGN'),
    (20,'BANK'), (20,'INSTITUTION'),
    (30,'PUBLIC_SECTOR'),
    (40,'INSTITUTION'),
    (50,'CORPORATE'),
    (60,'CORPORATE'),
    (70,'RETAIL')
) AS v(priority, ct)
WHERE rs.rule_set_name = 'RS_SACCR_RW'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND r.priority = v.priority
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_runtime_parameters (regulatory_version_id, parameter_name, parameter_type, parameter_value) VALUES
('CRR3_V9', 'DEFAULT_ALPHA_SACCR', 'REAL', '1.4')
ON CONFLICT (regulatory_version_id, parameter_name) DO UPDATE SET
    parameter_type = EXCLUDED.parameter_type,
    parameter_value = EXCLUDED.parameter_value;

COMMIT;
