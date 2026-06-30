-- =============================================================================
-- 99_regulatory_reference_model_hardening_v6_6_0.sql
-- Corep Engine Community v6.6.0 — Regulatory Reference Model Hardening
-- =============================================================================
-- Objectif : formaliser le modèle de références réglementaires sans refonte
-- destructive. Ce script complète la v6.6.0 : il catalogue les relations de
-- référence, documente leurs déterminants métier et ajoute des contraintes de
-- qualité non destructives sur les sources de vérité réglementaires.
--
-- Garanties de non-régression :
--   * idempotent ;
--   * aucune suppression de table, colonne ou donnée ;
--   * aucune modification des tables stg/core/rpt ;
--   * uniquement des contraintes/vues/référentiels de gouvernance ref/meta ;
--   * positionné avant les contraintes finales de bootstrap.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS meta.reference_model_assertions (
    assertion_code VARCHAR(160) PRIMARY KEY,
    target_relation VARCHAR(200) NOT NULL,
    normal_form VARCHAR(20) NOT NULL,
    determinant_columns TEXT NOT NULL,
    authoritative_scope VARCHAR(30) NOT NULL,
    edition_scope VARCHAR(30) NOT NULL,
    introduced_version VARCHAR(20) NOT NULL,
    active_flag BOOLEAN NOT NULL DEFAULT TRUE,
    assertion_description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_reference_model_assertions_normal_form_v660
        CHECK (normal_form IN ('3NF', 'BCNF', 'QUASI_BCNF', 'DENORMALIZED_SNAPSHOT')),
    CONSTRAINT ck_reference_model_assertions_scope_v660
        CHECK (authoritative_scope IN ('REFERENCE', 'MAPPING', 'TAXONOMY', 'RULE', 'STAGING', 'RESULT', 'AUDIT')),
    CONSTRAINT ck_reference_model_assertions_edition_v660
        CHECK (edition_scope IN ('COMMUNITY', 'ENTERPRISE', 'BOTH')),
    CONSTRAINT ck_reference_model_assertions_version_v660
        CHECK (introduced_version ~ '^[0-9]+[.][0-9]+[.][0-9]+$')
);

CREATE TABLE IF NOT EXISTS ref.ref_reference_tables (
    reference_relation VARCHAR(200) PRIMARY KEY,
    natural_key_columns TEXT NOT NULL,
    normal_form_target VARCHAR(20) NOT NULL,
    edition_scope VARCHAR(30) NOT NULL,
    authoritative_key TEXT NOT NULL,
    reference_description TEXT NOT NULL,
    introduced_version VARCHAR(20) NOT NULL DEFAULT '6.6.0',
    active_flag BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_ref_reference_tables_normal_form_v660
        CHECK (normal_form_target IN ('3NF', 'BCNF', 'QUASI_BCNF', 'DENORMALIZED_SNAPSHOT')),
    CONSTRAINT ck_ref_reference_tables_edition_v660
        CHECK (edition_scope IN ('COMMUNITY', 'ENTERPRISE', 'BOTH')),
    CONSTRAINT ck_ref_reference_tables_not_blank_v660
        CHECK (
            NULLIF(TRIM(reference_relation), '') IS NOT NULL
            AND NULLIF(TRIM(natural_key_columns), '') IS NOT NULL
            AND NULLIF(TRIM(authoritative_key), '') IS NOT NULL
            AND NULLIF(TRIM(reference_description), '') IS NOT NULL
        )
);

INSERT INTO ref.ref_reference_tables
    (reference_relation, natural_key_columns, normal_form_target, edition_scope, authoritative_key, reference_description, introduced_version)
