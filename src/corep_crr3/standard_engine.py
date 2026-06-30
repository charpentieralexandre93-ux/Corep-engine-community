"""
================================================================================
MODULE  : standard_engine.py
PROJET  : COREP Engine CRR3
VERSION : 6.6.0
================================================================================

DESCRIPTION
-----------
Ce module implémente l'engine de calcul du risque de crédit selon l'Approche
Standard (SA) de CRR3. Il constitue le moteur principal du système COREP et
traite la majorité des expositions d'un portefeuille bancaire standard.

APPROCHE STANDARD SA — BASES RÉGLEMENTAIRES
---------------------------------------------
L'Approche Standard du risque de crédit est définie aux Articles 107 à 141
de CRR3 (Capital Requirements Regulation 3, version 2024).

Principe : attribuer à chaque exposition une pondération de risque (Risk Weight)
prédéfinie selon la classe d'actif et la qualité de crédit de la contrepartie,
puis calculer l'exigence de fonds propres = RWA × 8%.

FLUX DE CALCUL PAR EXPOSITION
-------------------------------
Pour chaque exposition chargée dans stg.stg_exposures :

    1. LECTURE DES DONNÉES STAGING
       gross_exposure = exposure_amount (montant brut)
       provision      = provision_amount (provisions spécifiques)
       net            = max(gross − provision, 0)

    2. CCF (Credit Conversion Factor) — Art.111 CRR3
       Déterminé par le moteur de décision selon product_type_id :
         TERM_LOAN         → CCF = 1.0  (bilan → 100%)
         REVOLVING         → CCF = 0.75
         COMMITMENT        → CCF = 0.40
         REVOCABLE_COMMIT  → CCF = 0.10 (bucket 5 CRR3)
       EAD pré-CRM = net × CCF

    3. RISK WEIGHT (RW) — Art.114-136 CRR3
       Déterminé par le moteur de décision selon asset_class_id :
         SOVEREIGN         → RW selon CQS ; fallback prudentiel 100% si CQS absent
         INSTITUTION/BANK  → RW = 20% à 150%
         CORPORATE         → RW = 100%
         RETAIL            → RW = 75%
         DEFAULT           → RW = 50% à 150%

    4. CRM — Techniques d'atténuation du risque de crédit (Art.193-241)
       Pour chaque protection associée à l'exposition (table stg_protections),
       traitée en DEUX passes — FCP d'abord, UFCP ensuite (v3.7.0), conformément
       à la méthode générale (le collatéral funded réduit l'exposition avant la
       substitution unfunded), indépendamment de allocation_rank :
         FCP  (Funded Credit Protection)   : applique les haircuts superviseurs
              (volatilité Hc + change Hfx Art.224 si mismatch de devise) puis
              l'ajustement maturity mismatch (Art.239) avant de réduire l'EAD.
         UFCP (Unfunded Credit Protection) : ajuste d'abord la valeur de la
              garantie du change Hfx (Art.233(3) si mismatch de devise) et du
              maturity mismatch (Art.239), PUIS substitue partiellement le RW
              (Art.235) sur la portion résiduelle, sur l'EAD POST-FCP.
              [v3.9.0 — bug 2 : Hfx/Art.239 désormais appliqués à l'UFCP, à
              parité avec le FCP ; pas de haircut de volatilité Hc sur l'unfunded.]

    5. RWA PRÉ-SUPPORTING FACTORS
       rwa_pre_sf = ead_after_fcp × risk_weight_substituted

    6. SUPPORTING FACTORS — Art.501 / 501a CRR3
       Facteurs réducteurs pour PME et Projets d'infrastructure :
         SME_SUPPORTING_FACTOR   : two-tier Art.501(1) — 0,7619 sur la part de
                                   l'exposition totale PME (E* par obligor) ≤ 2,5 M€,
                                   0,85 sur la part > 2,5 M€ (correction v3.4.0).
         INFRA_SUPPORTING_FACTOR : × 0.75   si supporting_infra_flag = TRUE
       rwa_final = rwa_pre_sf × multiplier

CORRECTIONS CLÉS (versions antérieures)
-----------------------------------------
v2 — PERFORMANCE :
    Buffers + executemany groupé → 1 seule transaction par batch.
    trace_buffer passé à evaluate_rule_set() → 0 INSERT dans la boucle.

v3 — BUG DELETE :
    DELETE sur rpt.rpt_supporting_factor_trace déplacé au niveau batch
    (avant la boucle) au lieu du niveau exposition → 1 DELETE au lieu de N.

v4 — BUG SUPPORTING FACTORS :
    Les règles SF (ref_supporting_factor_rules) étaient rechargées depuis
    la base à CHAQUE appel apply_supporting_factors() dans la boucle principale.
    Sur 10 000 expositions → 10 000 SELECT identiques.
    FIX : pré-chargement UNE SEULE FOIS avant la boucle, passé via preloaded_rules.

DÉPENDANCES
-----------
    .db.Database
    .decision_engine.evaluate_rule_set, flush_trace_buffer, clear_rules_cache
    .protection_strategy.load_ranked_protections
    .supporting_factors.apply_supporting_factors
    .utils.to_float (alias _f)

SORTIE
------
    core.core_standard_results      : résultats SA par exposition
    core.core_protection_allocation : allocation des protections FCP/UFCP
    rpt.rpt_decision_rule_trace     : trace des décisions CCF et RW
    rpt.rpt_supporting_factor_trace : trace des facteurs PME/Infrastructure
================================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .db import Database
from .decision_engine import clear_rules_cache, evaluate_rule_set, flush_trace_buffer
from .protection_strategy import load_all_ranked_protections
from .supporting_factors import apply_supporting_factors
from .utils import to_float as _f

# v3.6.0 — Robustesse : `logger` était utilisé (warnings de fallback CCF/RW,
# protections CRM ignorées) mais n'était JAMAIS défini au niveau module → tout
# chemin de warning levait NameError. On le définit selon la convention projet.
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — CREDIT SA FINAL STANDARD v5.0.0
# ─────────────────────────────────────────────────────────────────────────────

_CCF_BY_ANNEX_I_BUCKET = {
    "BUCKET_1": 1.00,
    "BUCKET_2": 0.50,
    "BUCKET_3": 0.40,
    "BUCKET_4": 0.20,
    "BUCKET_5": 0.10,
    # Cas très encadré : arrangement contractuel non encore accepté par le client.
    "NOT_ACCEPTED_ZERO_CCF": 0.00,
}


def _norm_code(value: Any) -> str:
    return str(value or "").strip().upper()


def ccf_from_annex_i_bucket(bucket: str | None) -> Optional[float]:
    """Retourne le CCF CRR3 associé à un bucket Annex I.

    La grille v5.0.0 retient les cinq buckets CRR3 : 100 %, 50 %, 40 %,
    20 % et 10 %. Le 0 % n'est conservé que pour le cas distinct des
    arrangements contractuels non encore acceptés par le client, afin d'éviter
    de traiter tous les engagements révocables comme un équivalent 0 %.
    """
    code = _norm_code(bucket)
    return _CCF_BY_ANNEX_I_BUCKET.get(code)


def infer_ccf_bucket(row: dict) -> str | None:
    """Déduit un bucket CCF réglementaire depuis la ligne d'exposition.

    Priorité :
      1. `annex_i_bucket` fourni par la source ;
      2. cas contractuel non accepté par le client ;
      3. mapping prudent legacy product_type_id.
    """
    explicit = _norm_code(row.get("annex_i_bucket"))
    if explicit:
        return explicit

    not_accepted = _to_flag(row.get("contractual_arrangement_not_accepted_flag")) == "TRUE"
    client_acceptance = _to_flag(row.get("client_acceptance_required_flag")) == "TRUE"
    if not_accepted and client_acceptance:
        return "NOT_ACCEPTED_ZERO_CCF"

    product = _norm_code(row.get("product_type_id") or row.get("product_type"))
    if product in {
        "TERM_LOAN",
        "BOND",
        "MORTGAGE",
        "GUARANTEE",
        "STANDBY_LC",
        "ACCEPTANCE",
        "FORWARD_ASSET",
    }:
        return "BUCKET_1"
    if product in {"PERFORMANCE_BOND", "NIF", "RUF"}:
        return "BUCKET_2"
    if product in {"COMMITMENT", "REVOLVING"}:
        return "BUCKET_3"
    if product in {"LETTER_OF_CREDIT", "DOCUMENTARY_CREDIT"}:
        return "BUCKET_4"
    if product in {"REVOCABLE_COMMITMENT", "UCC", "UNCONDITIONALLY_CANCELLABLE_COMMITMENT"}:
        return "BUCKET_5"
    return None


def is_currency_mismatch_exposure(row: dict) -> bool:
    """Détermine si l'exposition entre dans le currency mismatch Art.123a.

    Le moteur reste défensif : le multiplicateur s'applique uniquement si la
    devise d'exposition diffère de la devise de revenu de l'emprunteur et que
    l'exposition n'est pas couverte/naturellement hedgée.
    """
    exposure_ccy = _norm_code(row.get("exposure_currency") or row.get("currency"))
    income_ccy = _norm_code(row.get("borrower_income_currency"))
    hedged = _to_flag(row.get("hedged_currency_mismatch_flag")) == "TRUE"
    natural_person = _to_flag(row.get("natural_person_flag")) == "TRUE"
    if not exposure_ccy or not income_ccy or exposure_ccy == income_ccy or hedged:
        return False
    asset_class = _norm_code(row.get("asset_class_id"))
    return natural_person or asset_class in {"RETAIL", "SME_RETAIL", "RESIDENTIAL_MORTGAGE"}


def apply_currency_mismatch_multiplier(base_rw: float, mismatch: bool) -> float:
    """Applique le multiplicateur currency mismatch : ×1,5 plafonné à 150 %."""
    rw = max(0.0, _f(base_rw))
    if not mismatch:
        return rw
    return min(1.50, rw * 1.50)


def ltv_bucket(ltv_ratio: Any) -> str | None:
    """Bucket LTV lisible pour la trace C07/C09."""
    if ltv_ratio in (None, ""):
        return None
    ltv = _f(ltv_ratio)
    if ltv <= 0.50:
        return "LTV_LE_50"
    if ltv <= 0.60:
        return "LTV_50_60"
    if ltv <= 0.80:
        return "LTV_60_80"
    if ltv <= 0.90:
        return "LTV_80_90"
    if ltv <= 1.00:
        return "LTV_90_100"
    return "LTV_GT_100"


def infer_rw_bucket(row: dict, applied_rw: float) -> str:
    """Bucket réglementaire synthétique pour la traçabilité Credit SA."""
    asset_class = _norm_code(row.get("asset_class_id"))
    subtype = _norm_code(row.get("exposure_subtype"))
    rw = round(_f(applied_rw), 4)
    if asset_class == "EQUITY":
        if subtype in {"SPECULATIVE", "SPECULATIVE_UNLISTED"} or rw >= 4.0:
            return "EQUITY_SPECULATIVE_UNLISTED_400"
        if subtype in {"STRATEGIC", "STRATEGIC_EQUITY"} or abs(rw - 1.5) < 1e-9:
            return "EQUITY_STRATEGIC_150"
        return "EQUITY_GENERIC_250"
    if subtype in {"ADC", "LAND_ACQUISITION_DEVELOPMENT_CONSTRUCTION"}:
        return "ADC"
    if subtype == "TRANSADC":
        return "TRANSADC"
    if subtype == "PROJECT_FINANCE":
        return "SPECIALISED_LENDING_PROJECT_FINANCE"
    if subtype in {"OBJECT_FINANCE", "COMMODITIES_FINANCE", "SPECIALISED_LENDING"}:
        return f"SPECIALISED_LENDING_{subtype}"
    return f"RW_{int(round(rw * 10000)):05d}BP"


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — SUBSTITUTION UFCP PARTIELLE (Art.235 CRR3)
# ─────────────────────────────────────────────────────────────────────────────


def apply_ufcp_partial_substitution(
    ead_at_obligor_rw: float,
    base_rw: float,
    rw_provider: Optional[float],
    protection_value: float,
) -> tuple[float, float, float]:
    """Calcule l'effet d'UNE protection UFCP sur le RWA selon Art.235 CRR3.

    Principe (Art.235(2)) :
        L'EAD est scindée en deux portions distinctes :
          • g_a (portion couverte) : prend le RW du garant.
          • E − g_a (portion résiduelle) : conserve le RW de l'obligor.

    La substitution n'est appliquée que si elle améliore le RWA (rw_provider
    < base_rw). Si rw_provider ≥ base_rw, la garantie n'est pas exploitée
    (CRR3 ne contraint pas à appliquer une substitution défavorable).

    Cette fonction est appelée séquentiellement pour chaque UFCP d'une
    exposition. À chaque appel, ead_at_obligor_rw diminue du montant de
    garantie effectivement allouée — ce qui permet de gérer correctement
    les UFCP MULTIPLES (chaque garant prend SA portion, indépendamment).

    Avant ce patch (v8quater et antérieur) :
        substituted_rw = min(substituted_rw, rw_provider)
        rwa = ead_after_fcp × substituted_rw
    → Bugs :
        (a) UFCP partielle (g_a < E) : rw_provider appliqué à E entière.
        (b) UFCP multiples : un seul rw_provider (le min) appliqué à toute
            l'EAD au lieu d'allouer chaque garant à sa portion.

    Paramètres
    ----------
    ead_at_obligor_rw : float
        EAD résiduelle encore au RW de l'obligor (mise à jour à chaque UFCP).
    base_rw : float
        RW de l'obligor original (avant toute substitution).
    rw_provider : float | None
        RW du garant (depuis evaluate_rule_set("SUBSTITUTION_RISK_WEIGHT")).
        None signale qu'aucune règle n'a matché — pas de substitution.
    protection_value : float
        Montant brut de la protection UFCP (V_a dans la notation CRR3).

    Retourne
    --------
    tuple (guarantee_amount, rwa_increment, new_ead_at_obligor_rw) :
        guarantee_amount : float
            Montant g_a effectivement alloué = min(EAD résiduelle, V_a).
            0.0 si la substitution n'est pas appliquée.
        rwa_increment : float
            Contribution au RWA = g_a × rw_provider.
            0.0 si la substitution n'est pas appliquée.
        new_ead_at_obligor_rw : float
            EAD restante au RW de l'obligor après allocation de cette UFCP.
            Égal à l'entrée si la substitution n'est pas appliquée.

    Exemple
    -------
        # EAD = 100, RW obligor = 100%, garantie 30 € à RW 20%
        g, dr, ead_rest = apply_ufcp_partial_substitution(100, 1.0, 0.2, 30)
        # g = 30, dr = 6 (= 30 × 0.2), ead_rest = 70
        # RWA final = dr + ead_rest × base_rw = 6 + 70 × 1.0 = 76
        # vs ANCIEN : substituted_rw = min(1.0, 0.2) = 0.2
        #             RWA = 100 × 0.2 = 20  ← sous-estimation de 56 !
    """
    # Substitution non applicable : pas de règle ou non-favorable.
    # v3.6.0 — Le test `is None` reste effectué sur la valeur BRUTE (un _f(None)
    # vaudrait 0.0 et déclencherait à tort une substitution à 0 %).
    if rw_provider is None:
        return (0.0, 0.0, _f(ead_at_obligor_rw))

    # Coercitions défensives (psycopg2 renvoie des Decimal pour les NUMERIC ;
    # Decimal × float lèverait TypeError plus bas). _f est idempotent sur float.
    rw_provider_f = _f(rw_provider)
    base_rw_f = _f(base_rw)
    ead_rest = _f(ead_at_obligor_rw)

    if rw_provider_f >= base_rw_f:
        return (0.0, 0.0, ead_rest)

    # EAD encore disponible déjà épuisée (toutes les UFCP précédentes
    # ont consommé toute la portion garantissable) → pas de substitution
    # supplémentaire pour cette protection.
    if ead_rest <= 0.0:
        return (0.0, 0.0, ead_rest)

    guarantee_amount = min(ead_rest, max(0.0, _f(protection_value)))
    rwa_increment = guarantee_amount * rw_provider_f
    new_ead = ead_rest - guarantee_amount
    return (guarantee_amount, rwa_increment, new_ead)


def _to_flag(value: Any) -> str:
    """Normalise les booléens du staging pour les règles BCNF (= TRUE/FALSE)."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    text = str(value or "").strip().upper()
    return "TRUE" if text in {"1", "TRUE", "T", "Y", "YES", "O", "OUI"} else "FALSE"


