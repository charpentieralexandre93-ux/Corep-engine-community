# Release Report — Corep Engine Community v6.1.3

**Statut local : GO pour soumission à la CI. Publication interdite tant que le workflow Community complet n’est pas vert.**

Date de validation locale : 19 juin 2026

## Périmètre

Édition publique générée depuis Enterprise v6.1.3, limitée à SA et SA-CCR. Aucun moteur privé et aucun changement de formule réglementaire.

## Correctifs livrés

- workflow Community réutilisable et bloquant avant publication ;
- job Docker avec utilisateur non-root, bootstrap Community et readiness PostgreSQL ;
- ZIP source déterministe sans caches, contrôlé deux fois en CI ;
- PostgreSQL Compose épinglé par digest ;
- preuves alignées sur Python 3.11/3.12/3.13 ;
- contrat public renforcé.

## Résultats locaux

- Pytest : **169 réussis, 1 ignoré** ;
- couverture combinée : **71,01 %** ; statements : **72,96 %** ; branches : **64,17 %** ;
- Ruff bloquant, Mypy (16 modules), Bandit moyen/élevé et politique des exceptions : **PASS** ;
- docstrings CLI : **71/71 (100 %)** ;
- frontière SA/SA-CCR, SBOM, contrats et manifeste : **PASS**.

Le test ignoré est la recette PostgreSQL Community exécutée dans GitHub Actions. Docker, audit réseau et Python 3.11/3.12 ne sont pas présentés comme exécutés localement.

## Chaîne de publication

Le job de publication dépend du workflow Community complet. Une GitHub Release ne peut donc pas être créée si les tests, PostgreSQL, Docker, la supply-chain, la frontière publique ou la reproductibilité échouent.

## Artefacts courants

- `RELEASE_MANIFEST.json` ;
- `SBOM_Corep_Community_v6.1.3.json` ;
- `VALIDATION_v6_1_3.md` ;
- ZIP source déterministe `Corep_engine_community_v6.1.3.zip`.
