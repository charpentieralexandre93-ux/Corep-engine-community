#!/usr/bin/env python3
"""Contrat bloquant de release Community."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from check_sbom_lock_sync import check as check_sbom

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
POSTGRES_IMAGE = "postgres:16-bookworm@sha256:da514b7d293c5e9126503f85ecd835f4fb0942a77e012fe74f016c114c3e25b8"
FORBIDDEN_CACHE_PARTS = {
    ".hypothesis",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
}


def _extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Version introuvable dans {label}")
    return match.group(1)


def _assert_release_pipeline(version: str) -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    required_ci = (
        "workflow_call:",
        "docker-smoke:",
        "docker compose build --progress=plain app",
        "docker compose config --quiet",
        "docker image inspect",
        "corep-community-bootstrap",
        'python-version: ["3.11", "3.12", "3.13"]',
        "build_source_archive.py",
        "performance:",
        "bench_pure_kernels.py",
        "ruff format --check",
        f"Corep_engine_community_v{version}",
    )
    missing_ci = [token for token in required_ci if token not in ci]
    if missing_ci:
        raise RuntimeError(f"garde-fous CI Community absents: {missing_ci}")
    required_release = (
        "uses: ./.github/workflows/ci.yml",
        "needs: validation",
        "build_source_archive.py",
        "dist/Corep_engine_community_v${PACKAGE_VERSION}.zip",
    )
    missing_release = [token for token in required_release if token not in release]
    if missing_release:
        raise RuntimeError(f"gating de release Community incomplet: {missing_release}")


def main() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_text = (ROOT / "src/corep_crr3/__init__.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / "sql/COMMUNITY_SQL_CONTRACT.json").read_text(encoding="utf-8"))
    versions = {
        "pyproject": _extract(r'^version\s*=\s*"([0-9.]+)"', pyproject, "pyproject.toml"),
        "package": _extract(r'__version__\s*=\s*"([0-9.]+)"', init_text, "__init__.py"),
        "README": _extract(r"^# COREP CRR3 Engine Community — v([0-9.]+)$", readme, "README.md"),
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
        "irb_engine.py",
        "cva_engine.py",
        "sft_engine.py",
        "liquidity_engine.py",
        "market_risk_engine.py",
        "operational_risk_engine.py",
        "own_funds_engine.py",
        "dpm_xbrl_exporter.py",
        "eba_xbrl_csv.py",
        "regulatory_release.py",
        "submission_governance.py",
        "stress_testing_engine.py",
    }
    present = {p.name for p in (ROOT / "src/corep_crr3").glob("*.py")}
    leaked = sorted(forbidden & present)
    if leaked:
        raise RuntimeError(f"Modules Enterprise présents dans Community : {leaked}")
    for required in (
        ROOT / "setup.py",
        ROOT / "MANIFEST.in",
        ROOT / "changelogs" / f"CHANGELOG_v{version.replace('.', '_')}.md",
        ROOT / "releases" / f"VALIDATION_v{version.replace('.', '_')}.md",
        ROOT / "releases" / f"RELEASE_REPORT_v{version.replace('.', '_')}.md",
        ROOT / f"SBOM_Corep_Community_v{version}.json",
        ROOT / "tools/build_source_archive.py",
        ROOT / "benchmarks/bench_pure_kernels.py",
        ROOT / f"evidence/coverage_baseline_v{version.replace('.', '_')}.json",
    ):
        if not required.is_file():
            raise RuntimeError(f"Artefact de release absent : {required.name}")
    if 'select = ["E", "F", "W", "I", "C90"]' not in pyproject:
        raise RuntimeError("Ruff complet et contrôle de complexité non configurés")
    if "max-complexity = 16" not in pyproject:  # ratchet v6.10.1
        raise RuntimeError("seuil cyclomatique Community absent")
    coverage = pyproject.split("[tool.coverage.run]", 1)[-1].split("[", 1)[0]
    if "community_gui.py" in coverage:
        raise RuntimeError("le GUI Community ne doit plus être exclu de la couverture")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    if "HEALTHCHECK" in dockerfile:
        raise RuntimeError("une image one-shot ne doit pas déclarer HEALTHCHECK")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    if POSTGRES_IMAGE not in compose:
        raise RuntimeError("l'image PostgreSQL Community n'est pas épinglée par digest")
    _assert_release_pipeline(version)
    errors = check_sbom(ROOT)
    if errors:
        raise RuntimeError("; ".join(errors))
    print(f"OK Community v{version}: Apache-2.0, SA/SA-CCR, CI gated, Docker et ZIP source cohérents")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
