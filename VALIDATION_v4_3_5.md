# Validation locale — Community v4.3.5

Contrôles exécutés dans l'environnement de génération :

```text
python -m ruff check src tests tools
All checks passed!

PYTHONPATH=src python -m pytest -q
114 passed, 1 skipped

PYTHONPATH=src python -m mypy src/corep_crr3
Success: no issues found in 11 source files

python -m bandit -r src/corep_crr3 -ll
Test results: No issues identified.
```
