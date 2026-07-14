"""Coverage ratchets for the v6.3.2 public runtime-critical paths."""

from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from corep_crr3 import db as dbm
from corep_crr3 import release_integrity as ri
from corep_crr3 import saccr_engine as saccr
from corep_crr3 import standard_engine as sa


class _Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        return list(self.rows)


class _Conn:
    def __init__(self, rows=()):
        self.autocommit = True
        self.rows = list(rows)
        self.cursors: list[_Cursor] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def cursor(self, **_kwargs):
        cursor = _Cursor(self.rows)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def test_database_full_dal_and_pool_paths(monkeypatch):
    execute_values_calls = []
    conn = _Conn([{"value": 1}])
    fake_pool = SimpleNamespace(
        getconn=lambda: conn,
        putconn=lambda value: execute_values_calls.append(("put", value)),
        closeall=lambda: execute_values_calls.append(("close", None)),
    )
    pool_factory_calls = []

    class _PoolFactory:
        def __new__(cls, minconn, maxconn, dsn):
            pool_factory_calls.append((minconn, maxconn, dsn))
            return fake_pool

    fake_psycopg2 = SimpleNamespace(
        connect=lambda dsn: conn,
        extras=SimpleNamespace(
            execute_values=lambda cur, sql, rows, page_size: execute_values_calls.append(
                (cur, sql, list(rows), page_size)
            )
        ),
        pool=SimpleNamespace(ThreadedConnectionPool=_PoolFactory),
    )
    monkeypatch.setattr(dbm, "psycopg2", fake_psycopg2)
    monkeypatch.setattr(dbm, "_psycopg2_extras", SimpleNamespace(RealDictCursor=object))

    database = dbm.Database("dsn")
    database.execute("UPDATE t SET x=%s", (1,))
    database.executescript("SELECT 1; SELECT 2")
    database.executemany("INSERT INTO t VALUES %s", [(1,), (2,)])
    assert database.query("SELECT value FROM t") == [{"value": 1}]
    assert conn.commits == 1
    assert len(conn.cursors) == 4

    pool = dbm.DatabasePool("pool-dsn", minconn=2, maxconn=4)
    with pool.acquire() as borrowed:
        assert borrowed.conn is conn
    assert conn.rollbacks == 1
    assert execute_values_calls[-1] == ("put", conn)
    pool.close()
    assert pool_factory_calls == [(2, 4, "pool-dsn")]
    assert execute_values_calls[-1] == ("close", None)

    conn.rollback = lambda: (_ for _ in ()).throw(RuntimeError("cleanup"))
    with pool.acquire():
        pass
    assert execute_values_calls[-1] == ("put", conn)


def test_database_dsn_optional_reads_and_missing_driver(monkeypatch, tmp_path):
    for name in ("DATABASE_URL", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGPASSWORD_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(dbm, "_psycopg2_make_dsn", None)
    assert dbm._quote_conninfo_value("plain") == "plain"
    assert dbm._quote_conninfo_value("a b") == "'a b'"
    assert "password='p\\\\q\\'r'" in dbm._build_conninfo({"password": "p\\q'r"})
    assert dbm.build_dsn_from_config(None, "fallback") == "fallback"
    assert dbm.build_dsn_from_config({"dbname": "db", "user": "u", "host": "h"}) == (
        "host=h port=5432 dbname=db user=u"
    )

    oversized = tmp_path / "secret"
    oversized.write_text("x" * 16_385, encoding="utf-8")
    monkeypatch.setenv("PGPASSWORD_FILE", str(oversized))
    with pytest.raises(RuntimeError, match="16 KiB"):
        dbm._resolve_pgpassword()

    class MissingRelation(RuntimeError):
        pgcode = "42P01"

    class MissingColumn(RuntimeError):
        pgcode = "42703"

    class Reader:
        def __init__(self, exc=None):
            self.exc = exc
            self.rollbacks = 0

        def query(self, *_args):
            if self.exc:
                raise self.exc
            return [1]

        def rollback(self):
            self.rollbacks += 1

    assert dbm.safe_read(Reader(), "SELECT") == [1]
    reader = Reader(MissingRelation("missing"))
    assert dbm.safe_read(reader, "SELECT", default=[]) == []
    assert reader.rollbacks == 1
    outer = RuntimeError("outer")
    outer.__cause__ = MissingColumn("column")
    assert dbm._is_optional_relation_error(outer)
    with pytest.raises(RuntimeError, match="operational"):
        dbm.safe_read(Reader(RuntimeError("operational")), "SELECT")

    rollback_reader = Reader(MissingRelation("missing"))
    rollback_reader.rollback = lambda: (_ for _ in ()).throw(RuntimeError("rollback failed"))
    with pytest.raises(RuntimeError, match="rollback failed"):
        dbm.safe_read(rollback_reader, "SELECT")

    monkeypatch.setattr(dbm, "psycopg2", None)
    with pytest.raises(RuntimeError, match="psycopg2 est requis"):
        dbm._require_psycopg2()


def test_release_manifest_roundtrip_cli_and_validation(tmp_path, capsys):
    root = tmp_path / "release"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / ".pytest_cache").mkdir()
    (root / ".pytest_cache" / "ignored").write_text("x", encoding="utf-8")
    (root / ".env.local").write_text("SECRET=x", encoding="utf-8")
    output = root / "RELEASE_MANIFEST.json"

    manifest = ri.create_manifest(root, version="6.3.2", edition="community", manifest_path=output)
    assert manifest.to_dict()["edition"] == "COMMUNITY"
    assert [entry.path for entry in manifest.entries] == ["src/app.py"]
    assert ri.write_manifest(manifest, output) == output
    loaded = ri.load_manifest(output)
    ri.verify_manifest(root, loaded, expected_version="6.3.2")
    assert ri.main(["--root", str(root), "--manifest", str(output), "--version", "6.3.2"]) == 0
    assert "1 artefacts vérifiés" in capsys.readouterr().out

    with pytest.raises(ri.ReleaseIntegrityError, match="Version invalide"):
        ri.create_manifest(root, version="v6", edition="COMMUNITY")
    with pytest.raises(ri.ReleaseIntegrityError, match="edition"):
        ri.create_manifest(root, version="6.3.2", edition="PRIVATE")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ri.ReleaseIntegrityError, match="Aucun artefact"):
        ri.create_manifest(empty, version="6.3.2", edition="COMMUNITY")

    bad = root / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ri.ReleaseIntegrityError, match="illisible"):
        ri.load_manifest(bad)
    assert ri.main(["--root", str(root), "--manifest", str(bad)]) == 1
    assert "ERROR:" in capsys.readouterr().out