VALUES
    ('ref.ref_regulatory_versions', 'regulatory_version_id', 'BCNF', 'COMMUNITY', 'regulatory_version_id', 'regulatory version master data'),
    ('ref.ref_counterparties', 'counterparty_id', '3NF', 'COMMUNITY', 'counterparty_id', 'counterparty master data; counterparty_type constrained via domain catalogue'),
    ('ref.ref_counterparty_types', 'counterparty_type', 'BCNF', 'COMMUNITY', 'counterparty_type', 'counterparty type dictionary'),
    ('ref.ref_asset_classes', 'asset_class_id', 'BCNF', 'COMMUNITY', 'asset_class_id', 'asset class dictionary'),
    ('ref.ref_product_types', 'product_type_id', 'BCNF', 'COMMUNITY', 'product_type_id', 'product type dictionary'),
    ('ref.ref_protection_types', 'protection_type', 'BCNF', 'COMMUNITY', 'protection_type', 'credit protection type dictionary'),
    ('ref.ref_protection_buckets', 'bucket_code', 'BCNF', 'COMMUNITY', 'bucket_code', 'credit protection bucket dictionary'),
    ('ref.ref_runtime_parameters', 'regulatory_version_id,parameter_name', 'BCNF', 'COMMUNITY', 'regulatory_version_id,parameter_name', 'versioned runtime parameters'),
    ('ref.ref_decision_rule_sets', 'regulatory_version_id,rule_set_name', 'BCNF', 'COMMUNITY', 'regulatory_version_id,rule_set_name', 'versioned decision rule sets'),
    ('ref.ref_decision_rules', 'rule_set_id,priority,result_key', 'BCNF', 'COMMUNITY', 'rule_set_id,priority,result_key', 'decision rule atoms'),
    ('ref.ref_rule_conditions', 'rule_id,condition_field,condition_operator,condition_value', 'BCNF', 'COMMUNITY', 'rule_id,condition_field,condition_operator,condition_value', 'decision rule conditions'),
    ('ref.ref_condition_fields', 'condition_field', 'BCNF', 'COMMUNITY', 'condition_field', 'allowed condition field dictionary'),
    ('ref.ref_mapping_rules', 'regulatory_version_id,framework,source_table,condition_set_key,metric_name,output_code', 'BCNF', 'COMMUNITY', 'regulatory_version_id,framework,source_table,condition_set_key,metric_name,output_code', 'COREP mapping rule headers'),
    ('ref.ref_mapping_rule_conditions', 'mapping_rule_id,condition_field,condition_operator,condition_value', 'BCNF', 'COMMUNITY', 'mapping_rule_id,condition_field,condition_operator,condition_value', 'COREP mapping rule condition atoms'),
    ('ref.ref_template_mapping_rules', 'regulatory_version_id,framework,template_id,source_table,condition_set_key,metric_name,output_cell_code', 'BCNF', 'COMMUNITY', 'regulatory_version_id,framework,template_id,source_table,condition_set_key,metric_name,output_cell_code', 'template mapping rule headers'),
    ('ref.ref_template_mapping_rule_conditions', 'template_mapping_rule_id,condition_field,condition_operator,condition_value', 'BCNF', 'COMMUNITY', 'template_mapping_rule_id,condition_field,condition_operator,condition_value', 'template mapping rule condition atoms'),
    ('ref.ref_supporting_factor_rules', 'regulatory_version_id,factor_code,priority', 'BCNF', 'COMMUNITY', 'regulatory_version_id,factor_code,priority', 'supporting factor rule catalogue'),
    ('ref.ref_collateral_haircuts', 'collateral_type,collateral_grade,issuer_type', 'BCNF', 'COMMUNITY', 'collateral_type,collateral_grade,issuer_type', 'collateral haircut reference table'),
    ('ref.ref_saccr_supervisory_parameters', 'asset_class,hedging_set', 'BCNF', 'COMMUNITY', 'asset_class,hedging_set', 'SA-CCR supervisory parameters')
ON CONFLICT (reference_relation) DO UPDATE SET
    natural_key_columns = EXCLUDED.natural_key_columns,
    normal_form_target = EXCLUDED.normal_form_target,
    edition_scope = EXCLUDED.edition_scope,
    authoritative_key = EXCLUDED.authoritative_key,
    reference_description = EXCLUDED.reference_description,
    introduced_version = EXCLUDED.introduced_version,
    active_flag = TRUE,
    updated_at = NOW();

INSERT INTO meta.reference_model_assertions
    (assertion_code, target_relation, normal_form, determinant_columns, authoritative_scope, edition_scope, introduced_version, assertion_description)
SELECT
    'REF_MODEL_' || upper(regexp_replace(reference_relation, '[^a-zA-Z0-9]+', '_', 'g')) AS assertion_code,
    reference_relation,
    normal_form_target,
    authoritative_key,
    CASE
        WHEN reference_relation LIKE 'ref.ref_%mapping%' THEN 'MAPPING'
        WHEN reference_relation LIKE 'ref.ref_dpm%' THEN 'TAXONOMY'
        WHEN reference_relation LIKE 'ref.ref_%rule%' THEN 'RULE'
        ELSE 'REFERENCE'
    END AS authoritative_scope,
    edition_scope,
    introduced_version,
    reference_description
