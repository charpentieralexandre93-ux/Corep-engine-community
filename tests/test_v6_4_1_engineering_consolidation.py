"""v6.4.1 engineering consolidation gates."""

from __future__ import annotations

import json
from pathlib import Path

from corep_crr3 import regulatory_dossier, resource_budgets, sql_migrations

ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.4.1"


def test_v640_sql_migration_plan_is_deterministic_and_production_safe() -> None:
    plan = sql_migrations.discover_plan(ROOT / "sql")
    assert plan
    current_paths = [step.path for step in plan]
    expected_paths = sorted(
        current_paths,
        key=lambda path: (next(step.order for step in plan if step.path == path), path),
    )
    assert current_paths == expected_paths
    assert sql_migrations.validate_plan(plan, production=True) == ()
    assert any(step.stage == "01_schema" for step in plan)
    assert any(step.stage == "02_seeds" for step in plan)
    assert any(step.stage == "03_mapping" for step in plan)
    assert any(step.stage == "04_post_seed" for step in plan)


def test_v640_resource_budgets_validate_measurements() -> None:
    budgets = resource_budgets.load_budgets(ROOT / "releases/evidence/resource_budgets_v6_4_1.json")
    indexed = resource_budgets.budget_index(budgets)
    assert "standard_engine_volume" in indexed
    ok = {
        "name": "standard_engine_volume",
        "elapsed_seconds": 0.01,
        "peak_rss_mb": 1.0,
        "rows": 10,
        "rows_per_second": 1000.0,
    }
    assert resource_budgets.validate_measurement(ok, indexed["standard_engine_volume"]) == ()
    bad = dict(ok, elapsed_seconds=indexed["standard_engine_volume"].max_seconds + 1.0)
    assert resource_budgets.validate_measurement(bad, indexed["standard_engine_volume"])


def test_v640_regulatory_dossier_is_fail_closed_until_external_evidence() -> None:
    payload = json.loads((ROOT / "releases/evidence/regulatory_dossier_v6_4_1.json").read_text(encoding="utf-8"))
    gates = regulatory_dossier.normalize_gates(payload)
    assert regulatory_dossier.readiness_status(gates) == "NO_GO"
    assert regulatory_dossier.validate_dossier(payload) == ()
    assert payload["fail_closed"] is True


def test_v640_active_version_references_are_current() -> None:
    assert (ROOT / "changelogs/CHANGELOG_v6_4_1.md").is_file()
    assert (ROOT / "releases/VALIDATION_v6_4_1.md").is_file()
    assert (ROOT / "releases/RELEASE_REPORT_v6_4_1.md").is_file()
    assert (ROOT / "releases/evidence/resource_budgets_v6_4_1.json").is_file()
    assert (ROOT / "releases/evidence/regulatory_dossier_v6_4_1.json").is_file()


def test_v640_sql_migration_state_table_and_drift_detection() -> None:
    plan = sql_migrations.discover_plan(ROOT / "sql")
    manifest = sql_migrations.build_apply_manifest(plan, version=VERSION, edition="ENTERPRISE")
    assert manifest["schema_version"] == 2
    assert "corep_schema_migrations" in str(manifest["state_table_ddl"])
    records = [{"path": step.path, "sha256": step.sha256, "applied_order": step.order} for step in plan]
    assert sql_migrations.validate_applied_records(plan, records) == ()
    drifted = [dict(item) for item in records]
    drifted[0]["sha256"] = "0" * 64
    assert sql_migrations.validate_applied_records(plan, drifted)
    assert "manual review required" in sql_migrations.build_rollback_template(plan).lower()


def test_v640_volume_benchmark_evidence_contains_real_stress_profiles() -> None:
    payload = json.loads((ROOT / "releases/evidence/volume_benchmark_v6_4_1.json").read_text(encoding="utf-8"))
    names = {item["name"] for item in payload["measurements"]}
    assert {"standard_engine_volume_100k", "saccr_multiplier_volume_100k", "mixed_portfolio_volume_10k"}.issubset(names)
    assert payload["summary"]["total_rows"] >= 210000
    budgets = resource_budgets.load_budgets(ROOT / "releases/evidence/resource_budgets_v6_4_1.json")
    assert resource_budgets.validate_measurements(payload["measurements"], budgets) == ()


