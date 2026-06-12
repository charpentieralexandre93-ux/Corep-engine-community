"""
================================================================================
MODULE  : standard_engine.py
PROJET  : COREP Engine CRR3
VERSION : 4.4.2
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
         REVOCABLE_COMMIT  → CCF = 0.0  (irrévocable uniquement)
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
from typing import Optional
from .db import Database
from .decision_engine import evaluate_rule_set, flush_trace_buffer, clear_rules_cache
from .protection_strategy import load_all_ranked_protections
from .supporting_factors import apply_supporting_factors
from .utils import to_float as _f

# v3.6.0 — Robustesse : `logger` était utilisé (warnings de fallback CCF/RW,
# protections CRM ignorées) mais n'était JAMAIS défini au niveau module → tout
# chemin de warning levait NameError. On le définit selon la convention projet.
logger = logging.getLogger(__name__)


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
    base_rw_f     = _f(base_rw)
    ead_rest      = _f(ead_at_obligor_rw)

    if rw_provider_f >= base_rw_f:
        return (0.0, 0.0, ead_rest)

    # EAD encore disponible déjà épuisée (toutes les UFCP précédentes
    # ont consommé toute la portion garantissable) → pas de substitution
    # supplémentaire pour cette protection.
    if ead_rest <= 0.0:
        return (0.0, 0.0, ead_rest)

    guarantee_amount = min(ead_rest, max(0.0, _f(protection_value)))
    rwa_increment    = guarantee_amount * rw_provider_f
    new_ead          = ead_rest - guarantee_amount
    return (guarantee_amount, rwa_increment, new_ead)


def _to_flag(value) -> str:
    """Normalise les booléens du staging pour les règles BCNF (= TRUE/FALSE)."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    text = str(value or "").strip().upper()
    return "TRUE" if text in {"1", "TRUE", "T", "Y", "YES", "O", "OUI"} else "FALSE"


def _maturity_bucket(months) -> Optional[str]:
    """Convertit une maturité en mois en bucket de haircut superviseur."""
    try:
        m = float(months)
    except Exception:
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


