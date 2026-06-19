"""v6.3.0 deterministic micro-performance evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pure_kernel_performance_gate_writes_machine_readable_evidence(tmp_path: Path) -> None:
    output = tmp_path / "performance.json"
    subprocess.run(
        [
            sys.executable,
            "benchmarks/bench_pure_kernels.py",
            "--iterations",
            "5000",
            "--min-calls-per-second",
            "5000",
            "--json-output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        env={"PYTHONPATH": str(ROOT / "src")},
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASSED"
    assert payload["minimum_calls_per_second"] == 5000
    assert len(payload["kernels"]) == 5
    assert all(row["calls_per_s"] >= 5000 for row in payload["kernels"])
