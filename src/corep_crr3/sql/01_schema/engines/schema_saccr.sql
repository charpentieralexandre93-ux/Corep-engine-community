-- =============================================================================
-- schema_saccr.sql
-- Moteur SA-CCR — schéma BCNF dédié.
-- VERSION : 4.4.0
-- =============================================================================
-- P2 v2.8 : les tables SA-CCR ne sont plus créées dans le schéma commun.
-- Ce fichier porte désormais la totalité du schéma moteur SA-CCR :
--   - stg.stg_saccr_trades ;
--   - core.core_saccr_results ;
--   - colonnes natives CRR3 Art.277-280 ;
--   - devise de paiement IRD Art.280a ;
--   - contraintes/index spécifiques.
--
-- Le script reste idempotent : CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT
-- EXISTS et CREATE INDEX IF NOT EXISTS.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Staging SA-CCR
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.stg_saccr_trades (
    batch_id VARCHAR(50) NOT NULL,
    trade_id VARCHAR(100) NOT NULL,
    netting_set_id VARCHAR(100),
    asset_class_id VARCHAR(50),
    mtm NUMERIC(18, 4),
    addon NUMERIC(18, 4),
    collateral NUMERIC(18, 4) CHECK (collateral >= 0),
    counterparty_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (batch_id, trade_id),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (asset_class_id) REFERENCES ref.ref_asset_classes(asset_class_id),
    FOREIGN KEY (counterparty_id) REFERENCES ref.ref_counterparties(counterparty_id)
);

COMMENT ON TABLE stg.stg_saccr_trades IS
    'Table de staging dédiée au moteur SA-CCR. Créée uniquement si run_saccr=true.';
COMMENT ON COLUMN stg.stg_saccr_trades.batch_id IS
    'Clé étrangère : identifiant du batch ayant chargé cette transaction.';
COMMENT ON COLUMN stg.stg_saccr_trades.trade_id IS
    'Identifiant unique de la transaction.';
COMMENT ON COLUMN stg.stg_saccr_trades.netting_set_id IS
    'Identifiant du netting set soumis à compensation.';

CREATE INDEX IF NOT EXISTS idx_stg_saccr_trades_netting_set_id
    ON stg.stg_saccr_trades (netting_set_id);

-- -----------------------------------------------------------------------------
-- 2. Résultats SA-CCR
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.core_saccr_results (
    batch_id VARCHAR(50) NOT NULL,
    netting_set_id VARCHAR(100) NOT NULL,
    counterparty_id VARCHAR(100) NOT NULL,
    counterparty_type VARCHAR(100),
    rc NUMERIC(18, 4),
    pfe NUMERIC(18, 4),
    ead NUMERIC(18, 4),
    risk_weight NUMERIC(9, 4) CHECK (risk_weight >= 0),
    rwa NUMERIC(18, 4) CHECK (rwa >= 0),
    PRIMARY KEY (batch_id, netting_set_id),
    FOREIGN KEY (batch_id) REFERENCES meta.batch_run_control(batch_id),
    FOREIGN KEY (counterparty_id) REFERENCES ref.ref_counterparties(counterparty_id)
);

COMMENT ON TABLE core.core_saccr_results IS
    'Résultats du moteur SA-CCR, normalisés en BCNF et créés uniquement si run_saccr=true.';
COMMENT ON COLUMN core.core_saccr_results.counterparty_type IS
    'Type de contrepartie résolu depuis ref.ref_counterparties et utilisé pour le mapping COREP C34.02.';

CREATE INDEX IF NOT EXISTS idx_core_saccr_results_batch_counterparty
    ON core.core_saccr_results (batch_id, counterparty_type);

-- -----------------------------------------------------------------------------
-- 3. Colonnes natives SA-CCR CRR3 Art.277-280
-- -----------------------------------------------------------------------------
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS asset_class VARCHAR(20);
COMMENT ON COLUMN stg.stg_saccr_trades.asset_class IS
    'Classe d''actif SA-CCR : IRD, FX, CREDIT, EQUITY, COMMODITY. NULL = fallback addon legacy.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS notional NUMERIC(18, 4);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS delta NUMERIC(10, 6);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS maturity_years NUMERIC(8, 4);
COMMENT ON COLUMN stg.stg_saccr_trades.notional IS 'Montant notionnel — base du calcul add-on natif.';
COMMENT ON COLUMN stg.stg_saccr_trades.delta IS 'Delta supervisory δ ∈ [-1, 1] Art.279b.';
COMMENT ON COLUMN stg.stg_saccr_trades.maturity_years IS 'Maturité résiduelle M en années.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS start_date_years NUMERIC(8, 4);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS end_date_years NUMERIC(8, 4);
COMMENT ON COLUMN stg.stg_saccr_trades.start_date_years IS
    'Date de début S en années pour la supervisory duration IRD Art.280a.';
COMMENT ON COLUMN stg.stg_saccr_trades.end_date_years IS
    'Date de fin E en années pour la supervisory duration IRD Art.280a.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS option_type VARCHAR(10);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS strike NUMERIC(18, 4);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS underlying_price NUMERIC(18, 4);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS implied_vol NUMERIC(10, 6);
