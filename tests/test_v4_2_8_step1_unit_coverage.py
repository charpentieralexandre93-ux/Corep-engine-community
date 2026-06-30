"""Étape 1 v4.2.8 — couverture unitaire des helpers purs SA / SA-CCR.

Ces tests sont volontairement sans PostgreSQL : ils verrouillent les fonctions
pures et les branches critiques qui alimentent les moteurs publics SA/SA-CCR.
"""

from __future__ import annotations

import math

import pytest

from corep_crr3.decision_engine import (
    _as_float,
    _load_rules_with_conditions,
    clear_rules_cache,
    evaluate_rule_set,
)
from corep_crr3.decision_engine import (
    _match as decision_match,
)
from corep_crr3.saccr_engine import (
    _addon_commodity,
    _addon_credit,
    _addon_equity,
    _addon_fx,
    _addon_ird,
    _adjusted_notional,
    _aggregate_addon_with_correlation,
    _calc_multiplier,
    _compute_delta,
    _compute_margin_state,
    _compute_pfe_full,
    _ird_bucket,
    _maturity_factor,
    _supervisory_duration,
)
from corep_crr3.standard_engine import (
    _maturity_bucket,
    _to_flag,
    apply_ufcp_partial_substitution,
    compute_recognized_fcp_value,
    compute_recognized_ufcp_value,
    lookup_fcp_haircut_rate_from_rules,
    maturity_mismatch_factor,
    preload_crm_fx_haircut,
)
from corep_crr3.supporting_factors import (
    _is_sme_factor,
    apply_supporting_factors,
    sme_blended_factor,
)
from corep_crr3.supporting_factors import (
    _match as supporting_match,
)


class FakeDb:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.queries = []
        self.executed = []

    def query(self, sql, params=()):
        self.queries.append((sql, params))
        return self.rows

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def executemany(self, sql, rows):
        self.executed.append((sql, tuple(rows)))


# ── decision_engine.py --------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12.5", 12.5),
        (10, 10.0),
        (None, None),
        ("not-a-number", None),
    ],
)
def test_decision_as_float(value, expected):
    assert _as_float(value) == expected


@pytest.mark.parametrize(
    ("value", "operator", "expected", "result"),
    [
        ("SA", "=", "SA", True),
        ("SA", "!=", "IRB", True),
        ("RETAIL", "IN", "SOVEREIGN|RETAIL|CORPORATE", True),
        ("IRB", "IN", "SA|SA_CCR", False),
        (100, ">", "50", True),
        (100, ">=", "100", True),
        (50, "<", "100", True),
        (50, "<=", "50", True),
        ("bad", ">", "50", False),
        ("SA", "UNKNOWN", "SA", False),
    ],
)
def test_decision_match_operators(value, operator, expected, result):
    assert decision_match(value, operator, expected) is result


def test_load_rules_with_conditions_groups_rows():
    db = FakeDb(
        [
            {
                "rule_id": 1,
                "rule_set_id": 10,
                "priority": 1,
                "result_key": "RW",
                "result_value": "0.75",
                "rule_set_name": "risk_weight",
                "condition_field": "asset_class_id",
                "condition_operator": "=",
                "condition_value": "RETAIL",
            },
            {
                "rule_id": 1,
                "rule_set_id": 10,
                "priority": 1,
                "result_key": "RW",
                "result_value": "0.75",
                "rule_set_name": "risk_weight",
                "condition_field": "country",
                "condition_operator": "=",
                "condition_value": "FR",
            },
            {
                "rule_id": 2,
                "rule_set_id": 10,
                "priority": 99,
                "result_key": "RW",
                "result_value": "1.00",
                "rule_set_name": "risk_weight",
                "condition_field": None,
                "condition_operator": None,
                "condition_value": None,
            },
        ]
    )

    rules = _load_rules_with_conditions(db, "CRR3_V9", "RISK_WEIGHT")

    assert list(rules) == [1, 2]
    assert len(rules[1]["conditions"]) == 2
    assert rules[2]["conditions"] == []


def test_evaluate_rule_set_uses_cache_and_trace_buffer():
    clear_rules_cache()
    db = FakeDb(
        [
            {
                "rule_id": 1,
                "rule_set_id": 10,
                "priority": 1,
                "result_key": "RW",
                "result_value": "0.75",
                "rule_set_name": "risk_weight",
                "condition_field": "asset_class_id",
                "condition_operator": "=",
                "condition_value": "RETAIL",
            }
        ]
    )
    trace = []

    first = evaluate_rule_set(
        db,
        "batch-1",
        "CRR3_V9",
        "RISK_WEIGHT",
        {"_context_key": "EXP1", "asset_class_id": "RETAIL"},
        trace_buffer=trace,
    )
    second = evaluate_rule_set(
        db,
        "batch-1",
        "CRR3_V9",
        "RISK_WEIGHT",
        {"_context_key": "EXP2", "asset_class_id": "RETAIL"},
        trace_buffer=trace,
    )

    assert first == second
    assert first["result_value"] == "0.75"
    assert len(db.queries) == 1
    assert [row[2] for row in trace] == ["EXP1", "EXP2"]


