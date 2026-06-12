"""
================================================================================
MODULE  : utils.py
PROJET  : COREP Engine CRR3
VERSION : 4.4.4
================================================================================

DESCRIPTION
-----------
Ce module centralise les fonctions utilitaires partagées par l'ensemble
des engines du moteur COREP. Il constitue le socle technique commun
utilisé par les 6 engines de calcul réglementaire.

PROBLÉMATIQUE RÉSOLUE (correction v2)
--------------------------------------
Avant v2, chaque engine définissait sa propre fonction locale _f() pour
convertir les valeurs en float. Cette duplication entraînait des comportements
légèrement différents selon les modules et rendait les tests impossibles à
mutualiser. Ce module centralise to_float() en un point unique.
Tous les engines importent désormais : from .utils import to_float as _f

UTILISATION TYPIQUE
-------------------
    from .utils import to_float as _f

    montant = _f(row.get("exposure_amount"))   # → float sûr, jamais None

DÉPENDANCES EXTERNES
--------------------
    Aucune — ce module est autonome.

RÉFÉRENCE
---------
    Interne — standard de codage COREP Engine.
================================================================================
"""

from __future__ import annotations
from typing import Any


def to_float(v: Any) -> float:
    """Convertit une valeur quelconque en float de manière tolérante aux erreurs.

    Cette fonction est la brique de base de tous les engines de calcul.
    Elle protège les calculs réglementaires contre les données de staging
    potentiellement incomplètes, nulles ou mal formatées.

    Stratégie de conversion
    -----------------------
    - Les valeurs falsy Python (None, "", 0, False) donnent 0.0 via `float(v or 0)`.
    - Si la conversion échoue (TypeError, ValueError), on retourne 0.0.
    - Les flottants, entiers, Decimal et chaînes numériques ("1234.56") passent
      normalement.

    Cas d'utilisation typiques (données PostgreSQL → Python via psycopg2)
    ---------------------------------------------------------------------
    - Colonnes NUMERIC/DECIMAL  : retournées comme Decimal  → converties en float
    - Colonnes TEXT avec montants: converties directement
    - Colonnes NULL              : None via psycopg2        → retourne 0.0
    - Colonnes BOOLEAN           : True → 1.0, False → 0.0 (via `or 0`)

    Paramètres
    ----------
    v : Any
        Valeur à convertir. Peut être None, str, int, float, Decimal ou tout
        type renvoyé par psycopg2 ou csv.DictReader.

    Retourne
    --------
    float
        La valeur convertie en float, ou 0.0 en cas d'échec.

    Exemples
    --------
    >>> to_float(None)          # 0.0  (NULL PostgreSQL)
    >>> to_float("")            # 0.0  (champ CSV vide)
    >>> to_float("1234.56")     # 1234.56
    >>> to_float("N/A")         # 0.0  (valeur non numérique — sans exception)
    >>> to_float(True)          # 1.0  (booléen → float)

    Usage recommandé : importer sous l'alias _f pour la concision des formules.
        from .utils import to_float as _f
        rwa = _f(row["exposure_amount"]) * _f(row["risk_weight"])
    """
    try:
        # `v or 0` traite None, "", False comme 0 avant la conversion.
        # float() gère alors Decimal, int, str numériques, etc.
        return float(v or 0)
    except (TypeError, ValueError):
        # Chaîne non numérique (ex. "N/A", "n.a.", texte libre) :
        # comportement défensif — retourner 0.0 plutôt que de stopper le batch.
        return 0.0
