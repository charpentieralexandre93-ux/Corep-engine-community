# Changelog v6.3.0 — COREP Engine Community

Date : 20 juin 2026

## P0 corrigés

- alignement du DDL `core.core_standard_results` sur les 26 colonnes réellement persistées par `standard_engine.py` ;
- ajout de `ccf_applied` et des neuf champs de traçabilité SA manquants ;
- `cqs_used` devient `VARCHAR(20)` afin d'accepter les valeurs numériques et `UNRATED` ;
- synchronisation du SQL source, du SQL Community généré et des ressources embarquées dans les wheels.

## P1 corrigés

- migration PostgreSQL idempotente pour les installations v6.2.x ;
- variable `PGPASSWORD` disponible pendant l'intégralité des workflows Docker/PostgreSQL ;
- quatre tests de non-régression sur le contrat DDL/INSERT, la migration et le SQL embarqué ;
- artefacts, preuves, SBOM, manifestes, wheels et ZIP renommés et synchronisés en 6.3.0.
- alignement du filtre du manifeste sur celui du ZIP : `.coverage`, `coverage.json` et `coverage.xml` sont exclus des deux contrats.

Aucune formule réglementaire ni calibration prudentielle n'est modifiée. Périmètre : SA et SA-CCR publics.