# ── standard_engine.py --------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "TRUE"),
        (False, "FALSE"),
        ("yes", "TRUE"),
        ("OUI", "TRUE"),
        ("0", "FALSE"),
        (None, "FALSE"),
    ],
)
def test_to_flag(value, expected):
    assert _to_flag(value) == expected


@pytest.mark.parametrize(
    ("months", "expected"),
    [(None, None), ("bad", None), (12, "≤1Y"), (60, "1Y-5Y"), (61, ">5Y")],
)
def test_maturity_bucket(months, expected):
    assert _maturity_bucket(months) == expected


@pytest.mark.parametrize(
    ("ead", "base_rw", "provider_rw", "protection", "expected"),
    [
        (100.0, 1.0, None, 30.0, (0.0, 0.0, 100.0)),
        (100.0, 1.0, 1.20, 30.0, (0.0, 0.0, 100.0)),
        (0.0, 1.0, 0.20, 30.0, (0.0, 0.0, 0.0)),
        (100.0, 1.0, 0.20, -30.0, (0.0, 0.0, 100.0)),
        (100.0, 1.0, 0.20, 30.0, (30.0, 6.0, 70.0)),
        (100.0, 1.0, 0.20, 150.0, (100.0, 20.0, 0.0)),
    ],
)
def test_partial_substitution_branches(ead, base_rw, provider_rw, protection, expected):
    assert apply_ufcp_partial_substitution(ead, base_rw, provider_rw, protection) == expected


@pytest.mark.parametrize(
    ("exposure_months", "protection_months", "expected"),
    [
        (None, 12, 1.0),
        (12, None, 1.0),
        (-1, 12, 1.0),
        (60, 60, 1.0),
        (60, 3, 0.0),
        (60, 36, (3.0 - 0.25) / (5.0 - 0.25)),
    ],
)
def test_maturity_mismatch_factor_boundaries(exposure_months, protection_months, expected):
    assert math.isclose(maturity_mismatch_factor(exposure_months, protection_months), expected)


def test_recognized_values_include_fx_and_maturity_mismatch():
    fcp = compute_recognized_fcp_value(
        100.0,
        0.10,
        fx_mismatch=True,
        fx_haircut=0.08,
        exposure_maturity_months=60,
        protection_maturity_months=36,
    )
    ufcp = compute_recognized_ufcp_value(
        100.0,
        fx_mismatch=True,
        fx_haircut=0.08,
        exposure_maturity_months=60,
        protection_maturity_months=36,
    )
    mm = (3.0 - 0.25) / (5.0 - 0.25)
    assert math.isclose(fcp, 82.0 * mm)
    assert math.isclose(ufcp, 92.0 * mm)


def test_haircut_lookup_prefers_exact_grade_and_maturity():
    rules = [
        {
            "collateral_type": "BOND",
            "collateral_grade": None,
            "residual_maturity": None,
            "haircut_rate": 0.08,
        },
        {
            "collateral_type": "BOND",
            "collateral_grade": "AA",
            "residual_maturity": None,
            "haircut_rate": 0.04,
        },
        {
            "collateral_type": "BOND",
            "collateral_grade": "AA",
            "residual_maturity": "1Y-5Y",
            "haircut_rate": 0.02,
        },
    ]
    assert (
        lookup_fcp_haircut_rate_from_rules(
            rules,
            {"collateral_type": "bond", "collateral_grade": "aa", "maturity_months": 48},
        )
        == 0.02
    )


def test_preload_crm_fx_haircut_fallback_and_valid_value():
    assert preload_crm_fx_haircut(FakeDb([]), "CRR3_V9") == 0.08
    assert preload_crm_fx_haircut(FakeDb([{"parameter_value": "0.12"}]), "CRR3_V9") == 0.12
    assert preload_crm_fx_haircut(FakeDb([{"parameter_value": "bad"}]), "CRR3_V9") == 0.08


# ── supporting_factors.py -----------------------------------------------------


@pytest.mark.parametrize(
    ("factor_code", "expected"),
    [("SME_SF", True), ("PME_SUPPORT", True), ("INFRA_SF", False), (None, False)],
)
def test_is_sme_factor(factor_code, expected):
    assert _is_sme_factor(factor_code) is expected


