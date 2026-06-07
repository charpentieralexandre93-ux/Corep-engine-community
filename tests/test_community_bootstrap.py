"""Tests unitaires du bootstrap SQL public SA / SA-CCR."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from corep_crr3 import community_bootstrap as cb


class FakeDb:
    def __init__(self):
        self.migrations = {}
        self.scripts = []
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def executescript(self, sql):
        self.scripts.append(sql)

    def query(self, sql, params=()):
        if "FROM meta.schema_migrations" in sql:
            script_name, checksum = params
            return [{"present": 1}] if self.migrations.get(script_name) == checksum else []
        return []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "INSERT INTO meta.schema_migrations" in sql:
            script_name, checksum, _notes = params
            self.migrations[script_name] = checksum

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _write_contract(sql_dir: Path, paths=("01_first.sql", "02_second.sql")) -> None:
    contract = {
        "version": "4.2.8",
        "edition": "Community",
        "engines": ["SA", "SA_CCR"],
        "reset_sql": "00_reset_database_dev_ONLY.sql",
        "steps": [
            {"path": path, "group": "always", "description": f"step {index}"}
            for index, path in enumerate(paths, start=1)
        ],
    }
    (sql_dir / "COMMUNITY_SQL_CONTRACT.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    (sql_dir / "00_reset_database_dev_ONLY.sql").write_text(
        "DROP SCHEMA IF EXISTS core CASCADE;", encoding="utf-8"
    )
    for path in paths:
        target = sql_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"SELECT '{path}';", encoding="utf-8")


def test_packaged_contract_is_strictly_sa_and_saccr():
    sql_dir = cb.resolve_sql_dir()
    contract = cb.load_sql_contract(sql_dir)
    assert contract["version"] == "4.2.8"
    assert contract["engines"] == ["SA", "SA_CCR"]
    paths = {step["path"] for step in contract["steps"]}
    assert "01_schema/01_schema_common_community.sql" in paths
    assert "01_schema/02_schema_domain_normalization_community.sql" in paths
    assert "02_seeds/00_seed_common_reference_community.sql" in paths
    assert "03_mapping/01_mapping_credit_standard_community.sql" in paths
    assert "01_schema/engines/schema_credit_standard.sql" in paths
    assert "01_schema/engines/schema_saccr.sql" in paths
    forbidden = cb._FORBIDDEN_SQL_TOKENS
    assert not any(any(token in path.lower() for token in forbidden) for path in paths)

    for step in contract["steps"]:
        content = (sql_dir / step["path"]).read_text(encoding="utf-8").lower()
        assert not any(token in content for token in forbidden), step["path"]

    common_sql = (sql_dir / "01_schema/01_schema_common_community.sql").read_text(
        encoding="utf-8"
    ).lower()
    assert "create role" not in common_sql


def test_manifest_is_generated_from_contract_and_all_files_exist():
    sql_dir = cb.resolve_sql_dir()
    manifest = cb.render_sql_manifest(sql_dir)
    steps = cb.sql_steps(sql_dir)
    assert "Corep Engine Community v4.2.8" in manifest
    assert "SA + SA-CCR" in manifest
    for step in steps:
        assert step["path"] in manifest
        assert (sql_dir / step["path"]).is_file()


def test_resolve_sql_dir_uses_explicit_directory(tmp_path):
    _write_contract(tmp_path)
    assert cb.resolve_sql_dir(tmp_path) == tmp_path.resolve()


def test_resolve_sql_dir_rejects_missing_contract(tmp_path):
    with pytest.raises(FileNotFoundError, match="contrat absent"):
        cb.resolve_sql_dir(tmp_path)


@pytest.mark.parametrize(
    "contract_update, message",
    [
        ({"edition": "Enterprise"}, "edition"),
        ({"engines": ["SA", "IRB"]}, "exactement SA et SA_CCR"),
        ({"steps": []}, "aucune étape"),
    ],
)
def test_contract_validation_rejects_invalid_scope(tmp_path, contract_update, message):
    _write_contract(tmp_path)
    path = tmp_path / "COMMUNITY_SQL_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract.update(contract_update)
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        cb.load_sql_contract(tmp_path)


def test_contract_rejects_unsafe_relative_path(tmp_path):
    _write_contract(tmp_path)
    path = tmp_path / "COMMUNITY_SQL_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["steps"][0]["path"] = "../enterprise.sql"
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="chemin non sûr"):
        cb.load_sql_contract(tmp_path)


def test_contract_rejects_duplicate_unknown_group_and_private_path(tmp_path):
    _write_contract(tmp_path)
    path = tmp_path / "COMMUNITY_SQL_CONTRACT.json"

    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["steps"][1]["path"] = contract["steps"][0]["path"]
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="dupliquée"):
        cb.load_sql_contract(tmp_path)

    _write_contract(tmp_path)
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["steps"][0]["group"] = "run_private"
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="groupe non autorisé"):
        cb.load_sql_contract(tmp_path)

    _write_contract(tmp_path)
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["steps"][0]["path"] = "schema_irb.sql"
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="hors périmètre"):
        cb.load_sql_contract(tmp_path)


def test_bootstrap_rejects_private_engine_content(tmp_path):
    _write_contract(tmp_path, paths=("01_first.sql",))
    (tmp_path / "01_first.sql").write_text(
        "CREATE TABLE core.private_cva_results(id integer);", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hors périmètre Community"):
        cb.bootstrap_postgresql(FakeDb(), tmp_path)


def test_bootstrap_applies_scripts_once_then_skips(tmp_path):
    _write_contract(tmp_path)
    db = FakeDb()

    first_count = cb.bootstrap_postgresql(db, tmp_path)
    first_script_count = len(db.scripts)
    second_count = cb.bootstrap_postgresql(db, tmp_path)

    assert first_count == 2
    assert second_count == 0
    # Une création idempotente de schema_migrations par appel + deux scripts métier.
    assert first_script_count == 3
    assert len(db.scripts) == 4
    assert set(db.migrations) == {"01_first.sql", "02_second.sql"}
    assert db.commits == 2


def test_bootstrap_reapplies_changed_checksum(tmp_path):
    _write_contract(tmp_path, paths=("01_first.sql",))
    db = FakeDb()
    assert cb.bootstrap_postgresql(db, tmp_path) == 1
    (tmp_path / "01_first.sql").write_text("SELECT 'changed';", encoding="utf-8")
    assert cb.bootstrap_postgresql(db, tmp_path) == 1
    assert len(db.migrations) == 1
    assert db.commits == 2


def test_bootstrap_fails_when_contract_file_is_missing(tmp_path):
    _write_contract(tmp_path)
    (tmp_path / "02_second.sql").unlink()
    with pytest.raises(FileNotFoundError, match="02_second.sql"):
        cb.bootstrap_postgresql(FakeDb(), tmp_path)


def test_bootstrap_rolls_back_when_script_execution_fails(tmp_path):
    _write_contract(tmp_path, paths=("01_first.sql",))

    class BrokenDb(FakeDb):
        def executescript(self, sql):
            if "SELECT '01_first.sql'" in sql:
                raise RuntimeError("SQL boom")
            super().executescript(sql)

    db = BrokenDb()
    with pytest.raises(RuntimeError, match="SQL boom"):
        cb.bootstrap_postgresql(db, tmp_path)
    assert db.rollbacks == 1


def test_reset_requires_confirmation_and_executes_when_confirmed(tmp_path):
    _write_contract(tmp_path)
    db = FakeDb()
    with pytest.raises(ValueError, match="Reset refusé"):
        cb._reset_database(db, tmp_path, None)
    cb._reset_database(db, tmp_path, "RESET")
    assert "DROP SCHEMA" in db.scripts[-1]


def test_write_manifest(tmp_path):
    _write_contract(tmp_path)
    path = cb.write_sql_manifest(tmp_path)
    assert path.name == "ACTIVE_SQL_MANIFEST.txt"
    assert path.read_text(encoding="utf-8") == cb.render_sql_manifest(tmp_path)


def test_main_list_and_manifest_do_not_connect(tmp_path, capsys):
    _write_contract(tmp_path)
    assert cb.main(["--sql-dir", str(tmp_path), "--list"]) == 0
    assert "01_first.sql" in capsys.readouterr().out
    assert cb.main(["--sql-dir", str(tmp_path), "--write-manifest"]) == 0
    assert (tmp_path / "ACTIVE_SQL_MANIFEST.txt").is_file()


def test_main_bootstrap_and_reset_with_injected_database(tmp_path, monkeypatch):
    _write_contract(tmp_path, paths=("01_first.sql",))
    db = FakeDb()
    monkeypatch.setattr(cb, "Database", lambda _dsn: db)
    monkeypatch.setattr(cb, "build_dsn_from_env", lambda: "fake-dsn")

    assert cb.main(["--sql-dir", str(tmp_path)]) == 0
    assert db.closed is True

    db2 = FakeDb()
    monkeypatch.setattr(cb, "Database", lambda _dsn: db2)
    assert cb.main([
        "--sql-dir", str(tmp_path), "--reset", "--confirm-reset", "RESET"
    ]) == 0
    assert any("DROP SCHEMA" in sql for sql in db2.scripts)
    assert db2.closed is True


def test_main_returns_one_on_invalid_directory(tmp_path):
    assert cb.main(["--sql-dir", str(tmp_path), "--list"]) == 1
