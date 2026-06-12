-- =============================================================================
-- 01_seed_credit_standard.sql
-- VERSION : 4.4.4
-- Moteur risque de crédit standard — CCF, RW discriminants, CRM UFCP/FCP, haircuts, supporting factors.
-- Forme BCNF : règles, conditions et référentiels séparés par clés naturelles.
-- =============================================================================
BEGIN;
-- Rule sets du moteur standard
-- Règles CCF (Art. 111 CRR3 — facteurs de conversion de crédit)
-- Ces règles s'appliquent avant le calcul du RW
INSERT INTO ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name, target_domain, is_active)
VALUES ('CRR3_V9', 'RS_CCF_V2', 'CCF', TRUE)
ON CONFLICT (regulatory_version_id, rule_set_name) DO UPDATE SET
    regulatory_version_id = EXCLUDED.regulatory_version_id,
    target_domain = EXCLUDED.target_domain,
    is_active = EXCLUDED.is_active;

-- Règles de Risk Weight étendues
INSERT INTO ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name, target_domain, is_active)
VALUES ('CRR3_V9', 'RS_RW_V2', 'RISK_WEIGHT', TRUE)
ON CONFLICT (regulatory_version_id, rule_set_name) DO UPDATE SET
    regulatory_version_id = EXCLUDED.regulatory_version_id,
    target_domain = EXCLUDED.target_domain,
    is_active = EXCLUDED.is_active;

-- Règles de substitution RW (CRM UFCP)
INSERT INTO ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name, target_domain, is_active)
VALUES ('CRR3_V9', 'RS_SUB_RW_V2', 'SUBSTITUTION_RISK_WEIGHT', TRUE)
ON CONFLICT (regulatory_version_id, rule_set_name) DO UPDATE SET
    regulatory_version_id = EXCLUDED.regulatory_version_id,
    target_domain = EXCLUDED.target_domain,
    is_active = EXCLUDED.is_active;

-- Règles haircut collatéral (CRM FCP — Art.197-200 CRR3)
INSERT INTO ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name, target_domain, is_active)
VALUES ('CRR3_V9', 'RS_COLLATERAL_HAIRCUT', 'COLLATERAL_HAIRCUT', TRUE)
ON CONFLICT (regulatory_version_id, rule_set_name) DO UPDATE SET
    regulatory_version_id = EXCLUDED.regulatory_version_id,
    target_domain = EXCLUDED.target_domain,
    is_active = EXCLUDED.is_active;


-- Rule set protection bucket conservé sous son target_domain dédié
INSERT INTO ref.ref_decision_rule_sets (regulatory_version_id, rule_set_name, target_domain, is_active) VALUES
('CRR3_V9', 'RS_PROTECTION_BUCKET', 'PROTECTION_BUCKET', TRUE)
ON CONFLICT (regulatory_version_id, rule_set_name) DO UPDATE SET
    target_domain = EXCLUDED.target_domain,
    is_active = EXCLUDED.is_active;

-- =============================================================================
-- 5. RÈGLES CCF COMPLÈTES (Art. 111 CRR3)
-- =============================================================================
-- Engagements irrévocables : 40% (général), ajustements selon maturité
-- Garanties, SBLC, acceptations : 100%
-- Lettres de crédit documentaires : 20%
-- Cautions performance : 50%
-- NIF/RUF : 50%
-- Engagements révocables : 10% (bucket 5 CRR3)

DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_CCF_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
);

DELETE FROM ref.ref_decision_rules
WHERE rule_set_id IN (
    SELECT rule_set_id
    FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_CCF_V2'
      AND regulatory_version_id = 'CRR3_V9'
);

INSERT INTO ref.ref_decision_rules
    (rule_set_id, priority, result_key, result_value)
SELECT rs.rule_set_id, v.priority, v.result_key, v.result_value
FROM (VALUES
    ('RS_CCF_V2', 10, 'CCF', '1.00'),
    ('RS_CCF_V2', 20, 'CCF', '1.00'),
    ('RS_CCF_V2', 30, 'CCF', '1.00'),
    ('RS_CCF_V2', 40, 'CCF', '1.00'),
    ('RS_CCF_V2', 50, 'CCF', '0.50'),
    ('RS_CCF_V2', 60, 'CCF', '0.40'),
    ('RS_CCF_V2', 70, 'CCF', '0.40'),
    ('RS_CCF_V2', 80, 'CCF', '0.20'),
    ('RS_CCF_V2', 90, 'CCF', '0.10'),
    ('RS_CCF_V2', 100, 'CCF', '1.00'),
    ('RS_CCF_V2', 110, 'CCF', '0.75'),
    ('RS_CCF_V2', 120, 'CCF', '1.00'),
    ('RS_CCF_V2', 130, 'CCF', '1.00'),
    ('RS_CCF_V2', 999, 'CCF', '1.00')
) AS v(rule_set_name, priority, result_key, result_value)
JOIN ref.ref_decision_rule_sets rs
  ON rs.rule_set_name = v.rule_set_name
 AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Conditions pour les CCF
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT r.rule_id, 'product_type_id', '=', v.val
FROM ref.ref_decision_rules r
CROSS JOIN (VALUES
    (10,'GUARANTEE'),(20,'STANDBY_LC'),(30,'ACCEPTANCE'),(40,'FORWARD_ASSET'),
    (50,'PERFORMANCE_BOND'),(60,'COMMITMENT'),(70,'COMMITMENT'),
    (80,'LETTER_OF_CREDIT'),(90,'REVOCABLE_COMMITMENT'),
    (100,'TERM_LOAN'),(110,'REVOLVING'),(120,'MORTGAGE'),(130,'BOND')
) AS v(priority, val)
WHERE r.rule_set_id = (SELECT rule_set_id FROM ref.ref_decision_rule_sets WHERE rule_set_name = 'RS_CCF_V2' AND regulatory_version_id = 'CRR3_V9') AND r.priority = v.priority
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 6. RÈGLES RISK WEIGHT COMPLÈTES (Art. 114-136 CRR3)
-- =============================================================================
DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_RW_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
);

DELETE FROM ref.ref_decision_rules
WHERE rule_set_id IN (
    SELECT rule_set_id
    FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_RW_V2'
      AND regulatory_version_id = 'CRR3_V9'
);

INSERT INTO ref.ref_decision_rules
    (rule_set_id, priority, result_key, result_value)
