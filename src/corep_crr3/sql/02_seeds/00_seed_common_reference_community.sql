-- =============================================================================
-- 00_seed_common_reference_community.sql
-- Socle commun BCNF : version réglementaire, référentiels partagés et paramètres transverses.
-- Aucune règle de calcul moteur n'est seedée ici.
-- =============================================================================
BEGIN;
-- 1. Version réglementaire
INSERT INTO ref.ref_regulatory_versions (regulatory_version_id, description, effective_date) VALUES
('CRR3_V9', 'Basel III / CRR3 V9 Edition Ultra Pédagogique', '2026-01-01')
ON CONFLICT (regulatory_version_id) DO UPDATE
    SET description = EXCLUDED.description,
        effective_date = EXCLUDED.effective_date;

-- 2. Classes d'actifs minimales
INSERT INTO ref.ref_asset_classes (asset_class_id, description) VALUES
('CORPORATE', 'Expositions sur les entreprises'),
('RETAIL', 'Expositions sur la clientèle de détail'),
('SOVEREIGN', 'Expositions sur les administrations centrales et banques centrales'),
('BANK', 'Expositions sur les établissements de crédit')
ON CONFLICT (asset_class_id) DO UPDATE
    SET description = EXCLUDED.description;

-- 3. Types de produits minimaux
INSERT INTO ref.ref_product_types (product_type_id, description) VALUES
('TERM_LOAN', 'Prêt à terme'),
('REVOLVING', 'Crédit renouvelable'),
('COMMITMENT', 'Engagement de financement')
ON CONFLICT (product_type_id) DO UPDATE
    SET description = EXCLUDED.description;

-- 4. Contreparties de démonstration
INSERT INTO ref.ref_counterparties (counterparty_id, counterparty_type, name) VALUES
('CP_CORP_01', 'CORPORATE', 'Enterprise Solutions SAS'),
('CP_BANK_01', 'BANK', 'Global Bank Corp'),
('CP_SOV_01', 'SOVEREIGN', 'French Republic'),
('CP_RETAIL_01', 'RETAIL', 'Jean Dupont')
ON CONFLICT (counterparty_id) DO UPDATE
    SET counterparty_type = EXCLUDED.counterparty_type,
        name = EXCLUDED.name;

-- 5. Paramètres runtime minimaux
INSERT INTO ref.ref_runtime_parameters (regulatory_version_id, parameter_name, parameter_type, parameter_value) VALUES
('CRR3_V9', 'ENABLE_TEMPLATE_MAPPING', 'TEXT', 'Y'),
('CRR3_V9', 'DEFAULT_ALPHA_SACCR', 'REAL', '1.4'),
('CRR3_V9', 'ENABLE_SUPPORTING_FACTORS', 'TEXT', 'Y')
ON CONFLICT (regulatory_version_id, parameter_name) DO UPDATE
    SET parameter_type = EXCLUDED.parameter_type,
        parameter_value = EXCLUDED.parameter_value;

