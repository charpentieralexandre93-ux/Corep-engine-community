#!/usr/bin/env python3
"""
================================================================================
BENCHMARK : bench_pure_kernels.py
PROJET    : COREP Engine CRR3
VERSION   : 6.10.0
================================================================================

Micro-benchmark des NOYAUX DE CALCUL PURS (CRM / SA / SA-CCR), sans base de
données ni psycopg2. Mesure le débit (appels/seconde) et la latence (ns/appel)
des fonctions critiques appliquées exposition par exposition.

But : donner un ordre de grandeur du coût CPU du cœur de calcul, indépendamment
des entrées/sorties PostgreSQL (cf. bench_engine_scale.py pour le bout-en-bout).

USAGE
-----
    PYTHONPATH=src python benchmarks/bench_pure_kernels.py [--iterations 1000000]
================================================================================
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable

from corep_crr3.saccr_engine import _maturity_factor
from corep_crr3.standard_engine import (
    apply_ufcp_partial_substitution,
    compile_fcp_haircut_rules,
    compute_recognized_fcp_value,
    lookup_fcp_haircut_rate_from_rules,
    maturity_mismatch_factor,
)

_RULES = [
    {
        "collateral_type": "CASH",
        "collateral_grade": None,
        "residual_maturity": None,
        "haircut_rate": 0.0,
    },
    {
        "collateral_type": "BOND",
        "collateral_grade": "AA",
        "residual_maturity": None,
        "haircut_rate": 0.02,
    },
    {
        "collateral_type": "EQUITY",
        "collateral_grade": None,
        "residual_maturity": None,
        "haircut_rate": 0.15,
    },
]
_RULE_BOOK = compile_fcp_haircut_rules(_RULES)


def _bench(name: str, fn: Callable[[], object], iterations: int) -> dict:
    fn()  # échauffement
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start
    return {
        "kernel": name,
        "iterations": iterations,
        "elapsed_s": round(elapsed, 4),
        "calls_per_s": int(iterations / elapsed) if elapsed else 0,
        "ns_per_call": round(elapsed / iterations * 1e9, 1),
    }


def run(iterations: int) -> list:
    kernels = {
        "compute_recognized_fcp_value": lambda: compute_recognized_fcp_value(
            100.0,
            0.15,
            fx_mismatch=True,
            fx_haircut=0.08,
            exposure_maturity_months=48,
            protection_maturity_months=30,
        ),
        "apply_ufcp_partial_substitution": lambda: apply_ufcp_partial_substitution(
            ead_at_obligor_rw=100.0, base_rw=1.0, rw_provider=0.20, protection_value=30.0
        ),
        "maturity_mismatch_factor": lambda: maturity_mismatch_factor(60, 36),
        "lookup_fcp_haircut_rate_from_rules": lambda: lookup_fcp_haircut_rate_from_rules(
            _RULE_BOOK, {"collateral_type": "bond", "collateral_grade": "aa"}
        ),
        "saccr_maturity_factor": lambda: _maturity_factor(1.0, margined=True, mpor_days=10.0),
    }
    return [_bench(name, fn, iterations) for name, fn in kernels.items()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Micro-benchmark des noyaux de calcul purs SA/SA-CCR.")
    parser.add_argument("--iterations", type=int, default=1_000_000)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--min-calls-per-second",
        type=int,
        default=0,
        help="Seuil bloquant par noyau ; 0 désactive le verdict.",
    )
    args = parser.parse_args(argv)

    if args.iterations <= 0:
        parser.error("--iterations doit être strictement positif")
    if args.min_calls_per_second < 0:
        parser.error("--min-calls-per-second doit être positif ou nul")

    results = run(args.iterations)
    width = max(len(r["kernel"]) for r in results)
    print(f"{'kernel':<{width}} | {'appels/s':>12} | {'ns/appel':>9}")
    print("-" * (width + 28))
    for r in results:
        print(f"{r['kernel']:<{width}} | {r['calls_per_s']:>12,} | {r['ns_per_call']:>9}")
    total = sum(r["calls_per_s"] for r in results) // len(results)
    print(f"\nDébit moyen par noyau : ~{total:,} appels/s ({args.iterations:,} itérations chacun).")

    failures = [result for result in results if result["calls_per_s"] < args.min_calls_per_second]
    payload = {
        "iterations": args.iterations,
        "minimum_calls_per_second": args.min_calls_per_second,
        "average_calls_per_second": total,
        "status": "FAILED" if failures else "PASSED",
        "kernels": results,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if failures:
        for result in failures:
            print(f"ECHEC {result['kernel']}: {result['calls_per_s']:,} < {args.min_calls_per_second:,} appels/s")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
