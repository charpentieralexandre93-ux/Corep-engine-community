"""Recette PostgreSQL réelle du périmètre Community SA / SA-CCR.

Activation explicite :

    RUN_POSTGRES_E2E=1 RUN_POSTGRES_E2E_RESET=1 \
    COREP_ALLOW_DESTRUCTIVE_RESET=1 pytest -q tests/test_postgresql_community_e2e.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_E2E") != "1",
    reason="Recette PostgreSQL Community désactivée.",
)


def _run(command, env):
    return subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
    )


def test_community_bootstrap_then_sa_and_saccr_engines():
    import psycopg2

    from corep_crr3.db import Database, build_dsn_from_env
    from corep_crr3.saccr_engine import run_saccr_engine
    from corep_crr3.standard_engine import run_standard_engine

    if isinstance(getattr(psycopg2, "connect", None), Mock):
        pytest.fail("psycopg2 réel requis pour RUN_POSTGRES_E2E=1")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    bootstrap_command = [sys.executable, "-m", "corep_crr3.community_bootstrap"]
    if os.getenv("RUN_POSTGRES_E2E_RESET") == "1":
        bootstrap_command.extend(["--reset", "--confirm-reset", "RESET"])
    bootstrap = _run(bootstrap_command, env)
    assert bootstrap.returncode == 0, bootstrap.stdout

    db = Database(build_dsn_from_env())
    batch_id = "COMMUNITY_E2E_428"
    reporting_date = "2026-06-30"
    try:
        with db.transaction():
            db.execute("DELETE FROM meta.batch_run_control WHERE batch_id = %s", (batch_id,))
            db.execute(
                """
                INSERT INTO meta.batch_run_control (
                    batch_id, regulatory_version_id, reporting_date, status,
                    loaded_rows, rejected_rows, calculated_rows, notes
                ) VALUES (%s, 'CRR3_V9', %s, 'RUNNING', 2, 0, 0, 'Community E2E')
                """,
                (batch_id, reporting_date),
            )
            db.execute(
                """
                INSERT INTO stg.stg_exposures (
                    batch_id, exposure_id, counterparty_id, asset_class_id,
                    product_type_id, calculation_approach, exposure_amount,
                    provision_amount, guarantee_amount, currency,
                    maturity_months, credit_quality_step, delinquent_flag,
                    supporting_sme_flag, supporting_infra_flag
                ) VALUES (
                    %s, 'EXP_COMMUNITY_1', 'CP_CORP_01', 'CORPORATE',
                    'TERM_LOAN', 'SA', 100000, 5000, 0, 'EUR',
                    36, 'UNRATED', FALSE, FALSE, FALSE
                )
                """,
                (batch_id,),
            )
            db.execute(
                """
                INSERT INTO stg.stg_saccr_trades (
                    batch_id, trade_id, netting_set_id, asset_class_id,
                    mtm, addon, collateral, counterparty_id, asset_class,
                    notional, delta, maturity_years, start_date_years,
                    end_date_years, payment_currency
                ) VALUES (
                    %s, 'TRD_COMMUNITY_1', 'NS_COMMUNITY_1', 'CORPORATE',
                    1000, 0, 0, 'CP_CORP_01', 'FX',
                    250000, 1, 1, 0, 1, 'EUR'
                )
                """,
                (batch_id,),
            )

        sa_count = run_standard_engine(
            db, batch_id, "CRR3_V9", reporting_date, strict_fallback_mode=True
        )
        saccr_count = run_saccr_engine(db, batch_id, "CRR3_V9", reporting_date)

        assert sa_count == 1
        assert saccr_count == 1

        sa_rows = db.query(
            """
            SELECT ead_pre_crm, risk_weight_base, rwa_final
            FROM core.core_standard_results
            WHERE batch_id = %s AND exposure_id = 'EXP_COMMUNITY_1'
            """,
            (batch_id,),
        )
        assert len(sa_rows) == 1
        assert float(sa_rows[0]["ead_pre_crm"]) > 0
        assert float(sa_rows[0]["risk_weight_base"]) > 0
        assert float(sa_rows[0]["rwa_final"]) > 0

        saccr_rows = db.query(
            """
            SELECT rc, pfe, ead, risk_weight, rwa
            FROM core.core_saccr_results
            WHERE batch_id = %s AND netting_set_id = 'NS_COMMUNITY_1'
            """,
            (batch_id,),
        )
        assert len(saccr_rows) == 1
        assert float(saccr_rows[0]["ead"]) > 0
        assert float(saccr_rows[0]["risk_weight"]) > 0
        assert float(saccr_rows[0]["rwa"]) > 0

        migrations = db.query("SELECT script_name FROM meta.schema_migrations")
        names = {row["script_name"] for row in migrations}
        assert "01_schema/01_schema_common_community.sql" in names
        assert "01_schema/engines/schema_credit_standard.sql" in names
        assert "01_schema/engines/schema_saccr.sql" in names
        forbidden = (
            "irb",
            "sft",
            "cva",
            "liquidity",
            "irrbb",
            "market_risk",
            "operational_risk",
            "own_funds",
            "securitisation",
            "large_exposures",
            "crypto_assets",
            "frtb",
            "output_floor",
            "dpm_xbrl",
            "finrep",
        )
        assert not any(any(token in name.lower() for token in forbidden) for name in names)

        private_objects = db.query(
            """
            SELECT
                to_regclass('core.core_irb_results') AS irb_results,
                to_regclass('core.core_cva_results') AS cva_results,
                to_regclass('core.core_sft_results') AS sft_results,
                to_regclass('rpt.rpt_finrep_premap') AS finrep_premap
            """
        )[0]
        assert all(value is None for value in private_objects.values())

        assert (
            db.query("SELECT COUNT(*) AS n FROM ref.ref_mapping_rules WHERE framework <> 'COREP'")[
                0
            ]["n"]
            == 0
        )
        assert (
            db.query(
                "SELECT COUNT(*) AS n FROM ref.ref_asset_classes "
                "WHERE asset_class_id = 'SECURITISATION'"
            )[0]["n"]
            == 0
        )
    finally:
        db.close()