-- Référentiels enrichis partagés par plusieurs moteurs
-- =============================================================================
-- 1. CLASSES D'ACTIFS (Art. 112 CRR3 — liste exhaustive)
-- =============================================================================
INSERT INTO ref.ref_asset_classes (asset_class_id, description) VALUES
-- Portefeuille standard
('CENTRAL_GOVT',          'Administrations centrales et banques centrales — Art.114'),
('REGIONAL_GOVT',         'Administrations régionales et autorités locales — Art.115'),
('PUBLIC_SECTOR',         'Entités du secteur public — Art.116'),
('MULTILATERAL_BANK',     'Banques multilatérales de développement — Art.117'),
('INTL_ORG',              'Organisations internationales — Art.118'),
('INSTITUTION',           'Établissements de crédit et entreprises d''investissement — Art.119-121'),
('CORPORATE',             'Entreprises — Art.122'),
('RETAIL',                'Clientèle de détail — Art.123'),
('RESIDENTIAL_MORTGAGE',  'Expositions garanties par un bien immobilier résidentiel — Art.124'),
('COMMERCIAL_MORTGAGE',   'Expositions garanties par un bien immobilier commercial — Art.126'),
('DEFAULT',               'Expositions en défaut — Art.127'),
('HIGH_RISK',             'Expositions à risque élevé — Art.128'),
('COVERED_BOND',          'Obligations garanties (covered bonds) — Art.129'),
('SHORT_TERM_CORP',       'Créances court terme sur établissements et entreprises — Art.131'),
('CIU',                   'Organismes de placement collectif (OPC) — Art.132'),
('EQUITY',                'Actions et participations — Art.133'),
('OTHER',                 'Autres actifs — Art.134'),
-- Sous-classes spéciales
('SME_CORPORATE',         'PME — Portefeuille entreprises (fatorer soutien 0,7619)'),
('SME_RETAIL',            'PME — Portefeuille retail (facteur soutien 0,7619)'),
('INFRA_CORPORATE',       'Infrastructure — Entreprises (facteur soutien 0,75)'),
('INFRA_PROJECT',         'Infrastructure — Financement de projets (Art.501a)'),
('SOVEREIGN',             'Souverains (alias CENTRAL_GOVT pour compatibilité)'),
('BANK',                  'Établissements (alias INSTITUTION pour compatibilité)')
ON CONFLICT (asset_class_id) DO NOTHING;

-- =============================================================================
-- 2. TYPES DE PRODUITS (couverture complète bilan + hors-bilan)
-- =============================================================================
INSERT INTO ref.ref_product_types (product_type_id, description) VALUES
-- Produits au bilan
('TERM_LOAN',             'Prêt à terme (amortissable ou in fine)'),
('REVOLVING',             'Crédit renouvelable (revolving credit facility)'),
('OVERDRAFT',             'Découvert bancaire'),
('MORTGAGE',              'Prêt immobilier (résidentiel ou commercial)'),
('LEASING',               'Contrat de crédit-bail (leasing / LOA)'),
('REPO',                  'Mise en pension (repo / sale and repurchase agreement)'),
('REVERSE_REPO',          'Prise en pension (reverse repo)'),
('SECURITIES_LENDING',    'Prêt de titres (securities lending)'),
('BOND',                  'Obligation (détenue à l''actif)'),
('COVERED_BOND_HELD',     'Obligation garantie détenue — Art.129'),
('EQUITY_HOLDING',        'Participation au capital / action'),
('FUND_UNIT',             'Part d''OPC / fonds d''investissement'),
('TRADE_RECEIVABLE',      'Créance commerciale (trade receivable)'),
-- Produits hors-bilan (Art.111 CRR3 — CCF requis)
('COMMITMENT',            'Engagement de financement irrévocable (CCF 40%)'),
('REVOCABLE_COMMITMENT',  'Engagement de financement révocable (CCF 0%)'),
('GUARANTEE',             'Garantie financière émise (CCF 100%)'),
('PERFORMANCE_BOND',      'Caution de bonne fin / performance bond (CCF 50%)'),
('LETTER_OF_CREDIT',      'Crédit documentaire (CCF 20%)'),
('STANDBY_LC',            'Stand-by letter of credit (CCF 100%)'),
('ACCEPTANCE',            'Acceptation bancaire (CCF 100%)'),
('NOTE_ISSUANCE',         'Facilité d''émission de billets — NIF / RUF (CCF 50%)'),
('FORWARD_ASSET',         'Achat à terme d''actif (CCF 100%)'),
-- Dérivés (traités via SA-CCR / C34.02)
('INTEREST_RATE_SWAP',    'Swap de taux d''intérêt (IRS)'),
('CDS',                   'Credit Default Swap'),
('FX_FORWARD',            'Change à terme / FX Forward'),
('FX_OPTION',             'Option de change'),
('EQUITY_OPTION',         'Option sur action'),
('COMMODITY_DERIV',       'Dérivé sur matière première'),
('CROSS_CURRENCY_SWAP',   'Swap de devises croisées (XCCY)')
ON CONFLICT (product_type_id) DO NOTHING;