def test_release_manifest_rejects_all_integrity_failures(tmp_path):
    root = tmp_path
    target = root / "file.txt"
    target.write_text("stable", encoding="utf-8")
    manifest = ri.create_manifest(root, version="6.3.2", edition="COMMUNITY")

    with pytest.raises(ri.ReleaseIntegrityError, match="version attendue"):
        ri.verify_manifest(root, manifest, expected_version="6.4.1")
    with pytest.raises(ri.ReleaseIntegrityError, match="schéma"):
        ri.verify_manifest(root, ri.ReleaseManifest(2, "6.3.2", "COMMUNITY", manifest.entries))
    duplicate = ri.ReleaseManifest(1, "6.3.2", "COMMUNITY", manifest.entries + manifest.entries)
    with pytest.raises(ri.ReleaseIntegrityError, match="dupliqué"):
        ri.verify_manifest(root, duplicate)

    target.write_text("longer content", encoding="utf-8")
    with pytest.raises(ri.ReleaseIntegrityError, match="taille différente"):
        ri.verify_manifest(root, manifest)
    target.write_text("alterx", encoding="utf-8")
    same_size_manifest = ri.create_manifest(root, version="6.3.2", edition="COMMUNITY")
    target.write_text("change", encoding="utf-8")
    with pytest.raises(ri.ReleaseIntegrityError, match="SHA-256 différent"):
        ri.verify_manifest(root, same_size_manifest)
    target.unlink()
    with pytest.raises(ri.ReleaseIntegrityError, match="fichier absent"):
        ri.verify_manifest(root, same_size_manifest)


BASE_ROW = {
    "exposure_id": "E1",
    "counterparty_id": "C1",
    "asset_class_id": "RETAIL",
    "product_type_id": "REVOCABLE_COMMITMENT",
    "exposure_amount": 100.0,
    "provision_amount": 10.0,
    "calculation_approach": "SA",
    "currency": "EUR",
    "counterparty_currency": "USD",
    "borrower_income_currency": "USD",
    "maturity_months": 60,
    "ltv_ratio": 0.70,
    "supporting_sme_flag": True,
    "credit_quality_step": 2,
    "exposure_subtype": "",
    "institution_scra_grade": None,
    "short_term_exposure_flag": False,
    "adc_flag": False,
    "ipre_flag": False,
    "transactor_flag": False,
    "delinquent_flag": False,
}