SELECT rs.rule_set_id, v.priority, v.result_key, v.result_value
FROM (VALUES
    ('RS_RW_V2', 10, 'RISK_WEIGHT', '0.00'),
    ('RS_RW_V2', 11, 'RISK_WEIGHT', '0.00'),
    ('RS_RW_V2', 12, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 13, 'RISK_WEIGHT', '0.50'),
    ('RS_RW_V2', 14, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 15, 'RISK_WEIGHT', '1.50'),
    ('RS_RW_V2', 20, 'RISK_WEIGHT', '0.00'),
    ('RS_RW_V2', 25, 'RISK_WEIGHT', '0.00'),
    ('RS_RW_V2', 30, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 31, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 32, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 33, 'RISK_WEIGHT', '0.50'),
    ('RS_RW_V2', 34, 'RISK_WEIGHT', '0.50'),
    ('RS_RW_V2', 35, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 36, 'RISK_WEIGHT', '1.50'),
    ('RS_RW_V2', 40, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 45, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 46, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 50, 'RISK_WEIGHT', '0.65'),
    ('RS_RW_V2', 51, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 52, 'RISK_WEIGHT', '1.30'),
    ('RS_RW_V2', 53, 'RISK_WEIGHT', '1.50'),
    ('RS_RW_V2', 60, 'RISK_WEIGHT', '0.75'),
    ('RS_RW_V2', 61, 'RISK_WEIGHT', '0.45'),
    ('RS_RW_V2', 70, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 71, 'RISK_WEIGHT', '0.25'),
    ('RS_RW_V2', 72, 'RISK_WEIGHT', '0.30'),
    ('RS_RW_V2', 73, 'RISK_WEIGHT', '0.40'),
    ('RS_RW_V2', 74, 'RISK_WEIGHT', '0.50'),
    ('RS_RW_V2', 75, 'RISK_WEIGHT', '0.70'),
    ('RS_RW_V2', 80, 'RISK_WEIGHT', '0.60'),
    ('RS_RW_V2', 81, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 90, 'RISK_WEIGHT', '1.50'),
    ('RS_RW_V2', 91, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 92, 'RISK_WEIGHT', '0.50'),
    ('RS_RW_V2', 100, 'RISK_WEIGHT', '1.50'),
    ('RS_RW_V2', 110, 'RISK_WEIGHT', '0.10'),
    ('RS_RW_V2', 111, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 112, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 120, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 121, 'RISK_WEIGHT', '0.75'),
    ('RS_RW_V2', 122, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 123, 'RISK_WEIGHT', '1.25'),
    ('RS_RW_V2', 130, 'RISK_WEIGHT', '2.50'),
    ('RS_RW_V2', 131, 'RISK_WEIGHT', '4.00'),
    ('RS_RW_V2', 132, 'RISK_WEIGHT', '1.50'),
    ('RS_RW_V2', 140, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 141, 'RISK_WEIGHT', '0.00'),
    ('RS_RW_V2', 142, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 150, 'RISK_WEIGHT', '0.75'),
    ('RS_RW_V2', 151, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 152, 'RISK_WEIGHT', '0.75'),
    ('RS_RW_V2', 900, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 901, 'RISK_WEIGHT', '0.20'),
    ('RS_RW_V2', 902, 'RISK_WEIGHT', '1.00'),
    ('RS_RW_V2', 903, 'RISK_WEIGHT', '0.75')
) AS v(rule_set_name, priority, result_key, result_value)
JOIN ref.ref_decision_rule_sets rs
  ON rs.rule_set_name = v.rule_set_name
 AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Conditions pour les règles RW (champ asset_class_id)
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT r.rule_id, 'asset_class_id', '=', v.val
FROM ref.ref_decision_rules r
CROSS JOIN (VALUES
    (10,'CENTRAL_GOVT'),(11,'SOVEREIGN'),(12,'CENTRAL_GOVT'),(13,'CENTRAL_GOVT'),
    (14,'CENTRAL_GOVT'),(15,'CENTRAL_GOVT'),
    (20,'MULTILATERAL_BANK'),(25,'INTL_ORG'),
    (30,'INSTITUTION'),(31,'BANK'),(32,'BANK'),(33,'INSTITUTION'),(34,'BANK'),
    (35,'INSTITUTION'),(36,'INSTITUTION'),
    (40,'PUBLIC_SECTOR'),(45,'REGIONAL_GOVT'),(46,'REGIONAL_GOVT'),
    (50,'CORPORATE'),(51,'CORPORATE'),(52,'CORPORATE'),(53,'CORPORATE'),
    (60,'RETAIL'),(61,'RETAIL'),
    (70,'RESIDENTIAL_MORTGAGE'),(71,'RESIDENTIAL_MORTGAGE'),(72,'RESIDENTIAL_MORTGAGE'),
    (73,'RESIDENTIAL_MORTGAGE'),(74,'RESIDENTIAL_MORTGAGE'),(75,'RESIDENTIAL_MORTGAGE'),
    (80,'COMMERCIAL_MORTGAGE'),(81,'COMMERCIAL_MORTGAGE'),
    (90,'DEFAULT'),(91,'DEFAULT'),(92,'DEFAULT'),
    (100,'HIGH_RISK'),
    (110,'COVERED_BOND'),(111,'COVERED_BOND'),(112,'COVERED_BOND'),
    (120,'CIU'),(121,'CIU'),(122,'CIU'),(123,'CIU'),
    (130,'EQUITY'),(131,'EQUITY'),(132,'EQUITY'),
    (140,'OTHER'),(141,'OTHER'),(142,'OTHER'),
    (150,'SME_RETAIL'),(151,'SME_CORPORATE'),(152,'INFRA_CORPORATE'),
    (900,'SOVEREIGN'),(901,'BANK'),(902,'CORPORATE'),(903,'RETAIL')
) AS v(priority, val)
WHERE r.rule_set_id = (SELECT rule_set_id FROM ref.ref_decision_rule_sets WHERE rule_set_name = 'RS_RW_V2' AND regulatory_version_id = 'CRR3_V9') AND r.priority = v.priority
ON CONFLICT DO NOTHING;

