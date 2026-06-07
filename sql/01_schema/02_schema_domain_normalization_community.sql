-- =============================================================================
-- 02_schema_domain_normalization_community.sql
-- PATCH v2.2 — Normalisation stricte BCNF des domaines métiers
-- =============================================================================
-- Objectifs :
--   1. Remplacer les textes libres counterparty_type / protection_type / bucket
--      par des domaines référencés.
--   2. Normaliser les conditions composées des règles de mapping dans des tables
--      filles, au lieu de porter toute la logique dans condition_field/value.
--   3. Faire du bucket CRM la source unique du type FCP/UFCP dans les allocations.
--
-- À exécuter après 02g et avant les seeds 04/05/10.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Domaines de contreparties
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.ref_counterparty_types (
    counterparty_type_id VARCHAR(50) PRIMARY KEY,
    description TEXT,
    regulatory_family VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE ref.ref_counterparty_types IS
    'Domaine normalisé des types de contreparties utilisés par les expositions SA et SA-CCR.';

INSERT INTO ref.ref_counterparty_types (counterparty_type_id, description, regulatory_family) VALUES
('BANK',               'Banque / établissement bancaire générique', 'INSTITUTION'),
('INSTITUTION',        'Établissement au sens CRR', 'INSTITUTION'),
('FINANCIAL',          'Contrepartie financière générique', 'FINANCIAL'),
('HEDGE_FUND',         'Fonds spéculatif / hedge fund', 'FINANCIAL'),
('CENTRAL_GOVT',       'Administration centrale / gouvernement central', 'SOVEREIGN'),
('SOVEREIGN',          'Souverain générique', 'SOVEREIGN'),
('REGIONAL_GOVT',      'Administration régionale ou locale', 'SOVEREIGN'),
('PUBLIC_SECTOR',      'Entité du secteur public', 'PUBLIC_SECTOR'),
('MULTILATERAL_BANK',  'Banque multilatérale de développement', 'MDB'),
('INTL_ORG',           'Organisation internationale', 'INTERNATIONAL_ORG'),
('CORPORATE',          'Entreprise non financière générique', 'CORPORATE'),
('NFC',                'Non-financial corporation pour LCR/NSFR', 'CORPORATE'),
('RETAIL',             'Clientèle de détail', 'RETAIL'),
('OTHER',              'Autre type de contrepartie', 'OTHER')
ON CONFLICT (counterparty_type_id) DO UPDATE SET
    description = EXCLUDED.description,
    regulatory_family = EXCLUDED.regulatory_family,
    updated_at = NOW();

-- -----------------------------------------------------------------------------
-- 2. Domaines de protections CRM
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.ref_protection_types (
    protection_type_id VARCHAR(50) PRIMARY KEY,
    description TEXT,
    crm_family VARCHAR(50) NOT NULL CHECK (crm_family IN ('FCP', 'UFCP', 'OTHER')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE ref.ref_protection_types IS
    'Domaine normalisé des types de protection CRM : funded credit protection et unfunded credit protection.';

INSERT INTO ref.ref_protection_types (protection_type_id, description, crm_family) VALUES
('FCP',  'Funded Credit Protection : collatéral / sûreté financée réduisant l''EAD', 'FCP'),
('UFCP', 'Unfunded Credit Protection : garantie personnelle / dérivé de crédit substituant le RW', 'UFCP')
ON CONFLICT (protection_type_id) DO UPDATE SET
    description = EXCLUDED.description,
    crm_family = EXCLUDED.crm_family,
    updated_at = NOW();

CREATE TABLE IF NOT EXISTS ref.ref_protection_buckets (
    protection_bucket_id VARCHAR(100) PRIMARY KEY,
    description TEXT,
    protection_type_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (protection_type_id) REFERENCES ref.ref_protection_types(protection_type_id)
);

COMMENT ON TABLE ref.ref_protection_buckets IS
    'Domaine normalisé des buckets CRM produits par les règles RS_PROTECTION_BUCKET.';

INSERT INTO ref.ref_protection_buckets (protection_bucket_id, description, protection_type_id) VALUES
('COLLATERAL_CASH',           'Collatéral cash / espèces', 'FCP'),
('COLLATERAL_SOVEREIGN_BOND', 'Titre souverain éligible en collatéral', 'FCP'),
('COLLATERAL_CORPORATE_BOND', 'Obligation corporate éligible en collatéral', 'FCP'),
('COLLATERAL_EQUITY',         'Action ou indice actions éligible en collatéral', 'FCP'),
('COLLATERAL_GOLD',           'Or physique / assimilé éligible', 'FCP'),
('COLLATERAL_COVERED_BOND',   'Covered bond éligible en collatéral', 'FCP'),
('COLLATERAL_REAL_ESTATE',    'Sûreté immobilière', 'FCP'),
('GUARANTEE_SOVEREIGN',       'Garantie souveraine', 'UFCP'),
('GUARANTEE_BANK',            'Garantie bancaire / établissement', 'UFCP'),
('GUARANTEE_CORPORATE',       'Garantie corporate', 'UFCP'),
('GUARANTEE_MULTILATERAL',    'Garantie banque multilatérale / organisation assimilée', 'UFCP'),
('CDS',                       'Dérivé de crédit / CDS éligible', 'UFCP'),
('DEFAULT_FCP',               'Bucket FCP par défaut lorsque la protection n''est pas classifiée', 'FCP'),
('DEFAULT_UFCP',              'Bucket UFCP par défaut lorsque la protection n''est pas classifiée', 'UFCP')
ON CONFLICT (protection_bucket_id) DO UPDATE SET
    description = EXCLUDED.description,
    protection_type_id = EXCLUDED.protection_type_id,
    updated_at = NOW();

-- -----------------------------------------------------------------------------
-- 3. Tables normalisées de conditions pour les mappings
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.ref_mapping_rule_conditions (
    condition_id BIGSERIAL PRIMARY KEY,
    mapping_rule_id BIGINT NOT NULL,
    condition_field VARCHAR(100) NOT NULL,
    condition_operator VARCHAR(10) NOT NULL DEFAULT '=',
    condition_value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (mapping_rule_id) REFERENCES ref.ref_mapping_rules(mapping_rule_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_mapping_rule_conditions_natural
ON ref.ref_mapping_rule_conditions (mapping_rule_id, condition_field, condition_operator, condition_value);

COMMENT ON TABLE ref.ref_mapping_rule_conditions IS
    'Conditions atomiques normalisées des règles ref_mapping_rules. Une règle multi-critères porte plusieurs lignes.';

CREATE TABLE IF NOT EXISTS ref.ref_template_mapping_rule_conditions (
    condition_id BIGSERIAL PRIMARY KEY,
    template_mapping_rule_id BIGINT NOT NULL,
    condition_field VARCHAR(100) NOT NULL,
    condition_operator VARCHAR(10) NOT NULL DEFAULT '=',
    condition_value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (template_mapping_rule_id) REFERENCES ref.ref_template_mapping_rules(template_mapping_rule_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_template_mapping_rule_conditions_natural
ON ref.ref_template_mapping_rule_conditions (template_mapping_rule_id, condition_field, condition_operator, condition_value);

COMMENT ON TABLE ref.ref_template_mapping_rule_conditions IS
    'Conditions atomiques normalisées des règles ref_template_mapping_rules. Une règle multi-critères porte plusieurs lignes.';

-- -----------------------------------------------------------------------------
-- 4. Contraintes FK des domaines normalisés
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ref_counterparties_counterparty_type') THEN
        ALTER TABLE ref.ref_counterparties
            ADD CONSTRAINT fk_ref_counterparties_counterparty_type
            FOREIGN KEY (counterparty_type) REFERENCES ref.ref_counterparty_types(counterparty_type_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_stg_protections_protection_type') THEN
        ALTER TABLE stg.stg_protections
            ADD CONSTRAINT fk_stg_protections_protection_type
            FOREIGN KEY (protection_type) REFERENCES ref.ref_protection_types(protection_type_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_stg_protections_provider_type') THEN
        ALTER TABLE stg.stg_protections
            ADD CONSTRAINT fk_stg_protections_provider_type
            FOREIGN KEY (provider_type) REFERENCES ref.ref_counterparty_types(counterparty_type_id);
    END IF;

    -- Community v4.2.8 : la contrainte de la table SA-CCR est portée par
    -- sql/01_schema/engines/schema_saccr.sql.
    -- Le schéma de normalisation commun ne référence plus de table moteur
    -- potentiellement absente lorsque l'engine est désactivé.

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_core_protection_allocation_bucket') THEN
        ALTER TABLE core.core_protection_allocation
            ADD CONSTRAINT fk_core_protection_allocation_bucket
            FOREIGN KEY (bucket) REFERENCES ref.ref_protection_buckets(protection_bucket_id);
    END IF;
END $$;

COMMIT;
