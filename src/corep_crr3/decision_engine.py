"""
================================================================================
MODULE  : decision_engine.py
PROJET  : COREP Engine CRR3
VERSION : 4.4.2
================================================================================

DESCRIPTION
-----------
Ce module implémente le moteur de décision réglementaire BCNF du système COREP.
Il évalue des jeux de règles stockées en base de données pour déterminer les
paramètres réglementaires (CCF, Risk Weight, substitution, bucket protection...)
à appliquer à chaque exposition ou dérivé.

PRINCIPE DE FONCTIONNEMENT
---------------------------
Les règles réglementaires (CCF, RW, SA-CCR, SFT, substitution...) sont
stockées en base de données dans une structure normalisée BCNF :

    ref.ref_decision_rule_sets     : groupes de règles par domaine cible
    ref.ref_decision_rules         : règles individuelles avec priorité
    ref.ref_rule_conditions        : conditions AND de chaque règle

    Exemple pour "CCF" (Credit Conversion Factor) :
    ┌───────────────┬───────────────┬──────────────────┬────────────────────┐
    │ target_domain │ priority      │ result_value     │ conditions         │
    ├───────────────┼───────────────┼──────────────────┼────────────────────┤
    │ CCF           │ 1             │ 1.0              │ product_type = GUARANTEE│
    │ CCF           │ 2             │ 0.75             │ product_type = REVOLVING│
    │ CCF           │ 3             │ 0.40             │ product_type = COMMITMENT│
    └───────────────┴───────────────┴──────────────────┴────────────────────┘

OPTIMISATIONS CLÉS (migration v2)
----------------------------------
1. SUPPRESSION DU PATTERN N+1
   AVANT : 1 requête pour les règles + 1 requête par règle pour ses conditions
           → 51 requêtes SQL pour 50 règles
   APRÈS : 1 seule requête JOIN (règles + conditions)
           → toujours 1 requête SQL, quel que soit le nombre de règles

2. CACHE EN MÉMOIRE (_rules_cache)
   Les règles chargées pour un (regulatory_version_id, target_domain) sont
   mises en cache pour la durée du batch. La même règle CCF n'est chargée
   qu'une seule fois, même si evaluate_rule_set() est appelé 10 000 fois.

3. TRACE BUFFER (flush groupé)
   AVANT : 1 INSERT par règle matchée = N INSERTs dans la boucle principale
   APRÈS : accumulation dans trace_buffer + 1 seul executemany en fin de boucle

DOMAINES DE RÈGLES SUPPORTÉS
------------------------------
    CCF                  : Facteur de conversion crédit (Art.111 CRR3)
    RISK_WEIGHT          : Pondération risque de crédit SA (Art.114-136 CRR3)
    SUBSTITUTION_RISK_WEIGHT : RW de substitution (protection UFCP)
    PROTECTION_BUCKET    : Classification des protections (FCP/UFCP)
    SACCR_RISK_WEIGHT    : Pondération SA-CCR par contrepartie
    SFT_RISK_WEIGHT      : Pondération SFT par contrepartie

DÉPENDANCES
-----------
    .db.Database

SORTIE
------
    rpt.rpt_decision_rule_trace : trace de chaque décision prise par le moteur
    corep_decision_trace_{batch_id}.csv : export via reporting.py

THREAD-SAFETY
-------------
Le cache _rules_cache est un dict global non protégé par un verrou.
SAFE en usage single-threaded (batch réglementaire standard).
En cas de parallélisation future, ajouter threading.Lock().
================================================================================
"""

from __future__ import annotations
import threading
from .db import Database


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS DE COMPARAISON
# ──────────────────────────────────────────────────────────────────────────────

def _as_float(v):
    """Tente une conversion en float pour les comparaisons numériques (>, <, >=, <=).

    Retourne None si la conversion est impossible — dans ce cas, la comparaison
    numérique dans _match() retournera False (comportement défensif).
    """
    try:
        return float(v)
    except Exception:
        return None


