#!/usr/bin/env python3
# VERSION : 6.10.0
"""Orchestrateur local des gates de release (à exécuter avant tout empaquetage).

Enchaîne les mêmes contrôles bloquants que la CI, dans l'ordre, et s'arrête au
premier échec. Objectif : éliminer la classe de défaut « code bon, CI rouge »
constatée sur les livraisons v6.5.0 et v6.9.0 (gates non rejouées avant zip).

Usage :
    python tools/release_check.py            # gates statiques + tests + métriques
    python tools/release_check.py --fast     # gates statiques seulement
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _version() -> str:
    """Lit la version depuis src/corep_crr3/__init__.py."""
    text = (ROOT / "src" / "corep_crr3" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("release_check: __version__ introuvable")
    return match.group(1)


def _edition() -> str:
    """ENTERPRISE si l'overlay Community est présent, sinon COMMUNITY."""
    return "ENTERPRISE" if (ROOT / "community" / "overlay").is_dir() else "COMMUNITY"


def _format_dirs() -> list[str]:
    dirs = ["src", "tools", "tests", "benchmarks", "scripts"]
    if (ROOT / "batch").is_dir():
        dirs.insert(3, "batch")
    return [d for d in dirs if (ROOT / d).is_dir()]


def _run(label: str, cmd: list[str]) -> None:
    print(f"[release-check] {label} ...", flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"release_check: ÉCHEC à l'étape « {label} » ({' '.join(cmd)})")


def static_gates(version: str, edition: str) -> None:
    """Gates statiques, identiques à la CI (voir .github/workflows/ci.yml)."""
    py = sys.executable
    _run("ruff check", ["ruff", "check", "src", "tools", "tests"])
    _run("ruff format --check", ["ruff", "format", "--check", *_format_dirs()])
    _run("mypy", ["mypy", "src/corep_crr3"])
    _run("bandit -ll", ["bandit", "-r", "src/corep_crr3", "-ll", "-q"])
    _run("taille de fonction ≤ 190", [py, "tools/check_function_size.py", "--root", "src", "--max-lines", "190"])
    if edition == "ENTERPRISE":
        _run("anti-drift overlay", [py, "tools/check_overlay_drift.py"])
        _run("frontière Community", [py, "tools/build_community_edition.py", "--check"])
    _run("cohérence de version", [py, "tools/bump_version.py", "--check"])
    _run("docstrings CLI ≥ 85 %", [py, "tools/check_cli_docstrings.py", "--min-percent", "85"])
    _run("contrat de release", [py, "tools/check_release_contract.py"])
    _run("SBOM ↔ lockfile", [py, "tools/check_sbom_lock_sync.py"])
    _run(
        "intégrité du manifeste",
        [
            py,
            "-m",
            "corep_crr3.release_integrity",
            "--root",
            ".",
            "--manifest",
            "RELEASE_MANIFEST.json",
            "--version",
            version,
            "--edition",
            edition,
        ],
    )


def test_gates(version: str) -> None:
    """Suite complète + couverture + synchronisation des métriques de release."""
    py = sys.executable
    with tempfile.TemporaryDirectory() as tmp:
        cov = str(Path(tmp) / "coverage.json")
        junit = str(Path(tmp) / "pytest-report.xml")
        _run(
            "pytest + couverture ≥ 65 %",
            [
                py,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--no-header",
                "--cov=corep_crr3",
                "--cov-branch",
                f"--cov-report=json:{cov}",
                "--cov-fail-under=65",
                f"--junitxml={junit}",
            ],
        )
        _run("couverture moteurs fragiles", [py, "tools/check_fragile_engine_coverage.py", cov])
        metrics = f"evidence/release_metrics_v{version.replace('.', '_')}.json"
        _run(
            "métriques de release synchrones",
            [
                py,
                "tools/check_release_metrics.py",
                "--metrics",
                metrics,
                "--readme",
                "README.md",
                "--coverage",
                cov,
                "--junit",
                junit,
            ],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="gates statiques seulement (sans pytest/métriques)")
    args = parser.parse_args()
    version, edition = _version(), _edition()
    print(f"[release-check] édition {edition}, version {version}")
    static_gates(version, edition)
    if not args.fast:
        test_gates(version)
    print(f"[release-check] ✅ Toutes les gates sont vertes ({edition} {version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