def preload_fcp_haircut_rules(db: Database, regulatory_version_id: str) -> list[dict]:
    """Charge en une seule requête les règles de haircuts FCP actives.

    Correctif performance v2.8 — suppression du N+1 haircut.
    Les haircuts sont un référentiel stable et faible volume : ils doivent être
    lus une seule fois par batch, pas à chaque protection FCP.
    """
    return db.query(
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


def lookup_fcp_haircut_rate_from_rules(haircut_rules: list[dict], protection: dict) -> float:
    """Recherche le haircut FCP dans des règles préchargées.

    La logique de priorité reproduit l'ancien SELECT :
    correspondance exacte type + grade + maturité, puis lignes génériques NULL.
    En absence de type de collatéral, fallback 0 % pour compatibilité historique.
    """
    collateral_type = (protection.get("collateral_type") or protection.get("protection_subtype") or "")
    collateral_type = str(collateral_type).strip().upper()
    if not collateral_type:
        return 0.0

    grade = protection.get("collateral_grade")
    grade = str(grade).strip().upper() if grade not in (None, "") else None
    residual_maturity = _maturity_bucket(protection.get("maturity_months"))

    best: tuple[int, int, dict] | None = None
    for rule in haircut_rules or []:
        if str(rule.get("collateral_type") or "").strip().upper() != collateral_type:
            continue

        rule_grade_raw = rule.get("collateral_grade")
        rule_grade = str(rule_grade_raw).strip().upper() if rule_grade_raw not in (None, "") else None
        if not (rule_grade == grade or rule_grade is None or grade is None):
            continue

        rule_maturity_raw = rule.get("residual_maturity")
        rule_maturity = str(rule_maturity_raw).strip() if rule_maturity_raw not in (None, "") else None
        if not (rule_maturity == residual_maturity or rule_maturity is None or residual_maturity is None):
            continue

        grade_rank = 0 if rule_grade == grade else 1 if rule_grade is None else 2
        maturity_rank = 0 if rule_maturity == residual_maturity else 1 if rule_maturity is None else 2
        candidate = (grade_rank, maturity_rank, rule)
        if best is None or candidate[:2] < best[:2]:
            best = candidate

    return _f(best[2].get("haircut_rate")) if best else 0.0


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


def run_standard_engine(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    reporting_date: str,
    strict_fallback_mode: bool = False,
) -> int:
    """Exécute le calcul SA (Approche Standard) pour toutes les expositions du batch.

    Traite chaque exposition de stg.stg_exposures selon la séquence CRR3 :
    CCF → EAD pré-CRM → CRM (FCP/UFCP) → RW → RWA → Supporting Factors.

    Paramètres
    ----------
    db : Database
        Instance de connexion PostgreSQL active.
    batch_id : str
        Identifiant UUID du batch courant.
    regulatory_version_id : str
        Version réglementaire active (ex. "CRR3_V9").
    reporting_date : str
        Date de reporting au format ISO (ex. "2026-03-31").
        Stockée dans core_standard_results pour le partitionnement.
    strict_fallback_mode : bool (v3.3.0)
        Si True, lève RuntimeError dès qu'un fallback CCF=1.0 ou RW=100% est
        appliqué — utile pour les déploiements de production où l'absence
        d'une règle est une erreur métier qui doit faire échouer le batch.
        Si False (défaut), les fallbacks sont autorisés mais comptés et
        loggés en WARNING (avec exposure_id).

    Retourne
    --------
    int
        Nombre d'expositions traitées et insérées dans core.core_standard_results.

    Performances
    ------------
    - 1 seule transaction pour tous les INSERTs (results + allocations + traces)
    - 0 requête SQL dans la boucle principale (cache règles + buffer traces)
    - Pré-chargement des règles SF avant la boucle (1 SELECT au lieu de N)
    """
    # ── Vider le cache de règles (règles fraîches pour ce batch) ───────────────
    # Garantit que les règles rechargées correspondent bien à la version active.
    clear_rules_cache()

    # ── Nettoyage des tables (idempotence — re-run du même batch) ──────────────
    db.execute("DELETE FROM core.core_standard_results           WHERE batch_id = %s", (batch_id,))
    db.execute("DELETE FROM core.core_protection_allocation       WHERE batch_id = %s", (batch_id,))
    db.execute("DELETE FROM rpt.rpt_supporting_factor_trace       WHERE batch_id = %s", (batch_id,))
    # Note : rpt_decision_rule_trace n'est PAS nettoyé ici — d'autres engines
    # peuvent aussi écrire dans cette table pour le même batch.

    # ── Chargement des expositions depuis le staging ───────────────────────────
    rows = db.query("SELECT * FROM stg.stg_exposures WHERE batch_id = %s", (batch_id,))

    # ── Routage par approche prudentielle (CRR3 Art.142) ───────────────────────
    # SA ne traite QUE les expositions standard. Les expositions IRB-F / IRB-A
    # sont traitées par irb_engine (édition enterprise). Filtre Python plutôt que
    # SQL : `.get` tolère l'absence de la colonne calculation_approach (édition
    # community SA/SA-CCR, où elle n'existe pas) -> None -> traitée en SA. Empeche
    # tout double comptage SA/IRB sans rendre la colonne obligatoire.
    rows = [
        r for r in rows
        if str(r.get("calculation_approach") or "SA").upper() not in ("IRB-F", "IRB-A")
    ]

    # ── Pré-chargement des règles Supporting Factors (CORRECTION v4) ──────────
    # AVANT : apply_supporting_factors() chargeait les règles depuis la base
    #         à CHAQUE appel → N SELECT identiques dans la boucle.
    # APRÈS : 1 seul SELECT avant la boucle, résultat passé via preloaded_rules.
    sf_rules = db.query(
        """
        SELECT *
        FROM ref.ref_supporting_factor_rules
        WHERE regulatory_version_id = %s
          AND is_active = TRUE
        ORDER BY priority, factor_code
        """,
        (regulatory_version_id,),
    )

    # ── Initialisation des buffers d'insertion ──────────────────────────────────
    results_batch:     list[tuple] = []   # core_standard_results
    allocations_batch: list[tuple] = []   # core_protection_allocation
    trace_buffer:      list[tuple] = []   # rpt_decision_rule_trace (flush groupé)
    sf_trace_buffer:   list[tuple] = []   # rpt_supporting_factor_trace (flush global)

    # ── v3.3.0 (point 5 audit) — Compteurs explicites de fallbacks ──────────
    # Avant v3.3.0 : si aucune règle ne matchait pour CCF ou RW, on retombait
    # silencieusement sur CCF=1.0 (bilan) et RW=100% (prudentiel). Ces
    # fallbacks sont CORRECTS sur le plan prudentiel mais MASQUENT un manque
    # de seed que l'utilisateur doit savoir corriger. La v3.3.0 :
    #   - logue un WARNING avec l'exposure_id à chaque hit ;
    #   - compte les hits dans rpt.rpt_controls (SA_CCF_FALLBACK_HITS / SA_RW_FALLBACK_HITS) ;
    #   - permet un mode strict (échec batch) via config runtime.strict_fallback_mode.
    ccf_fallback_count: int = 0
    rw_fallback_count: int  = 0
    ccf_fallback_exposures: list[str] = []   # capture des 50 premiers pour log
    rw_fallback_exposures:  list[str] = []   # idem
    MAX_LOGGED_FALLBACKS = 50

    # ── v3.6.0 — Robustesse CRM : observabilité des protections ignorées ─────
    # Une protection dont le type n'est ni FCP ni UFCP (NULL, faute de frappe,
    # type non géré) était auparavant SILENCIEUSEMENT ignorée dans la boucle CRM
    # (aucun effet, aucune trace) → risque de RWA erroné non détecté. On compte
    # et on loggue désormais ces cas.
    crm_ignored_protection_count: int = 0
    crm_ignored_protections: list[str] = []   # capture des 50 premiers pour log

    # ── Préchargements CRM performance v2.8 ─────────────────────────────────
    # 1 SELECT toutes protections, au lieu de 1 SELECT par exposition.
    protections_by_exposure = load_all_ranked_protections(
        db, batch_id, regulatory_version_id, trace_buffer=trace_buffer
    )
    # 1 SELECT référentiel haircuts, au lieu de 1 SELECT par protection FCP.
    haircut_rules = preload_fcp_haircut_rules(db, regulatory_version_id)
    # v3.5.0 (audit ④) — haircut de change CRM (Art.224) préchargé une fois.
    crm_fx_haircut = preload_crm_fx_haircut(db, regulatory_version_id)

    # ── v3.4.0 (audit ⑤) — Pré-agrégation E* du SME Supporting Factor two-tier ──
    # Art.501(1) : le seuil de 2,5 M€ (tranche 0,7619 / 0,85) s'apprécie sur
    # l'exposition TOTALE envers la PME (par obligor / groupe de clients liés),
    # et non exposition par exposition. On somme donc l'exposition nette
    # (brut − provisions) des expositions marquées PME-éligibles, par contrepartie.
    # Le facteur mélangé obtenu est ensuite appliqué uniformément au RWA de
    # chacune des expositions de l'obligor (cf. supporting_factors.sme_blended_factor).
    def _is_truthy_flag(v) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).strip().upper() in ("TRUE", "YES", "Y", "1")

    sme_total_by_obligor: dict[str, float] = {}
    for _row in rows:
        if _is_truthy_flag(_row.get("supporting_sme_flag")):
            _net = max(_f(_row.get("exposure_amount")) - _f(_row.get("provision_amount")), 0.0)
            _cp  = _row.get("counterparty_id")
            sme_total_by_obligor[_cp] = sme_total_by_obligor.get(_cp, 0.0) + _net

    # ── BOUCLE PRINCIPALE — une iteration par exposition ────────────────────────
    for r in rows:
        exposure_id = r["exposure_id"]

        # ── ÉTAPE 1 : Calcul du net après provisions ────────────────────────────
        gross = _f(r["exposure_amount"])             # Montant brut déclaré
        prov  = _f(r["provision_amount"])            # Provisions spécifiques
        net   = max(gross - prov, 0.0)               # Net = max(brut − provisions, 0)
        # Art.110 CRR3 : l'EAD ne peut être négative

        # ── ÉTAPE 2 : CCF — Credit Conversion Factor (Art.111 CRR3) ─────────────
        # Le CCF convertit un engagement hors-bilan en équivalent bilan.
        # Déterminé par le moteur de décision selon product_type_id.
        ccf_decision = evaluate_rule_set(
            db, batch_id, regulatory_version_id, "CCF",
            {
                "_context_key":    exposure_id,
                "product_type_id": r["product_type_id"],
                "asset_class_id":  r["asset_class_id"],
                "counterparty_id": r["counterparty_id"],
            },
            trace_buffer=trace_buffer,
        )
        if ccf_decision:
            ccf = _f(ccf_decision["result_value"])
        else:
            # v3.3.0 (point 5) — Fallback explicite avec log + comptage
            ccf = 1.0   # bilan = 100% (correctif prudentiel CRR3 Art.111)
            ccf_fallback_count += 1
            if len(ccf_fallback_exposures) < MAX_LOGGED_FALLBACKS:
                ccf_fallback_exposures.append(str(exposure_id))
                logger.warning(
                    "FALLBACK CCF=1.0 appliqué à exposure_id=%s (product_type=%s, "
                    "asset_class=%s) — aucune règle ref_decision_rules ne correspond. "
                    "Compléter le seed CCF pour éviter ce fallback.",
                    exposure_id, r.get("product_type_id"), r.get("asset_class_id"),
                )

        # ── ÉTAPE 3 : Risk Weight de base (Art.114-136 CRR3) ──────────────────
        provision_coverage_ratio = (prov / gross) if gross > 0 else 0.0
        rw_decision = evaluate_rule_set(
            db, batch_id, regulatory_version_id, "RISK_WEIGHT",
            {
                "_context_key":             exposure_id,
                "counterparty_id":          r["counterparty_id"],
                "asset_class_id":           r["asset_class_id"],
                "credit_quality_step": r.get("credit_quality_step"),
                "ltv_ratio":                r.get("ltv_ratio"),
                "exposure_subtype":         r.get("exposure_subtype"),
                "provision_coverage_ratio": provision_coverage_ratio,
                "delinquent_flag":          _to_flag(r.get("delinquent_flag")),
            },
            trace_buffer=trace_buffer,
        )
        if rw_decision:
            base_rw = _f(rw_decision["result_value"])
        else:
            # v3.3.0 (point 5) — Fallback explicite avec log + comptage
            base_rw = 1.0   # 100% prudentiel maximum (correctif CRR3 Art.114-136)
            rw_fallback_count += 1
            if len(rw_fallback_exposures) < MAX_LOGGED_FALLBACKS:
                rw_fallback_exposures.append(str(exposure_id))
                logger.warning(
                    "FALLBACK RW=100%% appliqué à exposure_id=%s (asset_class=%s, "
                    "counterparty=%s, CQS=%s) — aucune règle ref_decision_rules ne "
                    "correspond. Compléter le seed RISK_WEIGHT pour éviter ce fallback.",
                    exposure_id, r.get("asset_class_id"), r.get("counterparty_id"),
                    r.get("credit_quality_step"),
                )

        # ── CALCUL DE L'EAD PRÉ-CRM ────────────────────────────────────────────
        ead_pre_crm   = net * ccf          # EAD avant atténuation du risque de crédit
        ead_after_fcp = ead_pre_crm        # EAD courante (réduite par les FCP successifs)
        total_fcp      = 0.0               # Cumul des montants FCP alloués

        # ── ÉTAPE 4 : CRM — Techniques d'atténuation (Art.193-241 CRR3) ─────────
        # Correctif v2.8 : protections préchargées une fois par batch.
        protections = protections_by_exposure.get(str(exposure_id), [])

        # ── État UFCP — Substitution PARTIELLE Art.235 CRR3 (PATCH v9) ─────────
        # AVANT : substituted_rw = min(rw_obligor, rw_provider) appliqué à
        #         l'EAD ENTIÈRE → biais favorable pour UFCP partielles + un
        #         seul RW garant retenu pour UFCP multiples (cf. helper).
        # APRÈS : on suit explicitement la portion résiduelle au RW obligor
        #         et on accumule le RWA des portions garanties.
        ead_at_obligor_rw    = ead_after_fcp   # portion encore au RW de l'obligor
        rwa_substituted_acc  = 0.0             # cumul RWA des portions garanties
        # Plus petit RW garant rencontré — utile uniquement pour le rapport
        # (colonne risk_weight_substituted historique). Le calcul du RWA
        # passe désormais par la formule Art.235.
        min_provider_rw      = base_rw

        # ── v3.7.0 — Séquencement CRR funded → unfunded (indépendant du rang) ──
        # La méthode générale ajustée des sûretés impose que le collatéral FUNDED
        # (FCP) réduise l'exposition AVANT la substitution UNFUNDED (UFCP). On
        # partitionne donc les protections en DEUX passes, en CONSERVANT l'ordre
        # allocation_rank À L'INTÉRIEUR de chaque groupe (la liste `protections`
        # est déjà triée par rang). Avant v3.7.0, un parcours unique en ordre
        # allocation_rank rendait le RWA DÉPENDANT DE L'ORDRE : si une UFCP
        # précédait une FCP, la garantie était substituée sur la base PRÉ-FCP,
        # d'où un double comptage de l'exposition (RWA conservateur mais erroné).
        #
        # Robustesse v3.6.0 conservée : accès défensifs .get + normalisation du
        # type (un "fcp" / " UFCP " n'est plus silencieusement ignoré) ; un type
        # non géré est ignoré mais compté/logué.
        fcp_protections:  list[dict] = []
        ufcp_protections: list[dict] = []
        for p in protections:
            ptype = str(p.get("protection_type") or "").strip().upper()
            if ptype == "FCP":
                fcp_protections.append(p)
            elif ptype == "UFCP":
                ufcp_protections.append(p)
            else:
                crm_ignored_protection_count += 1
                if len(crm_ignored_protections) < MAX_LOGGED_FALLBACKS:
                    crm_ignored_protections.append(str(p.get("protection_id")))
                    logger.warning(
                        "CRM — protection ignorée (type non géré : %r) pour "
                        "exposure_id=%s, protection_id=%s. Types attendus : "
                        "FCP ou UFCP. Vérifier stg.stg_protections.protection_type.",
                        p.get("protection_type"), exposure_id, p.get("protection_id"),
                    )

        # ── PASSE 1/2 : FCP (Funded Credit Protection) — réduction d'EAD ───────
        for p in fcp_protections:
            value         = _f(p.get("protection_value"))
            protection_id = p.get("protection_id")
            bucket        = p.get("bucket") or "DEFAULT"

            # v2.8 : valeur reconnue = valeur brute × (1 − haircut volatilité).
            # v3.5.0 (audit ④) : haircut de change Hfx (Art.224) si mismatch de
            #   devise, et ajustement maturity mismatch (Art.239) si maturité de
            #   protection < maturité d'exposition.
            haircut_rate = lookup_fcp_haircut_rate_from_rules(haircut_rules, p)

            exp_ccy  = (str(r.get("currency")).strip().upper() if r.get("currency") else None)
            prot_ccy = (str(p.get("currency")).strip().upper() if p.get("currency") else None)
            fx_mismatch = bool(exp_ccy and prot_ccy and exp_ccy != prot_ccy)

            mm_factor = maturity_mismatch_factor(
                r.get("maturity_months"), p.get("maturity_months")
            )

            recognized_value = compute_recognized_fcp_value(
                value, haircut_rate,
                fx_mismatch=fx_mismatch,
                fx_haircut=crm_fx_haircut,
                exposure_maturity_months=r.get("maturity_months"),
                protection_maturity_months=p.get("maturity_months"),
            )
            cover = min(ead_after_fcp, recognized_value)
            ead_after_fcp -= cover
            # Les FCP étant traités AVANT les UFCP, la portion substituable suit
            # désormais directement l'EAD post-FCP (plus de dépendance à l'ordre).
            ead_at_obligor_rw = min(ead_at_obligor_rw, ead_after_fcp)
            total_fcp += cover

            effect_type = "EAD_REDUCTION_HAIRCUT"
            if fx_mismatch:
                effect_type += "_FX"
            if mm_factor < 1.0:
                effect_type += "_MMM"
            allocations_batch.append((
                batch_id, exposure_id, protection_id,
                bucket, cover, effect_type,
            ))

        # ── PASSE 2/2 : UFCP (Unfunded) — substitution Art.235 sur l'EAD post-FCP ─
        # Garde-fou v3.7.0 : la base substituable ne peut ni dépasser l'EAD
        # post-FCP ni être négative (robustesse contre une EAD/base incohérente).
        ead_at_obligor_rw = max(0.0, min(ead_at_obligor_rw, ead_after_fcp))
        for p in ufcp_protections:
            value_raw     = _f(p.get("protection_value"))
            protection_id = p.get("protection_id")
            bucket        = p.get("bucket") or "DEFAULT"

            # ── v3.9.0 (bug 2) — Ajustements CRM de la garantie UFCP ───────────
            # Mismatch de devise (Art.233(3), haircut Hfx) et asymétrie de maturité
            # (Art.239) — symétrie de traitement avec le FCP (v3.5.0). Pas de
            # haircut de volatilité Hc (réservé au collatéral financier).
            exp_ccy  = (str(r.get("currency")).strip().upper() if r.get("currency") else None)
            prot_ccy = (str(p.get("currency")).strip().upper() if p.get("currency") else None)
            fx_mismatch = bool(exp_ccy and prot_ccy and exp_ccy != prot_ccy)
            mm_factor   = maturity_mismatch_factor(
                r.get("maturity_months"), p.get("maturity_months")
            )
            value = compute_recognized_ufcp_value(
                value_raw,
                fx_mismatch=fx_mismatch,
                fx_haircut=crm_fx_haircut,
                exposure_maturity_months=r.get("maturity_months"),
                protection_maturity_months=p.get("maturity_months"),
            )

            rw_sub = evaluate_rule_set(
                db, batch_id, regulatory_version_id, "SUBSTITUTION_RISK_WEIGHT",
                {
                    "_context_key":    f"{exposure_id}:{protection_id}",
                    "provider_type":   p.get("provider_type"),
                    "protection_type": p.get("protection_type"),
                },
                trace_buffer=trace_buffer,
            )
            # v3.6.0 — Durcissement : result_value absent OU NULL → pas de RW
            # garant exploitable → aucune substitution (rw_provider = None).
            rw_value    = rw_sub.get("result_value") if rw_sub else None
            rw_provider = _f(rw_value) if rw_value is not None else None

            guarantee_amount, rwa_increment, ead_at_obligor_rw = (
                apply_ufcp_partial_substitution(
                    ead_at_obligor_rw=ead_at_obligor_rw,
                    base_rw=base_rw,
                    rw_provider=rw_provider,
                    protection_value=value,   # ← valeur reconnue (Hfx + maturity)
                )
            )
            rwa_substituted_acc += rwa_increment
            if rw_provider is not None and rw_provider < min_provider_rw:
                min_provider_rw = rw_provider

            # v3.9.0 — traçabilité de l'effet appliqué (parallèle au FCP).
            ufcp_effect = "RW_SUBSTITUTION"
            if fx_mismatch:
                ufcp_effect += "_FX"
            if mm_factor < 1.0:
                ufcp_effect += "_MMM"
            allocations_batch.append((
                batch_id, exposure_id, protection_id,
                bucket, guarantee_amount, ufcp_effect,
            ))

        # ── ÉTAPE 5 : RWA pré-supporting factors (Art.235 partielle) ──────────
        # Formule Art.235(2) : RWA = portion couverte × rw_provider
        #                          + portion résiduelle × rw_obligor
        rwa_pre_supporting = (
            rwa_substituted_acc                      # Σ g_a × rw_provider
            + ead_at_obligor_rw * base_rw            # (E − Σ g_a) × rw_obligor
        )

        # Pour la rétrocompatibilité du tuple de résultat, on calcule un RW
        # effectif (RWA / EAD post-FCP) — cohérent avec la sémantique d'une
        # substitution partielle.
        if ead_after_fcp > 0:
            substituted_rw = rwa_pre_supporting / ead_after_fcp
        else:
            substituted_rw = base_rw

        # ── ÉTAPE 6 : Supporting Factors (Art.501 CRR3) ───────────────────────
        # Facteurs réducteurs pour PME et Projets d'infrastructure.
        # Les règles sont passées pré-chargées (correction v4 — 0 SELECT ici).
        sf_result = apply_supporting_factors(
            db=db,
            batch_id=batch_id,
            regulatory_version=regulatory_version_id,
            exposure_row=r,
            rwa_pre_supporting=rwa_pre_supporting,
            preloaded_rules=sf_rules,   # ← CORRECTION v4 : règles déjà en mémoire
            trace_buffer=sf_trace_buffer,
            sme_total_exposure=sme_total_by_obligor.get(r["counterparty_id"], 0.0),  # v3.4.0 ⑤
        )
        rwa_final = sf_result["rwa_final"]   # RWA après application des facteurs PME/Infra

        # ── CONSTRUCTION DU TUPLE DE RÉSULTAT ─────────────────────────────────
        results_batch.append((
            batch_id,
            exposure_id,
            r["counterparty_id"],
            r["asset_class_id"],
            r["product_type_id"],
            gross,                           # Exposition brute avant provisions
            prov,                            # Provisions spécifiques
            ead_pre_crm,                     # EAD avant CRM (net × CCF)
            ead_after_fcp,                   # EAD après allocation FCP
            total_fcp,                       # Total FCP alloué
            base_rw,                         # RW de base (avant substitution)
            substituted_rw,                  # RW après substitution UFCP
            rwa_pre_supporting,              # RWA avant supporting factors
            sf_result["multiplier_final"],   # Multiplicateur final (produit des SF appliqués)
            sf_result["factor_codes"],       # Codes des facteurs appliqués (ex. "SME_SF|INFRA_SF")
            rwa_final,                       # RWA final (après tous les ajustements)
        ))

    # ── PERSISTANCE EN BASE (une seule transaction atomique) ────────────────────
    with db.transaction():
        # Insertion des résultats SA
        if results_batch:
            db.executemany(
                """
                INSERT INTO core.core_standard_results (
                    batch_id, exposure_id, counterparty_id, asset_class_id, product_type_id,
                    gross_exposure, provision_amount, ead_pre_crm, ead_post_fcp, total_fcp_allocated,
                    risk_weight_base, risk_weight_substituted, rwa_post_crm, supporting_factor_multiplier,
                    supporting_factor_codes, rwa_final
                ) VALUES %s
                """,
                results_batch,
            )

        # Insertion des allocations de protection (CRM)
        if allocations_batch:
            db.executemany(
                """
                INSERT INTO core.core_protection_allocation (
                    batch_id, exposure_id, protection_id,
                    bucket, allocated_amount, effect_type
                ) VALUES %s
                """,
                allocations_batch,
            )

        # Flush groupé des traces Supporting Factors (v2.8 : 1 INSERT global)
        if sf_trace_buffer:
            db.executemany(
                """
                INSERT INTO rpt.rpt_supporting_factor_trace (
                    batch_id, exposure_id, factor_rule_id, multiplier, applied_metric,
                    rwa_before, rwa_after
                ) VALUES %s
                """,
                sf_trace_buffer,
            )

        # Flush groupé des traces de décision (CCF, RW, substitution, protection bucket)
        flush_trace_buffer(db, trace_buffer)

        # v3.3.0 (point 5 audit) — Persistance des compteurs de fallbacks
        # dans rpt.rpt_controls pour visibilité dans l'export CSV des contrôles.
        # Insertion conditionnelle pour ne pas dupliquer si déjà présent
        # (controls.run_controls() ré-écrit ses propres métriques en fin de batch).
        # v3.6.0 — On persiste aussi le compteur de protections CRM ignorées.
        controls_metrics: list[tuple] = []
        if ccf_fallback_count > 0 or rw_fallback_count > 0:
            controls_metrics.append((batch_id, "SA_CCF_FALLBACK_HITS", ccf_fallback_count))
            controls_metrics.append((batch_id, "SA_RW_FALLBACK_HITS",  rw_fallback_count))
        if crm_ignored_protection_count > 0:
            controls_metrics.append(
                (batch_id, "SA_CRM_IGNORED_PROTECTIONS", crm_ignored_protection_count)
            )
        if controls_metrics:
            db.executemany(
                """
                INSERT INTO rpt.rpt_controls (batch_id, control_name, control_value)
                VALUES %s
                ON CONFLICT (batch_id, control_name) DO UPDATE
                  SET control_value = EXCLUDED.control_value
                """,
                controls_metrics,
            )

    # v3.3.0 — Log de synthèse + gestion du mode strict
    if ccf_fallback_count > 0 or rw_fallback_count > 0:
        logger.warning(
            "Standard engine — %d fallback(s) CCF + %d fallback(s) RW détectés "
            "(sur %d expositions). Premiers exposure_id concernés : "
            "CCF=%s ; RW=%s. Voir SA_CCF_FALLBACK_HITS / SA_RW_FALLBACK_HITS "
            "dans rpt.rpt_controls.",
            ccf_fallback_count, rw_fallback_count, len(results_batch),
            ccf_fallback_exposures[:5] or "(aucun)",
            rw_fallback_exposures[:5] or "(aucun)",
        )
        if strict_fallback_mode:
            raise RuntimeError(
                f"strict_fallback_mode=True : {ccf_fallback_count} fallback(s) "
                f"CCF et {rw_fallback_count} fallback(s) RW détectés. Le batch "
                f"a été arrêté pour préserver l'intégrité du calcul. Compléter "
                f"les seeds ref.ref_decision_rules avant de relancer."
            )

    # v3.6.0 — Log de synthèse des protections CRM ignorées (type non géré).
    if crm_ignored_protection_count > 0:
        logger.warning(
            "Standard engine — %d protection(s) CRM ignorée(s) (type ni FCP ni "
            "UFCP). Premiers protection_id concernés : %s. Voir "
            "SA_CRM_IGNORED_PROTECTIONS dans rpt.rpt_controls. Corriger "
            "stg.stg_protections.protection_type pour les prendre en compte.",
            crm_ignored_protection_count,
            crm_ignored_protections[:5] or "(aucun)",
        )

    return len(results_batch)
