-- =============================================================================
-- 03_schema_bcnf_integrity_patch.sql
-- PATCH v2.1 — Cohérence technique BCNF / intégrité référentielle
-- =============================================================================
-- Objectifs :
--   1. Lever le blocage PostgreSQL lié au versioning des rule sets.
--   2. Ajouter des clés naturelles sur les tables de règles et mappings.
--   3. Rendre les clauses ON CONFLICT DO NOTHING réellement efficaces.
--
-- À exécuter après les scripts 02 à 02f et avant les seeds 03/04/05/10.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Rule sets : le nom métier d'un rule set doit être unique PAR VERSION,
--    pas globalement. Sinon CRR3_V9 et CRR4_V1 ne peuvent pas réutiliser
--    RS_CCF, RS_RW, etc.
-- -----------------------------------------------------------------------------
ALTER TABLE ref.ref_decision_rule_sets
    DROP CONSTRAINT IF EXISTS ref_decision_rule_sets_rule_set_name_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_decision_rule_sets_version_name
ON ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name);

-- -----------------------------------------------------------------------------
-- 2. Règles de décision : une priorité ne doit pas être dupliquée dans un même
--    rule set pour un même result_key. Cette contrainte stabilise les seeds.
-- -----------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_decision_rules_natural
ON ref.ref_decision_rules (rule_set_id, priority, result_key);

-- La contrainte sur les conditions existe déjà dans le schéma P0, mais on la
-- rejoue ici pour sécuriser les bases créées depuis un ancien schéma.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_rule_conditions_natural
ON ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value);

-- -----------------------------------------------------------------------------
-- 3. Supporting factors : évite les doublons SME / INFRA entre 04 et 05.
-- -----------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_supporting_factor_rules_natural
ON ref.ref_supporting_factor_rules (
    regulatory_version_id,
    factor_code,
    priority,
    (COALESCE(eligibility_field, '')),
    (COALESCE(eligibility_operator, '')),
    (COALESCE(eligibility_value, '')),
    (COALESCE(applies_to_metric, ''))
);

-- -----------------------------------------------------------------------------
-- 4. Mapping rules : ON CONFLICT DO NOTHING ne protègeait pas contre les doublons
--    car aucune clé naturelle n'existait.
-- -----------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_mapping_rules_natural
ON ref.ref_mapping_rules (
    regulatory_version_id,
    framework,
    source_table,
    (COALESCE(condition_field, '')),
    (COALESCE(condition_value, '')),
    metric_name,
    output_code
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_template_mapping_rules_natural
ON ref.ref_template_mapping_rules (
    regulatory_version_id,
    framework,
    template_id,
    source_table,
    (COALESCE(condition_field, '')),
    (COALESCE(condition_value, '')),
    metric_name,
    output_cell_code
);

COMMIT;
