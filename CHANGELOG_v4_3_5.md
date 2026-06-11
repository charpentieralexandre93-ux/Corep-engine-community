# CHANGELOG — Community v4.3.5

> v4.3.5 = hotfix qualité de v4.3.4 : alignement version, nettoyage Ruff, typage Mypy minimal et packaging propre.

## Correctifs qualité

- Ruff : formatage et lint OK sur `src`, `tests`, `tools`.
- Pytest : contrat SQL Community et manifeste alignés sur `corep_crr3.__version__ == 4.3.5`.
- Mypy : ajout d'une configuration mypy minimale, imports `NotRequired` compatibles, signatures `dsn` optionnelles et cache décisionnel typé.
- Bandit : aucun issue identifié.

## Validation locale

- `ruff check src tests tools` : OK
- `pytest -q` : 114 passed, 1 skipped
- `mypy src/corep_crr3` : OK
- `bandit -r src/corep_crr3 -ll` : No issues identified
