-- =============================================================================
-- 02_mapping_saccr.sql
-- Mapping COREP du moteur SA-CCR.
-- =============================================================================
BEGIN;
DELETE FROM ref.ref_mapping_rules WHERE regulatory_version_id='CRR3_V9' AND source_table='core_saccr_results';
DELETE FROM ref.ref_template_mapping_rules WHERE regulatory_version_id='CRR3_V9' AND source_table='core_saccr_results';

INSERT INTO ref.ref_mapping_rules
    (regulatory_version_id, framework, source_table, condition_field, condition_value, metric_name, output_code)
VALUES
('CRR3_V9','COREP','core_saccr_results','counterparty_type','BANK',      'RWA','C34.02_RWA_SACCR_BANK'),
('CRR3_V9','COREP','core_saccr_results','counterparty_type','CORPORATE', 'RWA','C34.02_RWA_SACCR_CORP'),
('CRR3_V9','COREP','core_saccr_results','counterparty_type','SOVEREIGN', 'RWA','C34.02_RWA_SACCR_SOV')
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_template_mapping_rules
    (regulatory_version_id, framework, template_id, source_table, condition_field, condition_value, metric_name, output_cell_code)
VALUES
('CRR3_V9','COREP','C34.02','core_saccr_results','counterparty_type','BANK',      'RWA','r0010_c0010'),
('CRR3_V9','COREP','C34.02','core_saccr_results','counterparty_type','CORPORATE', 'RWA','r0020_c0010'),
('CRR3_V9','COREP','C34.02','core_saccr_results','counterparty_type','SOVEREIGN', 'RWA','r0030_c0010')
ON CONFLICT DO NOTHING;
COMMIT;
