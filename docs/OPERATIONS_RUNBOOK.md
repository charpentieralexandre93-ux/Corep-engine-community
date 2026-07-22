# Runbook d'exploitation et de résilience — Corep Engine
**Version 6.10.1.** Couvre : sauvegarde/restauration (avec drill exécuté et évidencé), objectifs RTO/RPO, réponse à incident, journalisation et supervision. S'applique aux deux éditions ; les exemples utilisent le profil production Phase 1 (fail-closed).

## 1. Sauvegarde et restauration (testé)
**Protocole** : `pg_dump -Fc` de la base complète → stockage hors site chiffré → restauration par `pg_restore` sur instance propre → vérification par digest (nombre de tables par schéma, comptes des tables `ref` de règles, spot-checks de paramètres réglementaires).

**Drill exécuté le 18/07/2026** (évidence : `evidence/dr_restore_drill_v6_10_1.json`) — PostgreSQL 16.14, profil production Phase 1 (34 fichiers SQL) : bootstrap 2,42 s ; dump 0,14 s (296 Kio) ; **drop + restore 1,45 s** ; digest avant/après **strictement identique** (75 tables ; `ref_decision_rules` 109, `ref_mapping_rules` 101, `ref_liquidity_factors` 105, `ref_runtime_parameters` 32 ; `DEFAULT_ALPHA_SACCR` = 1,4) ; **0 erreur de restauration**. *Limite documentée : dataset = seeds de référence en environnement de développement — le drill doit être rejoué sur la volumétrie production du client (protocole identique) pour chiffrer le RTO réel.*

**Objectifs cibles produit** : RPO ≤ 24 h avec `pg_dump` quotidien (RPO court : archivage WAL continu) ; RTO ≤ 4 h sur volumétrie production (à confirmer par drill client) ; drill de restauration **au moins annuel**, évidence versionnée au même format JSON.

**Rejouabilité métier** : les données `staging` étant re-chargeables et les moteurs déterministes par `batch_id`, une restauration à J-1 suivie du re-run du batch reconstruit l'état exact — la perte maximale se limite aux saisies de configuration entre deux sauvegardes.

## 2. Réponse à incident
Classification : **P1** production d'un état réglementaire bloquée en période de remise ; **P2** batch en échec hors période critique ; **P3** anomalie sans impact sur la production d'états.
Déroulé : (1) constat — le moteur est **fail-closed** : tout échec produit un statut NO-GO explicite, jamais un état partiel ; (2) diagnostic via les journaux applicatifs (module `logging`, messages horodatés par moteur) et les tables `rpt.rpt_controls` (contrôles échoués par batch) et `rpt.rpt_*_trace` ; (3) remédiation : correction des données sources puis re-run du `batch_id` (idempotent), ou restauration (§1) si corruption ; (4) post-mortem consigné, et entrée au `docs/SECURITY_FINDINGS_REGISTER.md` si l'incident a une composante sécurité. Escalade : exploitant → mainteneur applicatif → éditeur (releases correctives selon `docs/VULNERABILITY_MANAGEMENT_POLICY.md`).

## 3. Journalisation et supervision
À journaliser en exploitation : sorties `logging` du moteur (niveau INFO minimum, WARNING+ en alerte), statuts de batch (GO/NO-GO), durées par moteur (comparées aux benchmarks versionnés en `evidence/`), résultat quotidien de `python -m corep_crr3.operational_readiness` (sondes à froid : présence relations, versions, paramètres). Alertes minimales : NO-GO, échec readiness, dérive de durée > 2× le benchmark, échec de sauvegarde. Rétention recommandée des journaux : 5 ans (alignée sur les exigences d'archivage réglementaire des remises).

## 4. Exigences d'environnement (déploiement bancaire)
PostgreSQL ≥ 14 dédié, comptes séparés : bootstrap par rôle DBA (le schéma crée des rôles applicatifs à privilèges réduits), exécution applicative par rôle limité ; secrets de connexion hors code (variables d'environnement/coffre — jamais dans `config/*.yaml` versionnés) ; chiffrement en transit (TLS PostgreSQL) et au repos (volume) ; ségrégation des environnements dev/recette/production avec promotion de release par vérification du `RELEASE_MANIFEST.json`. Stratégie de sortie : l'édition Community (Apache-2.0, moteurs SA/SA-CCR au format identique) et le format ouvert des données (PostgreSQL + SQL versionné) garantissent la réversibilité.