def test_sme_blended_factor_two_tiers():
    assert sme_blended_factor(0.7619, 0.0) == 0.7619
    assert sme_blended_factor(0.7619, 1_000_000) == 0.7619
    blended = sme_blended_factor(0.7619, 5_000_000)
    assert 0.7619 < blended < 0.85


@pytest.mark.parametrize(
    ("operator", "left", "right", "expected"),
    [
        ("=", True, "TRUE", True),
        ("=", True, "Y", True),
        ("=", False, "FALSE", True),
        ("!=", True, "FALSE", True),
        ("=", "RETAIL", "RETAIL", True),
        ("!=", "RETAIL", "CORPORATE", True),
        ("?", "RETAIL", "RETAIL", False),
    ],
)
def test_supporting_match_boolean_and_text(operator, left, right, expected):
    assert supporting_match(operator, left, right) is expected


def test_apply_supporting_factors_with_preloaded_rules_and_trace_buffer():
    rules = [
        {
            "factor_code": "SME_SF",
            "eligibility_field": "supporting_sme_flag",
            "eligibility_operator": "=",
            "eligibility_value": "TRUE",
            "multiplier": 0.7619,
            "factor_rule_id": 1,
        },
        {
            "factor_code": "INFRA_SF",
            "eligibility_field": "supporting_infra_flag",
            "eligibility_operator": "=",
            "eligibility_value": "TRUE",
            "multiplier": 0.75,
            "factor_rule_id": 2,
        },
    ]
    trace = []
    result = apply_supporting_factors(
        FakeDb(),
        "batch-1",
        "CRR3_V9",
        {"exposure_id": "EXP1", "supporting_sme_flag": True, "supporting_infra_flag": True},
        100.0,
        preloaded_rules=rules,
        trace_buffer=trace,
        sme_total_exposure=1_000_000,
    )

    assert math.isclose(result["multiplier_final"], 0.7619 * 0.75)
    assert math.isclose(result["rwa_final"], 100.0 * 0.7619 * 0.75)
    assert result["factor_codes"] == "SME_SF|INFRA_SF"
    assert len(trace) == 2


# ── saccr_engine.py -----------------------------------------------------------


@pytest.mark.parametrize(
    ("maturity", "expected"),
    [(0.5, 1), (1.0, 1), (1.01, 2), (5.0, 2), (5.01, 3)],
)
def test_ird_bucket(maturity, expected):
    assert _ird_bucket(maturity) == expected


def test_supervisory_duration_is_positive_and_orders_dates():
    normal = _supervisory_duration(0.0, 5.0)
    corrected = _supervisory_duration(5.0, 2.0)
    assert normal > corrected > 0.0


@pytest.mark.parametrize(
    ("option_type", "bought", "lower", "upper"),
    [
        ("", True, 1.0, 1.0),
        ("", False, -1.0, -1.0),
        ("CALL", True, 0.0, 1.0),
        ("CALL", False, -1.0, 0.0),
        ("PUT", True, -1.0, 0.0),
        ("PUT", False, 0.0, 1.0),
    ],
)
def test_compute_delta_linear_and_options(option_type, bought, lower, upper):
    delta = _compute_delta(option_type, 100.0, 100.0, 0.20, 1.0, bought=bought)
    if lower == upper:
        assert delta == lower
    else:
        assert lower < delta < upper


def test_compute_delta_invalid_option_parameters_fall_back_to_sign():
    assert _compute_delta("CALL", 0.0, 100.0, 0.20, 1.0, bought=True) == 1.0
    assert _compute_delta("PUT", 100.0, 0.0, 0.20, 1.0, bought=False) == -1.0


def test_maturity_factor_unmargined_and_margined_floors():
    assert math.isclose(_maturity_factor(1.0, margined=False), 1.0)
    assert _maturity_factor(0.01, margined=False) > 0.0
    assert math.isclose(
        _maturity_factor(1.0, margined=True, mpor_days=1.0),
        _maturity_factor(1.0, margined=True, mpor_days=10.0),
    )


