"""Release contract for the generated Community v6.0.4 source project."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_product_entry_points_and_version_are_explicit() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    init_py = (ROOT / "src/corep_crr3/__init__.py").read_text(encoding="utf-8")
    assert 'version = "6.0.4"' in pyproject
    assert '__version__ = "6.0.4"' in init_py
    assert readme.startswith("# COREP CRR3 Engine Community — v6.0.4\n")
    assert "corep-community-gui" in readme
    assert "corep-community-bootstrap" in readme
    assert "Apache License 2.0" in readme
    assert not (ROOT / "batch/run_batch.py").exists()
    assert len(readme.splitlines()) < 160


def test_public_methodology_scope_is_sa_and_saccr_only() -> None:
    docs = {path.name for path in (ROOT / "docs").glob("*.md")}
    assert "SA_Credit_Methodology_Note.md" in docs
    assert "SA_CCR_Methodology_Note.md" in docs
    forbidden = {"CVA_Methodology_Note.md", "Output_Floor_Methodology_Note.md"}
    assert not (forbidden & docs)
