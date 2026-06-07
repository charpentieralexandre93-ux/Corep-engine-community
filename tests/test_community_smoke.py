from __future__ import annotations

import math

import corep_crr3
from corep_crr3.public_registry import PUBLIC_ENGINES, get_engine
from corep_crr3.saccr_engine import _maturity_factor
from corep_crr3.standard_engine import (
    apply_ufcp_partial_substitution,
    maturity_mismatch_factor,
)


def test_version():
    assert corep_crr3.__version__ == "4.2.6"


def test_registry_is_limited_to_sa_and_saccr():
    assert set(PUBLIC_ENGINES) == {"SA", "SA_CCR"}
    assert get_engine("SA") is PUBLIC_ENGINES["SA"]
    assert get_engine("SA-CCR") is PUBLIC_ENGINES["SA_CCR"]


def test_registry_rejects_enterprise_engine():
    try:
        get_engine("IRB")
    except ValueError as exc:
        assert "indisponible" in str(exc)
    else:
        raise AssertionError("IRB ne doit pas être exposé par Community")


def test_partial_ufcp_substitution():
    covered, rwa, residual = apply_ufcp_partial_substitution(
        ead_at_obligor_rw=100.0,
        base_rw=1.0,
        rw_provider=0.20,
        protection_value=30.0,
    )
    assert covered == 30.0
    assert rwa == 6.0
    assert residual == 70.0


def test_maturity_mismatch_factor():
    expected = (3.0 - 0.25) / (5.0 - 0.25)
    assert math.isclose(maturity_mismatch_factor(60, 36), expected)


def test_saccr_maturity_factor_is_positive():
    assert _maturity_factor(1.0, margined=False) > 0.0
