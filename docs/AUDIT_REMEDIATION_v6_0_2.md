# Matrice de remédiation publique — Community v6.0.2

Baseline : projet source complet Community v6.0.1, régénéré depuis l’overlay Enterprise v6.0.2.

| Priorité | Remédiation publique | Preuve |
|---|---|---|
| P0 | `run_standard_engine` décomposé ; unités surveillées sous CC 20 | `tests/test_p0_complexity.py` |
| P0 | README court et commandes publiques explicites | `README.md` |
| P1 | Notes méthodologiques SA et SA-CCR | `docs/REGULATORY_METHODOLOGY_INDEX.md` |
| P1 | SBOM avec licences SPDX | `SBOM_Corep_Community_v6.0.2.json` |
| P1 | Captures larges documentées et contrôlées | `tools/check_broad_exception_policy.py` |

Qualification locale : **152 tests réussis, 1 ignoré**, couverture globale avec branches **71 %**, compilation et frontière SA/SA-CCR réussies. PostgreSQL E2E, Ruff, Mypy, Bandit et pip-audit restent à rejouer dans la CI connectée.
