-- =============================================================================
-- 01_schema_common_community.sql
-- Schéma commun BCNF public SA / SA-CCR : meta / stg / ref / core / rpt.
-- Dérivé de 02_schema_postgresql_bcnf_actualise_config_main.sql.
-- Les tables spécifiques à un moteur sont sorties dans sql/01_schema/engines/.
-- =============================================================================
-- Cible PostgreSQL V10 ultra pédagogique - Schéma BCNF.
-- Ce script implémente le schéma en Forme Normale de Boyce-Codd (BCNF).
-- Il vise à éliminer toute redondance et anomalie de mise à jour en :
-- - Extrayant les attributs non-clés dépendants d'une partie de la clé primaire.
-- - Assurant que chaque déterminant est une clé candidate.

-- ─────────────────────────────────────────────────────────────────────────────
-- PATCH v2.4 — script non destructif par défaut.
-- Les DROP SCHEMA CASCADE ont été déplacés dans :
--   sql/00_reset_database_dev_ONLY.sql
-- Ce dernier n'est exécuté QUE par reset_database_dev_ONLY.bat (avec saisie
-- explicite "RESET" pour confirmation) ou par python -m corep_crr3.bootstrap
-- avec le flag --reset (cf. bootstrap.py).
-- Ne JAMAIS réintroduire de DROP automatique dans le batch métier.
-- ─────────────────────────────────────────────────────────────────────────────

-- Création des schémas dédiés pour organiser les tables (idempotent)
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS rpt;

-- Commentaires pédagogiques sur l'organisation des schémas
COMMENT ON SCHEMA meta IS 'Schéma pour les tables de métadonnées et de contrôle des traitements (ex: batch_run_control).';
COMMENT ON SCHEMA stg IS 'Schéma pour les tables de staging (données brutes importées).';
COMMENT ON SCHEMA ref IS 'Schéma pour les tables de référence (paramètres, règles de décision, mappings, entités maîtresses).';
COMMENT ON SCHEMA core IS 'Schéma pour les tables de résultats des calculs et traitements métiers principaux.';
COMMENT ON SCHEMA rpt IS 'Schéma pour les tables de reporting et de traçabilité.';

-- Table technique: meta.schema_migrations
-- Suit les scripts SQL appliqués par bootstrap.py afin de rendre le bootstrap relançable.
CREATE TABLE IF NOT EXISTS meta.schema_migrations (
    script_name VARCHAR(255) PRIMARY KEY,
    checksum_sha256 VARCHAR(64) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    notes TEXT
);
COMMENT ON TABLE meta.schema_migrations IS 'Scripts SQL appliqués par bootstrap.py avec checksum SHA-256.';


