"""Non-régression v5.0.9 de la frontière publique et de la licence."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_and_metadata_are_consistently_apache_2_0():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "Apache License 2.0" in readme
    assert "licence d'évaluation source-visible" not in readme.lower()
    assert 'license = "Apache-2.0"' in pyproject


def test_public_distribution_contains_no_enterprise_engine_modules():
    forbidden = {
        "irb_engine.py",
        "cva_engine.py",
        "sft_engine.py",
        "liquidity_engine.py",
        "market_risk_engine.py",
        "operational_risk_engine.py",
        "own_funds_engine.py",
        "dpm_xbrl_exporter.py",
        "stress_testing_engine.py",
    }
    present = {p.name for p in (ROOT / "src/corep_crr3").glob("*.py")}
    assert forbidden.isdisjoint(present)


def test_scipy_is_not_a_public_runtime_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"scipy' not in pyproject
