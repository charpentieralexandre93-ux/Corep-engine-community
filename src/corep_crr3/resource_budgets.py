"""Runtime performance and memory budget helpers for release gates.

VERSION : 6.10.1
"""

from __future__ import annotations

import argparse
import json
import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ResourceBudget:
    """A deterministic budget attached to a benchmark or batch stage."""

    name: str
    max_seconds: float
    max_rss_mb: float
    max_rows: int
    min_rows_per_second: float = 0.0
    scope: str = "unit"
    percentile: str = "single_run"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ResourceBudget":
        """Normalize a budget read from JSON evidence."""
        return cls(
            name=str(payload["name"]),
            max_seconds=float(payload["max_seconds"]),
            max_rss_mb=float(payload["max_rss_mb"]),
            max_rows=int(payload.get("max_rows", 0)),
            min_rows_per_second=float(payload.get("min_rows_per_second", 0.0)),
            scope=str(payload.get("scope", "unit")),
            percentile=str(payload.get("percentile", "single_run")),
        )


def _rss_mb() -> float:
    """Return the maximum resident set size in MiB across Linux and macOS."""
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value / (1024.0 * 1024.0) if value > 10_000_000 else value / 1024.0


def load_budgets(path: Path) -> tuple[ResourceBudget, ...]:
    """Load a budget file and reject duplicate names."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    budgets = tuple(ResourceBudget.from_mapping(item) for item in payload.get("budgets", []))
    names = [item.name for item in budgets]
    if len(names) != len(set(names)):
        raise ValueError("resource budget names must be unique")
    return budgets


def budget_index(budgets: Iterable[ResourceBudget]) -> dict[str, ResourceBudget]:
    """Index budgets by name."""
    return {budget.name: budget for budget in budgets}


def measure_callable(name: str, rows: int, func: Callable[[], T]) -> dict[str, Any]:
    """Measure elapsed time and peak RSS for a callable benchmark."""
    before = _rss_mb()
    started = time.perf_counter()
    result = func()
    elapsed = max(time.perf_counter() - started, 0.0)
    after = _rss_mb()
    return {
        "name": name,
        "rows": int(rows),
        "elapsed_seconds": elapsed,
        "peak_rss_mb": max(before, after),
        "rows_per_second": (float(rows) / elapsed) if elapsed > 0 else float("inf"),
        "result_type": type(result).__name__,
    }


def validate_measurement(measurement: Mapping[str, Any], budget: ResourceBudget) -> tuple[str, ...]:
    """Return every budget violation for one measurement."""
    errors: list[str] = []
    elapsed = float(measurement.get("elapsed_seconds", 0.0))
    rss = float(measurement.get("peak_rss_mb", 0.0))
    rows = int(measurement.get("rows", 0))
    rps = float(measurement.get("rows_per_second", 0.0))
    if elapsed > budget.max_seconds:
        errors.append(f"{budget.name}: elapsed {elapsed:.3f}s > budget {budget.max_seconds:.3f}s")
    if rss > budget.max_rss_mb:
        errors.append(f"{budget.name}: rss {rss:.1f}MiB > budget {budget.max_rss_mb:.1f}MiB")
    if budget.max_rows and rows > budget.max_rows:
        errors.append(f"{budget.name}: rows {rows} > budgeted scale {budget.max_rows}")
    if budget.min_rows_per_second and rps < budget.min_rows_per_second:
        errors.append(f"{budget.name}: throughput {rps:.1f}/s < floor {budget.min_rows_per_second:.1f}/s")
    return tuple(errors)


def validate_measurements(
    measurements: Iterable[Mapping[str, Any]],
    budgets: Iterable[ResourceBudget],
    *,
    require_all_budgets: bool = False,
) -> tuple[str, ...]:
    """Validate a benchmark report against its named budgets."""
    indexed = budget_index(budgets)
    seen: set[str] = set()
    errors: list[str] = []
    for measurement in measurements:
        name = str(measurement.get("name", ""))
        seen.add(name)
        budget = indexed.get(name)
        if budget is None:
            errors.append(f"{name}: no budget configured")
        else:
            errors.extend(validate_measurement(measurement, budget))
    if require_all_budgets:
        for missing in sorted(set(indexed) - seen):
            errors.append(f"{missing}: budget has no measurement")
    return tuple(errors)


def load_measurement_report(path: Path) -> tuple[Mapping[str, Any], ...]:
    """Load a benchmark report and normalize its measurement list."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("measurements", [])
    if not isinstance(raw, list):
        raise ValueError("measurement report must contain a measurements list")
    return tuple(item for item in raw if isinstance(item, dict))


def summarize_measurements(measurements: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a small deterministic summary used in release evidence."""
    rows = 0
    elapsed = 0.0
    peak = 0.0
    names: list[str] = []
    for item in measurements:
        names.append(str(item.get("name", "")))
        rows += int(item.get("rows", 0))
        elapsed += float(item.get("elapsed_seconds", 0.0))
        peak = max(peak, float(item.get("peak_rss_mb", 0.0)))
    return {
        "measurement_count": len(names),
        "names": sorted(names),
        "total_rows": rows,
        "total_elapsed_seconds": round(elapsed, 6),
        "peak_rss_mb": round(peak, 3),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI gate used by CI to validate a JSON benchmark report."""
    parser = argparse.ArgumentParser(description="Validate runtime resource budgets")
    parser.add_argument("--budgets", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--require-all-budgets", action="store_true")
    args = parser.parse_args(argv)
    budgets = load_budgets(args.budgets)
    measurements = load_measurement_report(args.measurements)
    errors = validate_measurements(measurements, budgets, require_all_budgets=args.require_all_budgets)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    summary = summarize_measurements(measurements)
    print(f"OK resource budgets: {len(measurements)} measurement(s), {summary['total_rows']} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