-- Condition supplémentaire : delinquent_flag = TRUE → DEFAULT (priorité haute)
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT r.rule_id, 'delinquent_flag', '=', 'TRUE'
FROM ref.ref_decision_rules r
WHERE r.rule_set_id = (SELECT rule_set_id FROM ref.ref_decision_rule_sets WHERE rule_set_name = 'RS_RW_V2' AND regulatory_version_id = 'CRR3_V9') AND r.priority IN (90, 91, 92)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 7. RÈGLES DE SUBSTITUTION RW (CRM UFCP — Art.235 CRR3)
-- Le RW du protecteur se substitue au RW de l'emprunteur si plus favorable
-- =============================================================================
DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_SUB_RW_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
);

DELETE FROM ref.ref_decision_rules
WHERE rule_set_id IN (
    SELECT rule_set_id
    FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_SUB_RW_V2'
      AND regulatory_version_id = 'CRR3_V9'
);

INSERT INTO ref.ref_decision_rules
    (rule_set_id, priority, result_key, result_value)
SELECT rs.rule_set_id, v.priority, v.result_key, v.result_value
FROM (VALUES
    ('RS_SUB_RW_V2', 10, 'RISK_WEIGHT', '0.00'),
    ('RS_SUB_RW_V2', 20, 'RISK_WEIGHT', '0.00'),
    ('RS_SUB_RW_V2', 30, 'RISK_WEIGHT', '0.00'),
    ('RS_SUB_RW_V2', 40, 'RISK_WEIGHT', '0.20'),
    ('RS_SUB_RW_V2', 50, 'RISK_WEIGHT', '0.20'),
    ('RS_SUB_RW_V2', 60, 'RISK_WEIGHT', '0.65'),
    ('RS_SUB_RW_V2', 70, 'RISK_WEIGHT', '1.00'),
    ('RS_SUB_RW_V2', 80, 'RISK_WEIGHT', '0.20')
) AS v(rule_set_name, priority, result_key, result_value)
JOIN ref.ref_decision_rule_sets rs
  ON rs.rule_set_name = v.rule_set_name
 AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT r.rule_id, 'provider_type', '=', v.val
FROM ref.ref_decision_rules r
CROSS JOIN (VALUES
    (10,'CENTRAL_GOVT'),(20,'SOVEREIGN'),(30,'MULTILATERAL_BANK'),
    (40,'BANK'),(40,'INSTITUTION'),(50,'PUBLIC_SECTOR'),
    (60,'CORPORATE'),(70,'CORPORATE'),(80,'REGIONAL_GOVT')
) AS v(priority, val)
WHERE r.rule_set_id = (SELECT rule_set_id FROM ref.ref_decision_rule_sets WHERE rule_set_name = 'RS_SUB_RW_V2' AND regulatory_version_id = 'CRR3_V9') AND r.priority = v.priority
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 8. HAIRCUTS COLLATÉRAL (Art.197-200 CRR3 — approche complète superviseur)
-- Table : ref_collateral_haircuts (nouvelle table à créer)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ref.ref_collateral_haircuts (
    haircut_id          SERIAL PRIMARY KEY,
    regulatory_version_id VARCHAR(50) NOT NULL,
    collateral_type     VARCHAR(100) NOT NULL,   -- Type de collatéral
    collateral_grade    VARCHAR(20),              -- Notation ECAi (AAA, AA, A, BBB, BB...)
    residual_maturity   VARCHAR(20),              -- Bucket maturité résiduelle
    haircut_rate        NUMERIC(6,4) NOT NULL,   -- Haircut en % (0.0 = 0%, 0.15 = 15%)
    is_active           BOOLEAN DEFAULT TRUE,
    reference_article   VARCHAR(100),
    FOREIGN KEY (regulatory_version_id) REFERENCES ref.ref_regulatory_versions(regulatory_version_id)
);

-- PATCH v2.8 — index composite aligné avec le préchargement et les lookups FCP.
-- Requête batch cible : WHERE regulatory_version_id = ? AND is_active = TRUE.
-- Lookups unitaires rétrocompatibles : version + type + grade + maturité.
CREATE INDEX IF NOT EXISTS idx_ref_collateral_haircuts_lookup
ON ref.ref_collateral_haircuts (
    regulatory_version_id,
    is_active,
    collateral_type,
    collateral_grade,
    residual_maturity
);

INSERT INTO ref.ref_collateral_haircuts
    (regulatory_version_id, collateral_type, collateral_grade, residual_maturity, haircut_rate, reference_article)
VALUES
-- ── Titres d'État zone euro (Art.197 §1 (a)) ──
('CRR3_V9', 'SOVEREIGN_BOND_EEA', 'AAA_AA',  '≤1Y',  0.005, 'Art.197 Annexe superviseur'),
('CRR3_V9', 'SOVEREIGN_BOND_EEA', 'AAA_AA',  '1Y-5Y',0.02,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'SOVEREIGN_BOND_EEA', 'AAA_AA',  '>5Y',  0.04,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'SOVEREIGN_BOND_EEA', 'A_BBB',   '≤1Y',  0.01,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'SOVEREIGN_BOND_EEA', 'A_BBB',   '1Y-5Y',0.03,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'SOVEREIGN_BOND_EEA', 'A_BBB',   '>5Y',  0.06,  'Art.197 Annexe superviseur'),
-- ── Obligations corporate investment grade (Art.197 §1 (b)) ──
('CRR3_V9', 'CORPORATE_BOND_IG',  'AAA_AA',  '≤1Y',  0.010, 'Art.197 Annexe superviseur'),
('CRR3_V9', 'CORPORATE_BOND_IG',  'AAA_AA',  '1Y-5Y',0.04,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'CORPORATE_BOND_IG',  'AAA_AA',  '>5Y',  0.08,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'CORPORATE_BOND_IG',  'A_BBB',   '≤1Y',  0.015, 'Art.197 Annexe superviseur'),
('CRR3_V9', 'CORPORATE_BOND_IG',  'A_BBB',   '1Y-5Y',0.06,  'Art.197 Annexe superviseur'),
('CRR3_V9', 'CORPORATE_BOND_IG',  'A_BBB',   '>5Y',  0.12,  'Art.197 Annexe superviseur'),
-- ── Obligations garanties (covered bonds) ──
('CRR3_V9', 'COVERED_BOND',       'AAA_AA',  '≤1Y',  0.005, 'Art.129/197'),
('CRR3_V9', 'COVERED_BOND',       'AAA_AA',  '1Y-5Y',0.02,  'Art.129/197'),
('CRR3_V9', 'COVERED_BOND',       'AAA_AA',  '>5Y',  0.04,  'Art.129/197'),
-- ── Actions cotées indice principal ──
('CRR3_V9', 'EQUITY_MAIN_INDEX',  NULL,      NULL,   0.15,  'Art.197 §1 (e)'),
-- ── Actions cotées hors indice principal ──
('CRR3_V9', 'EQUITY_OTHER',       NULL,      NULL,   0.25,  'Art.197 §1 (e)'),
-- ── OPCVM / Fonds d''investissement ──
('CRR3_V9', 'CIU_UCITS',          NULL,      NULL,   0.15,  'Art.197 §3'),
-- ── Dépôts en espèces / liquidités ──
('CRR3_V9', 'CASH_DEPOSIT',       NULL,      NULL,   0.00,  'Art.197 §1 (a)'),
-- ── Or physique ──
('CRR3_V9', 'GOLD',               NULL,      NULL,   0.15,  'Art.197 §1 (d)'),
-- ── Immobilier résidentiel (IPRE / IPPH) ──
('CRR3_V9', 'RESIDENTIAL_RE',     NULL,      NULL,   0.00,  'Art.199 — CRM immobilier (pas de haircut, plafond LTV)'),
-- ── Immobilier commercial ──
('CRR3_V9', 'COMMERCIAL_RE',      NULL,      NULL,   0.00,  'Art.199 — CRM immobilier (pas de haircut, plafond LTV)')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 9. RÈGLES PROTECTION_BUCKET (CRM — classification des sûretés)
-- =============================================================================
DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_PROTECTION_BUCKET'
      AND rs.regulatory_version_id = 'CRR3_V9'
);

