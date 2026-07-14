# Validation Community v6.8.0

## Validation strategy
This release is validated as a technical consolidation release. It adds operational controls without changing regulatory calculation formulas.

## Gates to execute in CI
- Unit and integration tests.
- Ruff, formatting, Mypy and Bandit.
- Release contract and release integrity.
- Source ZIP reproducibility.
- SQL migration plan validation.
- Resource budget validation from benchmark JSON.

## Supervisor readiness
Official submission remains `NO_GO` until the external regulatory and legal gates in `evidence/regulatory_dossier_v6_8_0.json` are marked `PASSED` with signed evidence.

## Patch P1 interne — v6.8.0 conservée

Cette archive conserve le numéro **6.8.0** et ajoute une consolidation P1 sans changement volontaire des formules réglementaires :

- benchmark volumétrique étendu à 100 000 lignes pour SA et SA-CCR ;
- plan SQL enrichi avec table d'état `meta.corep_schema_migrations`, checksum et template de rollback non destructif ;
- budget PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` contrôlable en CI ;
- dossier réglementaire fail-closed enrichi avec exigences d'artefacts externes et matrice CRR/DPM ;
- métriques de release et docstrings réalignées après ajout des nouveaux contrôles.

Statut superviseur : **NO-GO fail-closed** tant que les preuves externes ne sont pas signées.
