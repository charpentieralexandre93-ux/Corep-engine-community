# Cartographie BCBS 239 → contrôles Corep Engine
**Version 6.10.1.** Ce document mappe les principes BCBS 239 (agrégation des données de risque et reporting) vers les contrôles **concrets et vérifiables** du moteur. Périmètre : le produit ; les principes relevant de l'organisation de la banque (gouvernance d'entreprise, infrastructure IT globale) sont indiqués comme « responsabilité client, facilitée par ».

| Principe BCBS 239 | Contrôles Corep Engine (vérifiables dans le livré) |
|---|---|
| **P1 Gouvernance** | Responsabilité client, facilitée par : matrice de sign-off réglementaire versionnée (`docs/REGULATORY_SIGNOFF_MATRIX_v*.md`), changelog cumulatif à deux niveaux, revue légale (`docs/LEGAL_REVIEW_STATUS_*.md`), politique de vulnérabilités et registre sécurité. |
| **P2 Architecture données & IT** | Modèle relationnel **BCNF documenté et testé** (`docs/Architecture_BCNF.md`, tests `test_v6_5_0_data_model_bcnf_hardening`), 4 schémas à responsabilité unique : `staging` (brut), `ref` (référentiels versionnés par `ref_regulatory_versions`), `core` (résultats moteurs), `rpt` (restitution/traces). |
| **P3 Exactitude & intégrité** | Constantes réglementaires vérifiées contre les textes (audits P0/P1/P2 avec citations) ; requêtes systématiquement paramétrées ; typage strict global mypy ; manifest SHA-256 par release (952/349 artefacts) ; build reproductible (`SOURCE_DATE_EPOCH`). |
| **P4 Complétude** | Validation **fail-closed** en entrée (`validation.py` : rejets tracés par `_reject_batch`, contrôles de complétude par table — expositions, SA-CCR, SFT, MR) ; statut NO-GO bloquant : aucun état produit sur données incomplètes ; `rpt.rpt_controls` matérialise les contrôles passés/échoués par batch. |
| **P5 Actualité** | Paramètres réglementaires datés et versionnés (`ref.ref_regulatory_versions`, phase-in output floor sélectionné par date de reporting) ; régimes transitoires bornés par dates (FRTB 2027-2029, UCC Art.495d) ; benchmarks volumétriques versionnés en evidence. |
| **P6 Adaptabilité** | Règles de décision et de mapping **en données** (`ref.ref_decision_rules`, `ref.ref_mapping_rules`, `ref.ref_runtime_parameters`) modifiables sans changement de code ; multiplicateur Art.495v par établissement ; profils de configuration (`config/config_production*.yaml`). |
| **P7 Exactitude du reporting** | Réconciliation matérialisée (`rpt.rpt_reconciliation`) et reportée dans le classeur COREP ; feuille de synthèse recalculée depuis les mêmes tables `core` que les états détaillés ; audit d'export XBRL (`rpt.rpt_xbrl_export_audit`). |
| **P8 Exhaustivité du reporting** | Couverture des états : COREP C 01-C 04 (fonds propres), C 05-C 08 (SA/IRB), C 34 (SA-CCR), C 40/C 43 (LR), C 66-C 76 (LCR/NSFR/ALMM), grands risques, FINREP F 01-F 38 (périmètre Enterprise) — voir `docs/DATA_LINEAGE_COREP.md` pour le détail par feuille. |
| **P9 Clarté & utilité** | Notes méthodologiques par domaine (`docs/*_Methodology_Note.md`), index réglementaire (`docs/REGULATORY_METHODOLOGY_INDEX.md`), libellés réglementaires dans les classeurs générés. |
| **P10 Fréquence** | Moteur batch re-exécutable à volonté ; benchmarks de volumétrie versionnés attestant les temps de production ; readiness checks à froid (`operational_readiness`). |
| **P11 Distribution** | Exports Excel COREP/FINREP et XBRL/CSV EBA avec audit d'export ; intégrité du livrable vérifiable par manifest. |

## Traçabilité décisionnelle (transverse P3/P4/P7)
Chaque application de règle est journalisée en base : `rpt.rpt_decision_rule_trace` (règles de décision, ex. CCF), `rpt.rpt_mapping_rule_trace` (mapping produits/classes), `rpt.rpt_supporting_factor_trace` (facteurs Art.501/501a par exposition). Un chiffre COREP est ainsi remontable jusqu'aux règles et paramètres qui l'ont produit, par `batch_id`.

## Écarts connus et plan
Le lignage cellule-par-cellule est documenté au niveau feuille/fonction (`docs/DATA_LINEAGE_COREP.md`) ; une granularité cellule (datapoint DPM) est un chantier ultérieur. La ré-attestation périodique des preuves chiffrées relève de la CI PostgreSQL complète du mainteneur.
