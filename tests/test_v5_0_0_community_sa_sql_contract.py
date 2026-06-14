"""Non-régression du contrat SQL/Python du moteur SA Community v5.0.0."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = (
    PROJECT_ROOT
    / "sql"
    / "01_schema"
    / "01_schema_common_community.sql"
)


def test_sa_v5_result_columns_are_declared_in_community_schema():
    sql = SCHEMA_PATH.read_text(encoding="utf-8").lower()

    expected_columns = (
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

    missing = [
        column
        for column in expected_columns
        if (
            "alter table core.core_standard_results "
            f"add column if not exists {column}"
        ) not in " ".join(sql.split())
    ]

    assert not missing, (
        "Colonnes attendues par standard_engine.py absentes du schéma "
        f"Community : {missing}"
    )


def test_sa_v5_staging_columns_are_declared_in_community_schema():
    sql = " ".join(SCHEMA_PATH.read_text(encoding="utf-8").lower().split())

    expected_columns = (
        "annex_i_bucket",
        "unconditionally_cancellable_flag",
        "contractual_arrangement_not_accepted_flag",
        "client_acceptance_required_flag",
        "borrower_income_currency",
        "exposure_currency",
        "hedged_currency_mismatch_flag",
        "natural_person_flag",
        "institution_scra_grade",
        "short_term_exposure_flag",
        "original_maturity_months",
        "due_diligence_override",
        "property_valuation_amount",
        "property_value_cap_amount",
        "ipre_flag",
        "adc_flag",
        "transactor_flag",
        "loan_splitting_flag",
    )

    missing = [
        column
        for column in expected_columns
        if (
            "alter table stg.stg_exposures "
            f"add column if not exists {column}"
        ) not in sql
    ]

    assert not missing, (
        "Colonnes SA v5.0.0 absentes du staging Community : "
        f"{missing}"
    )
