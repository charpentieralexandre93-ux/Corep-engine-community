-- =============================================================================
-- 99_bcnf_hardening_v6_5_0.sql
-- Corep Engine Community v6.5.0 — Data Model BCNF Hardening
-- =============================================================================
-- Objectif : durcir le modèle de données réglementaire sans refonte destructive.
--
-- Périmètre volontairement ciblé : référentiels, règles de décision, mappings
-- et conditions atomiques. Les tables de staging et de résultats restent
-- inchangées afin de préserver les moteurs, les exports et les snapshots d'audit.
--
-- Garanties de non-régression :
--   * script idempotent ;
--   * aucune suppression de table/colonne ;
--   * contraintes ajoutées seulement sur les sources de vérité réglementaires ;
--   * vues de compatibilité pour relire les mappings normalisés au format legacy.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Dictionnaire BCNF des champs de condition
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.ref_condition_fields (
    condition_field VARCHAR(100) PRIMARY KEY,
    description TEXT,
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ref.ref_condition_fields IS
    'Dictionnaire BCNF des champs autorisés dans les conditions de règles et de mappings.';
COMMENT ON COLUMN ref.ref_condition_fields.condition_field IS
    'Déterminant métier unique d’un champ de condition ; utilisé par les tables de conditions atomiques.';

INSERT INTO ref.ref_condition_fields (condition_field)
SELECT DISTINCT condition_field
FROM (
    SELECT condition_field FROM ref.ref_rule_conditions
    UNION ALL
    SELECT condition_field FROM ref.ref_mapping_rule_conditions
    UNION ALL
    SELECT condition_field FROM ref.ref_template_mapping_rule_conditions
) AS fields
WHERE NULLIF(TRIM(condition_field), '') IS NOT NULL
ON CONFLICT (condition_field) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. Contraintes de domaine atomique : opérateurs, champs non vides, valeurs
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_rule_conditions_operator_v650'
          AND conrelid = 'ref.ref_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_rule_conditions
            ADD CONSTRAINT ck_ref_rule_conditions_operator_v650
            CHECK (condition_operator IN ('=', '!=', '<>', '>', '>=', '<', '<=', 'IN', 'NOT_IN', 'LIKE'))
            NOT VALID;
        ALTER TABLE ref.ref_rule_conditions VALIDATE CONSTRAINT ck_ref_rule_conditions_operator_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_mapping_rule_conditions_operator_v650'
          AND conrelid = 'ref.ref_mapping_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_mapping_rule_conditions
            ADD CONSTRAINT ck_ref_mapping_rule_conditions_operator_v650
            CHECK (condition_operator IN ('=', '!=', '<>', '>', '>=', '<', '<=', 'IN', 'NOT_IN', 'LIKE'))
            NOT VALID;
        ALTER TABLE ref.ref_mapping_rule_conditions VALIDATE CONSTRAINT ck_ref_mapping_rule_conditions_operator_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_template_mapping_rule_conditions_operator_v650'
          AND conrelid = 'ref.ref_template_mapping_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_template_mapping_rule_conditions
            ADD CONSTRAINT ck_ref_template_mapping_rule_conditions_operator_v650
            CHECK (condition_operator IN ('=', '!=', '<>', '>', '>=', '<', '<=', 'IN', 'NOT_IN', 'LIKE'))
            NOT VALID;
        ALTER TABLE ref.ref_template_mapping_rule_conditions VALIDATE CONSTRAINT ck_ref_template_mapping_rule_conditions_operator_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_rule_conditions_not_blank_v650'
          AND conrelid = 'ref.ref_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_rule_conditions
            ADD CONSTRAINT ck_ref_rule_conditions_not_blank_v650
            CHECK (
                NULLIF(TRIM(condition_field), '') IS NOT NULL
                AND NULLIF(TRIM(condition_operator), '') IS NOT NULL
                AND NULLIF(TRIM(condition_value), '') IS NOT NULL
            ) NOT VALID;
        ALTER TABLE ref.ref_rule_conditions VALIDATE CONSTRAINT ck_ref_rule_conditions_not_blank_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_mapping_rule_conditions_not_blank_v650'
          AND conrelid = 'ref.ref_mapping_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_mapping_rule_conditions
            ADD CONSTRAINT ck_ref_mapping_rule_conditions_not_blank_v650
            CHECK (
                NULLIF(TRIM(condition_field), '') IS NOT NULL
                AND NULLIF(TRIM(condition_operator), '') IS NOT NULL
                AND NULLIF(TRIM(condition_value), '') IS NOT NULL
            ) NOT VALID;
        ALTER TABLE ref.ref_mapping_rule_conditions VALIDATE CONSTRAINT ck_ref_mapping_rule_conditions_not_blank_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_template_mapping_rule_conditions_not_blank_v650'
          AND conrelid = 'ref.ref_template_mapping_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_template_mapping_rule_conditions
            ADD CONSTRAINT ck_ref_template_mapping_rule_conditions_not_blank_v650
            CHECK (
                NULLIF(TRIM(condition_field), '') IS NOT NULL
                AND NULLIF(TRIM(condition_operator), '') IS NOT NULL
                AND NULLIF(TRIM(condition_value), '') IS NOT NULL
            ) NOT VALID;
        ALTER TABLE ref.ref_template_mapping_rule_conditions VALIDATE CONSTRAINT ck_ref_template_mapping_rule_conditions_not_blank_v650;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 3. FK vers le dictionnaire de champs de condition
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_ref_rule_conditions_condition_field_v650'
          AND conrelid = 'ref.ref_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_rule_conditions
            ADD CONSTRAINT fk_ref_rule_conditions_condition_field_v650
            FOREIGN KEY (condition_field)
            REFERENCES ref.ref_condition_fields(condition_field)
            NOT VALID;
        ALTER TABLE ref.ref_rule_conditions VALIDATE CONSTRAINT fk_ref_rule_conditions_condition_field_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_ref_mapping_rule_conditions_condition_field_v650'
          AND conrelid = 'ref.ref_mapping_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_mapping_rule_conditions
            ADD CONSTRAINT fk_ref_mapping_rule_conditions_condition_field_v650
            FOREIGN KEY (condition_field)
            REFERENCES ref.ref_condition_fields(condition_field)
            NOT VALID;
        ALTER TABLE ref.ref_mapping_rule_conditions VALIDATE CONSTRAINT fk_ref_mapping_rule_conditions_condition_field_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_ref_template_mapping_rule_conditions_condition_field_v650'
          AND conrelid = 'ref.ref_template_mapping_rule_conditions'::regclass
    ) THEN
        ALTER TABLE ref.ref_template_mapping_rule_conditions
            ADD CONSTRAINT fk_ref_template_mapping_rule_conditions_condition_field_v650
            FOREIGN KEY (condition_field)
            REFERENCES ref.ref_condition_fields(condition_field)
            NOT VALID;
        ALTER TABLE ref.ref_template_mapping_rule_conditions VALIDATE CONSTRAINT fk_ref_template_mapping_rule_conditions_condition_field_v650;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 4. Natural keys et clés de groupes de conditions stabilisées
