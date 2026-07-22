# Release report Community v6.4.1

## Scope
v6.4.1 is an engineering consolidation release focused on migrations, resource budgets, volumetric benchmarks and regulatory readiness evidence.

## Non-regression objective
- No regulatory formula change.
- Public/private boundary preserved.
- Release manifest regenerated after the final tree is frozen.

## New v6.4.1 gates
- `corep_crr3.sql_migrations` validates deterministic SQL ordering.
- `corep_crr3.resource_budgets` validates benchmark measurements.
- `corep_crr3.regulatory_dossier` keeps official submission readiness fail-closed.

## Patch P1 interne — v6.4.1 conservée

Cette archive conserve le numéro **6.4.1** et ajoute une consolidation P1 sans changement volontaire des formules réglementaires :

- benchmark volumétrique étendu à 100 000 lignes pour SA et SA-CCR ;
- plan SQL enrichi avec table d'état `meta.corep_schema_migrations`, checksum et template de rollback non destructif ;
- budget PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` contrôlable en CI ;
- dossier réglementaire fail-closed enrichi avec exigences d'artefacts externes et matrice CRR/DPM ;
- métriques de release et docstrings réalignées après ajout des nouveaux contrôles.

Statut superviseur : **NO-GO fail-closed** tant que les preuves externes ne sont pas signées.
