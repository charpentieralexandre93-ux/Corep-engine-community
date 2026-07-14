#!/usr/bin/env python3
"""Volumetric benchmark used as a v6.4.1 CI gate.

VERSION   : 6.10.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from corep_crr3.resource_budgets import measure_callable, summarize_measurements
from corep_crr3.saccr_engine import _calc_multiplier
from corep_crr3.standard_engine import apply_ufcp_partial_substitution, compute_recognized_fcp_value


def _standard_kernel(rows: int) -> float:
    total = 0.0
    for i in range(rows):
        collateral = compute_recognized_fcp_value(100.0 + i, 0.02, fx_mismatch=False)
        covered, residual, rwa = apply_ufcp_partial_substitution(
            ead_at_obligor_rw=1000.0 + i,
            base_rw=1.0,
            rw_provider=0.2,
            protection_value=collateral,
        )
        total += covered + residual + rwa
    return total


def _saccr_kernel(rows: int) -> float:
    return sum(_calc_multiplier(float(i % 7), 1000.0 + i) for i in range(rows))


def _mixed_portfolio_kernel(rows: int) -> float:
    total = 0.0
    for i in range(rows):
        total += _standard_kernel(1)
        total += _calc_multiplier(float(i % 5), 500.0 + i)
    return total


def run(rows: int, *, stress_rows: int = 100000) -> dict[str, object]:
    """Run smoke and stress-sized pure-engine volumetric measurements."""
    smoke_rows = max(rows, 1)
    large_rows = max(stress_rows, smoke_rows)
    measurements = [
        measure_callable("standard_engine_volume", smoke_rows, lambda: _standard_kernel(smoke_rows)),
        measure_callable("saccr_multiplier_volume", smoke_rows, lambda: _saccr_kernel(smoke_rows)),
        measure_callable("standard_engine_volume_100k", large_rows, lambda: _standard_kernel(large_rows)),
        measure_callable("saccr_multiplier_volume_100k", large_rows, lambda: _saccr_kernel(large_rows)),
        measure_callable("mixed_portfolio_volume_10k", min(large_rows, 10000), lambda: _mixed_portfolio_kernel(10000)),
    ]
    return {
        "schema_version": 2,
        "product_version": "6.4.1",
        "measurements": measurements,
        "summary": summarize_measurements(measurements),
        "stress_profiles": [
            {"name": "standard_engine_volume_100k", "rows": large_rows},
            {"name": "saccr_multiplier_volume_100k", "rows": large_rows},
            {"name": "mixed_portfolio_volume_10k", "rows": 10000},
        ],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run v6.4.1 volumetric benchmarks")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--stress-rows", type=int, default=100000)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    payload = run(max(args.rows, 1), stress_rows=max(args.stress_rows, 1))
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