def test_adjusted_notional_sets_class_specific_buckets():
    ird = _adjusted_notional(
        {
            "trade_id": "IRD1",
            "asset_class": "IRD",
            "notional": 1000.0,
            "maturity_years": 5.0,
            "start_date_years": 0.0,
            "end_date_years": 5.0,
            "delta": 1.0,
            "payment_currency": "eur",
        }
    )
    fx = _adjusted_notional(
        {
            "trade_id": "FX1",
            "asset_class": "FX",
            "notional": 1000.0,
            "maturity_years": 1.0,
            "delta": -1.0,
            "reference_entity_id": "EUR/USD",
        }
    )
    equity = _adjusted_notional(
        {
            "trade_id": "EQ1",
            "asset_class": "EQUITY",
            "notional": 1000.0,
            "maturity_years": 1.0,
            "option_type": "CALL",
            "underlying_price": 100.0,
            "strike": 100.0,
            "implied_vol": 0.20,
            "equity_id": "SX5E",
            "equity_type": "INDEX",
        }
    )

    assert ird["bucket"] == "EUR"
    assert ird["adj_notional"] > 1000.0
    assert fx["bucket"] == "EUR/USD"
    assert fx["delta"] == -1.0
    assert equity["sub_type"] == "INDEX"
    assert 0.0 < equity["delta"] < 1.0


def test_addon_functions_single_bucket_exact_cases():
    base_trade = {
        "trade_id": "T1",
        "delta": 1.0,
        "adj_notional": 100_000.0,
        "maturity": 0.5,
        "bucket": "EUR",
        "sub_type": "",
    }
    assert math.isclose(_addon_ird([{**base_trade, "asset_class": "IRD"}]), 500.0)
    assert math.isclose(_addon_fx([{**base_trade, "asset_class": "FX", "bucket": "EUR/USD"}]), 4000.0)
    assert math.isclose(
        _addon_credit([{**base_trade, "asset_class": "CREDIT", "bucket": "REF1", "sub_type": "HY"}]),
        1000.0,
    )
    assert math.isclose(
        _addon_equity([{**base_trade, "asset_class": "EQUITY", "bucket": "AAPL", "sub_type": "SINGLE"}]),
        32_000.0,
    )
    assert math.isclose(
        _addon_equity([{**base_trade, "asset_class": "EQUITY", "bucket": "SX5E", "sub_type": "INDEX"}]),
        20_000.0,
    )
    assert math.isclose(
        _addon_commodity([{**base_trade, "asset_class": "COMMODITY", "bucket": "ENERGY", "sub_type": "ENERGY"}]),
        18_000.0,
    )


def test_aggregate_addon_with_correlation_formula():
    assert math.isclose(_aggregate_addon_with_correlation([], 0.5), 0.0)
    assert math.isclose(_aggregate_addon_with_correlation([10.0, 20.0], 0.5), math.sqrt(600.0))


def test_calc_multiplier_bounds():
    assert _calc_multiplier(0.0, 0.0) == 1.0
    assert _calc_multiplier(100.0, 50.0) == 1.0
    reduced = _calc_multiplier(-100.0, 50.0)
    assert 0.05 <= reduced < 1.0


def test_compute_pfe_full_fallback_and_native_paths():
    fallback = _compute_pfe_full(
        [
            {"trade_id": "L1", "addon": 10.0},
            {"trade_id": "L2", "addon": 20.0},
        ],
        mtm_net=100.0,
    )
    assert fallback["pfe_full"] == 30.0
    assert fallback["multiplier"] == 1.0
    assert fallback["pfe_final"] == 30.0

    native = _compute_pfe_full(
        [
            {
                "trade_id": "IRD1",
                "asset_class": "IRD",
                "notional": 100_000.0,
                "maturity_years": 1.0,
                "start_date_years": 0.0,
                "end_date_years": 1.0,
                "delta": 1.0,
                "payment_currency": "EUR",
            },
            {
                "trade_id": "FX1",
                "asset_class": "FX",
                "notional": 50_000.0,
                "maturity_years": 1.0,
                "delta": 1.0,
                "reference_entity_id": "EUR/USD",
            },
        ],
        mtm_net=-10.0,
    )
    assert native["addon_ird"] > 0.0
    assert native["addon_fx"] > 0.0
    assert native["pfe_full"] > native["addon_ird"]
    assert 0.05 <= native["multiplier"] <= 1.0


def test_compute_margin_state_legacy_and_csa_paths():
    legacy = _compute_margin_state([{"mtm": 100.0, "collateral": 30.0}])
    assert legacy["csa_present"] is False
    assert legacy["rc"] == 70.0
    assert legacy["collateral_for_multiplier"] == 30.0

    margined = _compute_margin_state(
        [
            {
                "mtm": 100.0,
                "collateral": 0.0,
                "vm_received": 20.0,
                "threshold_amount": 10.0,
                "mta": 5.0,
                "nica": 8.0,
                "csa_id": "CSA-1",
                "mpor_days": 20,
            }
        ]
    )
    assert margined["csa_present"] is True
    assert margined["rc"] == 72.0
    assert margined["mpor_days"] == 20
