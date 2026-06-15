from __future__ import annotations

from pathlib import Path

import pytest

from corep_crr3 import operational_readiness, runtime_rules
from corep_crr3.release_integrity import create_manifest, verify_manifest


class RuntimeDb:
    def query(self, sql, params=()):
        return [
            {"parameter_name": "DEFAULT_ALPHA_SACCR", "parameter_value": "1.4", "parameter_type": "REAL"},
            {"parameter_name": "ENABLE_TEMPLATE_MAPPING", "parameter_value": "Y", "parameter_type": "BOOLEAN"},
        ]


def test_public_runtime_parameters_are_typed_and_unknown_overrides_ignored():
    values = runtime_rules.get_parameters(
        RuntimeDb(), "CRR3_V9", ("DEFAULT_ALPHA_SACCR", "ENABLE_TEMPLATE_MAPPING")
    )
    assert values == {"DEFAULT_ALPHA_SACCR": 1.4, "ENABLE_TEMPLATE_MAPPING": True}
    assert runtime_rules.merge_parameters({"alpha": 1.0}, {"alpha": 1.4, "private": 99}) == {"alpha": 1.4}
    with pytest.raises(runtime_rules.RuntimeParameterError):
        runtime_rules._cast_parameter("maybe", "BOOLEAN", name="FLAG")


def test_public_readiness_is_fail_closed_and_can_only_be_explicitly_skipped(tmp_path: Path):
    failed = operational_readiness.run_readiness_checks(
        output_dir=tmp_path / "failed",
        min_free_mb=0,
        required_resources=(),
        database_probe=lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert not failed.passed
    assert next(item for item in failed.checks if item.code == "DATABASE").status == "FAIL"

    skipped = operational_readiness.run_readiness_checks(
        output_dir=tmp_path / "skipped",
        min_free_mb=0,
        required_resources=(),
        require_database=False,
    )
    assert skipped.passed
    assert next(item for item in skipped.checks if item.code == "DATABASE").status == "NOT_EXECUTED"


def test_public_default_database_probe_verifies_bootstrap_relations(monkeypatch):
    class FakeDb:
        def __init__(self, dsn):
            self.dsn = dsn

        def query(self, sql, params=()):
            if "current_database" in sql:
                return [{"database_name": "corep", "server_version": "PostgreSQL 16"}]
            if "to_regclass" in sql:
                return [{"relation_name": params[0]}]
            return [{"count": 12}]

        def close(self):
            return None

    monkeypatch.setattr(operational_readiness, "Database", FakeDb)
    monkeypatch.setattr(operational_readiness, "build_dsn_from_env", lambda: "dsn")
    result = operational_readiness._default_database_probe(("meta.schema_migrations",))
    assert result["database"] == "corep"
    assert result["applied_migrations"] == 12


def test_public_manifest_covers_root_files_not_only_selected_directories(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "NOTICE").write_text("notice\n", encoding="utf-8")
    manifest = create_manifest(tmp_path, version="6.0.2", edition="COMMUNITY")
    assert {entry.path for entry in manifest.entries} == {"NOTICE", "src/module.py"}
    verify_manifest(tmp_path, manifest, expected_version="6.0.2")