DELETE FROM ref.ref_decision_rules
WHERE rule_set_id IN (
    SELECT rule_set_id
    FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_PROTECTION_BUCKET'
      AND regulatory_version_id = 'CRR3_V9'
);

INSERT INTO ref.ref_decision_rules
    (rule_set_id, priority, result_key, result_value)
SELECT rs.rule_set_id, v.priority, v.result_key, v.result_value
FROM (VALUES
    ('RS_PROTECTION_BUCKET', 10, 'BUCKET', 'COLLATERAL_CASH'),
    ('RS_PROTECTION_BUCKET', 20, 'BUCKET', 'COLLATERAL_SOVEREIGN_BOND'),
    ('RS_PROTECTION_BUCKET', 30, 'BUCKET', 'COLLATERAL_CORPORATE_BOND'),
    ('RS_PROTECTION_BUCKET', 40, 'BUCKET', 'COLLATERAL_EQUITY'),
    ('RS_PROTECTION_BUCKET', 50, 'BUCKET', 'COLLATERAL_GOLD'),
    ('RS_PROTECTION_BUCKET', 60, 'BUCKET', 'COLLATERAL_COVERED_BOND'),
    ('RS_PROTECTION_BUCKET', 70, 'BUCKET', 'COLLATERAL_REAL_ESTATE'),
    ('RS_PROTECTION_BUCKET', 80, 'BUCKET', 'GUARANTEE_SOVEREIGN'),
    ('RS_PROTECTION_BUCKET', 90, 'BUCKET', 'GUARANTEE_BANK'),
    ('RS_PROTECTION_BUCKET', 100, 'BUCKET', 'GUARANTEE_CORPORATE'),
    ('RS_PROTECTION_BUCKET', 110, 'BUCKET', 'GUARANTEE_MULTILATERAL'),
    ('RS_PROTECTION_BUCKET', 120, 'BUCKET', 'CDS'),
    ('RS_PROTECTION_BUCKET', 998, 'BUCKET', 'DEFAULT_FCP'),
    ('RS_PROTECTION_BUCKET', 999, 'BUCKET', 'DEFAULT_UFCP')
) AS v(rule_set_name, priority, result_key, result_value)
JOIN ref.ref_decision_rule_sets rs
  ON rs.rule_set_name = v.rule_set_name
 AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Conditions bucket
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT r.rule_id, 'protection_type', '=', v.pt
FROM ref.ref_decision_rules r
CROSS JOIN (VALUES
    (10,'FCP'),(20,'FCP'),(30,'FCP'),(40,'FCP'),(50,'FCP'),(60,'FCP'),(70,'FCP'),
    (80,'UFCP'),(90,'UFCP'),(100,'UFCP'),(110,'UFCP'),(120,'UFCP'),
    (998,'FCP'),(999,'UFCP')
) AS v(priority, pt)
WHERE r.rule_set_id = (SELECT rule_set_id FROM ref.ref_decision_rule_sets WHERE rule_set_name = 'RS_PROTECTION_BUCKET' AND regulatory_version_id = 'CRR3_V9') AND r.priority = v.priority
ON CONFLICT DO NOTHING;


-- =============================================================================
-- 11. FACTEURS DE SOUTIEN ÉTENDUS (Art.501 / 501a CRR3)
-- =============================================================================
INSERT INTO ref.ref_supporting_factor_rules
    (regulatory_version_id, factor_code, priority, eligibility_field, eligibility_operator,
     eligibility_value, multiplier, applies_to_metric, is_active)
VALUES
-- SME supporting factor (Art.501(1) CRR3) — two-tier depuis v3.4.0 :
--   multiplier ci-dessous (0,7619) = facteur de la tranche E* ≤ 2,5 M€ ;
--   la tranche E* > 2,5 M€ reçoit 0,85 (constante moteur SME_SF_HIGH_TIER_FACTOR).
--   E* = exposition totale envers la PME (agrégée par obligor dans le moteur).
('CRR3_V9', 'SME_SUPPORTING_FACTOR',   1, 'supporting_sme_flag',   '=', 'TRUE', 0.7619, 'RWA', TRUE),
-- Infrastructure supporting factor (Art.501a CRR3) — 0,75
('CRR3_V9', 'INFRA_SUPPORTING_FACTOR', 2, 'supporting_infra_flag', '=', 'TRUE', 0.75,   'RWA', TRUE),
-- Infrastructure de base / projets éligibles — 0,75
('CRR3_V9', 'INFRA_PROJECT_FACTOR',    3, 'supporting_infra_flag', '=', 'TRUE', 0.75,   'RWA', TRUE),
-- Prêts verts / taxonomie UE (expérimental — pas encore CRR3 officiel)
('CRR3_V9', 'GREEN_ASSET_FACTOR',      10,'green_asset_flag',      '=', 'TRUE', 0.90,   'RWA', FALSE)
ON CONFLICT DO NOTHING;

