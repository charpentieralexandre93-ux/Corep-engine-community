"""
================================================================================
MODULE  : supporting_factors.py
PROJET  : COREP Engine CRR3
VERSION : 4.2.8
================================================================================

DESCRIPTION
-----------
Ce module applique les facteurs de soutien réglementaires (Supporting Factors)
qui réduisent l'exigence de fonds propres pour certaines catégories d'expositions
bénéficiant d'un traitement préférentiel dans CRR3.

FACTEURS RÉGLEMENTAIRES SUPPORTÉS
-----------------------------------

1. PME SUPPORTING FACTOR (SME_SF) — Art.501 CRR3   [TWO-TIER depuis v3.4.0]
   Mécanique two-tier (Art.501(1)) sur l'exposition totale E* envers la PME
   (somme par obligor / groupe de clients liés) :
       • part de E* ≤ 2,5 M€  → facteur 0,7619 (= 76,19 %) ;
       • part de E* > 2,5 M€  → facteur 0,85   (= 85 %).
   Multiplicateur mélangé appliqué au RWA :
       SF = [0,7619 × min(E*, 2,5M) + 0,85 × max(0, E* − 2,5M)] / E*
   Éligibilité : expositions sur PME (supporting_sme_flag = TRUE).

   CORRECTION v3.4.0 (audit point ⑤)
   ----------------------------------
   Avant v3.4.0 : un facteur PLAT 0,7619 était appliqué à toute la RWA, quel
   que soit le montant de l'exposition, et la documentation citait l'ancien
   seuil obsolète de 1,5 M€ (CRR2 d'avant le « quick fix » 2020). Le palier
   0,85 au-delà de 2,5 M€ était totalement absent → relief surévalué pour les
   grosses expositions PME (jusqu'à −24 % au lieu du −15 % réglementaire sur la
   tranche supérieure).

2. INFRASTRUCTURE SUPPORTING FACTOR (INFRA_SF) — Art.501a CRR3
   Multiplicateur : 0,75 (= 75%)
   Éligibilité    : projets d'infrastructure éligibles (supporting_infra_flag = TRUE)
   Effet          : RWA infrastructure × 0,75 → réduction de 25% des exigences

Ces deux facteurs peuvent se cumuler si une exposition est à la fois PME
et projet d'infrastructure (multiplier_final = SF_PME × 0,75).

ARCHITECTURE DES RÈGLES
------------------------
Les facteurs sont stockés dans ref.ref_supporting_factor_rules avec :
    factor_code          : "SME_SUPPORTING_FACTOR" ou "INFRA_SUPPORTING_FACTOR"
    eligibility_field    : colonne à tester (ex. "supporting_sme_flag")
    eligibility_operator : opérateur de comparaison ("=" ou "!=")
    eligibility_value    : valeur attendue ("TRUE", "Y", "1")
    multiplier           : facteur de la tranche basse (0,7619 ou 0,75)
    priority             : ordre d'application si plusieurs facteurs

Le seuil 2,5 M€ et le facteur de tranche haute 0,85 sont des constantes
réglementaires Art.501 (cf. SME_SF_TIER_THRESHOLD_EUR / SME_SF_HIGH_TIER_FACTOR).
Le facteur de tranche basse reste piloté par la règle en base (multiplier).

CORRECTIONS CRITIQUES APPORTÉES
----------------------------------

CORRECTION #A — Bug booléen PostgreSQL (v4)
    PROBLÈME : psycopg2 retourne les colonnes BOOLEAN comme Python bool
               (True/False). L'ancienne comparaison str(True) == "TRUE"
               échouait : str(True) = "True" (T majuscule, reste minuscule)
               → Les facteurs PME et Infrastructure n'étaient JAMAIS appliqués.
               → RWA des PME surestimé de 24% systématiquement.
    SOLUTION : La fonction _match() teste explicitement les valeurs truthy
               ("TRUE", "YES", "Y", "1") de manière insensible à la casse.

CORRECTION #B — Requête répétée N fois (v4)
    PROBLÈME : apply_supporting_factors() chargeait ref_supporting_factor_rules
               depuis la base à CHAQUE exposition → N requêtes identiques.
    SOLUTION : Le paramètre optionnel preloaded_rules permet à run_standard_engine
               de charger les règles UNE SEULE FOIS et de les passer à chaque
               appel. Rétrocompatibilité garantie (None → comportement ancien).

DÉPENDANCES
-----------
    .db.Database
    .utils.to_float (alias _f)

SORTIE
------
    rpt.rpt_supporting_factor_trace : trace par exposition et facteur appliqué
================================================================================
"""

from __future__ import annotations
from .db import Database
from .utils import to_float as _f

# ── v3.4.0 — SME Supporting Factor two-tier (Art.501(1) CRR3) ───────────────
# Seuil entre la tranche basse (0,7619) et la tranche haute (0,85).
SME_SF_TIER_THRESHOLD_EUR = 2_500_000.0
# Facteur appliqué à la part de l'exposition PME au-delà du seuil de 2,5 M€.
SME_SF_HIGH_TIER_FACTOR = 0.85
# Codes de facteur reconnus comme « SME » (deux conventions de nommage).
_SME_FACTOR_TOKENS = ("SME", "PME")


