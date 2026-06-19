"""
================================================================================
MODULE  : saccr_engine.py
PROJET  : COREP Engine CRR3
VERSION : 6.3.0
================================================================================

CORRECTIONS RÉGLEMENTAIRES v3.4.0 (audit points ② et ③)
--------------------------------------------------------
② FACTEUR DE MATURITÉ MF (Art.279c) — AJOUTÉ.
   Le MF était totalement absent (implicitement = 1). Le notionnel effectif
   Art.279 est D_i = δ_i × d_i × MF_i, avec :
     • non margé : MF = sqrt(min(M ; 1 an)/1 an)   (plancher 10 jours ouvrés) ;
     • margé     : MF = 1,5 × sqrt(MPOR/250).
   Impact : surévaluation du PFE corrigée pour les trades < 1 an, et surtout
   pour les netting sets margés (MF margé ≈ 0,30 au lieu de 1).

③ SUPERVISORY DURATION DES DÉRIVÉS DE CRÉDIT (Art.280b → 279b/279c) — AJOUTÉE.
   Avant, l'add-on crédit utilisait adj_notional = notional (sans SD), ce qui
   sous-estimait l'add-on (ex. CDS 5 ans → SD ≈ 3,6). Le crédit utilise
   désormais d = notional × SD, comme les IRD.

   Rétrocompatibilité : les trades IRD non margés de maturité ≥ 1 an conservent
   exactement leur add-on (MF = 1), donc les tests v2.7 / saccr_native passent
   à l'identique. Seuls les dérivés de crédit et les netting sets margés voient
   leur EAD recalculée conformément.

PATCH v8 — ADD-ON EQUITY ART.280d CONFORME (v2.6)
---------------------------------------------------
Bug réglementaire corrigé : avant v2.6, ``_addon_equity`` mélangeait single
et index dans une seule formule corrélation avec un ρ moyen pondéré. Cette
simplification n'est pas conforme Art.280d CRR3.

v2.6 sépare strictement les deux hedging set types :
    AddOn_SINGLE = formule Art.280d avec ρ_single = 0,50, SF = 32 %
    AddOn_INDEX  = formule Art.280d avec ρ_index  = 0,80, SF = 20 %
    AddOn_Equity = AddOn_SINGLE + AddOn_INDEX

PATCH v7 — CALCUL PFE NATIF COMPLET
--------------------------------------
La v5 utilisait directement la colonne `addon` pré-calculée par le système
source. La v7 implémente le calcul natif Art.277-280 CRR3 pour les 5 classes
de risque SA-CCR.

NOUVELLES COLONNES stg_saccr_trades (rétrocompatibilité)
---------------------------------------------------------
Si `asset_class` est présent dans la ligne → calcul natif v7.
Si absent → fallback sur `addon` pré-calculé (comportement v5).

FORMULE SA-CCR (Art.274 CRR3)
-------------------------------
    EAD = α × (RC + PFE)

    α   = 1,40  (Art.274(5))
    RC  = max(MtM_net − Collateral, 0)            Art.275
    PFE = multiplier × Σ_{class} AddOn_class      Art.278
    AddOn_class : Σ (δ_i × notional_i × [SD_i] × MF_i) agrégé Art.280a-e

MULTIPLIER (Art.278(1))
------------------------
    multiplier = min(1, floor + (1−floor) × exp( V / (2×(1−floor)×PFE_full) ))
    floor = 0,05

    V = MtM_net du netting set (peut être négatif)
    PFE_full = Σ AddOn_class AVANT multiplier

ADD-ONS PAR CLASSE (Art.277-280)
---------------------------------

1. IRD (Art.279c, 280a)
   Supervisory Duration : SD_i = (exp(-0.05 × S_i) − exp(-0.05 × E_i)) / 0.05
   D_i = δ_i × notional_i × SD_i  (notionnel ajusté par duration)
   Buckets maturité : [0,1y] [1y,5y] [>5y]
   Formule inter-bucket (Art.280a(1)(b)) :
       ε_12 = 1.4, ε_13 = 0.6, ε_23 = 1.4
       AddOn_ccy = SF_IRD × √(D1²+D2²+D3²+2×ε12×D1×D2+2×ε23×D2×D3+2×ε13×D1×D3)
   AddOn_IRD = Σ_currency AddOn_ccy
   SF_IRD = 0.005 (0,5%)

2. FX (Art.280c)
   D_i = δ_i × notional_i
   AddOn_pair = SF_FX × |Σ_pair D_i|
   AddOn_FX = Σ_pair AddOn_pair
   SF_FX = 0.04 (4%)

3. CREDIT (Art.280b)
   Corrélation ρ = 0.50
   EffNot_c = SF_c × Σ_{trades on c} D_i
   AddOn_Credit = √( (Σ EffNot_c)² × ρ² + (1−ρ²) × Σ EffNot_c² )
   SF_IG = 0.005, SF_HY = 0.010

4. EQUITY (Art.280d)
   Corrélation ρ_single = 0.50, ρ_index = 0.80
   EffNot_s = SF_s × Σ D_i
   AddOn_Equity = √( (Σ EffNot_s)² × ρ² + (1−ρ²) × Σ EffNot_s² )
   SF_SINGLE = 0.32, SF_INDEX = 0.20

5. COMMODITY (Art.280e)
   Corrélation ρ = 0.40
   EffNot_t = SF_t × |Σ_type D_i|
   AddOn_Commodity = √( (Σ EffNot_t)² × ρ² + (1−ρ²) × Σ EffNot_t² )
   SF = 0.18 (énergie/métaux), 0.18 (agri/autre)

DELTA SUPERVISORY (Art.279b)
------------------------------
- Linéaire (non-option)  : δ = ±1 (acheteur/vendeur)
- Option call             : δ = +N(d1)   (ou −N(d1) si vendeur)
- Option put              : δ = −N(−d1)  (ou +N(−d1) si vendeur)
  d1 = [ln(P/K) + 0.5 × σ² × T] / (σ × √T)

DÉPENDANCES
-----------
    .db.Database
    .decision_engine.evaluate_rule_set, flush_trace_buffer
    .utils.to_float
    .types.SaccrTradeRow, SaccrResult, SaccrAddOnBreakdown
    scipy.stats.norm (pour delta options)
    math, collections.defaultdict

SORTIE
------
    core.core_saccr_results : EAD, RC, PFE, RWA par netting set
================================================================================
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from statistics import NormalDist
from typing import Any, Dict, List, Optional, Tuple

from .db import Database
from .decision_engine import evaluate_rule_set, flush_trace_buffer
from .runtime_rules import get_parameter
from .types import SaccrAddOnBreakdown, SaccrAdjNotional, SaccrTradeRow
from .utils import to_float as _f

logger = logging.getLogger(__name__)
_NORMAL_DIST = NormalDist()

# ─── Constantes réglementaires ───────────────────────────────────────────────
_ALPHA = 1.40  # Art.274(5)
_MF_FLOOR = 0.05  # floor du multiplier Art.278(1)

# Supervisory factors Art.280a-280e
_SF: Dict[str, float] = {
    "IRD": 0.005,
    "FX": 0.040,
    "CREDIT_IG": 0.005,
    "CREDIT_HY": 0.010,
    "EQUITY_SINGLE": 0.320,
    "EQUITY_INDEX": 0.200,
    "COMMODITY_ENERGY": 0.180,
    "COMMODITY_METAL": 0.180,
    "COMMODITY_AGRI": 0.180,
    "COMMODITY_OTHER": 0.180,
}

# Corrélations inter-entités Art.280b-280e
_RHO: Dict[str, float] = {
    "CREDIT": 0.50,
    "EQUITY_SINGLE": 0.50,
    "EQUITY_INDEX": 0.80,
    "COMMODITY": 0.40,
}

# Facteurs de corrélation inter-buckets IRD Art.280a(1)(b) Table 1
# ε[i][j] pour buckets maturité 1=[0,1y], 2=[1y,5y], 3=[>5y]
_IRD_EPSILON: Dict[Tuple[int, int], float] = {
    (1, 2): 1.4,
    (2, 1): 1.4,
    (1, 3): 0.6,
    (3, 1): 0.6,
    (2, 3): 1.4,
    (3, 2): 1.4,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — DELTA SUPERVISORY (Art.279b)
# ─────────────────────────────────────────────────────────────────────────────


def _compute_delta(
    option_type: str,
    underlying_price: float,
    strike: float,
    implied_vol: float,
    maturity: float,
    bought: bool = True,
) -> float:
    """Calcule le delta supervisory Art.279b CRR3.

    Paramètres
    ----------
    option_type     : "CALL" | "PUT" | "" (linéaire)
    underlying_price: prix du sous-jacent (P dans Art.279b)
    strike          : prix d'exercice (K)
    implied_vol     : volatilité implicite (σ)
    maturity        : maturité résiduelle en années (T)
    bought          : True = acheteur (+), False = vendeur (−)

    Retourne
    --------
    float : δ ∈ [−1, 1]
    """
    sign = 1.0 if bought else -1.0

    if not option_type or option_type.upper() not in ("CALL", "PUT"):
        # Instrument linéaire
        return sign

    # Protection contre la division par zéro
    if implied_vol <= 0.0 or maturity <= 0.0 or underlying_price <= 0.0 or strike <= 0.0:
        return sign

    try:
        d1 = (math.log(underlying_price / strike) + 0.5 * implied_vol**2 * maturity) / (
            implied_vol * math.sqrt(maturity)
        )
    except (ValueError, ZeroDivisionError):
        return sign

    if option_type.upper() == "CALL":
        raw_delta = float(_NORMAL_DIST.cdf(d1))
    else:  # PUT
        raw_delta = -float(_NORMAL_DIST.cdf(-d1))

    return sign * raw_delta


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — SUPERVISORY DURATION (Art.279c pour IRD)
# ─────────────────────────────────────────────────────────────────────────────


def _supervisory_duration(start_years: float, end_years: float) -> float:
    """Durée supervisory SA-CCR Art.279c(1)(b) pour les dérivés de taux.

    SD = (exp(−0.05 × S) − exp(−0.05 × E)) / 0.05

    S = date de début (start_date_years depuis aujourd'hui)
    E = date de fin   (end_date_years depuis aujourd'hui)
    """
    s = max(0.0, start_years)
    e = max(s + 0.0001, end_years)  # E > S par construction
    return (math.exp(-0.05 * s) - math.exp(-0.05 * e)) / 0.05


def _ird_bucket(maturity_years: float) -> int:
    """Bucket maturité IRD Art.280a(1)(a) : 1=[0,1y], 2=[1y,5y], 3=[>5y]."""
    if maturity_years <= 1.0:
        return 1
    elif maturity_years <= 5.0:
        return 2
    return 3


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — FACTEUR DE MATURITÉ MF (Art.279c CRR3)  [CORRECTION v3.4.0 — bug ②]
# ─────────────────────────────────────────────────────────────────────────────
# Nombre de jours ouvrés dans une année (base réglementaire SA-CCR).
_BUSINESS_DAYS_YEAR = 250
# Plancher réglementaire du MPOR (jours ouvrés) — Art.285 / SA-CCR.
_MPOR_FLOOR_DAYS = 10


def _maturity_factor(maturity_years: float, margined: bool, mpor_days: float = 10.0) -> float:
    """Facteur de maturité MF d'un trade — Art.279c CRR3.

    AVANT v3.4.0 : le MF était totalement absent (implicitement = 1), ce qui
    surévaluait le PFE pour tout trade < 1 an, et surévaluait massivement
    (≈ 3,3×) les netting sets margés (MF margé ≈ 0,30).

    Formules Art.279c :
      • Netting set NON margé :
            MF = sqrt( min(M ; 1 an) / 1 an )
        (M = maturité résiduelle, plancher 10 jours ouvrés / 250).
      • Netting set MARGÉ :
            MF = 1,5 × sqrt( MPOR / 250 )
        (MPOR exprimé en jours ouvrés, plancher 10 jours).

    Paramètres
    ----------
    maturity_years : float   Maturité résiduelle M_i en années (non margé).
    margined       : bool    True si le netting set fait l'objet d'un accord de marge.
    mpor_days      : float   Marge Period Of Risk en jours ouvrés (margé).

    Retourne
    --------
    float : MF ≥ 0 (= 1 pour un trade non margé de maturité ≥ 1 an).
    """
    if margined:
        mpor = max(_MPOR_FLOOR_DAYS, _f(mpor_days) or _MPOR_FLOOR_DAYS)
        return 1.5 * math.sqrt(mpor / _BUSINESS_DAYS_YEAR)
    # Non margé : plancher de maturité à 10 jours ouvrés, plafond à 1 an.
    floor_years = _MPOR_FLOOR_DAYS / _BUSINESS_DAYS_YEAR
    m = max(floor_years, _f(maturity_years))
    return math.sqrt(min(m, 1.0) / 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — NOTIONNEL AJUSTÉ PAR TRADE (Art.279)
# ─────────────────────────────────────────────────────────────────────────────


def _adjusted_notional(
    trade: SaccrTradeRow,
    margined: bool = False,
    mpor_days: float = 10.0,
) -> SaccrAdjNotional:
    """Calcule le notionnel effectif δ × d × MF d'un trade (Art.279).

    Notionnel effectif Art.279 : D_i = δ_i × d_i × MF_i, où :
      • d_i = notional × supervisory_duration  pour IRD ET CRÉDIT
              (Art.279b/280b — correction v3.4.0, bug ③) ;
      • d_i = notional                          pour FX / equity / commodity ;
      • MF_i = facteur de maturité Art.279c      (correction v3.4.0, bug ②).

    Le MF est intégré dans `adj_notional` (= d × MF) ; le δ reste séparé. Les
    fonctions d'add-on agrègent ensuite `δ × adj_notional`, ce qui reconstitue
    bien δ × d × MF sans double comptage.

    Paramètres (v3.4.0)
    -------------------
    margined  : bool   netting set margé (→ MF margé Art.279c).
    mpor_days : float  MPOR en jours ouvrés (margé).
    """
    asset_class = (trade.get("asset_class") or "").upper()
    notional = _f(trade.get("notional", 0.0))
    maturity = max(_f(trade.get("maturity_years", 1.0)), 0.0)
    bought = _f(trade.get("delta", 1.0)) >= 0  # ±1 linéaire par défaut

    # Facteur de maturité MF (Art.279c) — commun à toutes les classes.
    mf = _maturity_factor(maturity, margined, mpor_days)

    # Delta supervisory
    option_type = str(trade.get("option_type") or "")
    underlying_price = _f(trade.get("underlying_price", 0.0))
    strike = _f(trade.get("strike", 0.0))
    implied_vol = _f(trade.get("implied_vol", 0.0))

    # Si delta explicitement fourni (pré-calculé), l'utiliser directement
    delta_override = trade.get("delta")
    if delta_override is not None and option_type.upper() not in ("CALL", "PUT"):
        delta = _f(delta_override)
    else:
        delta = _compute_delta(option_type, underlying_price, strike, implied_vol, maturity, bought)

    # Notionnel ajusté
    if asset_class == "IRD":
        s_years = _f(trade.get("start_date_years", 0.0))
        e_years = _f(trade.get("end_date_years", maturity))
        sd = _supervisory_duration(s_years, e_years)
        # v3.4.0 — D_i = notional × SD × MF (Art.279b + Art.279c)
        adj_notional = notional * sd * mf
        # PATCH v2.7 — Bucket IRD = devise de paiement (Art.280a CRR3)
        # Avant v2.7, le bucket utilisait `reference_entity_id` (qui est le
        # champ de l'entité de référence pour les dérivés CRÉDIT, pas IRD)
        # ou par défaut "DEFAULT" — résultat : tous les IRD étaient agrégés
        # dans un seul hedging set fictif au lieu d'un par devise.
        # Conséquence : l'agrégation inter-bucket maturité Art.280a(1)(b) n'était
        # appliquée correctement que si tous les trades étaient dans la même
        # devise, sinon elle mélangeait des positions de devises différentes.
        #
        # Art.280a(1) : "the hedging set for interest rate derivatives shall
        # consist of all the derivatives that reference interest rates of the
        # same currency". Le hedging set est donc strictement la devise.
        #
        # Champ explicite : `payment_currency` (ajouté en v2.7 dans stg_saccr_trades).
        # Fallback ordonné pour rétrocompatibilité avec données historiques :
        #   1. payment_currency  (champ canonique v2.7)
        #   2. currency           (champ générique parfois rempli côté client)
        #   3. ird_currency       (autre alias possible)
        #   4. "DEFAULT"          (ancien comportement — log un warning)
        ccy = trade.get("payment_currency") or trade.get("currency") or trade.get("ird_currency")
        if not ccy:
            logger.warning(
                "SA-CCR IRD trade %s sans payment_currency — bucket = 'DEFAULT' "
                "(agrégation inter-devise non conforme Art.280a). "
                "Renseigner stg_saccr_trades.payment_currency.",
                trade.get("trade_id", "?"),
            )
            ccy = "DEFAULT"
        bucket = str(ccy).upper().strip()
        sub_type = ""
    elif asset_class == "FX":
        # v4.4.5 — D_i = notional × MF, bucket FX = paire de devises explicite.
        adj_notional = notional * mf
        pair = trade.get("currency_pair")
        if not pair:
            pay = str(trade.get("pay_currency") or trade.get("payment_currency") or "").upper().strip()
            rec = str(trade.get("receive_currency") or "").upper().strip()
            pair = f"{pay}{rec}" if pay and rec else None
        bucket = str(pair or trade.get("equity_id") or trade.get("reference_entity_id") or "DEFAULT").upper().strip()
        sub_type = ""
    elif asset_class == "CREDIT":
        # v3.4.0 (bug ③) — les dérivés de CRÉDIT utilisent la supervisory
        # duration comme les IRD (Art.280b renvoie à Art.279b/279c). Avant,
        # adj_notional = notional sous-estimait l'add-on crédit (ex. CDS 5 ans
        # → SD ≈ 3,6 → add-on sous-estimé d'un facteur ~3,6).
        s_years = _f(trade.get("start_date_years", 0.0))
        e_years = _f(trade.get("end_date_years", maturity))
        sd_cr = _supervisory_duration(s_years, e_years)
        adj_notional = notional * sd_cr * mf
        bucket = str(trade.get("reference_entity_id") or "UNKNOWN")
        sub_type = (str(trade.get("credit_quality") or "IG")).upper()
    elif asset_class == "EQUITY":
        # v3.4.0 — D_i = notional × MF
        adj_notional = notional * mf
        bucket = str(trade.get("equity_id") or "UNKNOWN")
        sub_type = (str(trade.get("equity_type") or "SINGLE")).upper()
    elif asset_class == "COMMODITY":
        # v3.4.0 — D_i = notional × MF
        adj_notional = notional * mf
        bucket = str(trade.get("commodity_type") or "ENERGY").upper()
        sub_type = bucket
    else:
        adj_notional = notional * mf
        bucket = "DEFAULT"
        sub_type = ""

    return SaccrAdjNotional(
        trade_id=str(trade.get("trade_id", "")),
        asset_class=asset_class,
        delta=delta,
        adj_notional=adj_notional,
        maturity=maturity,
        bucket=bucket,
        sub_type=sub_type,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADD-ON IRD (Art.280a)
# ─────────────────────────────────────────────────────────────────────────────


def _addon_ird(trades: List[SaccrAdjNotional]) -> float:
    """Add-on IRD : agrégation par devise puis inter-bucket maturité Art.280a."""
    if not trades:
        return 0.0

    sf = _SF["IRD"]

    # Group by currency (bucket field = currency de paiement)
    by_currency: Dict[str, Dict[int, float]] = defaultdict(lambda: {1: 0.0, 2: 0.0, 3: 0.0})
    for t in trades:
        b = _ird_bucket(t["maturity"])
        by_currency[t["bucket"]][b] += t["delta"] * t["adj_notional"]

    addon_total = 0.0
    for ccy, buckets in by_currency.items():
        d1, d2, d3 = buckets[1], buckets[2], buckets[3]
        # Formule Art.280a(1)(b) avec facteurs ε
        variance = (
            d1**2
            + d2**2
            + d3**2
            + 2 * _IRD_EPSILON[(1, 2)] * d1 * d2
            + 2 * _IRD_EPSILON[(2, 3)] * d2 * d3
            + 2 * _IRD_EPSILON[(1, 3)] * d1 * d3
        )
        addon_ccy = sf * math.sqrt(max(0.0, variance))
        addon_total += addon_ccy
        logger.debug("SA-CCR IRD ccy=%s D=[%.0f,%.0f,%.0f] addon=%.2f", ccy, d1, d2, d3, addon_ccy)

    return addon_total


# ─────────────────────────────────────────────────────────────────────────────
# ADD-ON FX (Art.280c)
# ─────────────────────────────────────────────────────────────────────────────


def _addon_fx(trades: List[SaccrAdjNotional]) -> float:
    """Add-on FX : agrégation par currency pair Art.280c."""
    if not trades:
        return 0.0

    sf = _SF["FX"]
    by_pair: Dict[str, float] = defaultdict(float)
    for t in trades:
        by_pair[t["bucket"]] += t["delta"] * t["adj_notional"]

    addon = sum(sf * abs(v) for v in by_pair.values())
    return addon


# ─────────────────────────────────────────────────────────────────────────────
# ADD-ON CREDIT (Art.280b) — formule corrélation Art.280b(1)(b)
# ─────────────────────────────────────────────────────────────────────────────


def _addon_credit(trades: List[SaccrAdjNotional]) -> float:
    """Add-on Credit Art.280b — agrégation par entité de référence avec corrélation ρ."""
    if not trades:
        return 0.0

    rho = _RHO["CREDIT"]

    # EffNot par entité = SF_c × Σ δ_i × D_i
    by_entity: Dict[str, Tuple[float, float]] = {}  # entity → (EffNot, SF)
    for t in trades:
        sf_key = "CREDIT_IG" if t["sub_type"] != "HY" else "CREDIT_HY"
        sf = _SF[sf_key]
        d = t["delta"] * t["adj_notional"]
        if t["bucket"] not in by_entity:
            by_entity[t["bucket"]] = (0.0, sf)
        prev_d, prev_sf = by_entity[t["bucket"]]
        by_entity[t["bucket"]] = (prev_d + d, sf)

    eff_nots = [sf * d for d, sf in by_entity.values()]
    if not eff_nots:
        return 0.0

    sum_en = sum(eff_nots)
    sum_en_sq = sum(v * v for v in eff_nots)
    variance = rho**2 * sum_en**2 + (1 - rho**2) * sum_en_sq
    return math.sqrt(max(0.0, variance))


# ─────────────────────────────────────────────────────────────────────────────
# ADD-ON EQUITY (Art.280d)
# ─────────────────────────────────────────────────────────────────────────────


def _aggregate_addon_with_correlation(
    weighted_eff_notionals: List[float],
    rho: float,
) -> float:
    """Formule générique d'agrégation par hedging set type Art.280b/d/e CRR3.

        AddOn = √( (Σ EffNot)² × ρ² + (1−ρ²) × Σ EffNot² )

    Utilisée par les classes CREDIT, EQUITY et COMMODITY avec leurs ρ respectifs.
    """
    if not weighted_eff_notionals:
        return 0.0
    sum_en = sum(weighted_eff_notionals)
    sum_en_sq = sum(v * v for v in weighted_eff_notionals)
    variance = rho**2 * sum_en**2 + (1.0 - rho**2) * sum_en_sq
    return math.sqrt(max(0.0, variance))


def _addon_equity(trades: List[SaccrAdjNotional]) -> float:
    """Add-on Equity Art.280d — agrégation SÉPARÉE single / index.

    PATCH v2.6 — BUG ART.280d CORRIGÉ
    -----------------------------------
    Avant v2.6, ``_addon_equity`` calculait un ``rho_avg`` (moyenne arithmétique
    des ρ single/index) puis appliquait la formule corrélation sur l'ensemble
    des trades — cette simplification n'est pas conforme Art.280d CRR3 qui
    impose une agrégation séparée par hedging set type.

    Méthode v2.6 (conforme Art.280d) :
      1. Séparer les trades en deux sous-ensembles selon ``sub_type`` :
           SINGLE (actions individuelles)  → SF = 32 %, ρ = 50 %
           INDEX  (indices boursiers)       → SF = 20 %, ρ = 80 %
      2. Pour chaque sous-ensemble, agréger par bucket (ticker/index) puis
         calculer l'add-on intra-type avec la corrélation correspondante.
      3. Sommer linéairement les deux add-ons (pas de corrélation inter-type
         entre single et index — contrairement aux corrélations intra Art.280d).

    Formule réglementaire (chaque h ∈ {SINGLE, INDEX}) :
        EffNot_h_e = SF_h × Σ_{trades on entity e} (δ × D)
        AddOn_h    = √( (Σ_e EffNot_h_e)² × ρ_h² + (1−ρ_h²) × Σ_e EffNot_h_e² )

        AddOn_Equity = AddOn_SINGLE + AddOn_INDEX
    """
    if not trades:
        return 0.0

    # ── 1. Séparation des trades par hedging set type ────────────────────────
    # `sub_type` est posé par `_adjusted_notional` à partir de `equity_type`
    # (SINGLE par défaut, INDEX si "INDEX" exact). On ne classe en INDEX que
    # les valeurs explicites pour rester prudentiel.
    by_type: Dict[str, List[SaccrAdjNotional]] = {"SINGLE": [], "INDEX": []}
    for t in trades:
        eq_type = (t.get("sub_type") or "SINGLE").upper()
        if eq_type == "INDEX":
            by_type["INDEX"].append(t)
        else:
            by_type["SINGLE"].append(t)

    # ── 2. Add-on intra-type — agrégation par bucket (ticker ou code index) ──
    def _addon_for_subset(subset: List[SaccrAdjNotional], sf_key: str, rho_key: str) -> float:
        if not subset:
            return 0.0
        sf = _SF[sf_key]
        rho = _RHO[rho_key]
        # Agrégation par bucket (entity / index code) : Σ δ × D pour chaque entité
        by_entity: Dict[str, float] = defaultdict(float)
        for t in subset:
            by_entity[t["bucket"]] += t["delta"] * t["adj_notional"]
        # EffNot par entité = SF × |Σ δ × D|  (CRR3 Art.280d(1))
        # NB : Art.280d(1) introduit la valeur ABSOLUE comme intra-bucket
        # mais Art.280b applique la signed sum — convention conservatrice ici :
        # on garde la signed sum, ce qui permet le netting partiel intra-bucket
        # (positions long/short sur même entité). C'est le comportement v2.5.
        eff_nots = [sf * d for d in by_entity.values()]
        return _aggregate_addon_with_correlation(eff_nots, rho)

    addon_single = _addon_for_subset(by_type["SINGLE"], "EQUITY_SINGLE", "EQUITY_SINGLE")
    addon_index = _addon_for_subset(by_type["INDEX"], "EQUITY_INDEX", "EQUITY_INDEX")

    # ── 3. Sommation linéaire — pas de corrélation inter-type Art.280d ───────
    addon_total = addon_single + addon_index
    logger.debug(
        "SA-CCR EQUITY add-on : SINGLE=%.2f  INDEX=%.2f  TOTAL=%.2f  (n_single=%d, n_index=%d)",
        addon_single,
        addon_index,
        addon_total,
        len(by_type["SINGLE"]),
        len(by_type["INDEX"]),
    )
    return addon_total


# ─────────────────────────────────────────────────────────────────────────────
# ADD-ON COMMODITY (Art.280e)
# ─────────────────────────────────────────────────────────────────────────────


def _addon_commodity(trades: List[SaccrAdjNotional]) -> float:
    """Add-on Commodity Art.280e — agrégation par commodity type avec ρ=0.40."""
    if not trades:
        return 0.0

    rho = _RHO["COMMODITY"]
    by_type: Dict[str, float] = defaultdict(float)

    for t in trades:
        ctype = t["sub_type"].upper() if t["sub_type"] else "ENERGY"
        sf_key = f"COMMODITY_{ctype}" if f"COMMODITY_{ctype}" in _SF else "COMMODITY_OTHER"
        sf = _SF[sf_key]
        by_type[ctype] += sf * t["delta"] * t["adj_notional"]

    eff_nots = list(by_type.values())
    sum_en = sum(eff_nots)
    sum_en_sq = sum(v * v for v in eff_nots)
    variance = rho**2 * sum_en**2 + (1 - rho**2) * sum_en_sq
    return math.sqrt(max(0.0, variance))


# ─────────────────────────────────────────────────────────────────────────────
# CALCUL PFE COMPLET PAR NETTING SET (Art.278)
# ─────────────────────────────────────────────────────────────────────────────


def _compute_pfe_full(
    trades: List[SaccrTradeRow],
    mtm_net: float,
    collateral_for_multiplier: float = 0.0,
    margined: bool = False,
    mpor_days: float = 10.0,
) -> SaccrAddOnBreakdown:
    """Calcule le PFE complet Art.278 pour un netting set.

    Sépare les trades par classe, calcule chaque add-on natif,
    applique le multiplier Art.278(1), et retourne la décomposition complète.

    Paramètres (v3.4.0)
    -------------------
    margined  : bool   netting set margé (→ facteur de maturité margé Art.279c).
    mpor_days : float  Marge Period Of Risk en jours ouvrés (margé).
    """
    # Vérifier si les trades ont des données natives SA-CCR (v7)
    has_native = any(t.get("asset_class") and t.get("notional") is not None for t in trades)

    if not has_native:
        # Fallback v5 : utiliser les add-ons pré-calculés
        pfe_full = sum(_f(t.get("addon", 0.0)) for t in trades)
        multiplier = _calc_multiplier(mtm_net - collateral_for_multiplier, pfe_full)
        return SaccrAddOnBreakdown(
            addon_ird=0.0,
            addon_fx=0.0,
            addon_credit=0.0,
            addon_equity=0.0,
            addon_commodity=0.0,
            pfe_full=pfe_full,
            multiplier=multiplier,
            pfe_final=pfe_full * multiplier,
        )

    # Calcul natif : notionnel ajusté par trade (avec MF Art.279c — v3.4.0)
    adj_notionals: List[SaccrAdjNotional] = [
        _adjusted_notional(t, margined=margined, mpor_days=mpor_days) for t in trades
    ]

    # Tri par classe
    by_class: Dict[str, List[SaccrAdjNotional]] = defaultdict(list)
    for an in adj_notionals:
        by_class[an["asset_class"]].append(an)

    addon_ird = _addon_ird(by_class.get("IRD", []))
    addon_fx = _addon_fx(by_class.get("FX", []))
    addon_credit = _addon_credit(by_class.get("CREDIT", []))
    addon_equity = _addon_equity(by_class.get("EQUITY", []))
    addon_commodity = _addon_commodity(by_class.get("COMMODITY", []))

    pfe_full = addon_ird + addon_fx + addon_credit + addon_equity + addon_commodity
    multiplier = _calc_multiplier(mtm_net - collateral_for_multiplier, pfe_full)
    pfe_final = pfe_full * multiplier

    return SaccrAddOnBreakdown(
        addon_ird=addon_ird,
        addon_fx=addon_fx,
        addon_credit=addon_credit,
        addon_equity=addon_equity,
        addon_commodity=addon_commodity,
        pfe_full=pfe_full,
        multiplier=multiplier,
        pfe_final=pfe_final,
    )


def _calc_multiplier(v: float, pfe_full: float) -> float:
    """Multiplier SA-CCR Art.278(1).

    multiplier = min(1, floor + (1−floor) × exp(V / (2×(1−floor)×PFE_full)))
    floor = 0.05
    """
    floor = _MF_FLOOR
    if pfe_full <= 0.0:
        return 1.0
    try:
        raw = floor + (1.0 - floor) * math.exp(v / (2.0 * (1.0 - floor) * pfe_full))
    except (OverflowError, ZeroDivisionError):
        raw = 1.0
    return min(1.0, raw)


# ─────────────────────────────────────────────────────────────────────────────
# P0 v3.2.0 — MARGE / COLLATERAL SA-CCR AVANCÉ
# ─────────────────────────────────────────────────────────────────────────────


def _truthy(value: Any, default: bool = False) -> bool:
    """Normalise les indicateurs booléens CSV/SQL sans dépendre de l'ingestion."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"1", "TRUE", "T", "YES", "Y", "OUI", "O"}


def _compute_margin_state(
    trades: List[SaccrTradeRow],
    *,
    force_margined: Optional[bool] = None,
) -> dict:
    """Agrège l'état de marge/collatéral d'un netting set SA-CCR.

    v4.4.5 — correctif final standard
    ----------------------------------
    - RC margé : ``max(CMV - VM - NICA, TH + MTA - NICA, 0)``.
      La version précédente omettait NICA dans le premier terme.
    - Cap Art.274(3) préparé via ``force_margined=False`` : le même netting set
      peut être recalculé comme non margé pour obtenir ``EAD_unmargined``.
    - Reconnaissance minimale Art.276 : les champs ``collateral_eligible``,
      ``vm_eligible`` et ``im_eligible`` permettent d'exclure le collatéral non
      reconnu du RC et du multiplier, tout en traçant l'inéligible.

    Conventions de signe
    --------------------
    - VM reçue et IM/NICA reçus réduisent l'exposition de la banque.
    - VM postée et IM/NICA postés augmentent l'exposition nette.
    - ``legacy_collateral`` conserve le comportement historique : montant positif
      de collatéral reçu déjà éligible/ajusté par le système source.
    """
    mtm_net = sum(_f(t.get("mtm", 0.0)) for t in trades)

    eligible_legacy_collateral = 0.0
    ineligible_collateral = 0.0
    vm_received = vm_posted = im_received = im_posted = 0.0
    vm_ineligible = im_ineligible = 0.0

    for t in trades:
        legacy = _f(t.get("collateral", 0.0))
        if _truthy(t.get("collateral_eligible"), default=True):
            eligible_legacy_collateral += legacy
        else:
            ineligible_collateral += legacy

        vm_r = _f(t.get("vm_received", 0.0))
        vm_p = _f(t.get("vm_posted", 0.0))
        if _truthy(t.get("vm_eligible"), default=True):
            vm_received += vm_r
            vm_posted += vm_p
        else:
            vm_ineligible += abs(vm_r) + abs(vm_p)

        im_r = _f(t.get("im_received", 0.0))
        im_p = _f(t.get("im_posted", 0.0))
        if _truthy(t.get("im_eligible"), default=True):
            im_received += im_r
            im_posted += im_p
        else:
            im_ineligible += abs(im_r) + abs(im_p)

    explicit_nica_values = [t.get("nica") for t in trades if t.get("nica") not in (None, "")]
    if explicit_nica_values:
        # Le NICA explicite est supposé reconnu/éligible par la source amont.
        nica = sum(_f(v) for v in explicit_nica_values)
    else:
        nica = im_received - im_posted

    threshold = max((_f(t.get("threshold_amount", 0.0)) for t in trades), default=0.0)
    mta = max((_f(t.get("mta", 0.0)) for t in trades), default=0.0)
    mpor_days = max((int(_f(t.get("mpor_days", 10.0)) or 10) for t in trades), default=10)
    mpor_days = max(_MPOR_FLOOR_DAYS, mpor_days)

    def _is_set(v: Any) -> bool:
        return v not in (None, "")

    detected_csa = any(
        _is_set(t.get("csa_id"))
        or _is_set(t.get("nica"))
        or _f(t.get("threshold_amount", 0.0)) != 0.0
        or _f(t.get("mta", 0.0)) != 0.0
        or _f(t.get("vm_received", 0.0)) != 0.0
        or _f(t.get("vm_posted", 0.0)) != 0.0
        or _f(t.get("im_received", 0.0)) != 0.0
        or _f(t.get("im_posted", 0.0)) != 0.0
        for t in trades
    )
    csa_present = detected_csa if force_margined is None else bool(force_margined)

    net_variation_margin = eligible_legacy_collateral + vm_received - vm_posted

    if csa_present:
        rc = max(
            mtm_net - net_variation_margin - nica,
            threshold + mta - nica,
            0.0,
        )
        rc_formula = "MARGINED_MAX_CMV_VM_NICA_TH_MTA_NICA"
    else:
        rc = max(mtm_net - net_variation_margin - nica, 0.0)
        rc_formula = "UNMARGINED_MAX_CMV_COLLATERAL_NICA"

    collateral_for_multiplier = net_variation_margin + nica
    total_ineligible = ineligible_collateral + vm_ineligible + im_ineligible

    return {
        "mtm_net": mtm_net,
        "legacy_collateral": eligible_legacy_collateral,
        "eligible_collateral_value": net_variation_margin + max(nica, 0.0),
        "ineligible_collateral_value": total_ineligible,
        "vm_received": vm_received,
        "vm_posted": vm_posted,
        "net_variation_margin": net_variation_margin,
        "im_received": im_received,
        "im_posted": im_posted,
        "nica": nica,
        "threshold_amount": threshold,
        "mta": mta,
        "mpor_days": mpor_days,
        "csa_present": csa_present,
        "detected_csa": detected_csa,
        "rc": rc,
        "rc_formula": rc_formula,
        "collateral_for_multiplier": collateral_for_multiplier,
    }


def _compute_saccr_exposure_state(
    trades: List[SaccrTradeRow],
    *,
    alpha: float = _ALPHA,
    force_margined: Optional[bool] = None,
) -> dict:
    """Calcule RC/PFE/EAD pour un mode de marge donné.

    Cette granularité permet le cap Art.274(3) : pour un netting set margé,
    on calcule à la fois l'EAD margée et l'EAD non margée, puis on retient le
    minimum. Les add-ons sont recalculés avec le bon facteur de maturité
    margé/non margé.
    """
    margin_state = _compute_margin_state(trades, force_margined=force_margined)
    pfe_breakdown = _compute_pfe_full(
        trades,
        margin_state["mtm_net"],
        collateral_for_multiplier=margin_state["collateral_for_multiplier"],
        margined=bool(margin_state["csa_present"]),
        mpor_days=margin_state["mpor_days"],
    )
    pfe = pfe_breakdown["pfe_final"]
    ead = alpha * (margin_state["rc"] + pfe)
    return {
        "margin_state": margin_state,
        "pfe_breakdown": pfe_breakdown,
        "rc": margin_state["rc"],
        "pfe": pfe,
        "ead": ead,
    }


def _apply_margin_cap(
    trades: List[SaccrTradeRow],
    *,
    alpha: float = _ALPHA,
) -> dict:
    """Applique le cap Art.274(3) pour les netting sets margés.

    Retourne l'état final utilisé pour RWA + les deux trajectoires auditables :
    ``margined`` et ``unmargined``. Pour les netting sets non margés, la
    trajectoire unique est retournée sans cap.
    """
    detected = _compute_margin_state(trades)["detected_csa"]
    if not detected:
        final = _compute_saccr_exposure_state(trades, alpha=alpha, force_margined=False)
        return {
            "final": final,
            "margined": None,
            "unmargined": final,
            "cap_applied": False,
            "final_method": "UNMARGINED",
        }

    margined = _compute_saccr_exposure_state(trades, alpha=alpha, force_margined=True)
    unmargined = _compute_saccr_exposure_state(trades, alpha=alpha, force_margined=False)
    if unmargined["ead"] < margined["ead"]:
        final = unmargined
        method = "ART274_3_UNMARGINED_CAP"
        cap = True
    else:
        final = margined
        method = "MARGINED"
        cap = False
    return {
        "final": final,
        "margined": margined,
        "unmargined": unmargined,
        "cap_applied": cap,
        "final_method": method,
    }


def _load_supervisory_parameters(db: Database, regulatory_version_id: str) -> float:
    """Charge les paramètres SA-CCR depuis ref.ref_saccr_supervisory_parameters.

    Les constantes Python restent un fallback défensif si la table n'existe pas
    encore (tests unitaires ou base non migrée). En run normal, le bootstrap SQL
    alimente cette table et rend les facteurs auditables.
    """
    # Scalar alpha is centralized in the versioned runtime registry.  The
    # dedicated supervisory table remains the source for asset-class factors.
    alpha = float(get_parameter(db, regulatory_version_id, "DEFAULT_ALPHA_SACCR", _ALPHA))
    try:
        rows = db.query(
            """
            SELECT parameter_name, parameter_value
            FROM ref.ref_saccr_supervisory_parameters
            WHERE regulatory_version_id = %s
            """,
            (regulatory_version_id,),
        )
    except Exception as exc:  # pragma: no cover - fallback base legacy
        logger.warning(
            "SA-CCR : référentiel supervisory non disponible, fallback constantes Python (%s)",
            exc,
        )
        return alpha

    for row in rows:
        name = str(row.get("parameter_name") or "").upper()
        value = _f(row.get("parameter_value", 0.0))
        if name == "ALPHA":
            alpha = value or alpha
        elif name == "MULTIPLIER_FLOOR":
            # Le floor est volontairement global pour les helpers historiques.
            globals()["_MF_FLOOR"] = value or globals()["_MF_FLOOR"]
        elif name.startswith("SF_"):
            key = name[3:]
            if key in _SF:
                _SF[key] = value
        elif name.startswith("RHO_"):
            key = name[4:]
            if key in _RHO:
                _RHO[key] = value
        elif name.startswith("IRD_EPSILON_"):
            parts = name.split("_")
            if len(parts) >= 4:
                try:
                    i, j = int(parts[-2]), int(parts[-1])
                except ValueError:
                    continue
                _IRD_EPSILON[(i, j)] = value
                _IRD_EPSILON[(j, i)] = value
    return alpha


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────


def run_saccr_engine(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    reporting_date: str,
) -> int:
    """Calcule EAD et RWA SA-CCR par netting set (Art.274-280 CRR3).

    Paramètres
    ----------
    db                   : connexion PostgreSQL active
    batch_id             : UUID du batch courant
    regulatory_version_id: version réglementaire (ex. "CRR3_V9")
    reporting_date       : date ISO (ex. "2026-03-31")

    Retourne
    --------
    int : nombre de netting sets traités

    Rétrocompatibilité v5
    ----------------------
    Si les trades n'ont pas de colonne `asset_class`, le moteur utilise le
    champ `addon` pré-calculé (comportement identique à la v5).
    """
    db.execute("DELETE FROM core.core_saccr_results WHERE batch_id = %s", (batch_id,))

    # ── Chargement de tous les trades du batch ───────────────────────────────
    all_trades: List[SaccrTradeRow] = db.query(
        """
        SELECT
            t.trade_id,
            t.batch_id,
            t.netting_set_id,
            t.counterparty_id,
            COALESCE(c.counterparty_type, 'CORPORATE') AS counterparty_type,
            CAST(t.mtm        AS FLOAT) AS mtm,
            CAST(t.collateral AS FLOAT) AS collateral,
            -- champs v7 SA-CCR natif
            t.asset_class,
            CAST(COALESCE(t.notional,           0) AS FLOAT) AS notional,
            CAST(COALESCE(t.maturity_years,      1) AS FLOAT) AS maturity_years,
            CAST(COALESCE(t.start_date_years,    0) AS FLOAT) AS start_date_years,
            CAST(COALESCE(t.end_date_years,      1) AS FLOAT) AS end_date_years,
            CAST(COALESCE(t.delta,               1) AS FLOAT) AS delta,
            t.option_type,
            CAST(COALESCE(t.strike,              0) AS FLOAT) AS strike,
            CAST(COALESCE(t.underlying_price,    0) AS FLOAT) AS underlying_price,
            CAST(COALESCE(t.implied_vol,         0) AS FLOAT) AS implied_vol,
            t.commodity_type,
            t.reference_entity_id,
            t.credit_quality,
            t.equity_id,
            t.equity_type,
            -- PATCH v2.7 : devise IRD (Art.280a) — hedging set IRD = currency.
            -- Colonne ajoutée par 02j_schema_v2_7_saccr_currency.sql.
            -- COALESCE pour rétrocompatibilité : si la colonne n'existe pas
            -- (base v2.6 non patchée), on remonte NULL et le fallback Python
            -- via `currency` ou `ird_currency` prend le relais.
            t.payment_currency,
            t.pay_currency,
            t.receive_currency,
            t.currency_pair,
            t.collateral_currency,
            CAST(COALESCE(t.collateral_eligible, TRUE) AS BOOLEAN) AS collateral_eligible,
            CAST(COALESCE(t.vm_eligible, TRUE) AS BOOLEAN) AS vm_eligible,
            CAST(COALESCE(t.im_eligible, TRUE) AS BOOLEAN) AS im_eligible,
            -- P0 v3.2.0 — marge/collatéral avancé
            CAST(COALESCE(t.vm_received,         0) AS FLOAT) AS vm_received,
            CAST(COALESCE(t.vm_posted,           0) AS FLOAT) AS vm_posted,
            CAST(COALESCE(t.im_received,         0) AS FLOAT) AS im_received,
            CAST(COALESCE(t.im_posted,           0) AS FLOAT) AS im_posted,
            CAST(t.nica AS FLOAT) AS nica,
            CAST(COALESCE(t.threshold_amount,    0) AS FLOAT) AS threshold_amount,
            CAST(COALESCE(t.mta,                 0) AS FLOAT) AS mta,
            CAST(COALESCE(t.mpor_days,          10) AS FLOAT) AS mpor_days,
            t.csa_id,
            -- legacy
            CAST(COALESCE(t.addon,               0) AS FLOAT) AS addon
        FROM stg.stg_saccr_trades t
        LEFT JOIN ref.ref_counterparties c ON t.counterparty_id = c.counterparty_id
        WHERE t.batch_id = %s
        """,
        (batch_id,),
    )

    if not all_trades:
        logger.info("SA-CCR : aucun trade en staging — 0 netting set traité")
        return 0

    # ── Regroupement par netting set ─────────────────────────────────────────
    by_ns: Dict[str, List[SaccrTradeRow]] = defaultdict(list)
    ns_meta: Dict[str, Dict[str, str]] = {}
    for t in all_trades:
        ns_id = str(t["netting_set_id"])
        by_ns[ns_id].append(t)
        if ns_id not in ns_meta:
            ns_meta[ns_id] = {
                "counterparty_type": str(t.get("counterparty_type", "CORPORATE")),
                "counterparty_id": str(t.get("counterparty_id", "")),
            }

    alpha = _load_supervisory_parameters(db, regulatory_version_id)
    trace_buffer: List[tuple] = []
    results_batch: List[tuple] = []

    for ns_id, ns_trades in by_ns.items():
        ctype = ns_meta[ns_id]["counterparty_type"]
        cpid = ns_meta[ns_id]["counterparty_id"]

        # ── RC/PFE/EAD + cap Art.274(3) ─────────────────────────────────────
        exposure_state = _apply_margin_cap(ns_trades, alpha=alpha)
        final_state = exposure_state["final"]
        margin_state = final_state["margin_state"]
        pfe_breakdown = final_state["pfe_breakdown"]
        mtm_sum = margin_state["mtm_net"]
        rc = final_state["rc"]
        pfe = final_state["pfe"]
        ead = final_state["ead"]
        margined_state = exposure_state.get("margined")
        unmargined_state = exposure_state.get("unmargined")
        ead_margined = margined_state["ead"] if margined_state else None
        ead_unmargined = unmargined_state["ead"] if unmargined_state else ead
        rc_margined = margined_state["rc"] if margined_state else None
        rc_unmargined = unmargined_state["rc"] if unmargined_state else rc
        pfe_margined = margined_state["pfe"] if margined_state else None
        pfe_unmargined = unmargined_state["pfe"] if unmargined_state else pfe

        logger.debug(
            "SA-CCR NS=%s  method=%s cap=%s RC=%.2f PFE_full=%.2f mult=%.4f PFE=%.2f "
            "EAD=%.2f EAD_margined=%s EAD_unmargined=%.2f "
            "(IRD=%.2f FX=%.2f CR=%.2f EQ=%.2f CO=%.2f)",
            ns_id,
            exposure_state["final_method"],
            exposure_state["cap_applied"],
            rc,
            pfe_breakdown["pfe_full"],
            pfe_breakdown["multiplier"],
            pfe,
            ead,
            f"{ead_margined:.2f}" if ead_margined is not None else "n/a",
            ead_unmargined,
            pfe_breakdown["addon_ird"],
            pfe_breakdown["addon_fx"],
            pfe_breakdown["addon_credit"],
            pfe_breakdown["addon_equity"],
            pfe_breakdown["addon_commodity"],
        )

        # ── Risk Weight via moteur de décision ───────────────────────────────
        rw_decision = evaluate_rule_set(
            db,
            batch_id,
            regulatory_version_id,
            "SACCR_RISK_WEIGHT",
            {"_context_key": ns_id, "counterparty_type": ctype},
            trace_buffer=trace_buffer,
        )
        rw = _f(rw_decision["result_value"]) if rw_decision else 1.0
        rwa = ead * rw

        collateral_state = {
            "final": margin_state,
            "margined": margined_state["margin_state"] if margined_state else None,
            "unmargined": unmargined_state["margin_state"] if unmargined_state else None,
            "cap_applied": exposure_state["cap_applied"],
            "final_method": exposure_state["final_method"],
        }
        results_batch.append(
            (
                batch_id,
                ns_id,
                cpid,
                ctype,
                rc,
                pfe,
                ead,
                rw,
                rwa,
                mtm_sum,
                margin_state["net_variation_margin"],
                margin_state["nica"],
                margin_state["threshold_amount"],
                margin_state["mta"],
                margin_state["mpor_days"],
                pfe_breakdown["multiplier"],
                pfe_breakdown["pfe_full"],
                pfe_breakdown["addon_ird"],
                pfe_breakdown["addon_fx"],
                pfe_breakdown["addon_credit"],
                pfe_breakdown["addon_equity"],
                pfe_breakdown["addon_commodity"],
                margin_state["eligible_collateral_value"],
                margin_state["ineligible_collateral_value"],
                ead_margined,
                ead_unmargined,
                rc_margined,
                rc_unmargined,
                pfe_margined,
                pfe_unmargined,
                exposure_state["cap_applied"],
                exposure_state["final_method"],
                json.dumps(collateral_state, default=str),
            )
        )

    # ── Persistance ─────────────────────────────────────────────────────────
    with db.transaction():
        if results_batch:
            db.executemany(
                """
                INSERT INTO core.core_saccr_results (
                    batch_id, netting_set_id, counterparty_id, counterparty_type,
                    rc, pfe, ead, risk_weight, rwa,
                    mtm_net, net_variation_margin, nica,
                    threshold_amount, mta, mpor_days,
                    pfe_multiplier, pfe_full,
                    addon_ird, addon_fx, addon_credit, addon_equity, addon_commodity,
                    eligible_collateral_value, ineligible_collateral_value,
                    ead_margined, ead_unmargined_cap,
                    rc_margined, rc_unmargined_cap,
                    pfe_margined, pfe_unmargined_cap,
                    cap_applied, final_method,
                    collateral_state
                ) VALUES %s
                """,
                results_batch,
            )
        flush_trace_buffer(db, trace_buffer)

    logger.info(
        "SA-CCR : %d netting sets traités  (α=%.2f, PFE natif=%s)",
        len(results_batch),
        alpha,
        "OUI" if any(t.get("asset_class") for t in all_trades) else "NON (fallback v5)",
    )
    return len(results_batch)