-- Paramètres runtime du moteur standard
INSERT INTO ref.ref_runtime_parameters (regulatory_version_id, parameter_name, parameter_type, parameter_value) VALUES
('CRR3_V9', 'DEFAULT_CCF_COMMITMENT',  'REAL', '0.40'),
('CRR3_V9', 'DEFAULT_CCF_GUARANTEE',   'REAL', '1.00'),
('CRR3_V9', 'DEFAULT_RW_UNCLASSIFIED', 'REAL', '1.00'),
('CRR3_V9', 'ENABLE_CRM_FCP',          'TEXT', 'Y'),
('CRR3_V9', 'ENABLE_CRM_UFCP',         'TEXT', 'Y'),
-- v3.5.0 (audit ④) — Haircut de change CRM appliqué au collatéral FCP lorsque
-- la devise du collatéral diffère de celle de l'exposition (CRR3 Art.224) :
-- 8 % pour une fenêtre de liquidation de 10 jours ouvrés avec réévaluation quotidienne.
('CRR3_V9', 'CRM_FX_HAIRCUT',          'REAL', '0.08')
ON CONFLICT (regulatory_version_id, parameter_name) DO UPDATE SET
    parameter_type = EXCLUDED.parameter_type,
    parameter_value = EXCLUDED.parameter_value;

-- Corrections réglementaires v2.5 intégrées directement à la seed standard
-- =============================================================================
-- 05c_patch_v2_5_regulatory_corrections.sql
-- =============================================================================
-- Patch ciblé v2.5 — Corrections réglementaires majeures sur les seeds CRR3
-- enrichi (05_seed_crr3_enrichi.sql).
--
-- Cible 3 bugs réglementaires identifiés lors de l'audit du 29/04/2026 :
--   #1 RW SOUVERAIN — TOUS les souverains avaient RW=0 % faute de discrimination
--      par credit_quality_step → CRR3 Art.114(2) Table 1 non respectée.
--   #2 RS_SUB_RW priority 40 — Deux conditions AND (BANK ET INSTITUTION)
--      → règle inopérante (provider_type ne peut être les deux à la fois).
--   #3 SUPPORTING FACTOR INFRA dupliqué — INFRA_SUPPORTING_FACTOR (×0.75)
--      ET INFRA_PROJECT_FACTOR (×0.75) actifs simultanément avec mêmes conditions
--      → multiplicateur effectif 0.5625 au lieu de 0.75 → sous-estimation 25 %.
--
-- Stratégie : DELETE des conditions/règles à corriger puis ré-INSERT propre.
-- Idempotent : exécuter ce script plusieurs fois est sans effet supplémentaire.
--
-- Dépendances : doit s'exécuter APRÈS 05_seed_crr3_enrichi.sql.
-- Wiring : ajouté à _SQL_GROUPS dans bootstrap.py après le groupe 05.
-- =============================================================================



-- =============================================================================
-- BUG #1 — RW SOUVERAIN PAR CREDIT_QUALITY_STEP (CRR3 Art.114(2) Table 1)
-- =============================================================================
-- CRR3 Art.114(2) Table 1 — Pondération des expositions souveraines :
--    CQS 1 (AAA-AA)  →  0 %
--    CQS 2 (A)        → 20 %
--    CQS 3 (BBB)      → 50 %
--    CQS 4 (BB)       → 100 %
--    CQS 5 (B)        → 100 %
--    CQS 6 (CCC-)     → 150 %
--    UNRATED          → 100 % (régime par défaut Art.114(7))
-- Exception Art.114(4) : 0 % si exposition dans la devise de l'État souverain
-- ET noté ≥ CQS 3 — non implémenté ici (champ non présent dans staging).
--
-- Avant ce patch : priorités 10-15 toutes conditionnées sur asset_class_id seul
-- → priorité 10 (RW=0 %) match TOUTES les CENTRAL_GOVT, peu importe leur CQS.
-- Après : ajout de la condition discriminante credit_quality_step sur 11-15.
-- La priorité 10 reste pour CQS 1 (AAA-AA) qui correspond bien à RW = 0 %.
--
-- Note : la table stg.stg_exposures doit fournir la colonne credit_quality_step
-- (alimentée depuis le système notation interne ou external_rating mappé ECAI).
-- En son absence, la priorité 900 applique le fallback CRR3 Art.114(7) → RW 100 %.

-- 1a. Suppression des conditions existantes pour les priorités 10-15 souverain
DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_RW_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
      AND dr.priority IN (10, 11, 12, 13, 14, 15)
);

-- 1b. Re-création des conditions avec discrimination credit_quality_step
-- Note : asset_class_id IN ('CENTRAL_GOVT', 'SOVEREIGN') pour gérer les deux
-- conventions (CENTRAL_GOVT = code CRR3 officiel, SOVEREIGN = alias).
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'asset_class_id', 'IN', 'CENTRAL_GOVT|SOVEREIGN'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.priority IN (10, 11, 12, 13, 14, 15)
ON CONFLICT DO NOTHING;

-- Condition discriminante credit_quality_step par priorité
-- (Art.114(2) Table 1 — CQS 1 à CQS 6 + UNRATED traité par fallback Art.114(7))
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'credit_quality_step', '=', v.cqs
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
CROSS JOIN (VALUES
    (10, '1'),     -- AAA-AA → 0 %
    (11, '2'),     -- A      → 20 % (priorité 11 a déjà RW=0 mais sera ajustée ci-dessous)
    (12, '2'),     -- A      → 20 %
    (13, '3'),     -- BBB    → 50 %
    (14, '4'),     -- BB     → 100 %
    (15, '6')      -- CCC-   → 150 %
) AS v(priority, cqs)
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.priority = v.priority
ON CONFLICT DO NOTHING;

-- 1c. Correction du result_value de la priorité 11 (était 0 % par erreur, doit
-- être 20 % pour CQS 2 selon Art.114(2) Table 1).
UPDATE ref.ref_decision_rules
SET result_value = '0.20'
WHERE rule_set_id = (
    SELECT rule_set_id FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_RW_V2' AND regulatory_version_id = 'CRR3_V9'
)
  AND priority = 11;

