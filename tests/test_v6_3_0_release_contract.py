"""Release contract for the generated Community v6.10.0 source project."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_product_entry_points_and_version_are_explicit() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    init_py = (ROOT / "src/corep_crr3/__init__.py").read_text(encoding="utf-8")
    assert 'version = "6.10.0"' in pyproject
    assert '__version__ = "6.10.0"' in init_py
    assert readme.startswith("# COREP CRR3 Engine Community — v6.10.0\n")
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


def test_public_release_is_gated_by_complete_ci() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "workflow_call:" in ci
    assert "docker-smoke:" in ci
    assert "corep-community-bootstrap" in ci
    assert "uses: ./.github/workflows/ci.yml" in release
    assert "needs: validation" in release
    assert "build_source_archive.py" in ci and "build_source_archive.py" in release
    assert "performance:" in ci and "bench_pure_kernels.py" in ci
    assert "ruff format --check" in ci
    assert "docker compose config --quiet" in ci
    assert "docker image inspect" in ci
    assert "docker compose images -q app" not in ci


def test_public_postgresql_compose_image_is_digest_pinned() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:16-bookworm@sha256:" in compose


def test_public_quality_policy_covers_gui_and_complexity() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'select = ["E", "F", "W", "I", "C90"]' in pyproject
    assert "max-complexity = 20" in pyproject
    coverage_section = pyproject.split("[tool.coverage.run]", 1)[1].split("[", 1)[0]
    assert "community_gui.py" not in coverage_section


def test_public_branch_baseline_covers_product_surface() -> None:
    import json

    # v6_10_0 : référence dérivée de la version du package — le correctif
    # v6_8_1 n'avait été appliqué qu'à l'édition Enterprise (échec latent
    # de la CI Community détecté par la passe d'alignement).
    from corep_crr3 import __version__ as _pkg_version

    _vu = _pkg_version.replace(".", "_")
    payload = json.loads((ROOT / f"evidence/coverage_baseline_v{_vu}.json").read_text(encoding="utf-8"))
    assert payload["product_version"] == _pkg_version
    assert set(payload["modules"]) == {"standard_engine.py", "saccr_engine.py", "community_gui.py"}
    assert payload["modules"]["community_gui.py"]["branch_percent"] >= 60
