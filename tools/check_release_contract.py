#!/usr/bin/env python3
"""Contrôle public v6.0.4 : version, licence Apache et frontière SA/SA-CCR."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r'\d+\.\d+\.\d+')


def _extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"Version introuvable dans {label}")
    return match.group(1)


def main() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_text = (ROOT / "src/corep_crr3/__init__.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / "sql/COMMUNITY_SQL_CONTRACT.json").read_text(encoding="utf-8"))

    versions = {
        "pyproject": _extract(r'^version\s*=\s*"([0-9.]+)"', pyproject, "pyproject.toml"),
        "package": _extract(r'__version__\s*=\s*"([0-9.]+)"', init_text, "__init__.py"),
        "README": _extract(r'^# COREP CRR3 Engine Community — v([0-9.]+)$', readme, "README.md"),
        "SQL contract": str(contract.get("version", "")),
    }
    if len(set(versions.values())) != 1:
        raise RuntimeError(f"Dérive de version : {versions}")
    version = next(iter(versions.values()))
    if not SEMVER.fullmatch(version):
        raise RuntimeError(f"Version non semver : {version}")

    if 'license = "Apache-2.0"' not in pyproject:
        raise RuntimeError("pyproject Community doit rester Apache-2.0")
    if "Apache License" not in (ROOT / "LICENSE").read_text(encoding="utf-8")[:300]:
        raise RuntimeError("LICENSE Community n'est pas Apache-2.0")
    if "licence d'évaluation source-visible" in readme.lower():
        raise RuntimeError("Le README contient encore l'ancienne licence restrictive")
    if contract.get("engines") != ["SA", "SA_CCR"]:
        raise RuntimeError("Le contrat public doit contenir uniquement SA et SA_CCR")

    forbidden = {
        "irb_engine.py", "cva_engine.py", "sft_engine.py", "liquidity_engine.py",
        "market_risk_engine.py", "operational_risk_engine.py", "own_funds_engine.py",
        "dpm_xbrl_exporter.py", "eba_xbrl_csv.py", "regulatory_release.py",
        "submission_governance.py", "stress_testing_engine.py",
    }
    present = {p.name for p in (ROOT / "src/corep_crr3").glob("*.py")}
    leaked = sorted(forbidden & present)
    if leaked:
        raise RuntimeError(f"Modules Enterprise présents dans Community : {leaked}")

    required_release_files = ("setup.py", "MANIFEST.in")
    missing_release_files = [name for name in required_release_files if not (ROOT / name).is_file()]
    if missing_release_files:
        raise RuntimeError(f"Fichiers de release v6 absents : {missing_release_files}")

    changelog = ROOT / f"CHANGELOG_v{version.replace('.', '_')}.md"
    if not changelog.is_file():
        raise RuntimeError(f"Changelog de release manquant : {changelog.name}")
    print(f"OK Community v{version}: Apache-2.0, SA/SA-CCR uniquement, versions cohérentes")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
