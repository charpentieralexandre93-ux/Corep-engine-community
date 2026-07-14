#!/usr/bin/env python3
"""
Exemple « démarrage rapide » — édition Community.

Démontre les fonctions de calcul PURES (SA / CRM / SA-CCR) SANS PostgreSQL
ni psycopg2. À lancer après installation de base :

    python -m pip install -e .          # psycopg2 non requis pour cet exemple
    python examples/sa_pure_functions.py

Pour exécuter les moteurs complets (run_standard_engine / run_saccr_engine) sur
une base réelle, installer l'extra PostgreSQL : pip install -e ".[postgres]".
"""

from __future__ import annotations

from corep_crr3.saccr_engine import _maturity_factor
from corep_crr3.standard_engine import (
    apply_ufcp_partial_substitution,
    compute_recognized_fcp_value,
    maturity_mismatch_factor,
)


def main() -> None:
    print("=== CRM — valeur reconnue d'une sûreté (FCP, Art.223/224) ===")
    print("  100 de collatéral, haircut 15 %        ->", compute_recognized_fcp_value(100.0, 0.15))
    print(
        "  + asymétrie de change (Hfx 8 %, Art.224) ->",
        compute_recognized_fcp_value(100.0, 0.15, fx_mismatch=True, fx_haircut=0.08),
    )

    print("\n=== CRM — substitution UFCP partielle (garantie 30 sur EAD 100) ===")
    covered, rwa, residual = apply_ufcp_partial_substitution(
        ead_at_obligor_rw=100.0, base_rw=1.0, rw_provider=0.20, protection_value=30.0
    )
    print(f"  couvert={covered}  RWA_couvert={rwa}  résiduel_obligor={residual}")

    print("\n=== CRM — asymétrie de maturité (Art.239(3)) ===")
    print("  exposition 60 mois, protection 36 mois ->", round(maturity_mismatch_factor(60, 36), 4))

    print("\n=== SA-CCR — facteur de maturité ===")
    print("  non margé, 1 an   ->", round(_maturity_factor(1.0, margined=False), 4))
    print("  margé, MPOR 10 j  ->", round(_maturity_factor(1.0, margined=True, mpor_days=10.0), 4))


if __name__ == "__main__":
    main()
