-- =============================================================================
-- 99_mapping_conditions_bcnf.sql
-- v4.2.3 — Source unique BCNF des conditions de mapping
-- =============================================================================
-- Les fichiers de mapping historiques chargent encore temporairement
-- condition_field / condition_value afin de rester compatibles avec un reset
-- complet. Ce post-seed :
--   1. matérialise chaque condition atomique dans la table fille ;
--   2. calcule une clé stable du groupe de conditions ;
--   3. supprime définitivement les deux colonnes legacy des tables parentes ;
--   4. remplace les clés naturelles par des clés fondées sur condition_set_key.
-- Après COMMIT, il n'existe plus qu'une seule source de vérité : les tables
-- ref_mapping_rule_conditions et ref_template_mapping_rule_conditions.
-- =============================================================================

BEGIN;

-- Les colonnes peuvent déjà exister sur une base mise à niveau.
ALTER TABLE ref.ref_mapping_rules
    ADD COLUMN IF NOT EXISTS condition_set_key VARCHAR(64);
ALTER TABLE ref.ref_template_mapping_rules
    ADD COLUMN IF NOT EXISTS condition_set_key VARCHAR(64);

-- Rejouable : reconstruire les enfants à partir de l'état authoring legacy.
-- Sur une base déjà normalisée, les colonnes legacy n'existent plus et le bloc
-- est simplement ignoré grâce aux tests information_schema.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='ref' AND table_name='ref_mapping_rules'
          AND column_name='condition_field'
    ) THEN
        DELETE FROM ref.ref_mapping_rule_conditions c
        USING ref.ref_mapping_rules r
        WHERE c.mapping_rule_id = r.mapping_rule_id
          AND (
              r.condition_set_key IS NULL
              OR r.condition_field IS NOT NULL
              OR r.condition_value IS NOT NULL
          );

        WITH source_rules AS (
            SELECT mapping_rule_id,
                   string_to_array(COALESCE(condition_field, ''), ';') AS fields,
                   string_to_array(COALESCE(condition_value, ''), ';') AS values
            FROM ref.ref_mapping_rules
            WHERE NULLIF(TRIM(COALESCE(condition_field, '')), '') IS NOT NULL
        )
        INSERT INTO ref.ref_mapping_rule_conditions
            (mapping_rule_id, condition_field, condition_operator, condition_value)
        SELECT mapping_rule_id, TRIM(fields[i]), '=', TRIM(values[i])
        FROM source_rules
        CROSS JOIN LATERAL generate_subscripts(fields, 1) AS g(i)
        WHERE array_length(fields, 1) = array_length(values, 1)
          AND NULLIF(TRIM(fields[i]), '') IS NOT NULL
        ON CONFLICT DO NOTHING;

        UPDATE ref.ref_mapping_rules
        SET condition_set_key = md5(
            COALESCE(condition_field, '') || E'\x1f' || COALESCE(condition_value, '')
        )
        WHERE condition_set_key IS NULL
           OR condition_field IS NOT NULL
           OR condition_value IS NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='ref' AND table_name='ref_template_mapping_rules'
          AND column_name='condition_field'
    ) THEN
        DELETE FROM ref.ref_template_mapping_rule_conditions c
        USING ref.ref_template_mapping_rules r
        WHERE c.template_mapping_rule_id = r.template_mapping_rule_id
          AND (
              r.condition_set_key IS NULL
              OR r.condition_field IS NOT NULL
              OR r.condition_value IS NOT NULL
          );

        WITH source_rules AS (
            SELECT template_mapping_rule_id,
                   string_to_array(COALESCE(condition_field, ''), ';') AS fields,
                   string_to_array(COALESCE(condition_value, ''), ';') AS values
            FROM ref.ref_template_mapping_rules
            WHERE NULLIF(TRIM(COALESCE(condition_field, '')), '') IS NOT NULL
        )
        INSERT INTO ref.ref_template_mapping_rule_conditions
            (template_mapping_rule_id, condition_field, condition_operator, condition_value)
        SELECT template_mapping_rule_id, TRIM(fields[i]), '=', TRIM(values[i])
        FROM source_rules
        CROSS JOIN LATERAL generate_subscripts(fields, 1) AS g(i)
        WHERE array_length(fields, 1) = array_length(values, 1)
          AND NULLIF(TRIM(fields[i]), '') IS NOT NULL
        ON CONFLICT DO NOTHING;

        UPDATE ref.ref_template_mapping_rules
        SET condition_set_key = md5(
            COALESCE(condition_field, '') || E'\x1f' || COALESCE(condition_value, '')
        )
        WHERE condition_set_key IS NULL
           OR condition_field IS NOT NULL
           OR condition_value IS NOT NULL;
    END IF;
END $$;

-- Valeur stable pour les bases déjà partiellement migrées.
UPDATE ref.ref_mapping_rules
SET condition_set_key = md5('')
WHERE condition_set_key IS NULL;
UPDATE ref.ref_template_mapping_rules
SET condition_set_key = md5('')
WHERE condition_set_key IS NULL;

DROP INDEX IF EXISTS ref.uq_ref_mapping_rules_natural;
DROP INDEX IF EXISTS ref.uq_ref_template_mapping_rules_natural;

ALTER TABLE ref.ref_mapping_rules
    DROP COLUMN IF EXISTS condition_field,
    DROP COLUMN IF EXISTS condition_value,
    ALTER COLUMN condition_set_key SET NOT NULL;
ALTER TABLE ref.ref_template_mapping_rules
    DROP COLUMN IF EXISTS condition_field,
    DROP COLUMN IF EXISTS condition_value,
    ALTER COLUMN condition_set_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_mapping_rules_natural_v423
ON ref.ref_mapping_rules (
    regulatory_version_id, framework, source_table,
    condition_set_key, metric_name, output_code
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_template_mapping_rules_natural_v423
ON ref.ref_template_mapping_rules (
    regulatory_version_id, framework, template_id, source_table,
    condition_set_key, metric_name, output_cell_code
);

COMMENT ON COLUMN ref.ref_mapping_rules.condition_set_key IS
    'Clé stable du groupe de conditions ; les conditions métier sont stockées uniquement dans ref_mapping_rule_conditions.';
COMMENT ON COLUMN ref.ref_template_mapping_rules.condition_set_key IS
    'Clé stable du groupe de conditions ; les conditions métier sont stockées uniquement dans ref_template_mapping_rule_conditions.';

COMMIT;
