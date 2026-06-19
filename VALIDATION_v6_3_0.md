# Validation Corep Engine Community v6.3.0

Date de validation locale : 20 juin 2026

## Objet

Correction P0/P1 du contrat de persistance SA et de la chaîne GitHub Actions/packaging.

## Résultats locaux

- Pytest : **183 réussis, 1 ignoré** (recette PostgreSQL réelle) ;
- couverture globale : **67,99 %**, seuil CI 65 % respecté ;
- couverture branches surveillée : Standard **56,35 %**, SA-CCR **58,62 %**, GUI **60,20 %**, sans régression ;
- Ruff CI et formatage : réussis ;
- Mypy : réussi ;
- Bandit Medium/High : réussi ;
- contrat de release, SBOM/lockfiles et manifeste SHA-256 : réussis ;
- tests de performance : réussis, noyau le plus lent à environ **477 000 appels/s** pour un seuil de 5 000.

## Contrôles réservés à GitHub Actions

PostgreSQL 16, Docker et l'audit réseau `pip-audit` ne sont pas présentés comme exécutés localement. La publication reste interdite tant que tous les jobs distants ne sont pas verts.
