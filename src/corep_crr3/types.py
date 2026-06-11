"""Types publics strictement nécessaires aux moteurs SA et SA-CCR.

Ce fichier est volontairement limité aux contrats de données SA-CCR.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from typing_extensions import Literal, NotRequired, TypedDict


class SaccrTradeRow(TypedDict, total=False):
    """Ligne stg.stg_saccr_trades — v7 : champs complets pour calcul PFE natif."""

    trade_id: str
    batch_id: str
    netting_set_id: str
    counterparty_id: str
    asset_class: str
    mtm: float
    collateral: float
    notional: NotRequired[float]
    maturity_years: NotRequired[float]
    start_date_years: NotRequired[float]
    end_date_years: NotRequired[float]
    delta: NotRequired[float]
    option_type: NotRequired[str]
    strike: NotRequired[float]
    underlying_price: NotRequired[float]
    implied_vol: NotRequired[float]
    commodity_type: NotRequired[str]
    reference_entity_id: NotRequired[str]
    credit_quality: NotRequired[str]
    equity_id: NotRequired[str]
    equity_type: NotRequired[str]
    addon: NotRequired[float]
    reporting_date: str


class SaccrAdjNotional(TypedDict):
    """Notionnel ajusté d'un trade SA-CCR (calcul PFE natif v7)."""

    trade_id: str
    asset_class: str
    delta: float
    adj_notional: float
    maturity: float
    bucket: str
    sub_type: str


class SaccrAddOnBreakdown(TypedDict):
    """Décomposition PFE SA-CCR Art.278-280."""

    addon_ird: float
    addon_fx: float
    addon_credit: float
    addon_equity: float
    addon_commodity: float
    pfe_full: float
    multiplier: float
    pfe_final: float