def test_v640_regulatory_dossier_has_traceability_and_blocks_weak_passes() -> None:
    payload = json.loads((ROOT / "releases/evidence/regulatory_dossier_v6_4_1.json").read_text(encoding="utf-8"))
    assert payload["external_artifact_requirements"]
    assert payload["traceability_matrix"]
    assert regulatory_dossier.validate_traceability_matrix(payload) == ()
    weak = json.loads(json.dumps(payload))
    for gate in weak["gates"]:
        gate["status"] = "PASSED"
    weak["submission_readiness"] = "GO"
    assert regulatory_dossier.validate_dossier(weak)


def test_v640_postgres_explain_budget_gate() -> None:
    from corep_crr3 import postgres_profiling

    sample = json.loads((ROOT / "releases/evidence/postgres_explain_smoke_v6_4_1.json").read_text(encoding="utf-8"))
    budget = postgres_profiling.load_budgets(ROOT / "releases/evidence/postgres_query_budgets_v6_4_1.json")[0]
    summary = postgres_profiling.summarize_explain(sample)
    assert postgres_profiling.validate_summary(summary, budget) == ()
    assert "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)" in postgres_profiling.explain_sql("select 1")
    bad = dict(summary, seq_scan_rows=budget.max_seq_scan_rows + 1)
    assert postgres_profiling.validate_summary(bad, budget)


def test_v640_sql_migration_applied_order_is_unique_and_contiguous() -> None:
    plan = sql_migrations.discover_plan(ROOT / "sql")
    orders = [step.order for step in plan]
    assert orders == list(range(1, len(plan) + 1))
    assert len(orders) == len(set(orders))
    manifest = sql_migrations.build_apply_manifest(plan, version=VERSION, edition="ENTERPRISE")
    manifest_orders = [int(step["order"]) for step in manifest["steps"]]
    assert manifest_orders == orders


def test_v640_regulatory_dossier_requires_every_external_gate() -> None:
    payload = json.loads((ROOT / "releases/evidence/regulatory_dossier_v6_4_1.json").read_text(encoding="utf-8"))
    assert regulatory_dossier.validate_external_artifact_requirements(payload) == ()
    gate_names = {gate["name"] for gate in payload["gates"]}
    requirement_names = {item["name"] for item in payload["external_artifact_requirements"]}
    assert gate_names.issubset(requirement_names)

    incomplete = [gate for gate in regulatory_dossier.normalize_gates(payload) if gate.name != "github_live_ci_green"]
    assert regulatory_dossier.readiness_status(incomplete) == "NO_GO"


def test_v640_traceability_matrix_covers_full_p1_scope() -> None:
    payload = json.loads((ROOT / "releases/evidence/regulatory_dossier_v6_4_1.json").read_text(encoding="utf-8"))
    matrix = payload["traceability_matrix"]
    assert regulatory_dossier.validate_traceability_matrix(payload) == ()
    modules = {row["engine_module"] for row in matrix}
    expected_modules = {
        "saccr_engine",
        "standard_engine",
    }
    assert expected_modules.issubset(modules)
    for row in matrix:
        assert row["quality_status"] in regulatory_dossier.ALLOWED_QUALITY_STATUSES
        assert row["dpm_datapoint_or_kpi"]
        assert row["source_sql_or_input"]
        assert row["formula_or_rule"]


def test_v640_traceability_blocks_non_official_outputs_for_go() -> None:
    payload = regulatory_dossier.build_fail_closed_dossier(version=VERSION, edition="COMMUNITY")
    for gate in payload["gates"]:
        gate["status"] = "PASSED"
        gate["owner"] = "external-reviewer"
        gate["evidence"] = "signed external evidence"
        gate["evidence_sha256"] = "a" * 64
    for row in payload["traceability_matrix"]:
        row["status"] = "SIGNED_OFF"
    for entry in payload["signoff_register"]:
        entry["signature_status"] = "SIGNED"
        entry["signatory"] = "external-reviewer"
        entry["signature_date"] = "2026-06-29"
        entry["evidence_sha256"] = "a" * 64
    payload["submission_readiness"] = "GO"
    payload["fail_closed"] = False
    errors = regulatory_dossier.validate_dossier(payload)
    assert errors == ()