-- Table: meta.batch_run_control
-- Gère le contrôle des exécutions de batchs.
CREATE TABLE IF NOT EXISTS meta.batch_run_control (
    batch_id VARCHAR(50) PRIMARY KEY, -- Identifiant unique du batch
    regulatory_version_id VARCHAR(50) NOT NULL, -- Référence à la version réglementaire appliquée
    reporting_date DATE NOT NULL, -- Date de reporting du batch
    start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- Horodatage de début du batch
    end_timestamp TIMESTAMP WITH TIME ZONE, -- Horodatage de fin du batch
    status VARCHAR(40) NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED', 'FAILED_CONTROLS', 'FAILED_RECONCILIATION', 'FAILED_ENGINE', 'PENDING')), -- Statut du batch
    loaded_rows INTEGER CHECK (loaded_rows >= 0), -- Nombre de lignes chargées
    rejected_rows INTEGER CHECK (rejected_rows >= 0), -- Nombre de lignes rejetées
    calculated_rows INTEGER CHECK (calculated_rows >= 0), -- Nombre de lignes calculées
    notes TEXT, -- Notes additionnelles sur le batch
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
COMMENT ON TABLE meta.batch_run_control IS 'Table de contrôle des exécutions de batchs, enregistrant les métadonnées de chaque traitement.';
COMMENT ON COLUMN meta.batch_run_control.batch_id IS 'Clé primaire: Identifiant unique et non modifiable du batch.';
COMMENT ON COLUMN meta.batch_run_control.regulatory_version_id IS 'Clé étrangère: Identifiant de la version réglementaire appliquée lors de ce batch.';
COMMENT ON COLUMN meta.batch_run_control.reporting_date IS 'Date à laquelle les données du rapport se réfèrent.';
COMMENT ON COLUMN meta.batch_run_control.start_timestamp IS 'Moment exact où le traitement par lot a commencé.';
COMMENT ON COLUMN meta.batch_run_control.end_timestamp IS 'Moment exact où le traitement par lot s''est terminé.';
COMMENT ON COLUMN meta.batch_run_control.status IS 'État actuel ou final du traitement par lot (ex: SUCCÈS, ÉCHEC, EN COURS).';
COMMENT ON COLUMN meta.batch_run_control.loaded_rows IS 'Nombre total d''enregistrements chargés avec succès.';
COMMENT ON COLUMN meta.batch_run_control.rejected_rows IS 'Nombre total d''enregistrements qui n''ont pas pu être traités.';
COMMENT ON COLUMN meta.batch_run_control.calculated_rows IS 'Nombre total d''enregistrements pour lesquels des calculs ont été effectués.';
COMMENT ON COLUMN meta.batch_run_control.notes IS 'Informations supplémentaires ou commentaires sur l''exécution du lot.';

-- Trigger pour mettre à jour `updated_at`
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_batch_run_control_timestamp ON meta.batch_run_control;
CREATE TRIGGER update_batch_run_control_timestamp
BEFORE UPDATE ON meta.batch_run_control
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_regulatory_versions
-- Centralise les informations sur les versions réglementaires.
CREATE TABLE IF NOT EXISTS ref.ref_regulatory_versions (
    regulatory_version_id VARCHAR(50) PRIMARY KEY, -- Identifiant unique de la version réglementaire
    description TEXT, -- Description de la version
    effective_date DATE NOT NULL, -- Date d'entrée en vigueur
    end_date DATE, -- Date de fin de validité (si applicable)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
COMMENT ON TABLE ref.ref_regulatory_versions IS 'Table de référence pour les versions réglementaires, centralisant leurs métadonnées.';
COMMENT ON COLUMN ref.ref_regulatory_versions.regulatory_version_id IS 'Clé primaire: Identifiant unique de la version réglementaire.';
COMMENT ON COLUMN ref.ref_regulatory_versions.description IS 'Description détaillée de la version réglementaire.';
COMMENT ON COLUMN ref.ref_regulatory_versions.effective_date IS 'Date à partir de laquelle cette version réglementaire est applicable.';
COMMENT ON COLUMN ref.ref_regulatory_versions.end_date IS 'Date de fin de validité de la version réglementaire, si elle est remplacée.';

DROP TRIGGER IF EXISTS update_ref_regulatory_versions_timestamp ON ref.ref_regulatory_versions;
CREATE TRIGGER update_ref_regulatory_versions_timestamp
BEFORE UPDATE ON ref.ref_regulatory_versions
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_regulatory_version'
          AND conrelid = 'meta.batch_run_control'::regclass
    ) THEN
        ALTER TABLE meta.batch_run_control
            ADD CONSTRAINT fk_regulatory_version
            FOREIGN KEY (regulatory_version_id)
            REFERENCES ref.ref_regulatory_versions(regulatory_version_id);
    END IF;
END $$;


-- Table: ref.ref_counterparties
-- Centralise les informations sur les contreparties.
CREATE TABLE IF NOT EXISTS ref.ref_counterparties (
    counterparty_id VARCHAR(100) PRIMARY KEY, -- Identifiant unique de la contrepartie
    counterparty_type VARCHAR(50) NOT NULL, -- Type de la contrepartie (ex: 'BANK', 'CORPORATE', 'INDIVIDUAL')
    name TEXT, -- Nom de la contrepartie
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
COMMENT ON TABLE ref.ref_counterparties IS 'Table de référence pour les contreparties, évitant la redondance des types de contreparties.';
COMMENT ON COLUMN ref.ref_counterparties.counterparty_id IS 'Clé primaire: Identifiant unique de la contrepartie.';
COMMENT ON COLUMN ref.ref_counterparties.counterparty_type IS 'Type catégoriel de la contrepartie.';

DROP TRIGGER IF EXISTS update_ref_counterparties_timestamp ON ref.ref_counterparties;
CREATE TRIGGER update_ref_counterparties_timestamp
BEFORE UPDATE ON ref.ref_counterparties
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_asset_classes
-- Centralise les informations sur les classes d'actifs.
CREATE TABLE IF NOT EXISTS ref.ref_asset_classes (
    asset_class_id VARCHAR(50) PRIMARY KEY, -- Identifiant unique de la classe d'actifs
    description TEXT, -- Description de la classe d'actifs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
COMMENT ON TABLE ref.ref_asset_classes IS 'Table de référence pour les classes d''actifs.';
COMMENT ON COLUMN ref.ref_asset_classes.asset_class_id IS 'Clé primaire: Identifiant unique de la classe d''actifs.';

DROP TRIGGER IF EXISTS update_ref_asset_classes_timestamp ON ref.ref_asset_classes;
CREATE TRIGGER update_ref_asset_classes_timestamp
BEFORE UPDATE ON ref.ref_asset_classes
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_product_types
-- Centralise les informations sur les types de produits.
CREATE TABLE IF NOT EXISTS ref.ref_product_types (
    product_type_id VARCHAR(50) PRIMARY KEY, -- Identifiant unique du type de produit
    description TEXT, -- Description du type de produit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
COMMENT ON TABLE ref.ref_product_types IS 'Table de référence pour les types de produits.';
COMMENT ON COLUMN ref.ref_product_types.product_type_id IS 'Clé primaire: Identifiant unique du type de produit.';

DROP TRIGGER IF EXISTS update_ref_product_types_timestamp ON ref.ref_product_types;
CREATE TRIGGER update_ref_product_types_timestamp
BEFORE UPDATE ON ref.ref_product_types
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: stg.stg_exposures
-- Données de staging pour les expositions (référencement des entités maîtresses).
CREATE TABLE IF NOT EXISTS stg.stg_exposures (
    batch_id VARCHAR(50) NOT NULL, -- Référence au batch de chargement
    exposure_id VARCHAR(100) NOT NULL, -- Identifiant unique de l'exposition
    counterparty_id VARCHAR(100) NOT NULL, -- Référence à la contrepartie
    asset_class_id VARCHAR(50), -- Référence à la classe d'actifs
    product_type_id VARCHAR(50), -- Référence au type de produit
    calculation_approach VARCHAR(20), -- Approche prudentielle publique : 'SA'. NULL ⇒ traité en standard (SA) par défaut.
    exposure_amount NUMERIC(18, 4) CHECK (exposure_amount >= 0), -- Montant de l'exposition
    provision_amount NUMERIC(18, 4) CHECK (provision_amount >= 0), -- Montant de la provision
    guarantee_amount NUMERIC(18, 4) CHECK (guarantee_amount >= 0), -- Montant de la garantie
    currency VARCHAR(3) CHECK (LENGTH(currency) = 3), -- Devise (ISO 4217)
    maturity_months INTEGER CHECK (maturity_months >= 0), -- Maturité en mois
    credit_quality_step VARCHAR(20), -- CQS/ECAI normalisé pour RW standard (ex: 1..6, UNRATED)
    ltv_ratio NUMERIC(9, 4) CHECK (ltv_ratio IS NULL OR ltv_ratio >= 0), -- Loan-to-value pour expositions garanties par immobilier
    exposure_subtype VARCHAR(100), -- Sous-type réglementaire : IPRE, ADC, TRANSADC, RETAIL_TRANS_ACTOR, etc.
    delinquent_flag BOOLEAN DEFAULT FALSE, -- Indicateur de défaillance
    supporting_sme_flag BOOLEAN DEFAULT FALSE, -- Indicateur de soutien aux PME
    supporting_infra_flag BOOLEAN DEFAULT FALSE, -- Indicateur de soutien aux infrastructures
    PRIMARY KEY (batch_id, exposure_id), -- Clé primaire composite
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (counterparty_id) REFERENCES ref.ref_counterparties(counterparty_id),
    FOREIGN KEY (asset_class_id) REFERENCES ref.ref_asset_classes(asset_class_id),
    FOREIGN KEY (product_type_id) REFERENCES ref.ref_product_types(product_type_id)
);
COMMENT ON TABLE stg.stg_exposures IS 'Table de staging pour les données d''expositions financières, normalisée en BCNF.';
COMMENT ON COLUMN stg.stg_exposures.batch_id IS 'Clé étrangère: Identifiant du batch ayant chargé cette exposition.';
COMMENT ON COLUMN stg.stg_exposures.exposure_id IS 'Identifiant unique de l''exposition au sein du batch.';
COMMENT ON COLUMN stg.stg_exposures.counterparty_id IS 'Clé étrangère: Identifiant de la contrepartie associée à l''exposition.';
COMMENT ON COLUMN stg.stg_exposures.asset_class_id IS 'Clé étrangère: Identifiant de la classe d''actifs.';
COMMENT ON COLUMN stg.stg_exposures.product_type_id IS 'Clé étrangère: Identifiant du type de produit.';
COMMENT ON COLUMN stg.stg_exposures.credit_quality_step IS 'Credit Quality Step/ECAI normalisé utilisé par les règles RW CRR3.';
COMMENT ON COLUMN stg.stg_exposures.ltv_ratio IS 'Loan-to-value normalisé utilisé pour les règles RW immobilières CRR3.';
COMMENT ON COLUMN stg.stg_exposures.exposure_subtype IS 'Sous-type réglementaire optionnel permettant de discriminer les règles RW sans dénormaliser la classe d actifs.';

-- Index sur counterparty_id pour les recherches fréquentes
CREATE INDEX IF NOT EXISTS idx_stg_exposures_counterparty_id ON stg.stg_exposures (counterparty_id);


-- Table: stg.stg_protections
-- Données de staging pour les protections.
CREATE TABLE IF NOT EXISTS stg.stg_protections (
    batch_id VARCHAR(50) NOT NULL, -- Référence au batch de chargement
    protection_id VARCHAR(100) NOT NULL, -- Identifiant unique de la protection
    exposure_id VARCHAR(100) NOT NULL, -- Référence à l'exposition associée
    protection_type VARCHAR(50), -- Type de protection
    provider_type VARCHAR(50), -- Type de fournisseur de protection
    protection_value NUMERIC(18, 4) CHECK (protection_value >= 0), -- Valeur de la protection
    currency VARCHAR(3) CHECK (LENGTH(currency) = 3), -- Devise
    maturity_months INTEGER CHECK (maturity_months >= 0), -- Maturité en mois
    allocation_rank INTEGER CHECK (allocation_rank >= 0), -- Rang d'allocation
    collateral_type VARCHAR(100), -- Type de collatéral FCP : CASH_DEPOSIT, SOVEREIGN_BOND_EEA, CORPORATE_BOND_IG, etc.
    collateral_grade VARCHAR(20), -- Grade/qualité du collatéral : AAA_AA, A_BBB, etc.
    issuer_type VARCHAR(50), -- Type d'émetteur du collatéral ou du protecteur
    protection_subtype VARCHAR(100), -- Sous-type : GUARANTEE, CDS, CASH, GOLD, EQUITY_MAIN_INDEX, etc.
    PRIMARY KEY (batch_id, protection_id), -- Clé primaire composite
    FOREIGN KEY (batch_id, exposure_id) REFERENCES stg.stg_exposures(batch_id, exposure_id)
);
COMMENT ON TABLE stg.stg_protections IS 'Table de staging pour les protections associées aux expositions.';
COMMENT ON COLUMN stg.stg_protections.batch_id IS 'Clé étrangère: Identifiant du batch ayant chargé cette protection.';
COMMENT ON COLUMN stg.stg_protections.protection_id IS 'Identifiant unique de la protection.';
COMMENT ON COLUMN stg.stg_protections.exposure_id IS 'Clé étrangère: Identifiant de l''exposition à laquelle cette protection est liée.';
COMMENT ON COLUMN stg.stg_protections.collateral_type IS 'Type de collatéral utilisé pour bucketer la FCP et appliquer le haircut réglementaire.';
COMMENT ON COLUMN stg.stg_protections.collateral_grade IS 'Grade/ECAI du collatéral utilisé par les haircuts superviseurs.';
COMMENT ON COLUMN stg.stg_protections.issuer_type IS 'Type d émetteur ou de fournisseur pour les règles CRM.';
COMMENT ON COLUMN stg.stg_protections.protection_subtype IS 'Sous-type de protection : garantie, CDS, cash, obligation souveraine, equity, etc.';

-- Index simple conservé pour compatibilité avec les recherches ad hoc par exposition.
CREATE INDEX IF NOT EXISTS idx_stg_protections_exposure_id ON stg.stg_protections (exposure_id);

-- PATCH v2.8 — index composite aligné avec le préchargement CRM batch.
-- Requête cible : WHERE batch_id = ? ORDER BY exposure_id, allocation_rank, protection_id.
-- Objectif : éviter les scans/sorts coûteux lorsque le portefeuille contient beaucoup
-- d'expositions et de protections.
CREATE INDEX IF NOT EXISTS idx_stg_protections_batch_exposure_rank
ON stg.stg_protections (batch_id, exposure_id, allocation_rank, protection_id);


-- NOTE Community v4.2.8 — la table staging SA-CCR est créée par
-- sql/01_schema/engines/schema_saccr.sql. Le socle commun ne crée aucun objet
-- appartenant à un moteur privé.


-- Table: stg.stg_rejected_rows
-- Enregistre les lignes rejetées lors du chargement des données.
CREATE TABLE IF NOT EXISTS stg.stg_rejected_rows (
    id BIGSERIAL PRIMARY KEY, -- Identifiant auto-incrémenté de la ligne rejetée
    batch_id VARCHAR(50) NOT NULL, -- Référence au batch où le rejet a eu lieu
    dataset_name VARCHAR(100) NOT NULL, -- Nom du dataset d'où provient la ligne
    source_key TEXT, -- Clé ou identifiant de la ligne rejetée dans la source
    rejection_reason TEXT NOT NULL, -- Raison du rejet
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE stg.stg_rejected_rows IS 'Enregistre les détails des lignes de données qui ont été rejetées pendant le processus de chargement.';
COMMENT ON COLUMN stg.stg_rejected_rows.id IS 'Clé primaire: Identifiant unique auto-généré pour chaque enregistrement de rejet.';
COMMENT ON COLUMN stg.stg_rejected_rows.batch_id IS 'Clé étrangère: Identifiant du batch pendant lequel la ligne a été rejetée.';

-- Index sur batch_id et dataset_name pour les analyses de rejet
CREATE INDEX IF NOT EXISTS idx_stg_rejected_rows_batch_dataset ON stg.stg_rejected_rows (batch_id, dataset_name);


-- Table: ref.ref_runtime_parameters
-- Paramètres de configuration dynamiques.
CREATE TABLE IF NOT EXISTS ref.ref_runtime_parameters (
    regulatory_version_id VARCHAR(50) NOT NULL, -- Référence à la version réglementaire
    parameter_name VARCHAR(100) NOT NULL, -- Nom du paramètre
    parameter_type VARCHAR(50), -- Type du paramètre
    parameter_value TEXT, -- Valeur du paramètre
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (regulatory_version_id, parameter_name),
    FOREIGN KEY (regulatory_version_id) REFERENCES ref.ref_regulatory_versions(regulatory_version_id)
);
COMMENT ON TABLE ref.ref_runtime_parameters IS 'Table de référence pour les paramètres de configuration dynamiques utilisés par l''application.';
COMMENT ON COLUMN ref.ref_runtime_parameters.regulatory_version_id IS 'Clé primaire et étrangère: Version réglementaire à laquelle ce paramètre est lié.';
COMMENT ON COLUMN ref.ref_runtime_parameters.parameter_name IS 'Clé primaire: Nom unique du paramètre au sein d''une version réglementaire.';

DROP TRIGGER IF EXISTS update_ref_runtime_parameters_timestamp ON ref.ref_runtime_parameters;
CREATE TRIGGER update_ref_runtime_parameters_timestamp
BEFORE UPDATE ON ref.ref_runtime_parameters
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_decision_rule_sets
-- Ensembles de règles de décision.
CREATE TABLE IF NOT EXISTS ref.ref_decision_rule_sets (
    rule_set_id BIGSERIAL PRIMARY KEY, -- Identifiant unique de l'ensemble de règles
    regulatory_version_id VARCHAR(50) NOT NULL, -- Référence à la version réglementaire
    rule_set_name VARCHAR(100) NOT NULL UNIQUE, -- Nom de l'ensemble de règles
    target_domain VARCHAR(100), -- Domaine d'application des règles
    is_active BOOLEAN NOT NULL DEFAULT TRUE, -- Indique si l'ensemble de règles est actif
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (regulatory_version_id) REFERENCES ref.ref_regulatory_versions(regulatory_version_id)
);
COMMENT ON TABLE ref.ref_decision_rule_sets IS 'Table de référence définissant les ensembles de règles de décision utilisés dans les calculs.';
COMMENT ON COLUMN ref.ref_decision_rule_sets.rule_set_id IS 'Clé primaire: Identifiant unique auto-généré pour l''ensemble de règles.';
COMMENT ON COLUMN ref.ref_decision_rule_sets.regulatory_version_id IS 'Clé étrangère: Version réglementaire à laquelle cet ensemble de règles est lié.';
COMMENT ON COLUMN ref.ref_decision_rule_sets.rule_set_name IS 'Nom unique de l''ensemble de règles.';

DROP TRIGGER IF EXISTS update_ref_decision_rule_sets_timestamp ON ref.ref_decision_rule_sets;
CREATE TRIGGER update_ref_decision_rule_sets_timestamp
BEFORE UPDATE ON ref.ref_decision_rule_sets
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_decision_rules
-- Règles de décision individuelles (simplifiées pour BCNF).
CREATE TABLE IF NOT EXISTS ref.ref_decision_rules (
    rule_id BIGSERIAL PRIMARY KEY, -- Identifiant unique de la règle
    rule_set_id BIGINT NOT NULL, -- Référence à l'ensemble de règles
    priority INTEGER NOT NULL CHECK (priority >= 0), -- Priorité de la règle
    result_key VARCHAR(100) NOT NULL, -- Clé du résultat de la règle
    result_value TEXT NOT NULL, -- Valeur du résultat de la règle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (rule_set_id) REFERENCES ref.ref_decision_rule_sets(rule_set_id)
);
COMMENT ON TABLE ref.ref_decision_rules IS 'Table de référence pour les règles de décision individuelles, normalisée en BCNF.';
COMMENT ON COLUMN ref.ref_decision_rules.rule_id IS 'Clé primaire: Identifiant unique auto-généré pour chaque règle de décision.';
COMMENT ON COLUMN ref.ref_decision_rules.rule_set_id IS 'Clé étrangère: Identifiant de l''ensemble de règles auquel cette règle appartient.';
COMMENT ON COLUMN ref.ref_decision_rules.priority IS 'Ordre d''évaluation de la règle au sein de son ensemble.';

DROP TRIGGER IF EXISTS update_ref_decision_rules_timestamp ON ref.ref_decision_rules;
CREATE TRIGGER update_ref_decision_rules_timestamp
BEFORE UPDATE ON ref.ref_decision_rules
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- Table: ref.ref_rule_conditions
-- Conditions spécifiques pour chaque règle de décision.
CREATE TABLE IF NOT EXISTS ref.ref_rule_conditions (
    condition_id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT NOT NULL, -- Référence à la règle de décision
    condition_field VARCHAR(100) NOT NULL, -- Champ de la condition
    condition_operator VARCHAR(10) NOT NULL, -- Opérateur de la condition (ex: '=', '>', '<', 'LIKE')
    condition_value TEXT NOT NULL, -- Valeur de la condition
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (rule_id) REFERENCES ref.ref_decision_rules(rule_id)
);
COMMENT ON TABLE ref.ref_rule_conditions IS 'Table de référence pour les conditions individuelles de chaque règle de décision, permettant une flexibilité et une normalisation.';
COMMENT ON COLUMN ref.ref_rule_conditions.condition_id IS 'Clé primaire: Identifiant unique auto-généré pour chaque condition.';
COMMENT ON COLUMN ref.ref_rule_conditions.rule_id IS 'Clé étrangère: Identifiant de la règle de décision à laquelle cette condition appartient.';

DROP TRIGGER IF EXISTS update_ref_rule_conditions_timestamp ON ref.ref_rule_conditions;
CREATE TRIGGER update_ref_rule_conditions_timestamp
BEFORE UPDATE ON ref.ref_rule_conditions
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- PATCH v2 P0 : évite les doublons de conditions lors des seeds enrichis.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ref_rule_conditions_natural
ON ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value);



-- Table: ref.ref_mapping_rules
-- Règles de mapping génériques.
CREATE TABLE IF NOT EXISTS ref.ref_mapping_rules (
    mapping_rule_id BIGSERIAL PRIMARY KEY,
    regulatory_version_id VARCHAR(50) NOT NULL, -- Référence à la version réglementaire
    framework VARCHAR(50) NOT NULL, -- Cadre réglementaire public : COREP
    source_table VARCHAR(100) NOT NULL, -- Table source des données
    condition_field VARCHAR(100), -- Champ de condition pour le mapping
    condition_value TEXT, -- Colonne transitoire de bootstrap, supprimée par le post-seed v4.2.3
    condition_set_key VARCHAR(64), -- Identifiant stable du groupe de conditions normalisé
    metric_name VARCHAR(100) NOT NULL, -- Nom de la métrique cible
    output_code VARCHAR(100) NOT NULL, -- Code de sortie/reporting
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (regulatory_version_id) REFERENCES ref.ref_regulatory_versions(regulatory_version_id)
);
COMMENT ON TABLE ref.ref_mapping_rules IS 'Règles de mapping ; les conditions atomiques sont portées exclusivement par ref_mapping_rule_conditions après le post-seed v4.2.3.';
COMMENT ON COLUMN ref.ref_mapping_rules.mapping_rule_id IS 'Clé primaire: Identifiant unique auto-généré pour chaque règle de mappage.';
COMMENT ON COLUMN ref.ref_mapping_rules.regulatory_version_id IS 'Clé étrangère: Version réglementaire à laquelle cette règle de mappage est liée.';

-- Compatibilité de bootstrap réexécutable : sur une base déjà normalisée, ces
-- colonnes ont été retirées par 99_mapping_conditions_bcnf.sql. Elles sont
-- recréées temporairement pour charger les fichiers d'authoring historiques,
-- puis supprimées de nouveau avant la fin du bootstrap.
ALTER TABLE ref.ref_mapping_rules
    ADD COLUMN IF NOT EXISTS condition_field VARCHAR(100),
    ADD COLUMN IF NOT EXISTS condition_value TEXT;

DROP TRIGGER IF EXISTS update_ref_mapping_rules_timestamp ON ref.ref_mapping_rules;
CREATE TRIGGER update_ref_mapping_rules_timestamp
BEFORE UPDATE ON ref.ref_mapping_rules
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_template_mapping_rules
-- Règles de mapping spécifiques aux templates.
CREATE TABLE IF NOT EXISTS ref.ref_template_mapping_rules (
    template_mapping_rule_id BIGSERIAL PRIMARY KEY,
    regulatory_version_id VARCHAR(50) NOT NULL, -- Référence à la version réglementaire
    framework VARCHAR(50) NOT NULL,
    template_id VARCHAR(100) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    condition_field VARCHAR(100),
    condition_value TEXT, -- Colonne transitoire de bootstrap, supprimée par le post-seed v4.2.3
    condition_set_key VARCHAR(64), -- Identifiant stable du groupe de conditions normalisé
    metric_name VARCHAR(100) NOT NULL,
    output_cell_code VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (regulatory_version_id) REFERENCES ref.ref_regulatory_versions(regulatory_version_id)
);
COMMENT ON TABLE ref.ref_template_mapping_rules IS 'Règles de mapping template ; les conditions atomiques sont portées exclusivement par la table fille après le post-seed v4.2.3.';
COMMENT ON COLUMN ref.ref_template_mapping_rules.template_mapping_rule_id IS 'Clé primaire: Identifiant unique auto-généré pour chaque règle de mappage de template.';
COMMENT ON COLUMN ref.ref_template_mapping_rules.regulatory_version_id IS 'Clé étrangère: Version réglementaire à laquelle cette règle de mappage est liée.';

ALTER TABLE ref.ref_template_mapping_rules
    ADD COLUMN IF NOT EXISTS condition_field VARCHAR(100),
    ADD COLUMN IF NOT EXISTS condition_value TEXT;

DROP TRIGGER IF EXISTS update_ref_template_mapping_rules_timestamp ON ref.ref_template_mapping_rules;
CREATE TRIGGER update_ref_template_mapping_rules_timestamp
BEFORE UPDATE ON ref.ref_template_mapping_rules
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: ref.ref_supporting_factor_rules
-- Règles pour les facteurs de soutien/ajustement.
CREATE TABLE IF NOT EXISTS ref.ref_supporting_factor_rules (
    factor_rule_id BIGSERIAL PRIMARY KEY,
    regulatory_version_id VARCHAR(50) NOT NULL, -- Référence à la version réglementaire
    factor_code VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL CHECK (priority >= 0),
    eligibility_field VARCHAR(100),
    eligibility_operator VARCHAR(10),
    eligibility_value TEXT,
    multiplier NUMERIC(9, 4) NOT NULL CHECK (multiplier >= 0),
    applies_to_metric VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (regulatory_version_id) REFERENCES ref.ref_regulatory_versions(regulatory_version_id)
);
COMMENT ON TABLE ref.ref_supporting_factor_rules IS 'Table de référence pour les règles de facteurs de soutien ou d''ajustement appliqués aux calculs, normalisée en BCNF.';
COMMENT ON COLUMN ref.ref_supporting_factor_rules.factor_rule_id IS 'Clé primaire: Identifiant unique auto-généré pour chaque règle de facteur de soutien.';
COMMENT ON COLUMN ref.ref_supporting_factor_rules.regulatory_version_id IS 'Clé étrangère: Version réglementaire à laquelle cette règle de facteur est liée.';

DROP TRIGGER IF EXISTS update_ref_supporting_factor_rules_timestamp ON ref.ref_supporting_factor_rules;
CREATE TRIGGER update_ref_supporting_factor_rules_timestamp
BEFORE UPDATE ON ref.ref_supporting_factor_rules
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();


-- Table: core.core_standard_results
-- Résultats standard des calculs (nettoyée pour BCNF).
-- PATCH v2.1 BCNF : partitionnement retiré. La PK (batch_id, exposure_id)
-- est référencée par core_protection_allocation ; PostgreSQL impose que toute
-- PK/UNIQUE d'une table partitionnée contienne la clé de partition.
-- On conserve donc une table non partitionnée pour cohérence FK/PK.
CREATE TABLE IF NOT EXISTS core.core_standard_results (
    batch_id VARCHAR(50) NOT NULL,
    exposure_id VARCHAR(100) NOT NULL,
    counterparty_id VARCHAR(100) NOT NULL,
    asset_class_id VARCHAR(50),
    product_type_id VARCHAR(50),
    gross_exposure NUMERIC(18, 4) CHECK (gross_exposure >= 0),
    provision_amount NUMERIC(18, 4) CHECK (provision_amount >= 0),
    ead_pre_crm NUMERIC(18, 4) CHECK (ead_pre_crm >= 0),
    ead_post_fcp NUMERIC(18, 4) CHECK (ead_post_fcp >= 0),
    total_fcp_allocated NUMERIC(18, 4) CHECK (total_fcp_allocated >= 0),
    risk_weight_base NUMERIC(9, 4) CHECK (risk_weight_base >= 0),
    risk_weight_substituted NUMERIC(9, 4) CHECK (risk_weight_substituted >= 0),
    rwa_post_crm NUMERIC(18, 4) CHECK (rwa_post_crm >= 0),
    supporting_factor_multiplier NUMERIC(9, 4) CHECK (supporting_factor_multiplier >= 0),
    supporting_factor_codes TEXT,
    rwa_final NUMERIC(18, 4) CHECK (rwa_final >= 0),

    ccf_applied NUMERIC(9, 4) CHECK (ccf_applied >= 0),
    ccf_bucket VARCHAR(50),
    rw_rule_source VARCHAR(50),
    rw_bucket VARCHAR(100),
    cqs_used INTEGER,
    ltv_bucket VARCHAR(50),
    currency_mismatch_multiplier NUMERIC(9, 4) CHECK (currency_mismatch_multiplier >= 0),
    ead_after_ufcp NUMERIC(18, 4) CHECK (ead_after_ufcp >= 0),
    rwa_before_supporting_factor NUMERIC(18, 4) CHECK (rwa_before_supporting_factor >= 0),
    capital_requirement_8pct NUMERIC(18, 4) CHECK (capital_requirement_8pct >= 0),
    PRIMARY KEY (batch_id, exposure_id),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (counterparty_id) REFERENCES ref.ref_counterparties(counterparty_id),
    FOREIGN KEY (asset_class_id) REFERENCES ref.ref_asset_classes(asset_class_id),
    FOREIGN KEY (product_type_id) REFERENCES ref.ref_product_types(product_type_id)
);
-- Migration idempotente v6.2.1 : colonnes de traçabilité SA.
ALTER TABLE core.core_standard_results
    ADD COLUMN IF NOT EXISTS ccf_applied NUMERIC(9, 4) CHECK (ccf_applied >= 0),
    ADD COLUMN IF NOT EXISTS ccf_bucket VARCHAR(50),
    ADD COLUMN IF NOT EXISTS rw_rule_source VARCHAR(50),
    ADD COLUMN IF NOT EXISTS rw_bucket VARCHAR(100),
    ADD COLUMN IF NOT EXISTS cqs_used INTEGER,
    ADD COLUMN IF NOT EXISTS ltv_bucket VARCHAR(50),
    ADD COLUMN IF NOT EXISTS currency_mismatch_multiplier NUMERIC(9, 4) CHECK (currency_mismatch_multiplier >= 0),
    ADD COLUMN IF NOT EXISTS ead_after_ufcp NUMERIC(18, 4) CHECK (ead_after_ufcp >= 0),
    ADD COLUMN IF NOT EXISTS rwa_before_supporting_factor NUMERIC(18, 4) CHECK (rwa_before_supporting_factor >= 0),
    ADD COLUMN IF NOT EXISTS capital_requirement_8pct NUMERIC(18, 4) CHECK (capital_requirement_8pct >= 0);
COMMENT ON TABLE core.core_standard_results IS 'Table des résultats standardisés des calculs de risque de crédit, normalisée en BCNF et partitionnée.';
COMMENT ON COLUMN core.core_standard_results.batch_id IS 'Clé étrangère: Identifiant du batch ayant généré ces résultats.';
COMMENT ON COLUMN core.core_standard_results.exposure_id IS 'Identifiant unique de l''exposition analysée.';

-- Index sur counterparty_id et reporting_date pour les analyses de résultats
CREATE INDEX IF NOT EXISTS idx_core_standard_results_batch_cp ON core.core_standard_results (batch_id, counterparty_id);

-- Exemple de partitionnement par liste (à adapter selon les besoins réels)
-- CREATE TABLE core.core_standard_results_y2023m01 PARTITION OF core.core_standard_results FOR VALUES IN ('2023-01-01');
-- CREATE TABLE core.core_standard_results_y2023m02 PARTITION OF core.core_standard_results FOR VALUES IN ('2023-02-01');


-- Table: core.core_protection_allocation
-- Allocation des protections aux expositions.
CREATE TABLE IF NOT EXISTS core.core_protection_allocation (
    batch_id VARCHAR(50) NOT NULL,
    exposure_id VARCHAR(100) NOT NULL,
    protection_id VARCHAR(100) NOT NULL,
    bucket VARCHAR(50) NOT NULL,
    allocated_amount NUMERIC(18, 4) CHECK (allocated_amount >= 0),
    effect_type VARCHAR(50),
    PRIMARY KEY (batch_id, exposure_id, protection_id),
    FOREIGN KEY (batch_id, exposure_id) REFERENCES core.core_standard_results(batch_id, exposure_id)
);
COMMENT ON TABLE core.core_protection_allocation IS 'Allocations CRM normalisées : le type FCP/UFCP est déterminé par le bucket référencé.';

-- Index sur protection_id pour les analyses d'allocation
CREATE INDEX IF NOT EXISTS idx_core_protection_allocation_protection_id ON core.core_protection_allocation (protection_id);


-- NOTE Community v4.2.8 — la table de résultats SA-CCR est créée dans son
-- schéma moteur dédié. Le socle commun reste limité aux entités publiques
-- transverses : meta, ref, staging SA, core standard/CRM et reporting COREP.


-- Table: rpt.rpt_rule_snapshot
-- Snapshot des règles appliquées à un batch.
CREATE TABLE IF NOT EXISTS rpt.rpt_rule_snapshot (
    batch_id VARCHAR(50) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    rule_payload JSONB, -- Contenu JSON des règles (PostgreSQL JSONB pour l'efficacité)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, source_table),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE rpt.rpt_rule_snapshot IS 'Enregistre un instantané des règles de décision et de mappage utilisées pour un batch spécifique.';


-- Table: rpt.rpt_decision_rule_trace
-- Traçabilité des règles de décision appliquées.
CREATE TABLE IF NOT EXISTS rpt.rpt_decision_rule_trace (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    target_domain VARCHAR(100),
    context_key TEXT,
    rule_id BIGINT, -- Référence à la règle appliquée
    rule_set_id BIGINT, -- Référence à l'ensemble de règles
    result_key VARCHAR(100),
    result_value TEXT,
    match_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (rule_id) REFERENCES ref.ref_decision_rules(rule_id),
    FOREIGN KEY (rule_set_id) REFERENCES ref.ref_decision_rule_sets(rule_set_id)
);
COMMENT ON TABLE rpt.rpt_decision_rule_trace IS 'Table de traçabilité détaillant quelles règles de décision ont été appliquées et leurs résultats.';

-- Index sur batch_id et context_key pour la traçabilité
CREATE INDEX IF NOT EXISTS idx_rpt_decision_rule_trace_batch_context ON rpt.rpt_decision_rule_trace (batch_id, context_key);


-- Table: rpt.rpt_mapping_rule_trace
-- Traçabilité des règles de mapping appliquées.
CREATE TABLE IF NOT EXISTS rpt.rpt_mapping_rule_trace (
    trace_id VARCHAR(100) PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    mapping_rule_id BIGINT, -- Référence à la règle de mapping
    framework VARCHAR(50) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_key TEXT,
    rule_grain TEXT,
    matched_rule TEXT,
    metric_name VARCHAR(100),
    output_code VARCHAR(100),
    amount NUMERIC(18, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (mapping_rule_id) REFERENCES ref.ref_mapping_rules(mapping_rule_id)
);
COMMENT ON TABLE rpt.rpt_mapping_rule_trace IS 'Table de traçabilité détaillant comment les données sources ont été mappées vers les métriques de reporting.';

-- Index sur batch_id et source_key pour la traçabilité des mappings
CREATE INDEX IF NOT EXISTS idx_rpt_mapping_rule_trace_batch_source ON rpt.rpt_mapping_rule_trace (batch_id, source_key);


-- Table: rpt.rpt_corep_premap
-- Données pré-mappées pour COREPT.
CREATE TABLE IF NOT EXISTS rpt.rpt_corep_premap (
    batch_id VARCHAR(50) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_key TEXT,
    output_code VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100),
    amount NUMERIC(18, 4),
    framework VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, output_code, source_table, source_key),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE rpt.rpt_corep_premap IS 'Table des données pré-mappées spécifiquement pour les rapports COREPT.';

-- Index sur reporting_date et output_code pour les requêtes de reporting
CREATE INDEX IF NOT EXISTS idx_rpt_corep_premap_batch_output ON rpt.rpt_corep_premap (batch_id, output_code);


-- La pré-cartographie financière privée n'est pas distribuée dans l'édition Community.

-- Table: rpt.rpt_template_premap
-- Données pré-mappées pour les templates génériques.
CREATE TABLE IF NOT EXISTS rpt.rpt_template_premap (
    batch_id VARCHAR(50) NOT NULL,
    framework VARCHAR(50) NOT NULL,
    template_id VARCHAR(100) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_key TEXT,
    output_cell_code VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100),
    amount NUMERIC(18, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, framework, template_id, output_cell_code, source_table, source_key),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE rpt.rpt_template_premap IS 'Table des données pré-mappées pour les templates de reporting génériques.';

-- Index sur template_id et reporting_date pour les requêtes de reporting par template
CREATE INDEX IF NOT EXISTS idx_rpt_template_premap_batch_template ON rpt.rpt_template_premap (batch_id, template_id);


-- Table: rpt.rpt_controls
-- Contrôles de reporting.
CREATE TABLE IF NOT EXISTS rpt.rpt_controls (
    batch_id VARCHAR(50) NOT NULL,
    control_name VARCHAR(100) NOT NULL,
    control_value NUMERIC(18, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, control_name),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE rpt.rpt_controls IS 'Table enregistrant les valeurs des contrôles de reporting pour un batch donné.';


-- Table: rpt.rpt_reconciliation
-- Résultats de réconciliation.
CREATE TABLE IF NOT EXISTS rpt.rpt_reconciliation (
    batch_id VARCHAR(50) NOT NULL,
    control_name VARCHAR(100) NOT NULL,
    left_amount NUMERIC(18, 4),
    right_amount NUMERIC(18, 4),
    gap NUMERIC(18, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, control_name),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE rpt.rpt_reconciliation IS 'Table des résultats de réconciliation entre différentes sources ou calculs.';


-- Table: rpt.rpt_quality_findings
-- Statuts structurés des contrôles fail-closed (v6.0.1).
CREATE TABLE IF NOT EXISTS rpt.rpt_quality_findings (
    batch_id VARCHAR(50) NOT NULL,
    domain VARCHAR(30) NOT NULL,
    finding_code VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('PASS', 'WARNING', 'FAIL', 'NOT_APPLICABLE', 'NOT_EXECUTED')
    ),
    mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    observed NUMERIC(24, 6),
    expected NUMERIC(24, 6),
    gap NUMERIC(24, 6),
    tolerance NUMERIC(24, 6),
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, domain, finding_code),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id)
);
COMMENT ON TABLE rpt.rpt_quality_findings IS
'Résultats structurés des quality gates utilisés pour bloquer les batches et exports non conformes.';


-- Table: rpt.rpt_supporting_factor_trace
-- Traçabilité des facteurs de soutien appliqués.
CREATE TABLE IF NOT EXISTS rpt.rpt_supporting_factor_trace (
    batch_id VARCHAR(50) NOT NULL,
    exposure_id VARCHAR(100) NOT NULL,
    factor_rule_id BIGINT NOT NULL, -- Référence à la règle de facteur de soutien
    multiplier NUMERIC(9, 4),
    applied_metric VARCHAR(100),
    rwa_before NUMERIC(18, 4),
    rwa_after NUMERIC(18, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (batch_id, exposure_id, factor_rule_id),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (factor_rule_id) REFERENCES ref.ref_supporting_factor_rules(factor_rule_id)
);
COMMENT ON TABLE rpt.rpt_supporting_factor_trace IS 'Table de traçabilité des facteurs de soutien appliqués aux expositions, normalisée en BCNF.';

-- Index sur exposure_id pour la traçabilité par exposition
CREATE INDEX IF NOT EXISTS idx_rpt_supporting_factor_trace_exposure_id ON rpt.rpt_supporting_factor_trace (exposure_id);





-- Migration idempotente v6.0.1 : statuts batch fail-closed.
DO $$
DECLARE constraint_name TEXT;
BEGIN
    SELECT c.conname INTO constraint_name
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'meta' AND t.relname = 'batch_run_control'
      AND c.contype = 'c' AND pg_get_constraintdef(c.oid) ILIKE '%status%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE meta.batch_run_control DROP CONSTRAINT %I', constraint_name);
    END IF;
    ALTER TABLE meta.batch_run_control
        ADD CONSTRAINT chk_batch_run_control_status_v601
        CHECK (status IN (
            'RUNNING', 'COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED',
            'FAILED_CONTROLS', 'FAILED_RECONCILIATION', 'FAILED_ENGINE', 'PENDING'
        ));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


-- =============================================================================
-- Privilèges
-- =============================================================================
-- L'édition Community ne crée aucun rôle global et n'exige pas CREATEROLE.
-- Les GRANT éventuels restent sous la responsabilité de l'administrateur de la
-- base cible afin de fonctionner aussi sur les services PostgreSQL managés.