def _maturity_bucket(months: Any) -> Optional[str]:
    """Convertit une maturité en mois en bucket de haircut superviseur."""
    try:
        m = float(months)
    except (TypeError, ValueError):
        return None
    if m <= 12:
        return "≤1Y"
    if m <= 60:
        return "1Y-5Y"
    return ">5Y"


# ── v3.5.0 (audit ④) — CRM : haircut de change Art.224 + maturity mismatch Art.239 ──
# Plafond de l'horizon de maturité T (Art.239(3)) : 5 ans.
_CRM_MATURITY_CAP_YEARS = 5.0
# Plancher de 3 mois (0,25 an) dans la formule (t − 0,25)/(T − 0,25) (Art.239(3)).
_CRM_MATURITY_FLOOR_YEARS = 0.25
# Haircut de change superviseur Hfx par défaut (Art.224) : 8 % (fenêtre 10 j ouvrés).
# Surchargé par le paramètre runtime CRM_FX_HAIRCUT s'il est présent en base.
_CRM_FX_HAIRCUT_DEFAULT = 0.08


def maturity_mismatch_factor(
    exposure_maturity_months: Optional[float],
    protection_maturity_months: Optional[float],
) -> float:
    """Facteur d'ajustement pour asymétrie de maturité (CRR3 Art.239(3)).

    Lorsqu'une protection de crédit a une maturité résiduelle inférieure à celle
    de l'exposition couverte (maturity mismatch), sa valeur reconnue est réduite :

        Pa = P × (t − 0,25) / (T − 0,25)

    avec, exprimés en années :
        T = min(5 ; maturité résiduelle de l'exposition)
        t = min(T ; maturité résiduelle de la protection)

    Règles de reconnaissance (Art.239(2)) :
        - pas d'asymétrie (t ≥ T)            → facteur 1,0 (aucune réduction) ;
        - maturité résiduelle ≤ 3 mois       → facteur 0,0 (non reconnue) ;
        - sinon                              → (t − 0,25)/(T − 0,25), borné [0 ; 1].

    Si l'une des maturités est absente (None) ou ≤ 0, le facteur est 1,0
    (neutre) afin de préserver le comportement antérieur (rétrocompatibilité).

    Paramètres
    ----------
    exposure_maturity_months : float | None    Maturité résiduelle de l'exposition (mois).
    protection_maturity_months : float | None  Maturité résiduelle de la protection (mois).

    Retourne
    --------
    float : facteur multiplicatif ∈ [0 ; 1].
    """
    if exposure_maturity_months is None or protection_maturity_months is None:
        return 1.0
    em = _f(exposure_maturity_months)
    pm = _f(protection_maturity_months)
    if em <= 0 or pm <= 0:
        return 1.0

    T = min(_CRM_MATURITY_CAP_YEARS, em / 12.0)
    t = min(T, pm / 12.0)

    if t >= T:
        # Pas d'asymétrie : la protection couvre au moins l'horizon de l'exposition.
        return 1.0
    if t <= _CRM_MATURITY_FLOOR_YEARS:
        # Maturité résiduelle ≤ 3 mois en présence d'une asymétrie → non reconnue.
        return 0.0

    denom = T - _CRM_MATURITY_FLOOR_YEARS
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, (t - _CRM_MATURITY_FLOOR_YEARS) / denom))


