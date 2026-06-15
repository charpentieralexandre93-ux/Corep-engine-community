#!/usr/bin/env python3
"""Publish branch-coverage measurements and deltas for refactored engines."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _find_file(coverage: dict[str, Any], module: str) -> dict[str, Any]:
    """Return the coverage entry matching a module basename or relative path."""
    matches = [value for key, value in coverage["files"].items() if key.endswith(module)]
    if len(matches) != 1:
        raise ValueError(f"module coverage introuvable ou ambigu: {module}")
    return matches[0]


def _metric(entry: dict[str, Any]) -> dict[str, float | int]:
    """Extract stable statement and branch metrics from coverage.py JSON."""
    summary = entry["summary"]
    return {
        "statements": int(summary["num_statements"]),
        "statement_percent": round(float(summary["percent_statements_covered"]), 2),
        "branches": int(summary["num_branches"]),
        "covered_branches": int(summary["covered_branches"]),
        "branch_percent": round(float(summary["percent_branches_covered"]), 2),
    }


def build_report(
    coverage: dict[str, Any], baseline: dict[str, Any], modules: list[str], version: str
) -> dict[str, Any]:
    """Build a deterministic branch-coverage report against a recorded baseline."""
    rows: dict[str, Any] = {}
    for module in modules:
        current = _metric(_find_file(coverage, module))
        previous = baseline["modules"][module]
        rows[module] = {
            "baseline_version": baseline["product_version"],
            "baseline_branch_percent": previous["branch_percent"],
            "current_branch_percent": current["branch_percent"],
            "delta_percentage_points": round(
                current["branch_percent"] - float(previous["branch_percent"]), 2
            ),
            **current,
        }
    totals = coverage["totals"]
    return {
        "schema_version": 1,
        "product_version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage_tool": coverage.get("meta", {}).get("version"),
        "overall": {
            "statement_percent": round(float(totals["percent_statements_covered"]), 2),
            "branch_percent": round(float(totals["percent_branches_covered"]), 2),
        },
        "modules": rows,
    }


def main() -> int:
    """Compare coverage.py JSON with a baseline and fail on branch regression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--module", action="append", dest="modules", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()
    coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    report = build_report(coverage, baseline, args.modules, args.version)
    regressions = {
        module: row["delta_percentage_points"]
        for module, row in report["modules"].items()
        if row["delta_percentage_points"] < -abs(args.tolerance)
    }
    report["status"] = "FAILED" if regressions else "PASSED"
    report["regressions"] = regressions
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for module, row in report["modules"].items():
        print(
            f"{module}: branches {row['current_branch_percent']:.2f} % "
            f"(delta {row['delta_percentage_points']:+.2f} pp)"
        )
    return 1 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