def _is_sme_factor(factor_code: str | None) -> bool:
    """Vrai si le code de facteur correspond au SME Supporting Factor."""
    fc = (factor_code or "").upper()
    return any(tok in fc for tok in _SME_FACTOR_TOKENS)


def sme_blended_factor(
    low_tier_factor: float,
    total_sme_exposure: float,
    threshold: float = SME_SF_TIER_THRESHOLD_EUR,
    high_tier_factor: float = SME_SF_HIGH_TIER_FACTOR,
) -> float:
    """Multiplicateur mélangé du SME Supporting Factor — Art.501(1) CRR3.

        SF = [low × min(E*, seuil) + high × max(0, E* − seuil)] / E*

    où E* est l'exposition totale envers la PME (par obligor / groupe lié).

    Pour E* ≤ seuil, le résultat vaut exactement `low_tier_factor` (rétrocompat
    parfaite avec le comportement plat antérieur). Pour E* > seuil, la tranche
    supérieure est pondérée à `high_tier_factor` (0,85).

    Paramètres
    ----------
    low_tier_factor : float   Facteur de la tranche ≤ seuil (0,7619, depuis la règle).
    total_sme_exposure : float   E* — exposition totale envers la PME.
    threshold : float   Seuil réglementaire (2,5 M€).
    high_tier_factor : float   Facteur de la tranche > seuil (0,85).

    Retourne
    --------
    float : multiplicateur ∈ [low, high] à appliquer au RWA de l'exposition.
    """
    e = _f(total_sme_exposure)
    if e <= 0:
        # Pas d'information de montant → on retombe sur la tranche basse seule.
        return low_tier_factor
    low_part  = low_tier_factor * min(e, threshold)
    high_part = high_tier_factor * max(0.0, e - threshold)
    return (low_part + high_part) / e


def _match(operator: str, left, right) -> bool:
    """Évalue une condition d'éligibilité avec gestion correcte des booléens PostgreSQL.

    Comparateurs supportés : "=" / "==" et "!=" / "<>"

    CORRECTION #A : Gestion des booléens Python issus de psycopg2
    -------------------------------------------------------------
    psycopg2 retourne les colonnes BOOLEAN PostgreSQL comme Python bool.
    str(True) = "True" (T majuscule, reste minuscule) ≠ "TRUE" ni "Y".
    Cette fonction détecte les bool Python et les compare aux valeurs truthy
    connues : {"TRUE", "YES", "Y", "1"} — insensible à la casse.

    Sans cette correction :
        left = True (Python bool depuis psycopg2)
        right = "TRUE" (valeur en base)
        str(True) == "TRUE"  → False (!!!!)
        → Facteur PME jamais appliqué → RWA PME surestimé de 24%

    Paramètres
    ----------
    operator : str   Opérateur ("=" ou "!=")
    left     : any   Valeur depuis l'exposition (peut être bool, str, None)
    right    : str   Valeur attendue depuis la règle en base

    Retourne
    --------
    bool  True si la condition est satisfaite.
    """
    op = (operator or "=").strip().upper()

    if op in ("=", "=="):
        if isinstance(left, bool):
            # bool Python → comparer aux valeurs truthy connues
            truthy = str(right).upper() in ("TRUE", "YES", "Y", "1")
            return left == truthy
        # Comparaison textuelle générale (None → chaîne vide)
        return ("" if left is None else str(left)) == ("" if right is None else str(right))

    if op in ("!=", "<>"):
        if isinstance(left, bool):
            truthy = str(right).upper() in ("TRUE", "YES", "Y", "1")
            return left != truthy
        return ("" if left is None else str(left)) != ("" if right is None else str(right))

    return False