def compute_recognized_fcp_value(
    protection_value: float,
    haircut_rate: Optional[float],
    *,
    fx_mismatch: bool = False,
    fx_haircut: float = 0.0,
    exposure_maturity_months: Optional[float] = None,
    protection_maturity_months: Optional[float] = None,
) -> float:
    """Valeur reconnue d'une FCP après haircuts superviseurs et ajustements CRM.

    Méthode générale ajustée des sûretés (CRR3 Art.223) :

        valeur_ajustée = P × max(0 ; 1 − Hc − Hfx)
        valeur_reconnue = valeur_ajustée × facteur_maturity_mismatch

    où :
        - Hc  : haircut de volatilité du collatéral (règle ref_collateral_haircuts) ;
        - Hfx : haircut de change (Art.224, 8 %) appliqué SI ``fx_mismatch`` ;
        - facteur_maturity_mismatch : ajustement Art.239(3) (cf. helper dédié).

    Exemple : 100 de collatéral, Hc = 15 % → valeur reconnue 85.
    La fonction est bornée à [0, +∞[ pour éviter une EAD négative.

    CORRECTION v3.5.0 (audit ④)
    ----------------------------
    Avant v3.5.0, seul Hc était appliqué : ni le haircut de change Art.224 ni
    l'asymétrie de maturité Art.239 n'étaient pris en compte → valeur de
    collatéral SURESTIMÉE (EAD post-CRM sous-estimée) en cas de mismatch de
    devise ou de maturité.

    RÉTROCOMPATIBILITÉ : les paramètres FX/maturité sont keyword-only et neutres
    par défaut (``fx_mismatch=False``, maturités ``None`` → facteur 1,0), donc
    l'appel historique ``compute_recognized_fcp_value(P, Hc)`` reste identique.
    """
    value = max(0.0, _f(protection_value))
    haircut = max(0.0, min(1.0, _f(haircut_rate or 0.0)))
    hfx = max(0.0, min(1.0, _f(fx_haircut))) if fx_mismatch else 0.0

    # Art.223 / Art.224 — haircuts de volatilité et de change (additifs).
    adjusted = value * max(0.0, 1.0 - haircut - hfx)

    # Art.239(3) — asymétrie de maturité.
    mm = maturity_mismatch_factor(exposure_maturity_months, protection_maturity_months)

    return max(0.0, adjusted * mm)


