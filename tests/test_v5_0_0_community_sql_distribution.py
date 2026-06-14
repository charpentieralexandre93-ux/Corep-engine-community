"""Contrat de distribution SQL Community v5.0.0."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REPOSITORY_SCHEMA = (
    ROOT
    / "sql"
    / "01_schema"
    / "01_schema_common_community.sql"
)

PACKAGED_SCHEMA = (
    ROOT
    / "src"
    / "corep_crr3"
    / "sql"
    / "01_schema"
    / "01_schema_common_community.sql"
)

REQUIRED_RESULT_COLUMNS = (
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


def test_repository_and_packaged_schemas_are_identical():
    assert REPOSITORY_SCHEMA.read_bytes() == PACKAGED_SCHEMA.read_bytes()


def test_packaged_standard_result_schema_contains_v5_columns():
    sql = " ".join(
        PACKAGED_SCHEMA.read_text(encoding="utf-8").lower().split()
    )

    missing = [
        column
        for column in REQUIRED_RESULT_COLUMNS
        if f"add column if not exists {column}" not in sql
    ]

    assert not missing, (
        "Colonnes attendues par standard_engine.py absentes du "
        f"schéma SQL embarqué : {missing}"
    )
