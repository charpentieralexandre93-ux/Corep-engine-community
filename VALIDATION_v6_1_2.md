# Validation Corep Engine Community v6.1.2

Date de validation : 19 juin 2026

## Correctifs couverts

- cohérence de version package / CI / Docker / documentation ;
- SBOM aligné sur le lockfile runtime ;
- génération Community déterministe depuis Enterprise ;
- résolution DSN centralisée et secrets échappés ;
- image Docker documentée comme job one-shot ;
- frontière publique limitée à SA et SA-CCR.

## Non-régression locale

- `pytest` : 166 réussis, 1 ignoré ;
- couverture combinée : 71,00 % ; branches : 64,17 % ;
- Ruff bloquant, Mypy, Bandit moyen/élevé, compilation et politique d'exceptions : PASS ;
- SBOM, frontière publique, contrat de release et manifeste : PASS.

Les contrôles PostgreSQL réels, Docker, réseau et matrice multi-Python restent bloquants dans GitHub Actions avant publication du tag.
