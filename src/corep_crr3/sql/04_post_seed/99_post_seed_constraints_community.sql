-- =============================================================================
-- 99_post_seed_constraints_community.sql
-- Corep Engine Community v4.3.1 — validation finale SA / SA-CCR
-- =============================================================================
-- Ce script ne référence aucun moteur Enterprise. Il vérifie que le bootstrap
-- public a bien créé le socle requis par les moteurs SA et SA-CCR et remet en
-- place, de manière idempotente, les contraintes de domaine critiques.
-- =============================================================================

BEGIN;

DO $$
DECLARE
    missing_relations TEXT[];
BEGIN
    SELECT ARRAY_AGG(required_relation)
    INTO missing_relations
    FROM (VALUES
        ('meta.batch_run_control'),
        ('ref.ref_regulatory_versions'),
        ('ref.ref_counterparties'),
        ('ref.ref_decision_rule_sets'),
        ('ref.ref_decision_rules'),
        ('ref.ref_rule_conditions'),
        ('ref.ref_supporting_factor_rules'),
        ('ref.ref_collateral_haircuts'),
        ('stg.stg_exposures'),
        ('stg.stg_protections'),
        ('stg.stg_saccr_trades'),
        ('core.core_standard_results'),
        ('core.core_protection_allocation'),
        ('core.core_saccr_results'),
        ('rpt.rpt_decision_rule_trace'),
        ('rpt.rpt_supporting_factor_trace'),
        ('rpt.rpt_controls')
    ) AS required(required_relation)
    WHERE to_regclass(required_relation) IS NULL;

    IF missing_relations IS NOT NULL THEN
        RAISE EXCEPTION
            'Bootstrap Community incomplet. Relations manquantes : %',
            array_to_string(missing_relations, ', ');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_core_protection_allocation_bucket'
          AND conrelid = 'core.core_protection_allocation'::regclass
    ) THEN
        ALTER TABLE core.core_protection_allocation
            ADD CONSTRAINT fk_core_protection_allocation_bucket
            FOREIGN KEY (bucket)
            REFERENCES ref.ref_protection_buckets(protection_bucket_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_core_saccr_results_counterparty_type'
          AND conrelid = 'core.core_saccr_results'::regclass
    ) THEN
        ALTER TABLE core.core_saccr_results
            ADD CONSTRAINT fk_core_saccr_results_counterparty_type
            FOREIGN KEY (counterparty_type)
            REFERENCES ref.ref_counterparty_types(counterparty_type_id);
    END IF;
END $$;

COMMIT;