def compute_recognized_ufcp_value(
    protection_value: float,
    *,
    fx_mismatch: bool = False,
    fx_haircut: float = 0.0,
    exposure_maturity_months: Optional[float] = None,
    protection_maturity_months: Optional[float] = None,
) -> float:
    """Valeur reconnue d'une protection UFCP (garantie) — CRR3 Art.233 / Art.239.

    Pour la protection NON financée (garanties, dérivés de crédit), la valeur
    reconnue G_A est ajustée de deux effets :

        G_A = G × max(0 ; 1 − Hfx) × facteur_maturity_mismatch

    où :
        - Hfx : haircut de change (Art.233(3)) appliqué SI ``fx_mismatch`` — même
          calibrage superviseur que le FCP (8 %, fenêtre 10 jours ouvrés) ;
        - facteur_maturity_mismatch : ajustement Art.239(3) (helper dédié) si la
          maturité résiduelle de la garantie est < celle de l'exposition.

    DIFFÉRENCE AVEC LE FCP (Art.223) — IMPORTANT
    ---------------------------------------------
    La protection UFCP n'a **PAS** de haircut de volatilité Hc : celui-ci est
    propre au COLLATÉRAL FINANCIER (méthode générale ajustée des sûretés, FCP).
    Une garantie n'est donc réduite que par Hfx (mismatch de devise) et par
    l'asymétrie de maturité.

    CORRECTION v3.9.0 (bug 2)
    --------------------------
    Avant v3.9.0, la passe UFCP du moteur standard utilisait la valeur BRUTE de
    la garantie (``protection_value``), ignorant le mismatch de devise (Art.233(3))
    et l'asymétrie de maturité (Art.239) — pourtant déjà gérés pour le FCP depuis
    v3.5.0. Conséquence : garantie en devise étrangère ou de maturité plus courte
    que l'exposition SUR-reconnue → portion substituée trop grande → RWA
    SOUS-ESTIMÉ. Cette fonction rétablit la symétrie de traitement FCP/UFCP.

    RÉTROCOMPATIBILITÉ : sans mismatch de devise (``fx_mismatch=False``) et sans
    asymétrie de maturité (maturités ``None`` ou garantie ≥ exposition → facteur
    1,0), le résultat est exactement ``max(0, protection_value)`` — comportement
    antérieur préservé.
    """
    value = max(0.0, _f(protection_value))
    hfx = max(0.0, min(1.0, _f(fx_haircut))) if fx_mismatch else 0.0

    # Art.233(3) — haircut de change (pas de Hc sur l'unfunded).
    adjusted = value * max(0.0, 1.0 - hfx)

    # Art.239(3) — asymétrie de maturité (commune funded/unfunded).
    mm = maturity_mismatch_factor(exposure_maturity_months, protection_maturity_months)

    return max(0.0, adjusted * mm)