-- Ajout d'une priorité 16 pour CQS 5 (RW=100 % comme CQS 4) — manquait
INSERT INTO ref.ref_decision_rules (rule_set_id, priority, result_key, result_value)
SELECT rs.rule_set_id, 16, 'RISK_WEIGHT', '1.00'
FROM ref.ref_decision_rule_sets rs
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'asset_class_id', 'IN', 'CENTRAL_GOVT|SOVEREIGN'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.priority = 16
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'credit_quality_step', '=', '5'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.priority = 16
ON CONFLICT DO NOTHING;

-- 1d. Fallback souverain sans CQS / UNRATED : 100 % prudentiel (Art.114(7))
-- Supprime l'ancienne condition simple SOVEREIGN et recrée une condition IN afin
-- de couvrir aussi CENTRAL_GOVT. La règle reste en priorité 900, donc les CQS
-- explicites 1..6 matchent avant ce fallback.
UPDATE ref.ref_decision_rules
SET result_value = '1.00'
WHERE rule_set_id = (
    SELECT rule_set_id FROM ref.ref_decision_rule_sets
    WHERE rule_set_name = 'RS_RW_V2' AND regulatory_version_id = 'CRR3_V9'
)
  AND priority = 900;

DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_RW_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
      AND dr.priority = 900
);

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'asset_class_id', 'IN', 'CENTRAL_GOVT|SOVEREIGN'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.priority = 900
ON CONFLICT DO NOTHING;

-- =============================================================================
-- BUG #2 — RS_SUB_RW priority 40 (BANK + INSTITUTION en double condition AND)
-- =============================================================================
-- En v2.4, la priorité 40 du rule set RS_SUB_RW_V2 avait DEUX conditions
-- INSERT distinctes sur provider_type :
--    (40, 'BANK')  ET  (40, 'INSTITUTION')
-- → évaluation AND (toutes les conditions doivent matcher) → impossible
-- pour un seul provider_type d'être simultanément BANK et INSTITUTION.
-- Conséquence : aucune substitution UFCP n'était jamais appliquée pour les
-- garants bancaires → RW garant non utilisé → RWA surestimé.
--
-- Correction : remplacement par une condition unique IN avec opérateur 'IN'.

-- 2a. Suppression des conditions existantes pour la priorité 40
DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_SUB_RW_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
      AND dr.priority = 40
);

-- 2b. Re-création avec une seule condition IN (Art.235 + decision_engine._match)
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'provider_type', 'IN', 'BANK|INSTITUTION'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_SUB_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.priority = 40
ON CONFLICT DO NOTHING;

-- =============================================================================
-- BUG #3 — DOUBLE SUPPORTING FACTOR INFRA (multiplicateur cumulé 0.5625)
-- =============================================================================
-- En v2.4, deux règles supporting factor étaient actives simultanément avec
-- les mêmes conditions :
--    INFRA_SUPPORTING_FACTOR (priority 2, multiplier 0.75)
--    INFRA_PROJECT_FACTOR    (priority 3, multiplier 0.75)
-- Toutes deux sur la condition supporting_infra_flag = TRUE.
-- → apply_supporting_factors itère sur toutes les règles actives dont la
-- condition matche, et MULTIPLIE les multiplicateurs successivement :
-- multiplier_final = 0.75 × 0.75 = 0.5625 (au lieu de 0.75).
-- → RWA infra sous-estimé de 25 % en violation Art.501a CRR3.
--
-- Correction : désactivation de INFRA_PROJECT_FACTOR (doublon historique).
-- Le facteur INFRA_SUPPORTING_FACTOR couvre tous les cas d'application Art.501a.

UPDATE ref.ref_supporting_factor_rules
SET is_active = FALSE
WHERE regulatory_version_id = 'CRR3_V9'
  AND factor_code = 'INFRA_PROJECT_FACTOR';

-- =============================================================================
-- AUDIT TRAIL : trace de l'application du patch
-- =============================================================================
-- Insère une ligne dans ref.ref_runtime_parameters pour tracer la version du
-- patch appliquée. Permet aux outils d'audit de vérifier que les corrections
-- v2.5 sont bien actives sur la base.
INSERT INTO ref.ref_runtime_parameters
    (regulatory_version_id, parameter_name, parameter_value, parameter_type)
VALUES
    ('CRR3_V9', 'PATCH_V2_5_APPLIED', '2026-04-29', 'string')
ON CONFLICT (regulatory_version_id, parameter_name)
DO UPDATE SET parameter_value = EXCLUDED.parameter_value;



-- =============================================================================
-- PATCH P1 v2.8 — RÈGLES RW DISCRIMINANTES + CRM FCP BUCKET/Haircut
-- =============================================================================
-- Objectif : éviter que des règles larges (asset_class_id seul) masquent les
-- règles fines. Les règles ci-dessous ajoutent des attributs discriminants
-- BCNF au contexte de décision : credit_quality_step, ltv_ratio,
-- exposure_subtype, provision_coverage_ratio et delinquent_flag normalisé.

-- 1) Refonte des conditions RW pour les familles qui avaient plusieurs règles
--    avec la même condition asset_class_id mais des RW différents.
DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_RW_V2'
      AND rs.regulatory_version_id = 'CRR3_V9'
      AND dr.priority IN (
          30,31,32,33,34,35,36,
          50,51,52,53,
          60,61,
          70,71,72,73,74,75,
          80,81,
          90,91,92,
          110,111,112,
          120,121,122,123,
          130,131,132,
          140,141,142
      )
);

