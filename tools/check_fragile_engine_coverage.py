#!/usr/bin/env python3
"""Ratchet de couverture par composant critique de l'édition Community."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

DEFAULT_THRESHOLDS: dict[str, float] = {
    "standard_engine.py": 80.0,
    "saccr_engine.py": 80.0,
    "community_gui.py": 55.0,
    "db.py": 75.0,
    "release_integrity.py": 75.0,
    "regulatory_dossier.py": 65.0,
    "resource_budgets.py": 52.0,
    "postgres_profiling.py": 57.0,
}


def _module_coverage(payload: Mapping[str, Any], module_name: str) -> float:
    matches = [
        details
        for path, details in dict(payload.get("files") or {}).items()
        if str(path).replace("\\", "/").endswith(f"/{module_name}") or str(path) == module_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Couverture introuvable ou ambiguë pour {module_name}: {len(matches)}")
    return float(dict(matches[0].get("summary") or {})["percent_covered"])


def check_coverage(payload: Mapping[str, Any], thresholds: Mapping[str, float] = DEFAULT_THRESHOLDS) -> list[str]:
    failures: list[str] = []
    for module, minimum in thresholds.items():
        actual = _module_coverage(payload, module)
        if actual + 1e-9 < minimum:
            failures.append(f"{module}: {actual:.2f}% < {minimum:.2f}%")
        else:
            print(f"PASS {module}: {actual:.2f}% >= {minimum:.2f}%")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage_json", nargs="?", default="coverage.json")
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
        failures = check_coverage(payload)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERREUR couverture Community: {exc}")
        return 2
    if failures:
        print("ECHEC couverture Community:")
        print("\n".join(f"  - {failure}" for failure in failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
