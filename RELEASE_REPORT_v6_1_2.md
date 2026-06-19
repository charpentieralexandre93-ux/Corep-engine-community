# Release Report — Corep Engine Community v6.1.2

**Statut local : GO sous réserve des contrôles CI nécessitant PostgreSQL, Docker et l'accès réseau.**

Date de validation locale : 19 juin 2026

## Périmètre

Édition publique SA + SA-CCR générée depuis l'Enterprise v6.1.2. Aucun moteur Enterprise n'est inclus.

## Correctifs livrés

- cohérence 6.1.2 entre package, CI, release, Docker, documentation, SBOM et manifestes ;
- SBOM et métadonnées d'application réalignés ;
- génération déterministe depuis la source Enterprise avec overlay public et manifeste final ;
- construction DSN centralisée, valeurs libpq échappées et commande de secret bornée par timeout ;
- image Docker clarifiée comme job one-shot ;
- tests de non-régression dédiés aux correctifs v6.1.2.

## Résultats locaux

- Pytest : **166 réussis, 1 ignoré** ;
- couverture combinée lignes/branches : **71,00 %** ;
- couverture des statements : **72,94 %** ;
- couverture des branches : **64,17 %** ;
- Ruff bloquant : **PASS** ;
- Mypy : **PASS — 16 modules** ;
- Bandit moyen/élevé : **PASS** ;
- politique des exceptions larges : **PASS** ;
- compilation Python : **PASS** ;
- frontière publique Python/SQL : **PASS** ;
- synchronisation SBOM/lockfile : **PASS** ;
- contrat de release et manifeste : **PASS**.

## Contrôles restant obligatoires dans GitHub Actions

- bootstrap et E2E sur PostgreSQL réel ;
- construction effective de l'image Docker ;
- audit de dépendances nécessitant le réseau ;
- matrice Python du workflow ;
- reproductibilité des artefacts dans l'environnement Linux de release.

## Artefacts de preuve

- manifeste : `RELEASE_MANIFEST.json` ;
- SBOM : `SBOM_Corep_Community_v6.1.2.json` ;
- couverture de branches : `evidence/branch_coverage_v6_1_2.json` ;
- validation : `VALIDATION_v6_1_2.md`.
