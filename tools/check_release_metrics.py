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


def _junit_counts(path: Path) -> tuple[int, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(s.attrib.get("tests", 0)) for s in suites)
    skipped = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    failures = sum(int(s.attrib.get("failures", 0)) for s in suites)
    errors = sum(int(s.attrib.get("errors", 0)) for s in suites)
    passed = tests - skipped - failures - errors
    if failures or errors:
        raise ValueError(f"JUnit contient {failures} échec(s) et {errors} erreur(s)")
    return passed, skipped


def _live_metrics(coverage_path: Path, junit_path: Path) -> dict[str, Any]:
    totals = json.loads(coverage_path.read_text(encoding="utf-8"))["totals"]
    passed, skipped = _junit_counts(junit_path)
    return {
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

    tolerance_pp = float(metrics.get("metrics_tolerance_pp", 0.0) or 0.0)
    mismatches = [
        mismatch
        for key, value in live.items()
        for mismatch in [_metric_mismatch(key, metrics.get(key), value, tolerance_pp)]
        if mismatch is not None
    ]
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