-- 1a. Conditions asset_class_id de base.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'asset_class_id', '=', v.asset_class_id
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (30,'INSTITUTION'),(31,'BANK'),(32,'BANK'),(33,'INSTITUTION'),(34,'BANK'),(35,'INSTITUTION'),(36,'INSTITUTION'),
    (50,'CORPORATE'),(51,'CORPORATE'),(52,'CORPORATE'),(53,'CORPORATE'),
    (60,'RETAIL'),(61,'RETAIL'),
    (70,'RESIDENTIAL_MORTGAGE'),(71,'RESIDENTIAL_MORTGAGE'),(72,'RESIDENTIAL_MORTGAGE'),
    (73,'RESIDENTIAL_MORTGAGE'),(74,'RESIDENTIAL_MORTGAGE'),(75,'RESIDENTIAL_MORTGAGE'),
    (80,'COMMERCIAL_MORTGAGE'),(81,'COMMERCIAL_MORTGAGE'),
    (90,'DEFAULT'),(91,'DEFAULT'),(92,'DEFAULT'),
    (110,'COVERED_BOND'),(111,'COVERED_BOND'),(112,'COVERED_BOND'),
    (120,'CIU'),(121,'CIU'),(122,'CIU'),(123,'CIU'),
    (130,'EQUITY'),(131,'EQUITY'),(132,'EQUITY'),
    (140,'OTHER'),(141,'OTHER'),(142,'OTHER')
) AS v(priority, asset_class_id) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2'
  AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Institutions / banques : CQS explicite ; fallback historique traité par règles 901/904 si besoin.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'credit_quality_step', 'IN', v.cqs
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (30,'1|2'), (31,'1'), (32,'2|3'), (33,'3|4'), (34,'4|5'), (35,'UNRATED|UNKNOWN'), (36,'6')
) AS v(priority, cqs) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Corporate : Investment Grade / unrated / speculative grade.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'credit_quality_step', 'IN', v.cqs
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (50,'1|2|3'), (51,'UNRATED|UNKNOWN'), (52,'4'), (53,'5|6')
) AS v(priority, cqs) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Retail : règle transactor plus favorable, sinon retail général.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '!=', 'TRANS_ACTOR'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9' AND dr.priority = 60
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '=', 'TRANS_ACTOR'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9' AND dr.priority = 61
ON CONFLICT DO NOTHING;

-- Immobilier résidentiel : discrimination LTV.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, v.field, v.op, v.val
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (70,'ltv_ratio','<=','0.50'),
    (71,'ltv_ratio','>','0.50'), (71,'ltv_ratio','<=','0.55'),
    (72,'ltv_ratio','>','0.55'), (72,'ltv_ratio','<=','0.60'),
    (73,'ltv_ratio','>','0.60'), (73,'ltv_ratio','<=','0.80'),
    (74,'ltv_ratio','>','0.80'), (74,'ltv_ratio','<=','0.90'),
    (75,'ltv_ratio','>','0.90')
) AS v(priority, field, op, val) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Immobilier commercial : non IPRE plus favorable, IPRE standard 100 %.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '!=', 'IPRE'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9' AND dr.priority = 80
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '=', 'IPRE'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9' AND dr.priority = 81
ON CONFLICT DO NOTHING;

-- Défaut : traitement par provision coverage ratio ; résidentiel bien provisionné isolé.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, v.field, v.op, v.val
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (90,'delinquent_flag','=','TRUE'), (90,'provision_coverage_ratio','<','0.20'),
    (91,'delinquent_flag','=','TRUE'), (91,'provision_coverage_ratio','>=','0.20'), (91,'exposure_subtype','!=','RESIDENTIAL_MORTGAGE'),
    (92,'delinquent_flag','=','TRUE'), (92,'provision_coverage_ratio','>=','0.20'), (92,'exposure_subtype','=','RESIDENTIAL_MORTGAGE')
) AS v(priority, field, op, val) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

-- Covered bonds / CIU / Equity / Other : conditions de sous-type pour éviter le masquage.
INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'credit_quality_step', 'IN', v.cqs
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES (110,'1'),(111,'2|3'),(112,'4|5|6|UNRATED|UNKNOWN')) AS v(priority, cqs) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '=', v.subtype
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES (120,'LOOK_THROUGH'),(121,'MANDATE_BASED'),(122,'FALLBACK'),(123,'HIGH_RISK')) AS v(priority, subtype) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, v.field, v.op, v.val
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (130,'exposure_subtype','!=','SPECULATIVE'), (130,'exposure_subtype','!=','STRATEGIC'),
    (131,'exposure_subtype','=','SPECULATIVE'),
    (132,'exposure_subtype','=','STRATEGIC')
) AS v(priority, field, op, val) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '=', v.subtype
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES (141,'CASH'),(142,'COLLECTION_ITEM')) AS v(priority, subtype) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, 'exposure_subtype', '!=', 'CASH'
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
WHERE rs.rule_set_name = 'RS_RW_V2' AND rs.regulatory_version_id = 'CRR3_V9' AND dr.priority = 140
ON CONFLICT DO NOTHING;

-- 2) Protection bucket : ne plus classifier toutes les FCP/UFCP par la première
--    règle large ; utiliser collateral_type / provider_type / protection_subtype.
UPDATE ref.ref_decision_rules dr
SET priority = 75
FROM ref.ref_decision_rule_sets rs
WHERE dr.rule_set_id = rs.rule_set_id
  AND rs.rule_set_name = 'RS_PROTECTION_BUCKET'
  AND rs.regulatory_version_id = 'CRR3_V9'
  AND dr.result_value = 'CDS';

DELETE FROM ref.ref_rule_conditions
WHERE rule_id IN (
    SELECT dr.rule_id
    FROM ref.ref_decision_rules dr
    JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
    WHERE rs.rule_set_name = 'RS_PROTECTION_BUCKET'
      AND rs.regulatory_version_id = 'CRR3_V9'
);

INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
SELECT dr.rule_id, v.field, v.op, v.val
FROM ref.ref_decision_rules dr
JOIN ref.ref_decision_rule_sets rs ON rs.rule_set_id = dr.rule_set_id
JOIN (VALUES
    (10,'protection_type','=','FCP'), (10,'collateral_type','IN','CASH_DEPOSIT|CASH'),
    (20,'protection_type','=','FCP'), (20,'collateral_type','=','SOVEREIGN_BOND_EEA'),
    (30,'protection_type','=','FCP'), (30,'collateral_type','=','CORPORATE_BOND_IG'),
    (40,'protection_type','=','FCP'), (40,'collateral_type','IN','EQUITY_MAIN_INDEX|EQUITY_OTHER'),
    (50,'protection_type','=','FCP'), (50,'collateral_type','=','GOLD'),
    (60,'protection_type','=','FCP'), (60,'collateral_type','=','COVERED_BOND'),
    (70,'protection_type','=','FCP'), (70,'collateral_type','IN','RESIDENTIAL_RE|COMMERCIAL_RE'),
    (75,'protection_type','=','UFCP'), (75,'protection_subtype','=','CDS'),
    (80,'protection_type','=','UFCP'), (80,'provider_type','IN','CENTRAL_GOVT|SOVEREIGN'),
    (90,'protection_type','=','UFCP'), (90,'provider_type','IN','BANK|INSTITUTION'),
    (100,'protection_type','=','UFCP'), (100,'provider_type','=','CORPORATE'),
    (110,'protection_type','=','UFCP'), (110,'provider_type','=','MULTILATERAL_BANK'),
    (999,'protection_type','IN','FCP|UFCP')
) AS v(priority, field, op, val) ON v.priority = dr.priority
WHERE rs.rule_set_name = 'RS_PROTECTION_BUCKET'
  AND rs.regulatory_version_id = 'CRR3_V9'
