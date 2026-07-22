"""
================================================================================
MODULE  : db.py
PROJET  : COREP Engine CRR3
VERSION : 6.10.1
================================================================================

PATCH v6 — THREAD-SAFETY
--------------------------
Deux améliorations apportées :

1. Database.__init__ accepte désormais un paramètre optionnel `conn`.
   Cela permet à DatabasePool d'injecter une connexion déjà ouverte
   (empruntée au pool) sans en créer une nouvelle.
   ► Rétrocompatibilité totale : les appels Database() sans argument
     sont identiques à avant.

2. DatabasePool : nouveau wrapper autour de psycopg2.pool.ThreadedConnectionPool.
   Permet l'usage multi-thread sûr (ex. engines parallèles, workers).

   Usage recommandé :
       pool = DatabasePool(dsn=\"...\", minconn=2, maxconn=10)
       with pool.acquire() as db:
           db.query(\"SELECT ...\")
       pool.close()

   Garanties :
   - La connexion est restituée au pool même en cas d'exception.
   - Database.close() NE DOIT PAS être appelé sur une connexion empruntée
     (le pool gère le cycle de vie) — le context manager s'en charge.

AVERTISSEMENT : Database seul (sans pool) reste NON thread-safe.
Pour un usage multi-thread, utiliser DatabasePool.acquire().
================================================================================

DESCRIPTION
-----------
Ce module fournit la classe Database, wrapper minimaliste autour de psycopg2
pour la connexion et les opérations PostgreSQL. Il constitue l'unique couche
d'accès aux données (DAL) du moteur COREP.

ARCHITECTURE
------------
Toutes les interactions avec PostgreSQL passent par cette classe :
  - Engines de calcul (standard, IRB, SA-CCR, SFT, IRRBB, LCR/NSFR, CVA)
  - Ingestion CSV → staging tables
  - Rapports, audits, contrôles et exports

OPTIMISATIONS CLÉS (migration v2)
----------------------------------
1. AUTOCOMMIT DÉSACTIVÉ
   Avant : chaque execute() déclenchait un commit immédiat.
   Sur un batch de 10 000 expositions × 4 INSERTs = 40 000 commits individuels.
   Après : un seul commit par engine via db.transaction() — gain x10 à x100.

2. EXECUTE_VALUES (executemany)
   Les INSERTs en masse utilisent psycopg2.extras.execute_values(), qui génère
   un seul INSERT multi-valeurs côté serveur (ex. VALUES (%s,%s), (%s,%s), ...)
   au lieu de N INSERTs séquentiels.

3. SUPPRESSION DE LA RÉÉCRITURE '?' → '%s'
   Les requêtes utilisent directement la syntaxe psycopg2 native (%s),
   éliminant la conversion à chaque appel.

GESTION DES TRANSACTIONS
-------------------------
Pattern recommandé pour tous les engines :

    with db.transaction():          # Début de transaction atomique
        db.executemany(sql, rows)   # Tous les INSERTs groupés
        db.execute(sql2, params)    # Autres opérations
    # ↑ commit automatique à la sortie du with
    # ↑ rollback automatique si une exception est levée

CONFIGURATION DE CONNEXION
---------------------------
La connexion est configurée via DSN (Data Source Name) PostgreSQL :
    - Par paramètre direct : Database(dsn="dbname=corep user=corep_user ...")
    - Par variable d'environnement : DATABASE_URL=postgresql://...
    - Valeur par défaut (développement local) : dbname=corep_crr3 user=corep_user

En production, passer le DSN construit depuis config_postgresql.yaml via
run_batch.py ou les scripts CLI.

DÉPENDANCES EXTERNES
--------------------
    psycopg2 (ou psycopg2-binary) >= 2.9
    pip install psycopg2-binary

RÉFÉRENCE
---------
    Documentation psycopg2 : https://www.psycopg.org/docs/
================================================================================
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Generator, Optional

# Import paresseux : les fonctions de calcul pures (SA, SA-CCR, CRM…) n'ont pas
# besoin de PostgreSQL. On tolère donc l'absence de psycopg2 à l'import du module ;
# l'erreur n'est levée qu'au moment d'une connexion réelle (cf. _require_psycopg2).
psycopg2: Any = None
_psycopg2_extras: Any = None
_psycopg2_pool: Any = None
_psycopg2_make_dsn: Any = None
_PSYCOPG2_IMPORT_ERROR: Optional[BaseException] = None
try:
    import psycopg2 as _psycopg2
    from psycopg2 import extras as _loaded_psycopg2_extras
    from psycopg2 import pool as _loaded_psycopg2_pool
except (ImportError, OSError) as _exc:  # paquet absent ou extension native indisponible
    _PSYCOPG2_IMPORT_ERROR = _exc
else:
    # L'import du pilote de base ne doit pas dépendre d'un helper optionnel.
    # Certains doubles de test et distributions minimales exposent connect/extras/pool
    # sans sous-module psycopg2.extensions. L'ancien bloc invalidait alors à tort
    # tout le pilote et provoquait des NoneType dans Database/DatabasePool.
    psycopg2 = _psycopg2
    _psycopg2_extras = _loaded_psycopg2_extras
    _psycopg2_pool = _loaded_psycopg2_pool
    try:
        from psycopg2.extensions import make_dsn as _psycopg2_make_dsn
    except (ImportError, AttributeError):
        _psycopg2_make_dsn = None


# -----------------------------------------------------------------------------
# Constantes de performance
# -----------------------------------------------------------------------------
# v3.8.0 — Taille de page d'execute_values (levier de performance).
# psycopg2.extras.execute_values découpe la séquence en pages et fait UN
# aller-retour serveur par page. Le défaut psycopg2 est 100 → sur un batch de
# 10 000+ lignes, cela génère des centaines de round-trips. On le porte à 1000
# (≈10× moins d'allers-retours), sans changer le résultat des INSERTs.
# Surchargeable via la variable d'environnement COREP_EXECUTE_VALUES_PAGE_SIZE.
def _resolve_execute_values_page_size(default: int = 1000) -> int:
    raw = os.environ.get("COREP_EXECUTE_VALUES_PAGE_SIZE")
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


_EXECUTE_VALUES_PAGE_SIZE = _resolve_execute_values_page_size()


def _require_psycopg2() -> None:
    """Lève une erreur explicite si psycopg2 est requis mais indisponible."""
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 est requis pour se connecter à PostgreSQL mais n'a pas pu être "
            "importé. Installez-le : pip install psycopg2-binary. "
            "Les fonctions de calcul pures (SA, SA-CCR) n'en ont pas besoin."
        ) from _PSYCOPG2_IMPORT_ERROR


def _resolve_pgpassword() -> Optional[str]:
    """Résout un secret PostgreSQL avec bornes d'exécution explicites.

    Priorité : ``PGPASSWORD`` → ``PGPASSWORD_FILE`` → ``PGPASSWORD_CMD``.
    La commande opérateur est exécutée sans shell, avec timeout et limite de
    taille pour éviter qu'un fournisseur de secret bloqué ou bavard ne suspende
    indéfiniment un batch réglementaire.
    """
    direct = os.getenv("PGPASSWORD")
    if direct:
        return direct
    path = os.getenv("PGPASSWORD_FILE")
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            secret = handle.read(16_385)
        if len(secret.encode("utf-8")) > 16_384:
            raise RuntimeError("PGPASSWORD_FILE dépasse la limite de 16 KiB")
        return secret.strip() or None
    command = os.getenv("PGPASSWORD_CMD")
    if command:
        import shlex
        import subprocess  # nosec B404

        try:
            timeout = float(os.getenv("COREP_PGPASSWORD_CMD_TIMEOUT", "5"))
        except ValueError:
            timeout = 5.0
        timeout = min(max(timeout, 0.1), 60.0)
        result = subprocess.run(  # nosec B603
            shlex.split(command),
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        secret = result.stdout.strip()
        if len(secret.encode("utf-8")) > 16_384:
            raise RuntimeError("PGPASSWORD_CMD dépasse la limite de 16 KiB")
        return secret or None
    return None


def _quote_conninfo_value(value: object) -> str:
    """Échappe une valeur libpq lorsque psycopg2 n'est pas importable."""
    text = str(value)
    if text and not any(char.isspace() for char in text) and not ({"'", "\\"} & set(text)):
        return text
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _build_conninfo(parameters: Mapping[str, object]) -> str:
    clean = {key: str(value) for key, value in parameters.items() if value not in (None, "")}
    if _psycopg2_make_dsn is not None:
        return str(_psycopg2_make_dsn(**clean))
    return " ".join(f"{key}={_quote_conninfo_value(value)}" for key, value in clean.items())


