# Changelog v6.4.1

## Added
- SQL migration governance with deterministic ordered plan and SHA-256 evidence.
- Runtime resource budgets for volumetric, PostgreSQL, Excel and benchmark smoke gates.
- Lightweight volumetric benchmark for SA and SA-CCR kernels.
- Fail-closed regulatory readiness dossier for supervisor-use governance.

## Changed
- Bumped all active release contracts to v6.4.1.
- Kept historical release files as audit trail while active files now point to v6.4.1.

## Regulatory safety
- No official submission readiness is claimed. The release remains NO-GO for supervisor filing until external taxonomy, filing rules, legal review and golden datasets are signed.

## Patch P1 interne — v6.4.1 conservée

Cette archive conserve le numéro **6.4.1** et ajoute une consolidation P1 sans changement volontaire des formules réglementaires :

- benchmark volumétrique étendu à 100 000 lignes pour SA et SA-CCR ;
- plan SQL enrichi avec table d'état `meta.corep_schema_migrations`, checksum et template de rollback non destructif ;
- budget PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` contrôlable en CI ;
- dossier réglementaire fail-closed enrichi avec exigences d'artefacts externes et matrice CRR/DPM ;
- métriques de release et docstrings réalignées après ajout des nouveaux contrôles.

Statut superviseur : **NO-GO fail-closed** tant que les preuves externes ne sont pas signées.