@dataclass(frozen=True)
class FcpHaircutRuleBook:
    """Index normalisé des haircuts FCP, construit une fois par batch.

    Le dictionnaire réduit chaque recherche au seul type de collatéral concerné
    et évite les normalisations de chaînes répétées dans la boucle exposition ×
    protection. Les tuples conservent l'ordre SQL afin de préserver strictement
    la priorité historique en cas de règles de même rang.
    """

    by_collateral_type: dict[
        str,
        tuple[tuple[Optional[str], Optional[str], float], ...],
    ]


def compile_fcp_haircut_rules(haircut_rules: list[dict[str, Any]]) -> FcpHaircutRuleBook:
    """Compile les règles brutes en index immuable et normalisé."""
    grouped: dict[str, list[tuple[Optional[str], Optional[str], float]]] = {}
    for rule in haircut_rules or []:
        collateral_type = str(rule.get("collateral_type") or "").strip().upper()
        if not collateral_type:
            continue
        grade_raw = rule.get("collateral_grade")
        grade = str(grade_raw).strip().upper() if grade_raw not in (None, "") else None
        maturity_raw = rule.get("residual_maturity")
        maturity = str(maturity_raw).strip() if maturity_raw not in (None, "") else None
        grouped.setdefault(collateral_type, []).append((grade, maturity, _f(rule.get("haircut_rate"))))
    return FcpHaircutRuleBook({collateral_type: tuple(rules) for collateral_type, rules in grouped.items()})


def preload_fcp_haircut_rules(db: Database, regulatory_version_id: str) -> FcpHaircutRuleBook:
    """Charge et compile en une seule requête les règles de haircuts FCP actives.

    Correctif performance v6.3.1 : le référentiel est normalisé et indexé une
    seule fois par batch. Le chemin chaud ne rescane plus les autres types de
    collatéral et ne renormalise plus chaque ligne à chaque protection.
    """
    rows = db.query(
        """
        SELECT *
        FROM ref.ref_collateral_haircuts
        WHERE regulatory_version_id = %s
          AND is_active = TRUE
        ORDER BY collateral_type,
                 CASE WHEN collateral_grade IS NULL THEN 1 ELSE 0 END,
                 collateral_grade,
                 CASE WHEN residual_maturity IS NULL THEN 1 ELSE 0 END,
                 residual_maturity
        """,
        (regulatory_version_id,),
    )
    return compile_fcp_haircut_rules(rows)


def lookup_fcp_haircut_rate_from_rules(
    haircut_rules: list[dict[str, Any]] | FcpHaircutRuleBook,
    protection: dict,
) -> float:
    """Recherche le haircut FCP dans des règles préchargées ou compilées.

    La logique de priorité reproduit l'ancien SELECT : correspondance exacte
    type + grade + maturité, puis lignes génériques NULL. Une liste brute reste
    acceptée pour rétrocompatibilité ; le moteur utilise le RuleBook précompilé.
    """
    collateral_type = protection.get("collateral_type") or protection.get("protection_subtype") or ""
    collateral_type = str(collateral_type).strip().upper()
    if not collateral_type:
        return 0.0

    grade = protection.get("collateral_grade")
    grade = str(grade).strip().upper() if grade not in (None, "") else None
    residual_maturity = _maturity_bucket(protection.get("maturity_months"))

    rule_book = (
        haircut_rules if isinstance(haircut_rules, FcpHaircutRuleBook) else compile_fcp_haircut_rules(haircut_rules)
    )
    best: tuple[int, int, float] | None = None
    for rule_grade, rule_maturity, haircut_rate in rule_book.by_collateral_type.get(collateral_type, ()):
        if not (rule_grade == grade or rule_grade is None or grade is None):
            continue
        if not (rule_maturity == residual_maturity or rule_maturity is None or residual_maturity is None):
            continue

        grade_rank = 0 if rule_grade == grade else 1 if rule_grade is None else 2
        maturity_rank = 0 if rule_maturity == residual_maturity else 1 if rule_maturity is None else 2
        candidate = (grade_rank, maturity_rank, haircut_rate)
        if best is None or candidate[:2] < best[:2]:
            best = candidate

    return best[2] if best else 0.0


def lookup_fcp_haircut_rate(db: Database, regulatory_version_id: str, protection: dict) -> float:
    """Recherche rétrocompatible d'un haircut FCP.

    Conservée pour les tests/appels externes historiques. Le moteur standard
    v2.8 utilise ``preload_fcp_haircut_rules`` puis
    ``lookup_fcp_haircut_rate_from_rules`` pour éviter le N+1 SQL.
    """
    return lookup_fcp_haircut_rate_from_rules(
        preload_fcp_haircut_rules(db, regulatory_version_id),
        protection,
    )


def preload_crm_fx_haircut(db: Database, regulatory_version_id: str) -> float:
    """Charge le haircut de change CRM (Art.224) depuis ref_runtime_parameters.

    Lu une seule fois par batch (faible volume, référentiel stable). Si le
    paramètre ``CRM_FX_HAIRCUT`` est absent ou illisible, retombe sur la valeur
    superviseur par défaut de 8 % (Art.224, fenêtre de 10 jours ouvrés).
    """
    rows = db.query(
        """
        SELECT parameter_value
        FROM ref.ref_runtime_parameters
        WHERE regulatory_version_id = %s
          AND parameter_name = 'CRM_FX_HAIRCUT'
        """,
        (regulatory_version_id,),
    )
    if rows:
        try:
            return float(rows[0]["parameter_value"])
        except (TypeError, ValueError, KeyError):
            pass
    return _CRM_FX_HAIRCUT_DEFAULT


@dataclass
class _StandardBuffers:
    results: list[tuple] = field(default_factory=list)
    allocations: list[tuple] = field(default_factory=list)
    decision_traces: list[tuple] = field(default_factory=list)
    supporting_factor_traces: list[tuple] = field(default_factory=list)


@dataclass
class _StandardFallbackStats:
    ccf_count: int = 0
    rw_count: int = 0
    ignored_protection_count: int = 0
    ccf_exposures: list[str] = field(default_factory=list)
    rw_exposures: list[str] = field(default_factory=list)
    ignored_protections: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _StandardRuntime:
    supporting_factor_rules: list[dict[str, Any]]
    protections_by_exposure: dict[str, list[dict[str, Any]]]
    haircut_rules: FcpHaircutRuleBook
    crm_fx_haircut: float


_MAX_LOGGED_FALLBACKS = 50