def _match(value, operator: str, expected: str) -> bool:
    """Évalue une condition unitaire d'une règle de décision.

    Opérateurs supportés
    --------------------
    "="  : égalité stricte (comparaison en chaînes)
    "!=" : différence stricte
    "IN" : appartenance à une liste de valeurs séparées par "|"
           Exemple : condition_value = "SOVEREIGN|CENTRAL_BANK|MULTILATERAL"
    ">"  : supérieur (comparaison numérique)
    ">=" : supérieur ou égal
    "<"  : inférieur
    "<=" : inférieur ou égal

    Paramètres
    ----------
    value    : Valeur issue du contexte (ex. r["product_type_id"])
    operator : Opérateur de comparaison (depuis ref.ref_rule_conditions)
    expected : Valeur attendue (depuis ref.ref_rule_conditions)

    Retourne
    --------
    bool
        True si la condition est satisfaite, False sinon.
        En cas de comparaison numérique impossible, retourne False.
    """
    operator = (operator or "=").upper()

    if operator == "=":
        return str(value) == str(expected)
    if operator == "!=":
        return str(value) != str(expected)
    if operator == "IN":
        # Valeurs séparées par "|" dans condition_value
        # Exemple : "SOVEREIGN|CENTRAL_BANK" → {"SOVEREIGN", "CENTRAL_BANK"}
        allowed = [x.strip() for x in str(expected).split("|")]
        return str(value) in allowed

    # Comparaisons numériques : nécessitent la conversion en float
    if operator in {">", ">=", "<", "<="}:
        left, right = _as_float(value), _as_float(expected)
        if left is None or right is None:
            return False  # Comparaison impossible → non match
        if operator == ">":  return left > right
        if operator == ">=": return left >= right
        if operator == "<":  return left < right
        if operator == "<=": return left <= right

    # Opérateur non reconnu → non match par défaut
    return False


# ──────────────────────────────────────────────────────────────────────────────
# CHARGEMENT DES RÈGLES DEPUIS LA BASE (anti-N+1)
# ──────────────────────────────────────────────────────────────────────────────

def _load_rules_with_conditions(
    db: Database,
    regulatory_version_id: str,
    target_domain: str,
) -> dict[str, dict]:
    """Charge toutes les règles ET leurs conditions en une seule requête JOIN.

    OPTIMISATION N+1 ELIMINÉE
    --------------------------
    AVANT (pattern N+1) :
        1 SELECT pour les règles + 1 SELECT par règle pour ses conditions
        → 51 requêtes SQL pour un domaine de 50 règles
        → bottleneck majeur sur les 10 000+ expositions d'un batch réel

    APRÈS (1 seule requête JOIN) :
        Toujours 1 requête SQL, quel que soit le nombre de règles
        → gain x50 à x100 sur les performances du moteur de décision

    Structure de la requête
    -----------------------
    La requête JOIN peut retourner plusieurs lignes par règle si cette
    dernière a plusieurs conditions. Ces lignes sont ensuite regroupées
    par rule_id en mémoire.

    Si une règle n'a aucune condition (LEFT JOIN → NULL sur rc), elle
    correspond à TOUTES les expositions (règle "fourre-tout" de dernier recours).

    Paramètres
    ----------
    db : Database
        Instance de connexion active.
    regulatory_version_id : str
        Version réglementaire (filtre sur ref_decision_rule_sets).
    target_domain : str
        Domaine cible, ex. "CCF", "RISK_WEIGHT", "SACCR_RISK_WEIGHT".

    Retourne
    --------
    dict[str, dict]
        Dictionnaire ordonné par priorité/rule_id, chaque valeur contenant :
        {
          "rule_id": int,
          "priority": int,
          "result_key": str,     # ex. "CCF", "RISK_WEIGHT"
          "result_value": str,   # ex. "0.40", "0.75", "1.0"
          "rule_set_name": str,
          "conditions": [        # Liste de conditions AND
            {"condition_field": str, "condition_operator": str, "condition_value": str},
            ...
          ]
        }
    """
    rows = db.query(
        """
        SELECT
            dr.rule_id,
            dr.priority,
            dr.result_key,
            dr.result_value,
            rs.rule_set_id,
            rs.rule_set_name,
            rc.condition_field,
            rc.condition_operator,
            rc.condition_value
        FROM ref.ref_decision_rules dr
        JOIN ref.ref_decision_rule_sets rs
            ON dr.rule_set_id = rs.rule_set_id
        LEFT JOIN ref.ref_rule_conditions rc
            ON rc.rule_id = dr.rule_id
        WHERE rs.regulatory_version_id = %s
          AND rs.target_domain = %s
          AND rs.is_active = TRUE
        ORDER BY dr.priority, dr.rule_id
        """,
        (regulatory_version_id, target_domain),
    )

    # Reconstruction de la structure rules[rule_id] = {méta + conditions[]}
    # Un dict Python préserve l'ordre d'insertion depuis Python 3.7+
    # → l'ordre priority/rule_id de la requête SQL est conservé
    rules: dict[str, dict] = {}
    for row in rows:
        rid = row["rule_id"]
        if rid not in rules:
            # Première occurrence de cette règle : initialiser la structure
            rules[rid] = {
                "rule_id":       rid,
                "rule_set_id":   row["rule_set_id"],
                "priority":      row["priority"],
                "result_key":    row["result_key"],
                "result_value":  row["result_value"],
                "rule_set_name": row["rule_set_name"],
                "conditions":    [],
            }
        # Ajouter la condition (NULL si la règle n'a aucune condition → LEFT JOIN)
        if row["condition_field"] is not None:
            rules[rid]["conditions"].append({
                "condition_field":    row["condition_field"],
                "condition_operator": row["condition_operator"],
                "condition_value":    row["condition_value"],
            })

    return rules


