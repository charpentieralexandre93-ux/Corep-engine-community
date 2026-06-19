"""Non-régression v6.2.1 du contrat SQL du moteur Standard."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sql/01_schema/01_schema_common_community.sql"
ENGINE_PATH = ROOT / "src/corep_crr3/standard_engine.py"
EXPECTED_COLUMNS = (
    "ccf_applied",
    "ccf_bucket",
    "rw_rule_source",
    "rw_bucket",
    "cqs_used",
    "ltv_bucket",
    "currency_mismatch_multiplier",
    "ead_after_ufcp",
    "rwa_before_supporting_factor",
    "capital_requirement_8pct",
)


def _standard_results_create_block() -> str:
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS core\.core_standard_results\s*\((.*?)\n\);",
        ddl,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_standard_results_ddl_matches_engine_insert_contract() -> None:
    ddl = _standard_results_create_block()
    engine = ENGINE_PATH.read_text(encoding="utf-8")
    insert = re.search(
        r"INSERT INTO core\.core_standard_results\s*\((.*?)\) VALUES %s",
        engine,
        re.DOTALL,
    )
    assert insert is not None
    insert_columns = {item.strip() for item in insert.group(1).split(",")}
    for column in EXPECTED_COLUMNS:
        assert re.search(rf"(?m)^\s*{re.escape(column)}\s+", ddl), column
        assert column in insert_columns, column


def test_standard_results_upgrade_is_idempotent() -> None:
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    for column in EXPECTED_COLUMNS:
        assert f"ADD COLUMN IF NOT EXISTS {column}" in ddl