def apply_supporting_factors(
    db: Database,
    batch_id: str,
    regulatory_version: str,
    exposure_row: dict,
    rwa_pre_supporting: float,
    preloaded_rules: list | None = None,
    trace_buffer: list | None = None,
    sme_total_exposure: float | None = None,
) -> dict:
    """Applique les facteurs de soutien réglementaires (PME, Infrastructure) sur le RWA.

    Parcourt les règles de supporting factors configurées en base et applique
    les multiplicateurs des règles dont les conditions d'éligibilité sont
    satisfaites par l'exposition. Les facteurs applicables se multiplient.

    Paramètres
    ----------
    db : Database
        Instance de connexion PostgreSQL active.
    batch_id : str
        Identifiant du batch (pour la traçabilité).
    regulatory_version : str
        Version réglementaire (ex. "CRR3_V9").
    exposure_row : dict
        Données de l'exposition (dict psycopg2 depuis stg.stg_exposures).
        Colonnes testées par les règles : supporting_sme_flag, supporting_infra_flag.
    rwa_pre_supporting : float
        RWA calculé avant application des facteurs de soutien.
        = ead_post_fcp × risk_weight_substituted (depuis standard_engine.py)
    preloaded_rules : list | None
        CORRECTION #B : si fourni, utilise ces règles sans requête SQL.
        Si None (comportement original) : charge les règles depuis la base.
    trace_buffer : list | None
        Correctif v2.8 : si fourni, les traces sont ajoutées au buffer global
        du moteur standard et insérées en une seule fois en fin de batch. Si None,
        le comportement rétrocompatible écrit directement les traces de l'appel.
    sme_total_exposure : float | None
        v3.4.0 — exposition totale E* envers la PME (somme par obligor / groupe
        de clients liés), utilisée pour le calcul two-tier du SME Supporting
        Factor (Art.501(1)). Si None (comportement antérieur) ou ≤ seuil, le
        facteur appliqué reste celui de la règle (tranche basse 0,7619).

    Retourne
    --------
    dict avec trois clés :
        multiplier_final : float
            Produit de tous les multiplicateurs appliqués.
            Ex. : PME_SF (×0,7619) + INFRA_SF (×0,75) → 0,7619 × 0,75 ≈ 0,5714
        rwa_final : float
            RWA après application de tous les facteurs.
            = rwa_pre_supporting × multiplier_final
        factor_codes : str
            Codes des facteurs appliqués séparés par '|'.
            Ex. : "SME_SF" ou "SME_SF|INFRA_SF" ou "" (aucun facteur)

    Traçabilité
    -----------
    Chaque application de facteur génère une ligne dans rpt_supporting_factor_trace
    avec les montants avant et après application.
    """
    # CORRECTION #B : charger les règles depuis la base UNIQUEMENT si non pré-chargées
    if preloaded_rules is None:
        rules = db.query(
            """
            SELECT *
            FROM ref.ref_supporting_factor_rules
            WHERE regulatory_version_id = %s
              AND is_active = TRUE
            ORDER BY priority, factor_code
            """,
            (regulatory_version,),
        )
    else:
        rules = preloaded_rules  # ← 0 requête SQL supplémentaire

    rwa_running      = _f(rwa_pre_supporting)  # RWA courant (modifié par chaque facteur)
    multiplier_final = 1.0                      # Produit cumulé des multiplicateurs
    applied_codes:   list[str]   = []           # Codes des facteurs effectivement appliqués
    trace_batch:     list[tuple] = []           # Lignes de traçabilité
    exposure_id = exposure_row["exposure_id"]

    for rule in rules:
        # Lecture de la valeur du champ d'éligibilité sur l'exposition
        left = exposure_row.get(rule["eligibility_field"])

        # Test de la condition — CORRECTION #A : gestion booléens Python
        if not _match(rule["eligibility_operator"], left, rule["eligibility_value"]):
            continue  # Exposition non éligible → passer au facteur suivant

        # Application du multiplicateur
        rule_multiplier = _f(rule["multiplier"])

        # v3.4.0 (audit ⑤) — SME Supporting Factor two-tier (Art.501(1)).
        # Si la règle est le facteur PME et que l'exposition totale E* est
        # connue, on applique le multiplicateur MÉLANGÉ (0,7619 ≤ 2,5 M€ ;
        # 0,85 au-delà) au lieu du facteur plat. Pour E* ≤ 2,5 M€, le résultat
        # est identique au facteur de la règle (rétrocompatibilité parfaite).
        if _is_sme_factor(rule["factor_code"]) and sme_total_exposure is not None:
            factor_multiplier = sme_blended_factor(rule_multiplier, sme_total_exposure)
        else:
            factor_multiplier = rule_multiplier

        rwa_before   = rwa_running
        rwa_running  = rwa_running * factor_multiplier
        multiplier_final *= factor_multiplier
        applied_codes.append(rule["factor_code"])

        # Traçabilité de l'application
        # PATCH v2.5 : .get() défensif sur factor_rule_id — la colonne EST en
        # base (BIGSERIAL PK de ref_supporting_factor_rules) mais cette protection
        # évite un KeyError si un appelant injecte une règle pré-construite sans
        # cette clé (cas typique en test unitaire).
        trace_batch.append((
            batch_id,
            exposure_id,
            rule.get("factor_rule_id"),
            factor_multiplier,
            rule.get("applies_to_metric", "RWA"),
            rwa_before,
            rwa_running,
        ))

    # Flush des traces :
    # - v2.8 moteur batch : append dans un buffer global, puis 1 INSERT final.
    # - rétrocompatibilité appels unitaires : écriture directe si aucun buffer fourni.
    if trace_batch:
        if trace_buffer is not None:
            trace_buffer.extend(trace_batch)
        else:
            db.executemany(
                """
                INSERT INTO rpt.rpt_supporting_factor_trace (
                    batch_id, exposure_id, factor_rule_id, multiplier, applied_metric,
                    rwa_before, rwa_after
                ) VALUES %s
                """,
                trace_batch,
            )

    return {
        "multiplier_final": multiplier_final,
        "rwa_final":        rwa_running,
        "factor_codes":     "|".join(applied_codes),
    }
