# Release Report — Corep Engine Community v6.0.2

## Provenance et périmètre

Édition générée depuis la source unique Enterprise v6.0.2 et son overlay public, à partir des archives projets complètes v6.0.1. Le périmètre reste strictement **SA crédit + SA-CCR** ; aucun orchestrateur ou moteur premium Enterprise n’est distribué.

## Qualification exécutée

| Contrôle | Résultat |
|---|---|
| pytest complet | **152 réussis, 1 ignoré** |
| couverture globale, branches incluses | **71 %** |
| compilation Python | réussie |
| contrat de release Apache-2.0 | réussi |
| frontière Python/SQL | réussie, 9 modules partagés et 12 scripts SQL autorisés |
| politique `except Exception` | réussie |
| versions package/SQL/workflows | 6.0.2 cohérentes |
| SBOM licences SPDX, mode strict | réussi, 1/1 composant runtime |
| wheel `corep_crr3_community-6.0.2` | construit et smoke-testé en environnement isolé |

Le test PostgreSQL E2E a été ignoré faute de serveur PostgreSQL. Ruff, Mypy, Bandit, pip-audit et CycloneDX CLI restent à rejouer dans la CI connectée ; aucun résultat non exécuté n’est présenté comme réussi.