COMMENT ON COLUMN stg.stg_saccr_trades.option_type IS 'CALL, PUT ou NULL pour un trade linéaire.';
COMMENT ON COLUMN stg.stg_saccr_trades.strike IS 'Prix d''exercice K de l''option.';
COMMENT ON COLUMN stg.stg_saccr_trades.underlying_price IS 'Prix du sous-jacent P à la date d''observation.';
COMMENT ON COLUMN stg.stg_saccr_trades.implied_vol IS 'Volatilité implicite annualisée σ.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS reference_entity_id VARCHAR(100);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS credit_quality VARCHAR(10);
COMMENT ON COLUMN stg.stg_saccr_trades.reference_entity_id IS
    'Entité de référence du dérivé crédit — hedging set Art.280b.';
COMMENT ON COLUMN stg.stg_saccr_trades.credit_quality IS
    'IG ou HY pour piloter le supervisory factor crédit.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS equity_id VARCHAR(100);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS equity_type VARCHAR(10);
COMMENT ON COLUMN stg.stg_saccr_trades.equity_id IS
    'Identifiant equity — hedging set Art.280d.';
COMMENT ON COLUMN stg.stg_saccr_trades.equity_type IS
    'SINGLE ou INDEX — pilote supervisory factor et corrélation equity.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS commodity_type VARCHAR(20);
COMMENT ON COLUMN stg.stg_saccr_trades.commodity_type IS
    'ENERGY, METAL, AGRI ou OTHER — hedging set commodity Art.280e.';

ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS payment_currency VARCHAR(3);
COMMENT ON COLUMN stg.stg_saccr_trades.payment_currency IS
    'Devise de paiement IRD — code ISO 4217. Hedging set SA-CCR pour asset_class=IRD Art.280a.';

-- -----------------------------------------------------------------------------
-- 4. Contraintes normalisées propres au moteur
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_core_saccr_results_counterparty_type') THEN
        ALTER TABLE core.core_saccr_results
            ADD CONSTRAINT fk_core_saccr_results_counterparty_type
            FOREIGN KEY (counterparty_type) REFERENCES ref.ref_counterparty_types(counterparty_type_id);
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 5. Index spécifiques
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_stg_saccr_trades_asset_class
    ON stg.stg_saccr_trades (asset_class);
CREATE INDEX IF NOT EXISTS idx_stg_saccr_trades_reference_entity
    ON stg.stg_saccr_trades (reference_entity_id);
CREATE INDEX IF NOT EXISTS idx_stg_saccr_trades_equity_id
    ON stg.stg_saccr_trades (equity_id);
CREATE INDEX IF NOT EXISTS idx_stg_saccr_trades_payment_currency
    ON stg.stg_saccr_trades (payment_currency)
    WHERE payment_currency IS NOT NULL;


-- -----------------------------------------------------------------------------
-- P0 v3.2.0 — Marge et collatéral SA-CCR avancés (Art.274-278)
-- -----------------------------------------------------------------------------
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS vm_received NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS vm_posted NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS im_received NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS im_posted NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS nica NUMERIC(18, 4);
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS threshold_amount NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS mta NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS mpor_days INTEGER DEFAULT 10;
ALTER TABLE stg.stg_saccr_trades ADD COLUMN IF NOT EXISTS csa_id VARCHAR(100);

COMMENT ON COLUMN stg.stg_saccr_trades.vm_received IS 'Variation margin reçue par la banque — réduit l exposition courante.';
COMMENT ON COLUMN stg.stg_saccr_trades.vm_posted IS 'Variation margin postée par la banque — augmente l exposition nette.';
COMMENT ON COLUMN stg.stg_saccr_trades.im_received IS 'Initial margin reçue / independent collateral reçu.';
COMMENT ON COLUMN stg.stg_saccr_trades.im_posted IS 'Initial margin postée / independent collateral posté.';
COMMENT ON COLUMN stg.stg_saccr_trades.nica IS 'Net Independent Collateral Amount. Si NULL, calculé comme IM reçue - IM postée.';
COMMENT ON COLUMN stg.stg_saccr_trades.threshold_amount IS 'Threshold CSA utilisé dans la formule RC margée.';
COMMENT ON COLUMN stg.stg_saccr_trades.mta IS 'Minimum Transfer Amount CSA utilisé dans la formule RC margée.';
COMMENT ON COLUMN stg.stg_saccr_trades.mpor_days IS 'Margin Period of Risk en jours ouvrés.';
COMMENT ON COLUMN stg.stg_saccr_trades.csa_id IS 'Identifiant CSA / margin agreement.';

ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS mtm_net NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS net_variation_margin NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS nica NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS threshold_amount NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS mta NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS mpor_days INTEGER DEFAULT 10;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS pfe_multiplier NUMERIC(12, 8) DEFAULT 1;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS pfe_full NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE core.core_saccr_results ADD COLUMN IF NOT EXISTS collateral_state JSONB;

CREATE INDEX IF NOT EXISTS idx_stg_saccr_trades_csa_id
    ON stg.stg_saccr_trades (csa_id)
    WHERE csa_id IS NOT NULL;


INSERT INTO ref.ref_runtime_parameters
    (regulatory_version_id, parameter_name, parameter_value, parameter_type)
VALUES
    ('CRR3_V9', 'PATCH_V2_7_APPLIED', '2026-05-01', 'string'),
    ('CRR3_V9', 'PATCH_V2_8_SACCR_SCHEMA_ISOLATED', 'true', 'boolean'),
    ('CRR3_V9', 'PATCH_V3_0_SACCR_MARGIN_ADVANCED', 'true', 'boolean')
ON CONFLICT (regulatory_version_id, parameter_name)
DO UPDATE SET parameter_value = EXCLUDED.parameter_value;

COMMIT;
