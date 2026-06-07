"""
Tests de fumée — édition Community (SA + SA-CCR).

Tous les tests sont PURS : ils n'ouvrent aucune connexion PostgreSQL et ne
nécessitent donc PAS psycopg2 (cf. import paresseux dans db.py). Ils couvrent :
  - la frontière du registre public (SA / SA-CCR uniquement) ;
  - les fonctions de calcul pures CRM/SA et le facteur de maturité SA-CCR ;
  - le déterminisme (reproductibilité bit-à-bit d'un calcul pur).
"""

from __future__ import annotations

import math

import corep_crr3
from corep_crr3.public_registry import PUBLIC_ENGINES, get_engine
from corep_crr3.saccr_engine import _maturity_factor
from corep_crr3.standard_engine import (
    apply_ufcp_partial_substitution,
    compute_recognized_fcp_value,
    compute_recognized_ufcp_value,
    lookup_fcp_haircut_rate_from_rules,
    maturity_mismatch_factor,
)


# --- Version & registre public -------------------------------------------------
def test_version():
    assert corep_crr3.__version__ == "4.2.8"


def test_registry_is_limited_to_sa_and_saccr():
    assert set(PUBLIC_ENGINES) == {"SA", "SA_CCR"}
    assert get_engine("SA") is PUBLIC_ENGINES["SA"]
    assert get_engine("SA-CCR") is PUBLIC_ENGINES["SA_CCR"]


def test_registry_rejects_enterprise_engine():
    for code in ("IRB", "FRTB", "CVA"):
        try:
            get_engine(code)
        except ValueError as exc:
            assert "indisponible" in str(exc)
        else:
            raise AssertionError(f"{code} ne doit pas etre expose par Community")


def test_importable_without_psycopg2():
    """Le paquet et les moteurs s'importent meme sans psycopg2 installe."""
    from corep_crr3 import db
    assert hasattr(db, "Database")


# --- CRM / SA : substitution UFCP partielle -----------------------------------
def test_partial_ufcp_substitution():
    covered, rwa, residual = apply_ufcp_partial_substitution(
        ead_at_obligor_rw=100.0, base_rw=1.0, rw_provider=0.20, protection_value=30.0
    )
    assert covered == 30.0
    assert rwa == 6.0
    assert residual == 70.0


# --- CRM / SA : valeur reconnue d'une FCP (Art.223/224/239) --------------------
def test_recognized_fcp_haircut_only():
    assert compute_recognized_fcp_value(100.0, 0.15) == 85.0


def test_recognized_fcp_with_fx_mismatch():
    assert math.isclose(
        compute_recognized_fcp_value(100.0, 0.15, fx_mismatch=True, fx_haircut=0.08),
        77.0,
    )


def test_recognized_fcp_no_haircut_is_full_value():
    assert compute_recognized_fcp_value(100.0, None) == 100.0


def test_recognized_fcp_never_negative():
    assert compute_recognized_fcp_value(100.0, 0.9, fx_mismatch=True, fx_haircut=0.5) == 0.0


def test_recognized_ufcp_value_is_value_without_mismatch():
    assert compute_recognized_ufcp_value(50.0) == 50.0


# --- Asymetrie de maturite (Art.239(3)) ---------------------------------------
def test_maturity_mismatch_no_reduction_when_aligned():
    assert maturity_mismatch_factor(60, 60) == 1.0


def test_maturity_mismatch_factor():
    expected = (3.0 - 0.25) / (5.0 - 0.25)
    assert math.isclose(maturity_mismatch_factor(60, 36), expected)


def test_maturity_mismatch_short_protection_not_recognized():
    assert maturity_mismatch_factor(60, 3) == 0.0


def test_maturity_mismatch_none_is_neutral():
    assert maturity_mismatch_factor(None, 36) == 1.0


# --- Recherche de haircut FCP sur regles prechargees (pur) --------------------
def test_lookup_fcp_haircut_exact_match():
    rules = [
        {"collateral_type": "CASH", "collateral_grade": None, "residual_maturity": None, "haircut_rate": 0.0},
        {"collateral_type": "BOND", "collateral_grade": "AA", "residual_maturity": None, "haircut_rate": 0.02},
    ]
    assert lookup_fcp_haircut_rate_from_rules(
        rules, {"collateral_type": "bond", "collateral_grade": "aa"}
    ) == 0.02


def test_lookup_fcp_haircut_unknown_type_is_zero():
    rules = [{"collateral_type": "CASH", "collateral_grade": None, "residual_maturity": None, "haircut_rate": 0.0}]
    assert lookup_fcp_haircut_rate_from_rules(rules, {"collateral_type": "GOLD"}) == 0.0


def test_lookup_fcp_haircut_no_type_is_zero():
    assert lookup_fcp_haircut_rate_from_rules([], {}) == 0.0


# --- SA-CCR : facteur de maturite ---------------------------------------------
def test_saccr_maturity_factor_positive():
    assert _maturity_factor(1.0, margined=False) > 0.0


def test_saccr_margined_factor_below_unmargined():
    assert _maturity_factor(1.0, margined=True, mpor_days=10.0) < _maturity_factor(1.0, margined=False)


# --- Determinisme (reproductibilite d'un calcul pur) --------------------------
def test_pure_calculations_are_deterministic():
    args = dict(protection_value=137.5, haircut_rate=0.123,
                fx_mismatch=True, fx_haircut=0.08,
                exposure_maturity_months=48, protection_maturity_months=30)
    first = compute_recognized_fcp_value(**args)
    second = compute_recognized_fcp_value(**args)
    assert first == second
    assert repr(first) == repr(second)