FROM ref.ref_reference_tables
WHERE active_flag
ON CONFLICT (assertion_code) DO UPDATE SET
    target_relation = EXCLUDED.target_relation,
    normal_form = EXCLUDED.normal_form,
    determinant_columns = EXCLUDED.determinant_columns,
    authoritative_scope = EXCLUDED.authoritative_scope,
    edition_scope = EXCLUDED.edition_scope,
    introduced_version = EXCLUDED.introduced_version,
    assertion_description = EXCLUDED.assertion_description,
    active_flag = TRUE;

CREATE INDEX IF NOT EXISTS idx_ref_reference_tables_normal_form_v660
ON ref.ref_reference_tables (normal_form_target, edition_scope, active_flag);

CREATE INDEX IF NOT EXISTS idx_reference_model_assertions_scope_v660
ON meta.reference_model_assertions (authoritative_scope, normal_form, active_flag);

-- Validité temporelle et identifiants non vides sur les référentiels communs.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_regulatory_versions_dates_v660'
          AND conrelid = 'ref.ref_regulatory_versions'::regclass
    ) THEN
        ALTER TABLE ref.ref_regulatory_versions
            ADD CONSTRAINT ck_ref_regulatory_versions_dates_v660
            CHECK (end_date IS NULL OR end_date >= effective_date)
            NOT VALID;
        ALTER TABLE ref.ref_regulatory_versions VALIDATE CONSTRAINT ck_ref_regulatory_versions_dates_v660;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_regulatory_versions_id_not_blank_v660'
          AND conrelid = 'ref.ref_regulatory_versions'::regclass
    ) THEN
        ALTER TABLE ref.ref_regulatory_versions
            ADD CONSTRAINT ck_ref_regulatory_versions_id_not_blank_v660
            CHECK (NULLIF(TRIM(regulatory_version_id), '') IS NOT NULL)
            NOT VALID;
        ALTER TABLE ref.ref_regulatory_versions VALIDATE CONSTRAINT ck_ref_regulatory_versions_id_not_blank_v660;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_runtime_parameters_name_not_blank_v660'
          AND conrelid = 'ref.ref_runtime_parameters'::regclass
    ) THEN
        ALTER TABLE ref.ref_runtime_parameters
            ADD CONSTRAINT ck_ref_runtime_parameters_name_not_blank_v660
            CHECK (NULLIF(TRIM(parameter_name), '') IS NOT NULL AND NULLIF(TRIM(parameter_value), '') IS NOT NULL)
            NOT VALID;
        ALTER TABLE ref.ref_runtime_parameters VALIDATE CONSTRAINT ck_ref_runtime_parameters_name_not_blank_v660;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_decision_rule_sets_name_not_blank_v660'
          AND conrelid = 'ref.ref_decision_rule_sets'::regclass
    ) THEN
        ALTER TABLE ref.ref_decision_rule_sets
            ADD CONSTRAINT ck_ref_decision_rule_sets_name_not_blank_v660
            CHECK (NULLIF(TRIM(rule_set_name), '') IS NOT NULL)
            NOT VALID;
        ALTER TABLE ref.ref_decision_rule_sets VALIDATE CONSTRAINT ck_ref_decision_rule_sets_name_not_blank_v660;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_decision_rules_result_not_blank_v660'
          AND conrelid = 'ref.ref_decision_rules'::regclass
    ) THEN
        ALTER TABLE ref.ref_decision_rules
            ADD CONSTRAINT ck_ref_decision_rules_result_not_blank_v660
            CHECK (NULLIF(TRIM(result_key), '') IS NOT NULL AND NULLIF(TRIM(result_value), '') IS NOT NULL)
            NOT VALID;
        ALTER TABLE ref.ref_decision_rules VALIDATE CONSTRAINT ck_ref_decision_rules_result_not_blank_v660;
    END IF;
END $$;

CREATE OR REPLACE VIEW ref.v_reference_model_hardening_status AS
SELECT
    reference_relation,
    normal_form_target,
    edition_scope,
    authoritative_key,
    introduced_version,
    active_flag
FROM ref.ref_reference_tables
ORDER BY reference_relation;

COMMENT ON TABLE ref.ref_reference_tables IS
    'v6.6.0 Regulatory Reference Model Hardening: catalogue des tables de référence et de leurs clés naturelles.';
COMMENT ON TABLE meta.reference_model_assertions IS
    'v6.6.0 Regulatory Reference Model Hardening: assertions normal form / déterminants pour audit et revue réglementaire.';
COMMENT ON VIEW ref.v_reference_model_hardening_status IS
    'Vue de contrôle v6.6.0 listant le statut 3NF/BCNF des référentiels réglementaires.';

COMMIT;
