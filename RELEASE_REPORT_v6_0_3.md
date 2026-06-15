# Release Report — Corep Engine Community v6.0.3

## Provenance et périmètre

Édition régénérée depuis la source unique Enterprise v6.0.3 et son overlay public. Le périmètre reste strictement **SA crédit + SA-CCR** ; aucun moteur premium Enterprise n'est distribué.

## Qualification exécutée

| Contrôle | Résultat |
|---|---|
| pytest complet | **155 réussis, 1 ignoré** |
| couverture globale, branches incluses | **71 %** |
| docstrings des points d'entrée | **71/71 — 100 %** |
| `standard_engine.py` — branches | **56,35 %**, delta **+0,00 pp** |
| compilation Python | réussie |
| frontière Python/SQL | réussie, 9 modules partagés et 12 scripts SQL autorisés |
| licences SBOM runtime | résolues en mode strict |

Le test PostgreSQL E2E a été ignoré faute de serveur PostgreSQL. Ruff, Mypy, Bandit et pip-audit restent à rejouer dans la CI connectée.

## Non-régression

La couverture de branche du moteur SA partagé est inchangée par rapport à v6.0.2. Aucun moteur Enterprise n'est exposé et le contrat SQL public reste limité à SA/SA-CCR.