def test_standard_resolution_crm_and_full_orchestration(monkeypatch):
    decisions = {
        "CCF": {"result_value": 0.5},
        "RISK_WEIGHT": {"result_value": 0.75},
        "SUBSTITUTION_RISK_WEIGHT": {"result_value": 0.2},
    }
    monkeypatch.setattr(sa, "evaluate_rule_set", lambda _db, _b, _v, domain, *_a, **_k: decisions.get(domain))
    monkeypatch.setattr(
        sa,
        "apply_supporting_factors",
        lambda **kwargs: {
            "rwa_final": kwargs["rwa_pre_supporting"] * 0.9,
            "multiplier_final": 0.9,
            "factor_codes": "SME",
        },
    )
    monkeypatch.setattr(sa, "lookup_fcp_haircut_rate_from_rules", lambda *_a, **_k: 0.1)
    runtime = sa._StandardRuntime(
        supporting_factor_rules=[],
        protections_by_exposure={
            "E1": [
                {
                    "protection_id": "F1",
                    "protection_type": "FCP",
                    "protection_value": 20,
                    "currency": "USD",
                    "maturity_months": 24,
                    "bucket": "CASH",
                },
                {
                    "protection_id": "U1",
                    "protection_type": "UFCP",
                    "protection_value": 15,
                    "currency": "EUR",
                    "maturity_months": 60,
                    "provider_type": "CENTRAL_GOVERNMENT",
                },
            ]
        },
        haircut_rules=sa.FcpHaircutRuleBook(by_collateral_type={}),
        crm_fx_haircut=0.08,
    )
    buffers = sa._StandardBuffers()
    stats = sa._StandardFallbackStats()
    result = sa._process_standard_exposure(
        SimpleNamespace(),
        dict(BASE_ROW),
        batch_id="B",
        regulatory_version_id="V",
        runtime=runtime,
        buffers=buffers,
        stats=stats,
        sme_total_exposure=90.0,
    )
    assert result[0:5] == ("B", "E1", "C1", "RETAIL", "REVOCABLE_COMMITMENT")
    assert result[16] == 0.5
    assert len(buffers.allocations) == 2
    assert "FX" in buffers.allocations[0][-1]

    # Native Annex-I branch, then explicit fallback branches.
    monkeypatch.setattr(sa, "evaluate_rule_set", lambda *_a, **_k: None)
    row = dict(BASE_ROW, product_type_id="UNCONDITIONALLY_CANCELLABLE_COMMITMENT")
    ccf, bucket = sa._resolve_ccf(SimpleNamespace(), "B", "V", row, [], stats)
    assert (ccf, bucket) == (0.1, "BUCKET_5")
    row["product_type_id"] = "UNKNOWN"
    assert sa._resolve_ccf(SimpleNamespace(), "B", "V", row, [], stats)[0] == 1.0
    rw, bucket, multiplier = sa._resolve_base_risk_weight(SimpleNamespace(), "B", "V", row, 0.0, 0.0, [], stats)
    assert (rw, bucket, multiplier) == (1.5, "CURRENCY_MISMATCH", 1.5)
    assert sa._crm_effect("CRM", fx_mismatch=True, maturity_factor=0.5) == "CRM_FX_MMM"
    assert sa._currency_mismatch({"currency": "EUR"}, {"currency": "USD"})
    assert not sa._currency_mismatch({}, {"currency": "USD"})

    class EngineDB:
        def __init__(self):
            self.saved = []

        def execute(self, *_args):
            pass

        def query(self, sql, _params=()):
            if "stg.stg_exposures" in sql:
                return [dict(BASE_ROW), dict(BASE_ROW, exposure_id="IRB", calculation_approach="IRB-A")]
            return []

        def executemany(self, sql, values):
            self.saved.append((sql, list(values)))

        @contextmanager
        def transaction(self):
            yield self

    engine_db = EngineDB()
    monkeypatch.setattr(sa, "_load_standard_runtime", lambda *_a, **_k: runtime)
    monkeypatch.setattr(sa, "clear_rules_cache", lambda: None)
    monkeypatch.setattr(sa, "flush_trace_buffer", lambda *_a, **_k: None)
    decisions.update({"CCF": {"result_value": 0.5}, "RISK_WEIGHT": {"result_value": 0.75}})
    monkeypatch.setattr(sa, "evaluate_rule_set", lambda _db, _b, _v, domain, *_a, **_k: decisions.get(domain))
    assert sa.run_standard_engine(engine_db, "B", "V", "2026-03-31") == 1
    assert any("core_standard_results" in sql for sql, _ in engine_db.saved)


def test_standard_persistence_metrics_and_strict_failures(monkeypatch):
    class DB:
        def __init__(self):
            self.saved = []

        @contextmanager
        def transaction(self):
            yield self

        def executemany(self, sql, rows):
            self.saved.append((sql, list(rows)))

    db = DB()
    buffers = sa._StandardBuffers(
        results=[("result",)],
        allocations=[("allocation",)],
        decision_traces=[("decision",)],
        supporting_factor_traces=[("factor",)],
    )
    stats = sa._StandardFallbackStats(ccf_count=1, rw_count=2, ignored_protection_count=3)
    monkeypatch.setattr(sa, "flush_trace_buffer", lambda db, rows: db.saved.append(("trace", list(rows))))
    sa._persist_standard_batches(db, "B", buffers, stats)
    assert len(db.saved) == 5
    assert len(sa._standard_control_metrics("B", stats)) == 3
    sa._report_standard_anomalies(stats, 1, False)
    with pytest.raises(RuntimeError, match="strict_fallback_mode"):
        sa._report_standard_anomalies(stats, 1, True)


