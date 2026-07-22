# Lignage des données — de la source aux états COREP/FINREP
**Version 6.10.1.** Flux unique, identique pour toutes les feuilles ; chaque étape est matérialisée en base et re-jouable par `batch_id`.

## 1. Pipeline générique (5 étapes matérialisées)
```
(1) staging.*            ← ingestion.py : normalisation colonnes/types (Col specs, _to_bool/_norm),
                            sources multiples par champ, TRUNCATE contrôlé par liste interne
(2) validation           ← validation.py : contrôles fail-closed par table ; rejets → _reject_batch
                            → statut NO-GO ; contrôles matérialisés dans rpt.rpt_controls
(3) ref.*                ← seeds SQL versionnés (18 fichiers, paramètres cités article par article),
                            sélection par ref.ref_regulatory_versions + date de reporting
(4) core.*               ← moteurs : standard_engine (SA), irb_engine, saccr_engine, protection_strategy
                            (CRM), supporting_factors (Art.501), market_risk/mr_sa/mr_ima, liquidity_engine,
                            irrbb_engine, large_exposures, own_funds, output_floor, cva_engine
                            + traces : rpt.rpt_decision_rule_trace / rpt_mapping_rule_trace /
                            rpt_supporting_factor_trace
(5) restitution          ← corep_excel_filler / finrep_excel_filler / dpm_xbrl_exporter / eba_xbrl_csv
                            + rpt.rpt_reconciliation (réconciliation reportée) + rpt.rpt_xbrl_export_audit
```
Édition Community : mêmes étapes, moteurs limités à SA crédit + SA-CCR (+ CRM, facteurs de soutien).

## 2. Lignage par feuille COREP (fonction de remplissage → entrées)
| Feuille | Fonction | Entrées (tables/moteurs) |
|---|---|---|
| C 01.00 / C 02.00 / C 03.00 | `_c0100/_c0200/_c0300` | fonds propres (`own_funds_engine` → cap), RWA agrégés par domaine (SA, IRB, SA-CCR, SFT, MR, op., CVA), `core.core_output_floor` |
| C 05.01 / C 06.02 | `_c0501/_c0602` | solvabilité groupe / entités — agrégats `core.core_standard_results` + fonds propres |
| C 07.00 | `_c0700` | SA crédit : `core.core_standard_results` (+ traces mapping/décision) |
| C 08.01 | `_c0801` | IRB : résultats moteur IRB (PD/LGD floorés, K, RWA) |
| C 10.01 | `_c1001` (+ `_c1001_fill`) | ventilation par classe d'actifs × produit (agrégation des résultats SA/IRB) |
| C 11.01 / C 12.01 | `_c1101/_c1201` | règlement-livraison / contreparties (gross, EAD par contrepartie) |
| C 13.00-C 15.00 | `_c1300/_c1400/_c1500` | titrisation, CVA (`cva_engine`, agrégats BA-CVA) |
| C 17.00 | `_c1700` | risque opérationnel (approche SMA, buckets BI) |
| C 34.02 / C 34.08 | `_c3402/_c3408` | SA-CCR : `saccr_engine` (RC, PFE, add-ons par classe, alpha 1,4) |
| C 40.00 / C 43.00 | `_c4000/_c4300` | levier : expositions LR + fonds propres T1 |
| C 66-C 76 | `_c6601…_c7300` | LCR/NSFR/ALMM : `liquidity_engine` (items, facteurs `_liq_factors`, index `_build_liq_idx`) |
| Synthèse | `_synthese` | recalcul depuis les mêmes tables `core` + `rpt.rpt_reconciliation` |
| FINREP F 01.01-F 38.01 | `_build_f0101…_build_f3801` | états financiers depuis `core`/`staging` consolidés |

## 3. Garanties de lignage
Chaque ligne `core.*` porte `batch_id` + version réglementaire ; chaque application de règle est tracée (tables `rpt_*_trace`) ; la réconciliation entre agrégats et détails est matérialisée et reportée. Un chiffre d'un état est donc auditable : feuille → fonction filler → table `core` → moteur → règles/paramètres `ref` (versionnés) → lignes `staging` validées.

## 4. Limite documentée
La granularité est la feuille/colonne (fonction de remplissage), pas encore le datapoint DPM individuel ; l'export XBRL s'appuie sur `ref.ref_dpm_concepts`/`ref_dpm_taxonomies` et journalise chaque export (`rpt.rpt_xbrl_export_audit`).