ON CONFLICT DO NOTHING;

INSERT INTO ref.ref_runtime_parameters
    (regulatory_version_id, parameter_name, parameter_value, parameter_type)
VALUES
    ('CRR3_V9', 'PATCH_V2_8_P1_APPLIED', '2026-05-19', 'string')
ON CONFLICT (regulatory_version_id, parameter_name)
DO UPDATE SET parameter_value = EXCLUDED.parameter_value;


COMMIT;
-- =============================================================================
-- PATCH v5.0.0 — Credit SA Final Standard corrective overlay
-- =============================================================================
-- CRR3 Art.111 : bucketisation hors-bilan explicite. Le bucket 5 est à 10 %.
-- Rétrocompatibilité : les règles legacy product_type_id restent disponibles si
-- annex_i_bucket n'est pas alimenté.
DO $$
DECLARE
    rs_id BIGINT;
    r_id BIGINT;
BEGIN
    SELECT rule_set_id INTO rs_id
    FROM ref.ref_decision_rule_sets
    WHERE regulatory_version_id = 'CRR3_V9'
      AND rule_set_name = 'RS_CCF_V2';

    IF rs_id IS NOT NULL THEN
        -- Supprime les overlays bucket v5.0.0 s'ils existent déjà.
        DELETE FROM ref.ref_rule_conditions
        WHERE rule_id IN (SELECT rule_id FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority BETWEEN 1 AND 5);
        DELETE FROM ref.ref_decision_rules
        WHERE rule_set_id = rs_id AND priority BETWEEN 1 AND 5;

        INSERT INTO ref.ref_decision_rules (rule_set_id, priority, result_key, result_value)
        VALUES
            (rs_id, 1, 'CCF', '1.00'),
            (rs_id, 2, 'CCF', '0.50'),
            (rs_id, 3, 'CCF', '0.40'),
            (rs_id, 4, 'CCF', '0.20'),
            (rs_id, 5, 'CCF', '0.10');

        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'annex_i_bucket', '=', 'BUCKET_1'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 1;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'annex_i_bucket', '=', 'BUCKET_2'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 2;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'annex_i_bucket', '=', 'BUCKET_3'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 3;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'annex_i_bucket', '=', 'BUCKET_4'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 4;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'annex_i_bucket', '=', 'BUCKET_5'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 5;

        -- Legacy hardening : les engagements révocables classiques ne tombent plus à 0 %.
        UPDATE ref.ref_decision_rules
           SET result_value = '0.10'
         WHERE rule_set_id = rs_id
           AND priority = 90
           AND result_key = 'CCF';
    END IF;
END $$;

-- CRR3 Art.133 : equities ordinaires 250 %, speculative unlisted 400 %, strategic 150 %.
DO $$
DECLARE
    rs_id BIGINT;
BEGIN
    SELECT rule_set_id INTO rs_id
    FROM ref.ref_decision_rule_sets
    WHERE regulatory_version_id = 'CRR3_V9'
      AND rule_set_name = 'RS_RW_V2';

    IF rs_id IS NOT NULL THEN
        UPDATE ref.ref_decision_rules SET result_value = '2.50'
         WHERE rule_set_id = rs_id AND priority = 130 AND result_key = 'RISK_WEIGHT';
        UPDATE ref.ref_decision_rules SET result_value = '4.00'
         WHERE rule_set_id = rs_id AND priority = 131 AND result_key = 'RISK_WEIGHT';
        UPDATE ref.ref_decision_rules SET result_value = '1.50'
         WHERE rule_set_id = rs_id AND priority = 132 AND result_key = 'RISK_WEIGHT';

        -- Specialised lending / ADC high-level CRR3 grid.
        DELETE FROM ref.ref_rule_conditions
        WHERE rule_id IN (SELECT rule_id FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority BETWEEN 54 AND 59);
        DELETE FROM ref.ref_decision_rules
        WHERE rule_set_id = rs_id AND priority BETWEEN 54 AND 59;

        INSERT INTO ref.ref_decision_rules (rule_set_id, priority, result_key, result_value)
        VALUES
            (rs_id, 54, 'RISK_WEIGHT', '1.30'), -- PROJECT_FINANCE pre-operational / unrated prudentiel
            (rs_id, 55, 'RISK_WEIGHT', '1.00'), -- OBJECT_FINANCE / COMMODITIES_FINANCE generic
            (rs_id, 56, 'RISK_WEIGHT', '1.50'), -- ADC generic
            (rs_id, 57, 'RISK_WEIGHT', '1.00'), -- TRANSADC / qualifying ADC fallback
            (rs_id, 58, 'RISK_WEIGHT', '1.50'), -- speculative immovable property / high risk
            (rs_id, 59, 'RISK_WEIGHT', '1.30'); -- specialised lending fallback

        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'exposure_subtype', '=', 'PROJECT_FINANCE'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 54;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'exposure_subtype', 'IN', 'OBJECT_FINANCE|COMMODITIES_FINANCE'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 55;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'exposure_subtype', 'IN', 'ADC|LAND_ACQUISITION_DEVELOPMENT_CONSTRUCTION'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 56;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'exposure_subtype', '=', 'TRANSADC'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 57;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'exposure_subtype', '=', 'SPECULATIVE_IMMOVABLE_PROPERTY'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 58;
        INSERT INTO ref.ref_rule_conditions (rule_id, condition_field, condition_operator, condition_value)
        SELECT rule_id, 'exposure_subtype', '=', 'SPECIALISED_LENDING'
        FROM ref.ref_decision_rules WHERE rule_set_id = rs_id AND priority = 59;
    END IF;
END $$;

