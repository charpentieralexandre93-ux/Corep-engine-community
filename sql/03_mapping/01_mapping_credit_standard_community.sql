-- =============================================================================
-- 01_mapping_credit_standard_community.sql
-- Mapping COREP public du moteur risque de crédit standard.
-- =============================================================================
BEGIN;

DELETE FROM ref.ref_mapping_rules
 WHERE regulatory_version_id = 'CRR3_V9'
   AND source_table = 'core_standard_results';

DELETE FROM ref.ref_template_mapping_rules
 WHERE regulatory_version_id = 'CRR3_V9'
   AND source_table = 'core_standard_results';

INSERT INTO ref.ref_mapping_rules
    (regulatory_version_id, framework, source_table, condition_field, condition_value, metric_name, output_code)
VALUES
('CRR3_V9','COREP','core_standard_results','asset_class_id','CENTRAL_GOVT',    'RWA','C07.00_RWA_CENTRAL_GOVT'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','SOVEREIGN',       'RWA','C07.00_RWA_SOV'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','INSTITUTION',      'RWA','C07.00_RWA_INSTITUTION'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','BANK',            'RWA','C07.00_RWA_BANK'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','PUBLIC_SECTOR',   'RWA','C07.00_RWA_PSE'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','REGIONAL_GOVT',   'RWA','C07.00_RWA_REGIONAL'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','MULTILATERAL_BANK','RWA','C07.00_RWA_MDB'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','CORPORATE',        'RWA','C07.00_RWA_CORP'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','SME_CORPORATE',    'RWA','C07.00_RWA_SME_CORP'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','RETAIL',           'RWA','C07.00_RWA_RETAIL'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','SME_RETAIL',       'RWA','C07.00_RWA_SME_RETAIL'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','RESIDENTIAL_MORTGAGE','RWA','C07.00_RWA_RESID_MORT'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','COMMERCIAL_MORTGAGE', 'RWA','C07.00_RWA_COMM_MORT'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','DEFAULT',           'RWA','C07.00_RWA_DEFAULT'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','HIGH_RISK',         'RWA','C07.00_RWA_HIGH_RISK'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','COVERED_BOND',      'RWA','C07.00_RWA_COVERED_BOND'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','CIU',               'RWA','C07.00_RWA_CIU'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','EQUITY',            'RWA','C07.00_RWA_EQUITY'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','OTHER',             'RWA','C07.00_RWA_OTHER'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','INFRA_CORPORATE',   'RWA','C07.00_RWA_INFRA'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','CORPORATE',    'EAD','C09.01_EAD_CORP'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','RETAIL',       'EAD','C09.01_EAD_RETAIL'),
('CRR3_V9','COREP','core_standard_results','asset_class_id','DEFAULT',      'EAD','C09.01_EAD_DEFAULT')
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_template_mapping_rules
    (regulatory_version_id, framework, template_id, source_table, condition_field, condition_value, metric_name, output_cell_code)
VALUES
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','CENTRAL_GOVT',    'RWA','r0010_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','SOVEREIGN',       'RWA','r0010_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','INSTITUTION',     'RWA','r0050_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','BANK',            'RWA','r0050_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','CORPORATE',       'RWA','r0100_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','SME_CORPORATE',   'RWA','r0100_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','RETAIL',          'RWA','r0200_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','SME_RETAIL',      'RWA','r0200_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','RESIDENTIAL_MORTGAGE','RWA','r0300_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','COMMERCIAL_MORTGAGE', 'RWA','r0400_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','DEFAULT',         'RWA','r0500_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','HIGH_RISK',       'RWA','r0600_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','COVERED_BOND',    'RWA','r0700_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','EQUITY',          'RWA','r0800_c0100'),
('CRR3_V9','COREP','C07.00','core_standard_results','asset_class_id','OTHER',           'RWA','r0900_c0100')
ON CONFLICT DO NOTHING;

COMMIT;