def _trade(**overrides):
    trade = {
        "trade_id": "T1",
        "batch_id": "B",
        "netting_set_id": "NS1",
        "counterparty_id": "C1",
        "counterparty_type": "CORPORATE",
        "mtm": 10.0,
        "collateral": 0.0,
        "asset_class": "FX",
        "notional": 1000.0,
        "maturity_years": 1.0,
        "start_date_years": 0.0,
        "end_date_years": 1.0,
        "delta": 1.0,
        "option_type": "",
        "strike": 0.0,
        "underlying_price": 0.0,
        "implied_vol": 0.0,
        "commodity_type": "ENERGY",
        "reference_entity_id": "REF",
        "credit_quality": "IG",
        "equity_id": "EQ",
        "equity_type": "SINGLE",
        "payment_currency": "EUR",
        "pay_currency": "EUR",
        "receive_currency": "USD",
        "currency_pair": "EURUSD",
        "collateral_currency": "EUR",
        "collateral_eligible": True,
        "vm_eligible": True,
        "im_eligible": True,
        "vm_received": 0.0,
        "vm_posted": 0.0,
        "im_received": 0.0,
        "im_posted": 0.0,
        "nica": None,
        "threshold_amount": 0.0,
        "mta": 0.0,
        "mpor_days": 10.0,
        "csa_id": None,
        "addon": 0.0,
    }
    trade.update(overrides)
    return trade


def test_saccr_margin_parameters_calculation_and_orchestration(monkeypatch):
    assert saccr._apply_margin_cap([_trade()])["final_method"] == "UNMARGINED"
    margined = _trade(csa_id="CSA", vm_received=5.0, collateral=5.0)
    capped = saccr._apply_margin_cap([margined])
    assert capped["margined"] is not None
    assert capped["final_method"] in {"MARGINED", "ART274_3_UNMARGINED_CAP"}

    class ParamDB:
        def query(self, *_args):
            return [
                {"parameter_name": "ALPHA", "parameter_value": 1.5},
                {"parameter_name": "MULTIPLIER_FLOOR", "parameter_value": 0.06},
                {"parameter_name": "SF_FX", "parameter_value": 0.05},
                {"parameter_name": "RHO_CREDIT", "parameter_value": 0.6},
                {"parameter_name": "IRD_EPSILON_1_2", "parameter_value": 1.2},
                {"parameter_name": "IRD_EPSILON_BAD_X", "parameter_value": 9},
            ]

    monkeypatch.setattr(saccr, "get_parameter", lambda *_a, **_k: 1.4)
    assert saccr._load_supervisory_parameters(ParamDB(), "V") == 1.5
    assert saccr._SF["FX"] == 0.05
    assert saccr._RHO["CREDIT"] == 0.6
    assert saccr._IRD_EPSILON[(2, 1)] == 1.2

    monkeypatch.setattr(saccr, "evaluate_rule_set", lambda *_a, **_k: {"result_value": 0.5})
    row = saccr._calculate_saccr_netting_set(SimpleNamespace(), "B", "V", "NS1", [_trade()], "CORPORATE", "C1", 1.4, [])
    assert row[0:4] == ("B", "NS1", "C1", "CORPORATE")
    assert row[8] == pytest.approx(row[6] * 0.5)
    assert json.loads(row[-1])["final_method"] == "UNMARGINED"

    class EngineDB:
        def __init__(self, trades):
            self.trades = trades
            self.saved = []

        def execute(self, *_args):
            pass

        def query(self, *_args):
            return list(self.trades)

        def executemany(self, sql, rows):
            self.saved.append((sql, list(rows)))

        @contextmanager
        def transaction(self):
            yield self

    monkeypatch.setattr(saccr, "_load_supervisory_parameters", lambda *_a: 1.4)
    monkeypatch.setattr(saccr, "flush_trace_buffer", lambda *_a: None)
    db = EngineDB([_trade(), _trade(trade_id="T2", netting_set_id="NS2", counterparty_id="C2")])
    assert saccr.run_saccr_engine(db, "B", "V", "2026-03-31") == 2
    assert len(db.saved[0][1]) == 2
    assert saccr.run_saccr_engine(EngineDB([]), "B", "V", "2026-03-31") == 0


def test_saccr_supervisory_fallback(monkeypatch):
    class BrokenDB:
        def query(self, *_args):
            raise RuntimeError("legacy schema")

    monkeypatch.setattr(saccr, "get_parameter", lambda *_a, **_k: 1.41)
    assert saccr._load_supervisory_parameters(BrokenDB(), "V") == 1.41
