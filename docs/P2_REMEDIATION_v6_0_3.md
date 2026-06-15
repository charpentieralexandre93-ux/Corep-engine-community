# Remédiation P2 — v6.0.3

## P2.8 — compatibilité Python

`requires-python` est borné à `>=3.9,<3.14`. Python 3.11 est la baseline de production reproductible et dispose des lockfiles hashés. Python 3.9, 3.12 et 3.13 restent exécutés dans la matrice CI, mais leur résolution de dépendances est qualifiée best-effort et non byte-reproductible.

## P2.9 — docstrings des points d’entrée

Le contrôle AST `tools/check_cli_docstrings.py` couvre les modules déclarés dans `[project.scripts]`, ainsi que `launcher.py` et `batch/run_batch.py`. Le seuil CI est 85 %. Résultat Community : **71/71 fonctions, 100 %**.

## P2.10 — couverture de branche post-refactoring

`tools/branch_coverage_delta.py` lit le JSON natif de coverage.py, compare les métriques aux valeurs v6.0.2 archivées et bloque toute régression supérieure à la tolérance. Le module partagé surveillé dans l’édition Community est `standard_engine.py`.

Le rapport machine lisible est `evidence/branch_coverage_v6_0_3.json` et est embarqué dans la preuve de release.