# ──────────────────────────────────────────────────────────────────────────────
# CACHE DES RÈGLES
# ──────────────────────────────────────────────────────────────────────────────

# Cache en mémoire : dict[(regulatory_version_id, target_domain)] → rules_dict
# Évite de recharger les mêmes règles à chaque appel dans la boucle principale.
# Sur 10 000 expositions × 3 appels evaluate_rule_set() = 30 000 appels :
# sans cache → 30 000 requêtes SQL
# avec cache → 3 requêtes SQL (1 par domaine distinct : CCF, RISK_WEIGHT, PROTECTION_BUCKET)
_rules_cache: dict[tuple, dict] = {}
# PATCH v8 — THREAD-SAFETY : protège les lectures/écritures du cache en contexte multi-thread
_rules_cache_lock: threading.Lock = threading.Lock()

# v3.8.0 — MÉMOÏSATION DU MATCHING (levier de performance)
# Le matching d'une règle est une fonction PURE des champs de contexte (hors
# "_context_key", qui ne sert qu'à la trace). Deux objets au contexte identique
# matchent donc la même règle. On mémoïse le résultat (et les champs de la règle
# nécessaires à la trace) pour éviter de re-scanner les M règles à CHAQUE ligne.
# Coût du matching : O(N×M) → O(distinct_contextes × M). La trace reste produite
# à chaque appel avec le _context_key courant → cardinalité/contenu inchangés.
# Le mémo partage le cycle de vie du cache de règles (vidé par clear_rules_cache).
_decision_memo: dict[tuple, tuple] = {}
_MEMO_MISS = object()   # sentinelle d'absence (distincte d'un résultat None mémoïsé)


def clear_rules_cache():
    """Vide le cache des règles.

    À appeler en début de chaque batch (dans run_standard_engine) pour garantir
    que les règles rechargées correspondent à la version réglementaire courante.

    Note : le cache est local au processus Python. Il est automatiquement vide
    au démarrage de chaque exécution de run_batch.py.

    PATCH v8 : opération protégée par Lock pour l'usage multi-thread.
    v3.8.0 : vide aussi le mémo de matching (lié au même cycle de vie que les
    règles — un changement de règles invalide les deux).
    """
    with _rules_cache_lock:
        _rules_cache.clear()
        _decision_memo.clear()



