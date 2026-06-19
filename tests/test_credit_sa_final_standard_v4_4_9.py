"""Tests v5.0.0 — Credit SA Final Standard.

Ces tests couvrent les corrections P0/P1 du moteur SA partagé Community / Enterprise :
CCF CRR3 bucket 5 à 10 %, equity Art.133, currency mismatch Art.123a et traces.
"""

import math

from corep_crr3.standard_engine import (
    apply_currency_mismatch_multiplier,
    ccf_from_annex_i_bucket,
    infer_ccf_bucket,
    infer_rw_bucket,
)


def test_annex_i_bucket_ccf_grid_final_standard():
    assert ccf_from_annex_i_bucket("BUCKET_1") == 1.0
    assert ccf_from_annex_i_bucket("BUCKET_2") == 0.5
    assert ccf_from_annex_i_bucket("BUCKET_3") == 0.4
    assert ccf_from_annex_i_bucket("BUCKET_4") == 0.2
    assert ccf_from_annex_i_bucket("BUCKET_5") == 0.1
    assert ccf_from_annex_i_bucket("UNKNOWN") is None


def test_revocable_commitment_infers_bucket_5_not_zero():
    row = {
        "product_type_id": "REVOCABLE_COMMITMENT",
        "unconditionally_cancellable_flag": True,
    }
    assert infer_ccf_bucket(row) == "BUCKET_5"
    assert ccf_from_annex_i_bucket(infer_ccf_bucket(row)) == 0.1


def test_client_acceptance_not_yet_accepted_can_keep_zero_ccf():
    row = {
        "product_type_id": "REVOCABLE_COMMITMENT",
        "contractual_arrangement_not_accepted_flag": True,
        "client_acceptance_required_flag": True,
    }
    assert infer_ccf_bucket(row) == "NOT_ACCEPTED_ZERO_CCF"
    assert ccf_from_annex_i_bucket(infer_ccf_bucket(row)) == 0.0


def test_currency_mismatch_multiplier_applies_and_caps_at_150_percent():
    assert math.isclose(apply_currency_mismatch_multiplier(0.75, True), 1.125)
    assert math.isclose(apply_currency_mismatch_multiplier(1.20, True), 1.50)
    assert math.isclose(apply_currency_mismatch_multiplier(0.75, False), 0.75)


def test_infer_rw_bucket_equity_and_specialised_lending():
    assert infer_rw_bucket({"asset_class_id": "EQUITY", "exposure_subtype": "GENERIC"}, 2.5) == "EQUITY_GENERIC_250"
    assert (
        infer_rw_bucket({"asset_class_id": "EQUITY", "exposure_subtype": "SPECULATIVE_UNLISTED"}, 4.0)
        == "EQUITY_SPECULATIVE_UNLISTED_400"
    )
    assert infer_rw_bucket({"exposure_subtype": "ADC"}, 1.5) == "ADC"
    assert infer_rw_bucket({"exposure_subtype": "PROJECT_FINANCE"}, 1.3) == "SPECIALISED_LENDING_PROJECT_FINANCE"
