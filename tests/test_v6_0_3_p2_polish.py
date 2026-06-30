"""Community non-regression tests for the P2 polish release."""

from __future__ import annotations

import json
from pathlib import Path

from tools.check_cli_docstrings import analyse

ROOT = Path(__file__).resolve().parents[1]


def test_python_support_policy_matches_public_packaging() -> None:
    """Keep Community's Python support and lock policy explicit."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    policy = (ROOT / "docs/PYTHON_COMPATIBILITY.md").read_text(encoding="utf-8")
    runtime_lock = (ROOT / "requirements-runtime-py311-linux.lock").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.14"' in pyproject
    assert "Python 3.11" in policy and "best-effort" in policy
    assert "reproducible Python 3.11 Linux baseline" in runtime_lock


def test_public_cli_docstring_gate_is_above_target() -> None:
    """Prevent undocumented public CLI and GUI callables from accumulating."""
    metrics = analyse(ROOT)
    assert metrics["percent"] >= 85.0
    assert metrics["documented"] == metrics["functions"]


def test_public_branch_baseline_tracks_shared_standard_engine() -> None:
    """Keep a machine-readable baseline for the shared refactored engine."""
    payload = json.loads((ROOT / "evidence/coverage_baseline_v6_0_2.json").read_text())
    assert set(payload["modules"]) == {"standard_engine.py"}
    assert payload["modules"]["standard_engine.py"]["branches"] > 0