# ──────────────────────────────────────────────────────────────────────────────
# ÉVALUATION DES RÈGLES
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_rule_set(
    db: Database,
    batch_id: str,
    regulatory_version_id: str,
    target_domain: str,
    context: dict,
    trace_buffer: list | None = None,
):
    """Évalue un jeu de règles BCNF pour un contexte donné et retourne le premier match.

    Parcourt les règles dans l'ordre de priorité croissante. Pour chaque règle,
    évalue toutes ses conditions en logique AND. Retourne la première règle
    dont toutes les conditions sont satisfaites.

    Paramètres
    ----------
    db : Database
        Instance de connexion PostgreSQL active.
    batch_id : str
        Identifiant du batch (utilisé pour tracer les décisions).
    regulatory_version_id : str
        Version réglementaire (ex. "CRR3_V9").
    target_domain : str
        Domaine de règles à évaluer :
          "CCF"                    → Facteur de conversion crédit
          "RISK_WEIGHT"            → Pondération SA par classe d'actif
          "SUBSTITUTION_RISK_WEIGHT" → RW substitué (UFCP)
          "PROTECTION_BUCKET"      → Classification FCP/UFCP
          "SACCR_RISK_WEIGHT"      → Pondération SA-CCR
          "SFT_RISK_WEIGHT"        → Pondération SFT
    context : dict
        Attributs de l'objet à évaluer (exposition, netting set, protection).
        Doit contenir toutes les colonnes référencées dans les conditions.
        La clé "_context_key" est utilisée pour identifier l'objet en trace.
        Exemples :
          {"_context_key": "EXP001", "product_type_id": "REVOLVING", "asset_class_id": "RETAIL"}
          {"_context_key": "NS_042", "counterparty_type": "BANK"}
    trace_buffer : list | None
        Si fourni, les traces sont accumulées dans cette liste (mode buffer).
        Si None, la trace est insérée immédiatement en base (mode direct).
        Le mode buffer est recommandé pour les boucles principales (perf).

    Retourne
    --------
    dict | None
        Dictionnaire de la règle matchée :
          {"rule_id": int, "result_key": str, "result_value": str}
        Exemple : {"rule_id": 5, "result_key": "CCF", "result_value": "0.40"}
        Retourne None si aucune règle ne correspond au contexte.

    Usage dans standard_engine.py
    ------------------------------
        trace_buffer = []
        ccf_decision = evaluate_rule_set(
            db, batch_id, regulatory_version_id, "CCF",
            {"_context_key": exposure_id, "product_type_id": r["product_type_id"]},
            trace_buffer=trace_buffer,
        )
        ccf = _f(ccf_decision["result_value"]) if ccf_decision else 1.0
        # ... fin de boucle ...
        flush_trace_buffer(db, trace_buffer)   # 1 seul INSERT pour toutes les traces
    """
    # Chargement des règles depuis le cache (ou base si absent du cache)
    # PATCH v8 — double-checked locking : on évite le verrou si la clé est déjà présente
    # (cas majoritaire après le premier chargement — lecture sans Lock possible sous GIL).
    cache_key = (regulatory_version_id, target_domain)
    if cache_key not in _rules_cache:
        with _rules_cache_lock:
            # Deuxième vérification dans le verrou : un autre thread a pu charger
            # la clé entre le premier test et l'acquisition du Lock.
            if cache_key not in _rules_cache:
                _rules_cache[cache_key] = _load_rules_with_conditions(
                    db, regulatory_version_id, target_domain
                )

    rules = _rules_cache[cache_key]

    # ── v3.8.0 — Mémoïsation du matching ──────────────────────────────────────
    # Signature = contexte hors "_context_key" (qui n'influence PAS le matching,
    # seulement la trace). repr() garantit une clé hashable et stable.
    memo_key = (
        regulatory_version_id,
        target_domain,
        tuple(sorted(
            (k, repr(v)) for k, v in context.items() if k != "_context_key"
        )),
    )
    cached = _decision_memo.get(memo_key, _MEMO_MISS)
    if cached is _MEMO_MISS:
        # MISS → scanner les règles (coût O(M)) UNE fois pour cette signature.
        result = None
        trace_core = None   # (rule_id, rule_set_id, result_key, result_value, match_reason)
        for rule in rules.values():
            conditions = rule["conditions"]

            # ── Évaluation AND de toutes les conditions de la règle ───────────
            all_match    = True
            match_details = []
            for c in conditions:
                val = context.get(c["condition_field"])
                if not _match(val, c["condition_operator"], c["condition_value"]):
                    all_match = False
                    break  # Court-circuit AND
                match_details.append(
                    f"{c['condition_field']} {c['condition_operator']} {c['condition_value']}"
                )
            if not all_match:
                continue

            match_reason = " | ".join(match_details) if match_details else "NO_CONDITIONS"
            result = {
                "rule_id":      rule["rule_id"],
                "rule_set_id":  rule["rule_set_id"],
                "result_key":   rule["result_key"],
                "result_value": rule["result_value"],
            }
            trace_core = (
                rule["rule_id"], rule["rule_set_id"],
                rule["result_key"], rule["result_value"], match_reason,
            )
            break  # Première règle matchée = priorité la plus haute

        # Écriture mémo protégée (le résultat est déterministe : une éventuelle
        # course recalcule simplement la même valeur — aucun impact fonctionnel).
        with _rules_cache_lock:
            _decision_memo[memo_key] = (result, trace_core)
    else:
        result, trace_core = cached

    # ── Trace émise à CHAQUE appel (cardinalité/contenu inchangés vs avant) ────
    # Le _context_key courant est réinjecté → une trace par objet évalué.
    if trace_core is not None:
        rule_id, rule_set_id, result_key, result_value, match_reason = trace_core
        trace_row = (
            batch_id,
            target_domain,
            context.get("_context_key", "UNKNOWN"),
            rule_id,
            rule_set_id,
            result_key,
            result_value,
            match_reason,
        )
        if trace_buffer is not None:
            # MODE BUFFER (recommandé) : accumulation en mémoire, flush groupé.
            trace_buffer.append(trace_row)
        else:
            # MODE DIRECT (compatible v1) : INSERT immédiat (peu performant en boucle).
            db.execute(
                """
                INSERT INTO rpt.rpt_decision_rule_trace (
                    batch_id, target_domain, context_key,
                    rule_id, rule_set_id, result_key, result_value, match_reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                trace_row,
            )

    # result = dict de la règle matchée, ou None si aucune règle ne correspond.
    return result


def flush_trace_buffer(db: Database, trace_buffer: list):
    """Insère toutes les traces accumulées en un seul executemany.

    Remplace N INSERTs unitaires (un par décision dans la boucle principale)
    par un seul execute_values avec toutes les traces accumulées.

    Gain typique : 1 INSERT pour 10 000 décisions au lieu de 10 000 INSERTs.

    Paramètres
    ----------
    db : Database
        Instance de connexion PostgreSQL active (dans un contexte db.transaction()).
    trace_buffer : list
        Liste de tuples de traces accumulés par evaluate_rule_set().
        La liste est vidée après le flush (trace_buffer.clear()).

    Usage recommandé
    ----------------
        trace_buffer = []
        for exposition in expositions:
            evaluate_rule_set(..., trace_buffer=trace_buffer)
        # Fin de boucle — flush groupé
        flush_trace_buffer(db, trace_buffer)
    """
    if not trace_buffer:
        return  # Rien à insérer

    db.executemany(
        """
        INSERT INTO rpt.rpt_decision_rule_trace (
            batch_id, target_domain, context_key,
            rule_id, rule_set_id, result_key, result_value, match_reason
        ) VALUES %s
        """,
        trace_buffer,
    )

    # Vider le buffer après flush pour éviter les doublons en cas de ré-appel
    trace_buffer.clear()
