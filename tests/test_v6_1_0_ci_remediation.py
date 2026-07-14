"""Non-regression guards for the v6.1.0 CI remediation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_contract_starts_at_311():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11,<3.14"' in pyproject
    assert 'python_version = "3.11"' in pyproject


def test_ci_runtime_matrix_excludes_eol_python():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'python-version: ["3.11", "3.12", "3.13"]' in workflow
    assert 'python-version: ["3.9"' not in workflow