# -----------------------------------------------------------------------------
# Construction du DSN PostgreSQL
# -----------------------------------------------------------------------------
def build_dsn_from_env(
    default: str = "dbname=corep_crr3 user=corep_user host=localhost port=5432",
) -> str:
    """Construit un DSN depuis l'environnement avec échappement libpq sûr."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    pgdatabase = os.getenv("PGDATABASE")
    pguser = os.getenv("PGUSER")
    if pgdatabase and pguser:
        return _build_conninfo(
            {
                "host": os.getenv("PGHOST", "localhost"),
                "port": os.getenv("PGPORT", "5432"),
                "dbname": pgdatabase,
                "user": pguser,
                "password": _resolve_pgpassword(),
            }
        )
    return default


def build_dsn_from_config(
    database_config: Optional[Mapping[str, object]],
    default: str = "dbname=corep_crr3 user=corep_user host=localhost port=5432",
) -> str:
    """Résout le DSN unique utilisé par le batch.

    Priorité : URL complète, variables PostgreSQL standard, configuration YAML,
    puis fallback. Le mot de passe YAML vide est remplacé par le fournisseur de
    secret standard afin d'éviter les implémentations divergentes.
    """
    if os.getenv("DATABASE_URL") or (os.getenv("PGDATABASE") and os.getenv("PGUSER")):
        return build_dsn_from_env(default)
    config = dict(database_config or {})
    if config.get("dbname") and config.get("user"):
        return _build_conninfo(
            {
                "host": config.get("host", "localhost"),
                "port": config.get("port", 5432),
                "dbname": config["dbname"],
                "user": config["user"],
                "password": config.get("password") or _resolve_pgpassword(),
            }
        )
    return default


logger = logging.getLogger(__name__)


class Database:
    """Wrapper PostgreSQL pour le moteur COREP — couche d'accès aux données unique.

    Encapsule une connexion psycopg2 unique avec gestion explicite des
    transactions. Toutes les interactions avec PostgreSQL dans le moteur
    COREP passent par cette classe.

    Attributs
    ---------
    dsn : str
        La chaîne de connexion PostgreSQL (Data Source Name).
    conn : psycopg2.connection
        La connexion active à PostgreSQL.
    cursor_factory : psycopg2.extras.RealDictCursor
        Le curseur utilisé par db.query() pour retourner des dict Python
        plutôt que des tuples — accès aux colonnes par nom.

    Notes
    -----
    - Cette classe n'est PAS thread-safe. Pour un usage multi-thread,
      instancier une Database par thread ou utiliser un pool de connexions
      (ex. psycopg2.pool.ThreadedConnectionPool).
    - La connexion doit être fermée explicitement via db.close() ou
      gérée via le pattern `db = None` / `finally: if db: db.close()`
      implémenté dans les scripts CLI (run_batch.py, bootstrap.py, etc.).
    """

    def __init__(self, dsn: Optional[str] = None, *, conn: Any = None):
        """Initialise et ouvre la connexion à PostgreSQL.

        Paramètres
        ----------
        dsn : str, optionnel
            Data Source Name PostgreSQL.
            Ignoré si `conn` est fourni.
        conn : psycopg2.connection, optionnel (keyword-only)
            Connexion existante à réutiliser (ex. empruntée depuis DatabasePool).
            Si fourni, `dsn` est ignoré et aucune nouvelle connexion n'est créée.
            ► NE PAS appeler db.close() sur une instance créée avec conn= :
              le pool gère le cycle de vie via DatabasePool.acquire().

        PATCH v6 : ce paramètre permet à DatabasePool d'injecter une connexion
        du pool sans en créer une nouvelle — clé de la thread-safety.
        """
        if conn is not None:
            # Connexion fournie externement (depuis DatabasePool)
            self.dsn = None
            self.conn = conn
        else:
            _require_psycopg2()
            self.dsn = dsn or build_dsn_from_env()
            self.conn = psycopg2.connect(self.dsn)

        # Désactivation de l'autocommit : les transactions sont gérées explicitement.
        #
        # IMPORTANT : psycopg2 interdit toute réaffectation de ``autocommit``
        # lorsqu'une transaction est déjà ouverte, même si la valeur demandée
        # est identique à la valeur courante. Une connexion injectée via
        # ``conn=`` peut légitimement avoir exécuté des lectures avant d'être
        # encapsulée par Database (cas de la recette PostgreSQL E2E).
        # On ne modifie donc la propriété que lorsqu'elle est réellement active.
        if bool(getattr(self.conn, "autocommit", False)):
            self.conn.autocommit = False

        # RealDictCursor : chaque ligne retournée par query() est un dict Python.
        self.cursor_factory = (
            getattr(_psycopg2_extras, "RealDictCursor", None) if _psycopg2_extras is not None else None
        )

    # ──────────────────────────────────────────────────────────────────────────
    # GESTION DES TRANSACTIONS
    # ──────────────────────────────────────────────────────────────────────────

    def commit(self) -> None:
        """Valide (commit) la transaction courante.

        À appeler après un bloc d'opérations DML (INSERT/UPDATE/DELETE)
        qui ne sont pas encapsulées dans db.transaction().

        Usage typique : après ingest_dataset() dans ingestion.py.
        Préférer db.transaction() pour les blocs multi-opérations.
        """
        self.conn.commit()

    def rollback(self) -> None:
        """Annule (rollback) la transaction courante.

        À appeler dans les blocs except pour annuler les modifications
        partielles en cas d'erreur.

        Note : db.transaction() gère le rollback automatiquement via
        son bloc except — inutile de l'appeler manuellement dans ce cas.
        """
        self.conn.rollback()

    @contextlib.contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager pour un bloc transactionnel atomique.

        Garantit l'atomicité : soit toutes les opérations réussissent
        (commit), soit aucune n'est persistée (rollback automatique
        en cas d'exception).

        Usage recommandé (pattern standard de tous les engines)
        -------------------------------------------------------
            with db.transaction():
                db.executemany(insert_sql, results_batch)
                db.executemany(trace_sql,  trace_batch)
            # → commit automatique si tout réussit
            # → rollback automatique + re-raise si exception

        Comportement
        ------------
        - Entrée : rien (la transaction psycopg2 est implicitement active
          dès la première opération DML).
        - Sortie sans exception : conn.commit() est appelé.
        - Sortie avec exception : conn.rollback() est appelé, puis
          l'exception est re-levée vers l'appelant.

        Raises
        ------
        Exception
            Toute exception levée dans le bloc with est re-levée après
            le rollback.
        """
        try:
            yield  # Exécution du bloc with
            self.conn.commit()  # Validation si pas d'exception
        except Exception:  # fail-closed: error is re-raised or translated after cleanup
            self.conn.rollback()  # Annulation en cas d'erreur
            raise  # Re-lever pour que l'appelant gère

    # ──────────────────────────────────────────────────────────────────────────
    # COMMANDES DML (Data Manipulation Language)
    # ──────────────────────────────────────────────────────────────────────────

    def execute(self, sql: str, params: Sequence[object] = ()) -> Any:
        """Exécute une commande SQL (INSERT, UPDATE, DELETE, TRUNCATE).

        Paramètres
        ----------
        sql : str
            Requête SQL avec placeholders %s (syntaxe psycopg2 native).
            Exemples :
              "DELETE FROM core.core_standard_results WHERE batch_id = %s"
              "INSERT INTO meta.batch_run_control (batch_id, status) VALUES (%s, %s)"
        params : tuple, optionnel
            Valeurs à injecter aux placeholders %s.
            Toujours passer des paramètres via ce tuple — JAMAIS par
            formatage Python (f-string) pour éviter les injections SQL.

        Retourne
        --------
        psycopg2.cursor
            Le curseur d'exécution (rarement utilisé directement).

        IMPORTANT
        ---------
        Ne commit PAS automatiquement. Appeler db.commit() ou utiliser
        db.transaction() après les opérations DML.
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur

    def executescript(self, sql_script: str) -> None:
        """Exécute un script SQL complet (plusieurs instructions séparées par ;).

        Utilisé exclusivement par bootstrap.py pour jouer les fichiers
        de seeds SQL (schéma + données de référence) lors de l'initialisation
        de la base de données.

        Paramètres
        ----------
        sql_script : str
            Script SQL complet lu depuis un fichier .sql (seeds 02 à 08).

        Note
        ----
        Commite automatiquement après exécution (contrairement à execute).
        Les scripts SQL utilisent BEGIN/COMMIT explicites pour les transactions.
        """
        with self.conn.cursor() as cur:
            cur.execute(sql_script)
        self.conn.commit()

    def executemany(self, sql: str, params_seq: Iterable[Sequence[object]]) -> Any:
        """Insère une séquence de lignes en un seul appel SQL (batch INSERT).

        Utilise psycopg2.extras.execute_values, qui génère un seul INSERT
        multi-valeurs côté serveur :
            INSERT INTO table (c1, c2) VALUES (%s,%s), (%s,%s), (%s,%s)
        au lieu de N INSERTs séquentiels — gain de performance majeur.

        Paramètres
        ----------
        sql : str
            Requête INSERT avec VALUES %s (un seul placeholder, pas par colonne).
            Exemple :
              "INSERT INTO core.core_standard_results (col1, col2) VALUES %s"
        params_seq : list[tuple]
            Liste de tuples, un par ligne à insérer.
            Chaque tuple doit correspondre à l'ordre des colonnes dans sql.

        IMPORTANT
        ---------
        Ne commit PAS automatiquement. Utiliser dans un bloc db.transaction().

        Performance
        -----------
        Sur 10 000 lignes × 18 colonnes : ~50 ms vs ~5 s avec INSERTs unitaires.
        v3.8.0 : page_size porté à 1000 (cf. _EXECUTE_VALUES_PAGE_SIZE) pour
        réduire d'un facteur ~10 le nombre d'allers-retours serveur sur les gros
        batchs. Sans effet sur le contenu inséré.
        """
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, params_seq, page_size=_EXECUTE_VALUES_PAGE_SIZE)
            return cur

    # ──────────────────────────────────────────────────────────────────────────
    # REQUÊTES SELECT
    # ──────────────────────────────────────────────────────────────────────────

    def query(self, sql: str, params: Sequence[object] = ()) -> list[dict[str, Any]]:
        """Exécute une requête SELECT et retourne les résultats sous forme de dicts.

        Paramètres
        ----------
        sql : str
            Requête SELECT avec placeholders %s.
        params : tuple, optionnel
            Valeurs à injecter aux placeholders.

        Retourne
        --------
        list[dict]
            Liste de dictionnaires, un par ligne. Les clés sont les noms
            des colonnes SELECT. Retourne une liste vide si aucun résultat.

        Exemples
        --------
            rows = db.query(
                "SELECT exposure_id, rwa_final FROM core.core_standard_results "
                "WHERE batch_id = %s",
                (batch_id,)
            )
            for row in rows:
                print(row["exposure_id"], row["rwa_final"])

        Note
        ----
        Les colonnes NUMERIC retournent des objets Decimal Python.
        Utiliser to_float() ou _f() pour les convertir en float avant calcul.
        """
        cursor_kwargs = {"cursor_factory": self.cursor_factory} if self.cursor_factory is not None else {}
        with self.conn.cursor(**cursor_kwargs) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    # ──────────────────────────────────────────────────────────────────────────
    # CYCLE DE VIE
    # ──────────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Ferme la connexion à PostgreSQL et libère les ressources.

        À appeler impérativement dans le bloc finally des scripts CLI :
            db = None
            try:
                db = Database()
                ...
            finally:
                if db:
                    db.close()

        Note : une connexion non fermée reste ouverte côté serveur jusqu'au
        timeout PostgreSQL (paramètre idle_in_transaction_session_timeout).

        PATCH v6 : NE PAS appeler cette méthode sur une instance créée via
        DatabasePool.acquire() — le pool restitue la connexion automatiquement.
        """
        if self.conn:
            self.conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# PATCH v6 : POOL DE CONNEXIONS THREAD-SAFE
