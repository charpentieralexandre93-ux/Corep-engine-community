#!/usr/bin/env python3
"""Generate or validate the versioned release metrics published in README."""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

START = "<!-- RELEASE_METRICS_START -->"
END = "<!-- RELEASE_METRICS_END -->"


def _round(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def _junit_counts(path: Path) -> tuple[int, int, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(s.attrib.get("tests", 0)) for s in suites)
    skipped = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    failures = sum(int(s.attrib.get("failures", 0)) for s in suites)
    errors = sum(int(s.attrib.get("errors", 0)) for s in suites)
    passed = tests - skipped - failures - errors
    if failures or errors:
        raise ValueError(f"JUnit contient {failures} échec(s) et {errors} erreur(s)")
    return tests, passed, skipped


def _live_metrics(coverage_path: Path, junit_path: Path) -> dict[str, Any]:
    totals = json.loads(coverage_path.read_text(encoding="utf-8"))["totals"]
    collected, passed, skipped = _junit_counts(junit_path)
    return {
        # tests_collected est désormais dérivé du rapport JUnit (v6.7.0) :
        # il était auparavant reporté à la main et avait dérivé (collected < passed
        # dans les preuves publiées). Toute valeur du JSON qui ne correspond pas au
        # rapport d'exécution fait maintenant échouer la gate.
        "tests_collected": collected,
        "tests_passed": passed,
        "tests_skipped": skipped,
        "coverage_combined": _round(totals["percent_covered"]),
        "coverage_branches": _round(totals["percent_branches_covered"]),
    }


def _environment_metrics() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }


def _metric_mismatch(key: str, expected: Any, observed: Any, tolerance_pp: float) -> str | None:
    if key.startswith("coverage_") and expected is not None:
        try:
            if abs(float(expected) - float(observed)) <= tolerance_pp:
                return None
        except (TypeError, ValueError):
            pass
    return None if expected == observed else f"{key}: preuve={expected!r}, exécution={observed!r}"


def _block(metrics: dict[str, Any]) -> str:
    version = metrics["product_version"]
    passed = metrics["tests_passed"]
    skipped = metrics["tests_skipped"]
    combined = metrics["coverage_combined"]
    branches = metrics["coverage_branches"]
    mypy_modules = metrics["mypy_modules"]
    documented = metrics["cli_docstrings_documented"]
    total = metrics["cli_docstrings_total"]
    skipped_label = "ignoré" if skipped == 1 else "ignorés"
    return "\n".join(
        [
            START,
            f"## Preuves qualité v{version}",
            "",
            f"- **{passed} tests réussis, {skipped} {skipped_label}** ;",
            f"- couverture lignes/branches combinée : **{combined:.2f} %**, dont **{branches:.2f} %** de branches ;",
            f"- Mypy valide les **{mypy_modules} modules** du périmètre ;",
            f"- **{documented}/{total} fonctions CLI/GUI documentées** ;",
            "- Ruff, formatage, Bandit, seuils par composant, manifeste et reproductibilité sont bloquants en CI.",
            END,
        ]
    )


def _replace_block(readme: str, block: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if pattern.search(readme):
        return pattern.sub(block, readme)
    heading = re.search(r"^## Preuves qualité.*?(?=^## |\Z)", readme, re.M | re.S)
    if not heading:
        raise ValueError("section 'Preuves qualité' introuvable dans README")
    return readme[: heading.start()] + block + "\n\n" + readme[heading.end() :]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_version = pyproject["project"]["version"]
    if metrics.get("product_version") != package_version:
        raise ValueError(f"version métriques {metrics.get('product_version')} != pyproject {package_version}")

    live = _live_metrics(args.coverage, args.junit)
    if args.write:
        metrics.update(live)
        metrics.setdefault("toolchain", {}).update(_environment_metrics())
        args.metrics.write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        readme = args.readme.read_text(encoding="utf-8")
        args.readme.write_text(_replace_block(readme, _block(metrics)), encoding="utf-8")
        print(f"Métriques v{package_version} mises à jour.")
        return 0

    # Cohérence interne des preuves (v6.7.0) : un fichier de métriques
    # incohérent avec lui-même (collected != passed + skipped) est rejeté avant
    # toute comparaison au run courant. Les échecs/erreurs faisant déjà échouer
    # _junit_counts, l'identité doit être exacte.
    declared_total = int(metrics.get("tests_passed", 0)) + int(metrics.get("tests_skipped", 0))
    declared_collected = metrics.get("tests_collected")
    if declared_collected is not None and int(declared_collected) != declared_total:
        raise ValueError(
            f"preuves incohérentes: tests_collected={declared_collected} != tests_passed+tests_skipped={declared_total}"
        )

    tolerance_pp = float(metrics.get("metrics_tolerance_pp", 0.0) or 0.0)
    locked_python = str(metrics.get("toolchain", {}).get("python_version", ""))
    on_locked_toolchain = bool(locked_python) and locked_python == platform.python_version()
    mismatches: list[str] = []
    for key, value in live.items():
        mismatch = _metric_mismatch(key, metrics.get(key), value, tolerance_pp)
        if mismatch is None:
            continue
        # La couverture peut varier légèrement selon la version de Python. Elle n'est
        # bloquante que sur la toolchain de verrouillage ; hors de celle-ci elle est
        # informative (les comptes de tests, eux, restent stricts). Le plancher réel
        # de couverture reste garanti séparément par pytest --cov-fail-under.
        if key.startswith("coverage_") and not on_locked_toolchain:
            print(
                f"AVERTISSEMENT: couverture informative ({mismatch}); "
                f"toolchain courante {platform.python_version()} != verrouillée {locked_python or '?'}",
                file=sys.stderr,
            )
            continue
        mismatches.append(mismatch)
    if mismatches:
        raise ValueError("métriques périmées: " + "; ".join(mismatches))
    expected = _block(metrics)
    readme = args.readme.read_text(encoding="utf-8")
    if expected not in readme:
        raise ValueError("bloc métriques README absent ou périmé; exécuter avec --write")
    print(
        f"Métriques {metrics['edition']} v{package_version}: "
        f"{live['tests_passed']} tests, {live['coverage_combined']:.2f}% couverture."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, json.JSONDecodeError, ET.ParseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
