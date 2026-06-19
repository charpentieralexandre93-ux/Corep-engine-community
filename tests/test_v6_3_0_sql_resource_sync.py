"""P0/P1 v6.3.0: SQL Community source, wheel et PostgreSQL."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_SCHEMA = ROOT / "sql/01_schema/01_schema_common_community.sql"
PACKAGED_SCHEMA = ROOT / "src/corep_crr3/sql/01_schema/01_schema_common_community.sql"
ENGINE = ROOT / "src/corep_crr3/standard_engine.py"
BOOTSTRAP = ROOT / "src/corep_crr3/community_bootstrap.py"
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


def _table(text: str) -> str:
    match = re.search(r"CREATE TABLE IF NOT EXISTS core\.core_standard_results\s*\((.*?)\n\);", text, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_root_and_packaged_sql_are_byte_identical() -> None:
    assert ROOT_SCHEMA.read_bytes() == PACKAGED_SCHEMA.read_bytes()


def test_packaged_ddl_matches_standard_engine_insert() -> None:
    ddl = PACKAGED_SCHEMA.read_text(encoding="utf-8")
    table = _table(ddl)
    engine = ENGINE.read_text(encoding="utf-8")
    match = re.search(r"INSERT INTO core\.core_standard_results\s*\((.*?)\) VALUES %s", engine, re.DOTALL)
    assert match is not None
    insert = {item.strip() for item in match.group(1).split(",")}
    for column in EXPECTED_COLUMNS:
        assert re.search(rf"(?m)^\s*{re.escape(column)}\s+", table), column
        assert column in insert, column


def test_cqs_accepts_unrated_and_v62_upgrade_is_idempotent() -> None:
    ddl = PACKAGED_SCHEMA.read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*cqs_used\s+VARCHAR\(20\)\s*,", _table(ddl))
    assert "ADD COLUMN IF NOT EXISTS cqs_used VARCHAR(20)" in ddl
    assert "ALTER COLUMN cqs_used TYPE VARCHAR(20)" in ddl
    assert "USING cqs_used::text" in ddl
    assert "UNRATED" in (ROOT / "tests/test_postgresql_community_e2e.py").read_text(encoding="utf-8")


def test_bootstrap_prefers_packaged_sql() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")
    package = 'Path(__file__).resolve().parent / "sql"'
    checkout = 'Path(__file__).resolve().parents[2] / "sql"'
    assert package in source and checkout in source
    assert source.index(package) < source.index(checkout)