# ──────────────────────────────────────────────────────────────────────────────


class DatabasePool:
    """Pool de connexions PostgreSQL thread-safe pour usage concurrent.

    Encapsule psycopg2.pool.ThreadedConnectionPool — garantit qu'une
    connexion distincte est utilisée par chaque thread simultané, évitant
    les corruptions de curseur et les erreurs de transaction croisées.

    Usage type (moteur batch avec workers parallèles)
    -------------------------------------------------
        pool = DatabasePool(dsn=\"postgresql://...\", minconn=2, maxconn=10)

        def worker(batch_id: str):
            with pool.acquire() as db:
                rows = db.query(\"SELECT * FROM stg.stg_exposures WHERE batch_id = %s\",
                                (batch_id,))
                # La connexion est rendue au pool à la sortie du with

        threads = [Thread(target=worker, args=(bid,)) for bid in batch_ids]
        for t in threads: t.start()
        for t in threads: t.join()

        pool.close()   # ← fermeture de toutes les connexions en fin de programme

    Paramètres de construction
    --------------------------
    dsn : str, optionnel
        Data Source Name PostgreSQL (même format que Database).
        Fallback : variable DATABASE_URL, puis \"dbname=corep_crr3 user=corep_user\".
    minconn : int
        Nombre minimum de connexions maintenues ouvertes (défaut : 1).
    maxconn : int
        Nombre maximum de connexions simultanées autorisées (défaut : 10).
        Au-delà, acquire() lève psycopg2.pool.PoolError.

    Thread-safety
    -------------
    ThreadedConnectionPool est thread-safe pour getconn()/putconn().
    Chaque thread obtient une connexion dédiée — pas de partage de curseur.
    """

    def __init__(self, dsn: Optional[str] = None, minconn: int = 1, maxconn: int = 10):
        _require_psycopg2()
        resolved_dsn = dsn or build_dsn_from_env()
        self._pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, resolved_dsn)
        logger.info("DatabasePool initialisé : minconn=%d maxconn=%d", minconn, maxconn)

    @contextlib.contextmanager
    def acquire(self) -> Generator[Database, None, None]:
        """Emprunte une connexion depuis le pool et la restitue automatiquement.

        Context manager — garantit la restitution même en cas d'exception :

            with pool.acquire() as db:
                db.execute(\"INSERT INTO ...\")
            # → connexion rendue au pool ici (succès ou exception)

        Yields
        ------
        Database
            Instance Database encapsulant la connexion empruntée.
            NE PAS appeler db.close() — le pool gère le cycle de vie.

        Raises
        ------
        psycopg2.pool.PoolError
            Si toutes les connexions du pool sont déjà empruntées (maxconn atteint).
        """
        conn = self._pool.getconn()
        db = Database(conn=conn)
        try:
            yield db
        finally:
            # Restitution inconditionnelle (même en cas d'exception dans le with)
            # NE PAS appeler conn.close() — putconn() remet la connexion en pool
            try:
                conn.rollback()  # Annuler toute transaction pendante avant restitution
            except Exception:  # best-effort: cleanup or optional UI action may fail safely
                pass
            self._pool.putconn(conn)

    def close(self) -> None:
        """Ferme toutes les connexions du pool et libère les ressources serveur.

        À appeler en fin de programme ou de test :
            pool.close()

        Après cet appel, le pool n'est plus utilisable.
        """
        self._pool.closeall()
        logger.info("DatabasePool fermé.")