-- -----------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_condition_fields_pk_v650
ON ref.ref_condition_fields (condition_field);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_mapping_rule_conditions_ordered_v650
ON ref.ref_mapping_rule_conditions (mapping_rule_id, condition_field, condition_operator, condition_value);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_template_mapping_rule_conditions_ordered_v650
ON ref.ref_template_mapping_rule_conditions (template_mapping_rule_id, condition_field, condition_operator, condition_value);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_mapping_rules_condition_set_key_v650'
          AND conrelid = 'ref.ref_mapping_rules'::regclass
    ) THEN
        ALTER TABLE ref.ref_mapping_rules
            ADD CONSTRAINT ck_ref_mapping_rules_condition_set_key_v650
            CHECK (condition_set_key ~ '^[0-9a-f]{32,64}$')
            NOT VALID;
        ALTER TABLE ref.ref_mapping_rules VALIDATE CONSTRAINT ck_ref_mapping_rules_condition_set_key_v650;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_ref_template_mapping_rules_condition_set_key_v650'
          AND conrelid = 'ref.ref_template_mapping_rules'::regclass
    ) THEN
        ALTER TABLE ref.ref_template_mapping_rules
            ADD CONSTRAINT ck_ref_template_mapping_rules_condition_set_key_v650
            CHECK (condition_set_key ~ '^[0-9a-f]{32,64}$')
            NOT VALID;
        ALTER TABLE ref.ref_template_mapping_rules VALIDATE CONSTRAINT ck_ref_template_mapping_rules_condition_set_key_v650;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 5. Vues de compatibilité : lecture legacy sans réintroduire les colonnes legacy
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW ref.v_ref_mapping_rules_authoring AS
SELECT
    r.mapping_rule_id,
    r.regulatory_version_id,
    r.framework,
    r.source_table,
    STRING_AGG(c.condition_field, ';' ORDER BY c.condition_field, c.condition_operator, c.condition_value) AS condition_field,
    STRING_AGG(c.condition_value, ';' ORDER BY c.condition_field, c.condition_operator, c.condition_value) AS condition_value,
    r.condition_set_key,
    r.metric_name,
    r.output_code,
    r.created_at,
    r.updated_at
FROM ref.ref_mapping_rules r
LEFT JOIN ref.ref_mapping_rule_conditions c
  ON c.mapping_rule_id = r.mapping_rule_id
GROUP BY r.mapping_rule_id;

CREATE OR REPLACE VIEW ref.v_ref_template_mapping_rules_authoring AS
SELECT
    r.template_mapping_rule_id,
    r.regulatory_version_id,
    r.framework,
    r.template_id,
    r.source_table,
    STRING_AGG(c.condition_field, ';' ORDER BY c.condition_field, c.condition_operator, c.condition_value) AS condition_field,
    STRING_AGG(c.condition_value, ';' ORDER BY c.condition_field, c.condition_operator, c.condition_value) AS condition_value,
    r.condition_set_key,
    r.metric_name,
    r.output_cell_code,
    r.created_at,
    r.updated_at
FROM ref.ref_template_mapping_rules r
LEFT JOIN ref.ref_template_mapping_rule_conditions c
  ON c.template_mapping_rule_id = r.template_mapping_rule_id
GROUP BY r.template_mapping_rule_id;

COMMENT ON VIEW ref.v_ref_mapping_rules_authoring IS
    'Vue de compatibilité v6.5.0 : expose les conditions de mapping normalisées sous forme legacy lisible.';
COMMENT ON VIEW ref.v_ref_template_mapping_rules_authoring IS
    'Vue de compatibilité v6.5.0 : expose les conditions de mapping template normalisées sous forme legacy lisible.';

COMMIT;
