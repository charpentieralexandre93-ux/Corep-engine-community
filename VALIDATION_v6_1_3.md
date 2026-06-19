# Validation Corep Engine Community v6.1.3

Date de validation locale : 19 juin 2026

## Contrôles introduits

- release dépendante de la CI Community complète ;
- Docker bloquant avec utilisateur `10001:10001`, bootstrap public et readiness ;
- PostgreSQL 16 Compose épinglé par digest ;
- ZIP source déterministe construit deux fois et comparé ;
- archive interdite aux caches, secrets locaux et sorties binaires ;
- matrice déclarée : Python 3.11, 3.12 et 3.13 ;
- périmètre public toujours limité à SA et SA-CCR.

## Non-régression locale

- Pytest : **169 réussis, 1 ignoré** ;
- couverture : **71,01 %**, branches : **64,17 %** ;
- Ruff bloquant : PASS ; Mypy : PASS sur 16 modules ; Bandit moyen/élevé : PASS ;
- docstrings CLI, exceptions larges, frontière publique, SBOM et contrats : PASS ;
- build wheel et ZIP source reproductibles : contrôlés dans la recette finale et en CI.

## Contrôles exclusivement CI

Docker, PostgreSQL réel, `pip-audit` réseau et Python 3.11/3.12 ne sont pas présentés comme exécutés localement. Ils précèdent obligatoirement le job de publication.
