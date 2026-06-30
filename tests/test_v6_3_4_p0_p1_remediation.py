"""Non-régression P0/P1 Community v6.6.0."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from corep_crr3 import community_gui as gui
from corep_crr3.engine_contracts import EngineContext, EngineProfiler, EngineResult, FunctionEngineAdapter
from corep_crr3.operational_readiness import ReadinessReport, run_readiness_checks

ROOT = Path(__file__).resolve().parents[1]


def test_public_boundary_artifacts_and_metrics_are_current() -> None:
    expected = [
        ROOT / "CHANGELOG_v6_6_0.md",
        ROOT / "VALIDATION_v6_6_0.md",
        ROOT / "RELEASE_REPORT_v6_6_0.md",
        ROOT / "SBOM_Corep_Community_v6.6.0.json",
        ROOT / "docs/DATA_MODEL_BCNF_HARDENING_v6_6_0.md",
        ROOT / "evidence/github_ci_proof_checklist_v6_6_0.json",
        ROOT / "evidence/release_metrics_v6_6_0.json",
    ]
    for path in expected:
        assert path.is_file(), path
    for path in [ROOT / "README.md", ROOT / "Dockerfile", ROOT / "docs/COMMUNITY_RELEASE_V6.md"]:
        text = path.read_text(encoding="utf-8")
        assert "6.6.0" in text
        assert "6.3.2" not in text
    metrics = json.loads((ROOT / "evidence/release_metrics_v6_6_0.json").read_text(encoding="utf-8"))
    assert metrics["product_version"] == "6.6.0"
    assert metrics["edition"] == "COMMUNITY"
    assert metrics["metrics_tolerance_pp"] <= 0.05


def test_community_gui_pure_helpers_cover_boundary_and_validation(tmp_path: Path) -> None:
    root = tmp_path / "community"
    (root / "sql").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname="x"\n', encoding="utf-8")
    (root / ".env.example").write_text("PGHOST=127.0.0.1\nPGPORT=5432\nPGDATABASE=c\nPGUSER=u\n", encoding="utf-8")
    contract = root / "sql/COMMUNITY_SQL_CONTRACT.json"
    contract.write_text(json.dumps({"version": "6.6.0", "engines": ["SA", "SA_CCR"]}), encoding="utf-8")

    assert gui.resolve_project_root(root / "sql") == root
    paths = gui.get_community_paths(root)
    assert paths.contract_path == contract
    assert gui.read_env_file(root / ".env.example")["PGHOST"] == "127.0.0.1"
    backup = gui.write_env_file(
        root / ".env",
        {"PGHOST": "localhost", "PGPORT": "5432", "PGDATABASE": "corep", "PGUSER": "u", "PGPASSWORD": "secret"},
        root / "old/config_backups",
    )
    assert backup is None
    assert gui.validate_env_values(gui.read_env_file(root / ".env")).ok
    assert not gui.validate_env_values({"PGPORT": "70000"}).ok
    assert gui.mask_secret("secret") == "s***t"
    assert gui.load_contract(contract)["engines"] == ["SA", "SA_CCR"]
    assert gui.load_contract(root / "missing.json") == {}
    broken = root / "sql/broken.json"
    broken.write_text("{", encoding="utf-8")
    assert gui.load_contract(broken) == {}


def test_engine_contracts_and_operational_readiness_paths(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def legacy(db, batch_id, regulatory_version_id, reporting_date, **kwargs):
        calls.append((batch_id, regulatory_version_id))
        assert kwargs["flag"] is True
        return 3

    ctx = EngineContext(
        db=object(),
        batch_id="B",
        regulatory_version_id="CRR3",
        reporting_date="2026-03-31",
        runtime_kwargs={"flag": True},
        engine_key="run_sa",
        engine_label="SA",
    )
    assert ctx.kwargs() == {"flag": True}
    result = FunctionEngineAdapter(legacy, name="SA").run(ctx)
    assert isinstance(result, EngineResult)
    assert int(result) == 3
    assert calls == [("B", "CRR3")]
    assert int(EngineResult.from_legacy(None)) == 0
    with pytest.raises(TypeError):
        FunctionEngineAdapter(None)  # type: ignore[arg-type]

    profiler = EngineProfiler(enabled=True, slow_threshold_seconds=0.0)
    profiler.run(FunctionEngineAdapter(legacy, name="SA"), ctx)
    json_path, csv_path = profiler.write_reports(tmp_path, "B")
    assert json_path is not None and json_path.exists()
    assert csv_path is not None and csv_path.exists()

    report = run_readiness_checks(
        output_dir=tmp_path / "out",
        min_free_mb=0,
        required_env=(),
        require_database=False,
        required_resources=(),
    )
    assert isinstance(report, ReadinessReport)
    assert report.passed is True
    assert report.to_dict()["engine_version"] == "6.6.0"