-- =============================================================================
-- 3. TYPES DE CONTREPARTIES (enrichis)
-- =============================================================================
INSERT INTO ref.ref_counterparties (counterparty_id, counterparty_type, name) VALUES
-- Institutionnels
('CP_SOVEREIGN_FR',  'CENTRAL_GOVT',      'État français — Trésor'),
('CP_SOVEREIGN_DE',  'CENTRAL_GOVT',      'État allemand — Bundesrepublik'),
('CP_ECB',           'CENTRAL_GOVT',      'Banque centrale européenne'),
('CP_BDF',           'CENTRAL_GOVT',      'Banque de France'),
('CP_EIB',           'MULTILATERAL_BANK', 'Banque Européenne d''Investissement'),
('CP_EBRD',          'MULTILATERAL_BANK', 'Banque Européenne pour la Reconstruction et le Développement'),
('CP_IMF',           'INTL_ORG',          'Fonds Monétaire International'),
-- Établissements financiers (RW 20-50% selon notation)
('CP_BANK_AA',       'INSTITUTION',       'Établissement noté AA — RW 20%'),
('CP_BANK_A',        'INSTITUTION',       'Établissement noté A — RW 20%'),
('CP_BANK_BBB',      'INSTITUTION',       'Établissement noté BBB — RW 50%'),
('CP_BANK_UNRATED',  'INSTITUTION',       'Établissement non noté — RW 50%'),
-- Secteur public
('CP_PSE_FR',        'PUBLIC_SECTOR',     'Collectivité territoriale française'),
('CP_PSE_DE',        'PUBLIC_SECTOR',     'Entité publique allemande'),
-- Entreprises
('CP_CORP_IG',       'CORPORATE',         'Grande entreprise investment grade (noté BBB+)'),
('CP_CORP_HY',       'CORPORATE',         'Entreprise high yield (noté BB)'),
('CP_CORP_UNRATED',  'CORPORATE',         'Entreprise non notée — RW 100%'),
('CP_SME_001',       'CORPORATE',         'PME éligible facteur de soutien — chiffre d''affaires < 50M EUR'),
('CP_SME_002',       'CORPORATE',         'PME — secteur technologique'),
-- Retail
('CP_RETAIL_001',    'RETAIL',            'Particulier — crédit immobilier résidentiel'),
('CP_RETAIL_002',    'RETAIL',            'Particulier — crédit consommation'),
('CP_RETAIL_003',    'RETAIL',            'Travailleur indépendant — crédit professionnel'),
-- Défaut
('CP_DEFAULT_001',   'CORPORATE',         'Entreprise en défaut — EAD résiduelle'),
-- Existants (compatibilité)
('CP001', 'CORPORATE', 'Contrepartie existante 001'),
('CP002', 'RETAIL',    'Contrepartie existante 002'),
('CP003', 'SOVEREIGN', 'Contrepartie existante 003'),
('CP004', 'BANK',      'Contrepartie existante 004'),
-- Compatibilité avec input/saccr_trades.csv
('CP_BANK_01', 'BANK',      'Banque de marché 01 — exemple SA-CCR'),
('CP_BANK_02', 'BANK',      'Banque de marché 02 — exemple SA-CCR'),
('CP_BANK_03', 'BANK',      'Banque de marché 03 — exemple SA-CCR'),
('CP_CORP_01', 'CORPORATE', 'Entreprise 01 — exemple SA-CCR'),
('CP_CORP_02', 'CORPORATE', 'Entreprise 02 — exemple SA-CCR')
ON CONFLICT (counterparty_id) DO NOTHING;

-- Paramètres runtime transverses
INSERT INTO ref.ref_runtime_parameters (regulatory_version_id, parameter_name, parameter_type, parameter_value) VALUES
('CRR3_V9', 'ENABLE_TEMPLATE_MAPPING',   'TEXT', 'Y'),
('CRR3_V9', 'ENABLE_SUPPORTING_FACTORS', 'TEXT', 'Y'),
('CRR3_V9', 'REPORTING_CURRENCY',        'TEXT', 'EUR')
ON CONFLICT (regulatory_version_id, parameter_name) DO UPDATE SET
    parameter_type = EXCLUDED.parameter_type,
    parameter_value = EXCLUDED.parameter_value;
COMMIT;
