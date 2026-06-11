"""
================================================================================
MODULE  : protection_strategy.py
PROJET  : COREP Engine CRR3
VERSION : 4.3.5
================================================================================

DESCRIPTION
-----------
Ce module gère le chargement, le tri et l'enrichissement des protections
(garanties et collatéraux) associées à chaque exposition du portefeuille.
Il constitue la couche de préparation CRM (Credit Risk Mitigation) utilisée
par l'engine SA avant le calcul des EAD post-CRM et des RW substitués.

CONCEPT CRM (ART.193-241 CRR3)
--------------------------------
Les techniques d'atténuation du risque de crédit (CRM) permettent à une banque
de réduire son exigence de fonds propres en s'appuyant sur des protections :

    FCP  (Funded Credit Protection — Art.199-217)
         → Collatéral financier ou physique détenu par la banque.
         → Effet : RÉDUIT L'EAD (déduction de la valeur du collatéral).
         → Exemples : cash, obligations souveraines, actions, immobilier.

    UFCP (Unfunded Credit Protection — Art.193-198)
         → Garantie personnelle ou dérivé de crédit (CDS).
         → Effet : SUBSTITUE LE RISK WEIGHT (celui du garant, plus favorable).
         → Exemples : garantie état, garantie banque centrale, CDS.

ORDRE D'ALLOCATION
------------------
Les protections sont triées par allocation_rank (rang croissant) :
    - Rang le plus bas = protection appliquée en premier
    - Protections sans rang → traitées en dernier (rang 9999 par défaut)

Cette logique de tri permet d'allouer les meilleures protections (FCP L1,
garanties souveraines) avant les protections moins efficaces.

CORRECTION v3 (Bug NULLIF)
---------------------------
BUG : CAST(allocation_rank AS INT) plante si allocation_rank est NULL
      (DataError PostgreSQL : "invalid input syntax for integer")
FIX : COALESCE(NULLIF(TRIM(allocation_rank::TEXT), ''), '9999')::INT
      → Protections sans rang triées en dernier (rang 9999)

ENRICHISSEMENT VIA MOTEUR DE DÉCISION
--------------------------------------
Chaque protection est enrichie d'un "bucket" déterminé par les règles
PROTECTION_BUCKET du moteur de décision :
    - Contexte : protection_type, provider_type, collateral_type, issuer_type, protection_subtype
    - Résultat : "COLLATERAL_CASH", "COLLATERAL_SOVEREIGN_BOND", "GUARANTEE_BANK", etc.
Le bucket est utilisé pour la traçabilité dans core_protection_allocation.

DÉPENDANCES
-----------
    .db.Database
    .decision_engine.evaluate_rule_set
================================================================================
"""

from __future__ import annotations
from .decision_engine import evaluate_rule_set
from .db import Database


def _allocation_rank_sort_value(value) -> int:
    """Convertit allocation_rank en entier triable, avec NULL/blank en dernier."""
    try:
        text = str(value if value is not None else "").strip()
        return int(text) if text else 9999
    except (TypeError, ValueError):
        return 9999


def _enrich_protection_bucket(
    db: Database,
    batch_id: str,
    regulatory_version: str,
    protection: dict,
    trace_buffer: list | None = None,
) -> dict:
    """Ajoute le bucket CRM à une protection via PROTECTION_BUCKET.

    La fonction est volontairement séparée pour être réutilisée à la fois par
    le chargement unitaire rétrocompatible et par le préchargement batché v2.8.
    Les règles restent cachées par decision_engine : l'enrichissement ne crée
    pas de N+1 SQL sur les règles.
    """
    exposure_id = protection.get("exposure_id")
    protection_id = protection.get("protection_id")
    context = {
        "_context_key": f"{exposure_id}:{protection_id}",
        "protection_type": protection.get("protection_type"),
        "provider_type": protection.get("provider_type"),
        "collateral_type": protection.get("collateral_type"),
        "collateral_grade": protection.get("collateral_grade"),
        "issuer_type": protection.get("issuer_type") or protection.get("provider_type"),
        "protection_subtype": protection.get("protection_subtype"),
    }
    decision = evaluate_rule_set(
        db,
        batch_id,
        regulatory_version,
        "PROTECTION_BUCKET",
        context,
        trace_buffer=trace_buffer,
    )
    enriched = dict(protection)
    ptype = str(protection.get("protection_type") or "").strip().upper()
    default_bucket = "DEFAULT_UFCP" if ptype == "UFCP" else "DEFAULT_FCP"
    bucket = decision["result_value"] if decision else default_bucket
    # Migration v4.2.3 : l'ancien bucket générique ne doit plus être persisté.
    enriched["bucket"] = default_bucket if bucket == "DEFAULT" else bucket
    return enriched


def load_all_ranked_protections(
    db: Database,
    batch_id: str,
    regulatory_version: str,
    trace_buffer: list | None = None,
) -> dict[str, list[dict]]:
    """Précharge toutes les protections d'un batch, groupées par exposition.

    Correctif performance v2.8 — suppression du N+1 principal CRM.
    ------------------------------------------------------------------
    Avant : ``run_standard_engine`` appelait ``load_ranked_protections`` pour
    chaque exposition, ce qui générait 1 requête SQL par exposition.

    Après : cette fonction charge toutes les lignes de ``stg.stg_protections``
    en une seule requête puis construit en mémoire :

        exposure_id -> [protections triées et enrichies]

    La fonction conserve l'ordre réglementaire d'allocation : ``allocation_rank``
    croissant, ``NULL``/vide en dernier, puis ``protection_id``.
    """
    rows = db.query(
        """
        SELECT *
        FROM stg.stg_protections
        WHERE batch_id = %s
        ORDER BY exposure_id,
                 COALESCE(allocation_rank, 9999),
                 protection_id
        """,
        (batch_id,),
    )

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        enriched = _enrich_protection_bucket(
            db, batch_id, regulatory_version, row, trace_buffer=trace_buffer
        )
        grouped.setdefault(str(row.get("exposure_id")), []).append(enriched)

    # Double garde-fou pour les mocks/tests qui ne respectent pas toujours le ORDER BY.
    for exposure_id, protections in grouped.items():
        protections.sort(
            key=lambda p: (
                _allocation_rank_sort_value(p.get("allocation_rank")),
                str(p.get("protection_id") or ""),
            )
        )
    return grouped


def load_ranked_protections(
    db: Database,
    batch_id: str,
    regulatory_version: str,
    exposure_id: str,
    trace_buffer: list | None = None,
) -> list[dict]:
    """Charge, trie et enrichit les protections d'une exposition.

    Cette fonction est conservée pour rétrocompatibilité des appels unitaires.
    Pour le moteur standard batch, utiliser ``load_all_ranked_protections`` afin
    d'éviter le N+1 SQL exposition → protections.
    """
    rows = db.query(
        """
        SELECT *
        FROM stg.stg_protections
        WHERE batch_id = %s AND exposure_id = %s
        ORDER BY COALESCE(allocation_rank, 9999),
                 protection_id
        """,
        (batch_id, exposure_id),
    )

    return [
        _enrich_protection_bucket(db, batch_id, regulatory_version, row, trace_buffer=trace_buffer)
        for row in rows
    ]
