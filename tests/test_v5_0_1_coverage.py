"""Targeted Community regression and coverage tests for v5.0.1."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from corep_crr3 import db as db_module
from corep_crr3 import protection_strategy
from corep_crr3.public_registry import get_engine
from corep_crr3.public_registry import main as registry_main
from corep_crr3.saccr_engine import run_saccr_engine
from corep_crr3.standard_engine import run_standard_engine
from corep_crr3.utils import to_float


class _ProtectionDb:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.queries: list[tuple[str, tuple]] = []

    def query(self, sql: str, params=()):
        self.queries.append((" ".join(sql.split()), params))
        return list(self.rows)


def test_protections_are_enriched_grouped_and_ranked(monkeypatch):
    rows = [
        {
            "exposure_id": "EXP1",
            "protection_id": "P3",
            "protection_type": "FCP",
            "allocation_rank": None,
        },
        {
            "exposure_id": "EXP1",
            "protection_id": "P1",
            "protection_type": "UFCP",
            "allocation_rank": "1",
        },
        {
            "exposure_id": "EXP1",
            "protection_id": "P2",
            "protection_type": "FCP",
            "allocation_rank": "2",
        },
    ]
    db = _ProtectionDb(rows)

    def _decision(_db, _batch, _version, domain, context, trace_buffer=None):
        assert domain == "PROTECTION_BUCKET"
        assert context["_context_key"].startswith("EXP1:")
        if context["_context_key"].endswith(":P2"):
            return {"result_value": "DEFAULT"}
        if context["_context_key"].endswith(":P3"):
            return {"result_value": "COLLATERAL_CASH"}
        return None

    monkeypatch.setattr(protection_strategy, "evaluate_rule_set", _decision)
    trace_buffer: list = []
    grouped = protection_strategy.load_all_ranked_protections(db, "B1", "CRR3_V9", trace_buffer=trace_buffer)

    assert len(db.queries) == 1
    assert [p["protection_id"] for p in grouped["EXP1"]] == ["P1", "P2", "P3"]
    assert grouped["EXP1"][0]["bucket"] == "DEFAULT_UFCP"
    assert grouped["EXP1"][1]["bucket"] == "DEFAULT_FCP"
    assert grouped["EXP1"][2]["bucket"] == "COLLATERAL_CASH"


def test_unit_protection_loader_and_rank_fallbacks(monkeypatch):
    db = _ProtectionDb(
        [
            {
                "exposure_id": "EXP2",
                "protection_id": "P9",
                "protection_type": "FCP",
                "allocation_rank": "not-an-int",
            }
        ]
    )
    monkeypatch.setattr(protection_strategy, "evaluate_rule_set", lambda *a, **k: None)

    loaded = protection_strategy.load_ranked_protections(db, "B1", "CRR3_V9", "EXP2")

    assert loaded[0]["bucket"] == "DEFAULT_FCP"
    assert protection_strategy._allocation_rank_sort_value(" 3 ") == 3
    assert protection_strategy._allocation_rank_sort_value("") == 9999
    assert protection_strategy._allocation_rank_sort_value(None) == 9999
    assert protection_strategy._allocation_rank_sort_value("bad") == 9999


def test_database_environment_helpers_cover_all_resolution_modes(monkeypatch, tmp_path):
    for name in (
        "DATABASE_URL",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGPASSWORD_FILE",
        "PGPASSWORD_CMD",
        "COREP_EXECUTE_VALUES_PAGE_SIZE",
    ):
        monkeypatch.delenv(name, raising=False)

    assert db_module._resolve_execute_values_page_size(321) == 321
    monkeypatch.setenv("COREP_EXECUTE_VALUES_PAGE_SIZE", "2048")
    assert db_module._resolve_execute_values_page_size() == 2048
    monkeypatch.setenv("COREP_EXECUTE_VALUES_PAGE_SIZE", "0")
    assert db_module._resolve_execute_values_page_size(777) == 777
    monkeypatch.setenv("COREP_EXECUTE_VALUES_PAGE_SIZE", "invalid")
    assert db_module._resolve_execute_values_page_size(888) == 888

    assert db_module.build_dsn_from_env("fallback-dsn") == "fallback-dsn"
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    assert db_module.build_dsn_from_env() == "postgresql://example/test"
    monkeypatch.delenv("DATABASE_URL")

    monkeypatch.setenv("PGDATABASE", "corep")
    monkeypatch.setenv("PGUSER", "analyst")
    monkeypatch.setenv("PGHOST", "db.internal")
    monkeypatch.setenv("PGPORT", "5544")
    monkeypatch.setenv("PGPASSWORD", "direct-secret")
    assert db_module.build_dsn_from_env() == (
        "host=db.internal port=5544 dbname=corep user=analyst password=direct-secret"
    )

    monkeypatch.delenv("PGPASSWORD")
    password_file = tmp_path / "pgpassword"
    password_file.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("PGPASSWORD_FILE", str(password_file))
    assert db_module._resolve_pgpassword() == "file-secret"

    monkeypatch.delenv("PGPASSWORD_FILE")
    monkeypatch.setenv("PGPASSWORD_CMD", "secret-command --safe")
    import subprocess

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="command-secret\n"),
    )
    assert db_module._resolve_pgpassword() == "command-secret"

    monkeypatch.delenv("PGPASSWORD_CMD")
    assert db_module._resolve_pgpassword() is None


def test_database_transaction_commit_rollback_and_close(monkeypatch):
    class _Conn:
        def __init__(self):
            self.autocommit = True
            self.commits = 0
            self.rollbacks = 0
            self.closed = 0

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed += 1

    fake_psycopg2 = SimpleNamespace(extras=SimpleNamespace(RealDictCursor=object))
    monkeypatch.setattr(db_module, "psycopg2", fake_psycopg2)
    conn = _Conn()
    database = db_module.Database(conn=conn)
    assert conn.autocommit is False

    with database.transaction():
        pass
    assert conn.commits == 1

    with pytest.raises(RuntimeError, match="rollback"):
        with database.transaction():
            raise RuntimeError("rollback")
    assert conn.rollbacks == 1

    database.commit()
    database.rollback()
    database.close()
    assert (conn.commits, conn.rollbacks, conn.closed) == (2, 2, 1)


def test_public_registry_cli_and_tolerant_float(capsys):
    assert get_engine("sa") is run_standard_engine
    assert get_engine("sa-ccr") is run_saccr_engine
    with pytest.raises(ValueError, match="indisponible"):
        get_engine("IRB")

    registry_main()
    assert "SA, SA_CCR" in capsys.readouterr().out
    assert to_float("123.5") == 123.5
    assert to_float(None) == 0.0
    assert to_float("not-a-number") == 0.0