def _filter_standard_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Conserve les expositions SA et exclut les approches IRB."""
    return [row for row in rows if str(row.get("calculation_approach") or "SA").upper() not in {"IRB-F", "IRB-A"}]


def _truthy_flag(value: Any) -> bool:
    return value if isinstance(value, bool) else str(value).strip().upper() in {"TRUE", "YES", "Y", "1"}


def _sme_totals_by_obligor(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        if not _truthy_flag(row.get("supporting_sme_flag")):
            continue
        net = max(_f(row.get("exposure_amount")) - _f(row.get("provision_amount")), 0.0)
        counterparty_id = str(row.get("counterparty_id") or "")
        totals[counterparty_id] = totals.get(counterparty_id, 0.0) + net
    return totals


def _load_standard_runtime(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    buffers: _StandardBuffers,
) -> _StandardRuntime:
    supporting_factor_rules = db.query(
        """
        SELECT *
        FROM ref.ref_supporting_factor_rules
        WHERE regulatory_version_id = %s
          AND is_active = TRUE
        ORDER BY priority, factor_code
        """,
        (regulatory_version_id,),
    )
    protections = load_all_ranked_protections(
        db,
        batch_id,
        regulatory_version_id,
        trace_buffer=buffers.decision_traces,
    )
    return _StandardRuntime(
        supporting_factor_rules=supporting_factor_rules,
        protections_by_exposure=protections,
        haircut_rules=preload_fcp_haircut_rules(db, regulatory_version_id),
        crm_fx_haircut=preload_crm_fx_haircut(db, regulatory_version_id),
    )


def _remember(identifier: Any, target: list[str]) -> None:
    if len(target) < _MAX_LOGGED_FALLBACKS:
        target.append(str(identifier))


def _resolve_ccf(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    row: dict[str, Any],
    trace_buffer: list[tuple],
    stats: _StandardFallbackStats,
) -> tuple[float, str | None]:
    exposure_id = row["exposure_id"]
    bucket = infer_ccf_bucket(row)
    decision = evaluate_rule_set(
        db,
        batch_id,
        regulatory_version_id,
        "CCF",
        {
            "_context_key": exposure_id,
            "product_type_id": row["product_type_id"],
            "asset_class_id": row["asset_class_id"],
            "counterparty_id": row["counterparty_id"],
            "annex_i_bucket": bucket,
        },
        trace_buffer=trace_buffer,
    )
    if decision:
        return _f(decision["result_value"]), bucket
    bucket_value = ccf_from_annex_i_bucket(bucket)
    if bucket_value is not None:
        return bucket_value, bucket
    stats.ccf_count += 1
    _remember(exposure_id, stats.ccf_exposures)
    logger.warning(
        "FALLBACK CCF=1.0 appliqué à exposure_id=%s (product_type=%s, asset_class=%s) — règle absente.",
        exposure_id,
        row.get("product_type_id"),
        row.get("asset_class_id"),
    )
    return 1.0, bucket


def _resolve_base_risk_weight(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    row: dict[str, Any],
    gross: float,
    provision: float,
    trace_buffer: list[tuple],
    stats: _StandardFallbackStats,
) -> tuple[float, str, float]:
    exposure_id = row["exposure_id"]
    coverage_ratio = provision / gross if gross > 0 else 0.0
    decision = evaluate_rule_set(
        db,
        batch_id,
        regulatory_version_id,
        "RISK_WEIGHT",
        {
            "_context_key": exposure_id,
            "counterparty_id": row["counterparty_id"],
            "asset_class_id": row["asset_class_id"],
            "credit_quality_step": row.get("credit_quality_step"),
            "ltv_ratio": row.get("ltv_ratio"),
            "exposure_subtype": row.get("exposure_subtype"),
            "institution_scra_grade": row.get("institution_scra_grade"),
            "short_term_exposure_flag": _to_flag(row.get("short_term_exposure_flag")),
            "adc_flag": _to_flag(row.get("adc_flag")),
            "ipre_flag": _to_flag(row.get("ipre_flag")),
            "transactor_flag": _to_flag(row.get("transactor_flag")),
            "provision_coverage_ratio": coverage_ratio,
            "delinquent_flag": _to_flag(row.get("delinquent_flag")),
        },
        trace_buffer=trace_buffer,
    )
    if decision:
        base_rw = _f(decision["result_value"])
    else:
        base_rw = 1.0
        stats.rw_count += 1
        _remember(exposure_id, stats.rw_exposures)
        logger.warning(
            "FALLBACK RW=100%% appliqué à exposure_id=%s (asset_class=%s, counterparty=%s, CQS=%s) — règle absente.",
            exposure_id,
            row.get("asset_class_id"),
            row.get("counterparty_id"),
            row.get("credit_quality_step"),
        )
    mismatch = is_currency_mismatch_exposure(row)
    adjusted_rw = apply_currency_mismatch_multiplier(base_rw, mismatch)
    bucket = "CURRENCY_MISMATCH" if mismatch else infer_rw_bucket(row, adjusted_rw)
    return adjusted_rw, bucket, 1.5 if mismatch else 1.0


def _partition_protections(
    protections: list[dict[str, Any]],
    exposure_id: Any,
    stats: _StandardFallbackStats,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    funded: list[dict[str, Any]] = []
    unfunded: list[dict[str, Any]] = []
    for protection in protections:
        protection_type = str(protection.get("protection_type") or "").strip().upper()
        if protection_type == "FCP":
            funded.append(protection)
        elif protection_type == "UFCP":
            unfunded.append(protection)
        else:
            stats.ignored_protection_count += 1
            _remember(protection.get("protection_id"), stats.ignored_protections)
            logger.warning(
                "CRM — protection ignorée (type=%r), exposure_id=%s, protection_id=%s.",
                protection.get("protection_type"),
                exposure_id,
                protection.get("protection_id"),
            )
    return funded, unfunded


def _currency_mismatch(exposure: dict[str, Any], protection: dict[str, Any]) -> bool:
    exposure_currency = str(exposure.get("currency") or "").strip().upper()
    protection_currency = str(protection.get("currency") or "").strip().upper()
    return bool(exposure_currency and protection_currency and exposure_currency != protection_currency)


def _crm_effect(prefix: str, *, fx_mismatch: bool, maturity_factor: float) -> str:
    effect = prefix
    if fx_mismatch:
        effect += "_FX"
    if maturity_factor < 1.0:
        effect += "_MMM"
    return effect


def _apply_funded_protections(
    row: dict[str, Any],
    protections: list[dict[str, Any]],
    ead_pre_crm: float,
    runtime: _StandardRuntime,
    batch_id: str,
    allocations: list[tuple],
) -> tuple[float, float]:
    ead_after_fcp = ead_pre_crm
    total_fcp = 0.0
    exposure_id = row["exposure_id"]
    for protection in protections:
        haircut_rate = lookup_fcp_haircut_rate_from_rules(runtime.haircut_rules, protection)
        mismatch = _currency_mismatch(row, protection)
        maturity_factor = maturity_mismatch_factor(row.get("maturity_months"), protection.get("maturity_months"))
        recognized_value = compute_recognized_fcp_value(
            _f(protection.get("protection_value")),
            haircut_rate,
            fx_mismatch=mismatch,
            fx_haircut=runtime.crm_fx_haircut,
            exposure_maturity_months=row.get("maturity_months"),
            protection_maturity_months=protection.get("maturity_months"),
        )
        cover = min(ead_after_fcp, recognized_value)
        ead_after_fcp -= cover
        total_fcp += cover
        allocations.append(
            (
                batch_id,
                exposure_id,
                protection.get("protection_id"),
                protection.get("bucket") or "DEFAULT",
                cover,
                _crm_effect("EAD_REDUCTION_HAIRCUT", fx_mismatch=mismatch, maturity_factor=maturity_factor),
            )
        )
    return ead_after_fcp, total_fcp


def _apply_unfunded_protections(
    db: Database,
    row: dict[str, Any],
    protections: list[dict[str, Any]],
    ead_after_fcp: float,
    base_rw: float,
    runtime: _StandardRuntime,
    batch_id: str,
    regulatory_version_id: str,
    buffers: _StandardBuffers,
) -> tuple[float, float]:
    exposure_id = row["exposure_id"]
    residual_ead = max(0.0, ead_after_fcp)
    substituted_rwa = 0.0
    for protection in protections:
        mismatch = _currency_mismatch(row, protection)
        maturity_factor = maturity_mismatch_factor(row.get("maturity_months"), protection.get("maturity_months"))
        recognized_value = compute_recognized_ufcp_value(
            _f(protection.get("protection_value")),
            fx_mismatch=mismatch,
            fx_haircut=runtime.crm_fx_haircut,
            exposure_maturity_months=row.get("maturity_months"),
            protection_maturity_months=protection.get("maturity_months"),
        )
        decision = evaluate_rule_set(
            db,
            batch_id,
            regulatory_version_id,
            "SUBSTITUTION_RISK_WEIGHT",
            {
                "_context_key": f"{exposure_id}:{protection.get('protection_id')}",
                "provider_type": protection.get("provider_type"),
                "protection_type": protection.get("protection_type"),
            },
            trace_buffer=buffers.decision_traces,
        )
        raw_provider_rw = decision.get("result_value") if decision else None
        provider_rw = _f(raw_provider_rw) if raw_provider_rw is not None else None
        guarantee, rwa_increment, residual_ead = apply_ufcp_partial_substitution(
            ead_at_obligor_rw=residual_ead,
            base_rw=base_rw,
            rw_provider=provider_rw,
            protection_value=recognized_value,
        )
        substituted_rwa += rwa_increment
        buffers.allocations.append(
            (
                batch_id,
                exposure_id,
                protection.get("protection_id"),
                protection.get("bucket") or "DEFAULT",
                guarantee,
                _crm_effect("RW_SUBSTITUTION", fx_mismatch=mismatch, maturity_factor=maturity_factor),
            )
        )
    return residual_ead, substituted_rwa


def _build_standard_result(
    row: dict[str, Any],
    *,
    batch_id: str,
    gross: float,
    provision: float,
    ead_pre_crm: float,
    ead_after_fcp: float,
    total_fcp: float,
    base_rw: float,
    substituted_rw: float,
    rwa_pre_supporting: float,
    supporting_factor_result: dict[str, Any],
    ccf: float,
    ccf_bucket: str | None,
    rw_bucket: str,
    currency_mismatch_multiplier: float,
    ead_after_ufcp: float,
) -> tuple:
    rwa_final = supporting_factor_result["rwa_final"]
    return (
        batch_id,
        row["exposure_id"],
        row["counterparty_id"],
        row["asset_class_id"],
        row["product_type_id"],
        gross,
        provision,
        ead_pre_crm,
        ead_after_fcp,
        total_fcp,
        base_rw,
        substituted_rw,
        rwa_pre_supporting,
        supporting_factor_result["multiplier_final"],
        supporting_factor_result["factor_codes"],
        rwa_final,
        ccf,
        ccf_bucket,
        "DECISION_ENGINE",
        rw_bucket,
        row.get("credit_quality_step"),
        ltv_bucket(row.get("ltv_ratio")),
        currency_mismatch_multiplier,
        ead_after_ufcp,
        rwa_pre_supporting,
        rwa_final * 0.08,
    )


def _process_standard_exposure(
    db: Database,
    row: dict[str, Any],
    *,
    batch_id: str,
    regulatory_version_id: str,
    runtime: _StandardRuntime,
    buffers: _StandardBuffers,
    stats: _StandardFallbackStats,
    sme_total_exposure: float,
) -> tuple:
    gross = _f(row["exposure_amount"])
    provision = _f(row["provision_amount"])
    net = max(gross - provision, 0.0)
    ccf, ccf_bucket = _resolve_ccf(db, batch_id, regulatory_version_id, row, buffers.decision_traces, stats)
    base_rw, rw_bucket, mismatch_multiplier = _resolve_base_risk_weight(
        db,
        batch_id,
        regulatory_version_id,
        row,
        gross,
        provision,
        buffers.decision_traces,
        stats,
    )
    ead_pre_crm = net * ccf
    funded, unfunded = _partition_protections(
        runtime.protections_by_exposure.get(str(row["exposure_id"]), []),
        row["exposure_id"],
        stats,
    )
    ead_after_fcp, total_fcp = _apply_funded_protections(
        row, funded, ead_pre_crm, runtime, batch_id, buffers.allocations
    )
    ead_after_ufcp, substituted_rwa = _apply_unfunded_protections(
        db,
        row,
        unfunded,
        ead_after_fcp,
        base_rw,
        runtime,
        batch_id,
        regulatory_version_id,
        buffers,
    )
    rwa_pre_supporting = substituted_rwa + ead_after_ufcp * base_rw
    substituted_rw = rwa_pre_supporting / ead_after_fcp if ead_after_fcp > 0 else base_rw
    supporting_factor_result = apply_supporting_factors(
        db=db,
        batch_id=batch_id,
        regulatory_version=regulatory_version_id,
        exposure_row=row,
        rwa_pre_supporting=rwa_pre_supporting,
        preloaded_rules=runtime.supporting_factor_rules,
        trace_buffer=buffers.supporting_factor_traces,
        sme_total_exposure=sme_total_exposure,
    )
    return _build_standard_result(
        row,
        batch_id=batch_id,
        gross=gross,
        provision=provision,
        ead_pre_crm=ead_pre_crm,
        ead_after_fcp=ead_after_fcp,
        total_fcp=total_fcp,
        base_rw=base_rw,
        substituted_rw=substituted_rw,
        rwa_pre_supporting=rwa_pre_supporting,
        supporting_factor_result=supporting_factor_result,
        ccf=ccf,
        ccf_bucket=ccf_bucket,
        rw_bucket=rw_bucket,
        currency_mismatch_multiplier=mismatch_multiplier,
        ead_after_ufcp=ead_after_ufcp,
    )


def _standard_control_metrics(batch_id: str, stats: _StandardFallbackStats) -> list[tuple]:
    metrics: list[tuple] = []
    if stats.ccf_count > 0 or stats.rw_count > 0:
        metrics.extend(
            [
                (batch_id, "SA_CCF_FALLBACK_HITS", stats.ccf_count),
                (batch_id, "SA_RW_FALLBACK_HITS", stats.rw_count),
            ]
        )
    if stats.ignored_protection_count > 0:
        metrics.append((batch_id, "SA_CRM_IGNORED_PROTECTIONS", stats.ignored_protection_count))
    return metrics


def _persist_standard_batches(
    db: Database,
    batch_id: str,
    buffers: _StandardBuffers,
    stats: _StandardFallbackStats,
) -> None:
    with db.transaction():
        if buffers.results:
            db.executemany(
                """
                INSERT INTO core.core_standard_results (
                    batch_id, exposure_id, counterparty_id, asset_class_id, product_type_id,
                    gross_exposure, provision_amount, ead_pre_crm, ead_post_fcp, total_fcp_allocated,
                    risk_weight_base, risk_weight_substituted, rwa_post_crm, supporting_factor_multiplier,
                    supporting_factor_codes, rwa_final,
                    ccf_applied, ccf_bucket, rw_rule_source, rw_bucket, cqs_used, ltv_bucket,
                    currency_mismatch_multiplier, ead_after_ufcp, rwa_before_supporting_factor,
                    capital_requirement_8pct
                ) VALUES %s
                """,
                buffers.results,
            )
        if buffers.allocations:
            db.executemany(
                """
                INSERT INTO core.core_protection_allocation (
                    batch_id, exposure_id, protection_id, bucket, allocated_amount, effect_type
                ) VALUES %s
                """,
                buffers.allocations,
            )
        if buffers.supporting_factor_traces:
            db.executemany(
                """
                INSERT INTO rpt.rpt_supporting_factor_trace (
                    batch_id, exposure_id, factor_rule_id, multiplier, applied_metric,
                    rwa_before, rwa_after
                ) VALUES %s
                """,
                buffers.supporting_factor_traces,
            )
        flush_trace_buffer(db, buffers.decision_traces)
        metrics = _standard_control_metrics(batch_id, stats)
        if metrics:
            db.executemany(
                """
                INSERT INTO rpt.rpt_controls (batch_id, control_name, control_value)
                VALUES %s
                ON CONFLICT (batch_id, control_name) DO UPDATE
                  SET control_value = EXCLUDED.control_value
                """,
                metrics,
            )


def _report_standard_anomalies(
    stats: _StandardFallbackStats,
    result_count: int,
    strict_fallback_mode: bool,
) -> None:
    if stats.ccf_count > 0 or stats.rw_count > 0:
        logger.warning(
            "Standard engine — %d fallback(s) CCF + %d fallback(s) RW sur %d expositions; CCF=%s; RW=%s.",
            stats.ccf_count,
            stats.rw_count,
            result_count,
            stats.ccf_exposures[:5] or "(aucun)",
            stats.rw_exposures[:5] or "(aucun)",
        )
        if strict_fallback_mode:
            raise RuntimeError(
                "strict_fallback_mode=True : "
                f"{stats.ccf_count} fallback(s) CCF et {stats.rw_count} fallback(s) RW détectés."
            )
    if stats.ignored_protection_count > 0:
        logger.warning(
            "Standard engine — %d protection(s) CRM ignorée(s); protection_id=%s.",
            stats.ignored_protection_count,
            stats.ignored_protections[:5] or "(aucun)",
        )


def run_standard_engine(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    reporting_date: str,
    strict_fallback_mode: bool = False,
) -> int:
    """Exécute le calcul SA par phases isolées et testables.

    La signature et les écritures SQL restent compatibles avec la v6.0.1.
    ``reporting_date`` est conservé dans le contrat public, même si le schéma
    normalisé porte la date au niveau du batch.
    """
    del reporting_date
    clear_rules_cache()
    db.execute("DELETE FROM core.core_standard_results WHERE batch_id = %s", (batch_id,))
    db.execute("DELETE FROM core.core_protection_allocation WHERE batch_id = %s", (batch_id,))
    db.execute("DELETE FROM rpt.rpt_supporting_factor_trace WHERE batch_id = %s", (batch_id,))
    rows = _filter_standard_rows(db.query("SELECT * FROM stg.stg_exposures WHERE batch_id = %s", (batch_id,)))
    buffers = _StandardBuffers()
    stats = _StandardFallbackStats()
    runtime = _load_standard_runtime(db, batch_id, regulatory_version_id, buffers)
    sme_totals = _sme_totals_by_obligor(rows)
    for row in rows:
        buffers.results.append(
            _process_standard_exposure(
                db,
                row,
                batch_id=batch_id,
                regulatory_version_id=regulatory_version_id,
                runtime=runtime,
                buffers=buffers,
                stats=stats,
                sme_total_exposure=sme_totals.get(str(row.get("counterparty_id") or ""), 0.0),
            )
        )
    _persist_standard_batches(db, batch_id, buffers, stats)
    _report_standard_anomalies(stats, len(buffers.results), strict_fallback_mode)
    return len(buffers.results)