# ──────────────────────────────────────────────────────────────────────────────
# LECTURE TOLÉRANTE AUX RELATIONS ABSENTES (helper transverse — v4.1.2)
# ──────────────────────────────────────────────────────────────────────────────
_OPTIONAL_RELATION_SQLSTATES = frozenset({"42P01", "42703"})  # undefined_table / undefined_column


def _is_optional_relation_error(exc: BaseException) -> bool:
    """Return True only for PostgreSQL missing-table/missing-column errors."""
    current: Optional[BaseException] = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if str(getattr(current, "pgcode", "")) in _OPTIONAL_RELATION_SQLSTATES:
            return True
        current = current.__cause__ or current.__context__
    return False


def safe_read(db: Any, sql: str, params: tuple[Any, ...] = (), default: Any = None) -> Any:
    """Execute an optional-schema SELECT without masking operational defects.

    Only PostgreSQL ``undefined_table`` (42P01) and ``undefined_column`` (42703)
    are tolerated. Syntax errors, permission failures, connection loss and all
    other defects are re-raised so a regulatory batch fails closed.
    """
    try:
        return db.query(sql, params)
    except Exception as exc:  # fail-closed: error is re-raised or translated after cleanup
        if not _is_optional_relation_error(exc):
            raise
        try:
            db.rollback()
        except Exception:  # fail-closed: error is re-raised or translated after cleanup
            logger.exception("Rollback impossible après absence de relation optionnelle")
            raise
        logger.info(
            "Lecture optionnelle ignorée (SQLSTATE=%s): %s",
            getattr(exc, "pgcode", "unknown"),
            exc,
        )
        return default
