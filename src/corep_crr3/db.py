"""
================================================================================
MODULE  : db.py
PROJET  : COREP Engine CRR3
VERSION : 4.4.0
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
import os
import contextlib
import logging
from typing import Generator, Optional

# Import paresseux : les fonctions de calcul pures (SA, SA-CCR, CRM…) n'ont pas
# besoin de PostgreSQL. On tolère donc l'absence de psycopg2 à l'import du module ;
# l'erreur n'est levée qu'au moment d'une connexion réelle (cf. _require_psycopg2).
try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    _PSYCOPG2_IMPORT_ERROR = None
except Exception as _exc:  # ModuleNotFoundError ou échec de chargement natif
    psycopg2 = None  # type: ignore[assignment]
    _PSYCOPG2_IMPORT_ERROR = _exc


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
    """Résout le mot de passe PostgreSQL sans le coder en dur (hook coffre-fort).

    Ordre : ``PGPASSWORD`` (direct) → ``PGPASSWORD_FILE`` (chemin d'un fichier
    secret, ex. monté par Vault / un Secret Manager) → ``PGPASSWORD_CMD``
    (commande dont la sortie standard est le secret). Renvoie ``None`` si aucun.
    """
    direct = os.getenv("PGPASSWORD")
    if direct:
        return direct
    path = os.getenv("PGPASSWORD_FILE")
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip() or None
    command = os.getenv("PGPASSWORD_CMD")
    if command:
        import shlex
        # Commande fournie par l'opérateur via env, sans shell implicite.
        import subprocess  # nosec B404
        # Arguments splittés via shlex, sans shell=True.
        result = subprocess.run(  # nosec B603
            shlex.split(command),
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip() or None
    return None


# -----------------------------------------------------------------------------
# Construction du DSN PostgreSQL
# -----------------------------------------------------------------------------
def build_dsn_from_env(
    default: str = "dbname=corep_crr3 user=corep_user host=localhost port=5432",
) -> str:
    """Construit un DSN PostgreSQL en respectant l'ordre de priorité standard.

    Ordre de résolution :
      1. ``DATABASE_URL`` (variable d'environnement) → renvoyée telle quelle.
      2. Variables PostgreSQL standard ``PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD``
         → assemblées en DSN format `key=value`. Au moins ``PGDATABASE`` ET
         ``PGUSER`` doivent être renseignés pour que ce mode soit retenu.
      3. ``default`` → fallback localhost (utile pour les tests / smoke tests).

    Cette fonction NE LIT PAS ``config_postgresql.yaml`` : le câblage YAML est
    fait dans ``run_batch.py`` qui passe explicitement le DSN à ``Database()``.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    pgdatabase = os.getenv("PGDATABASE")
    pguser = os.getenv("PGUSER")
    if pgdatabase and pguser:
        parts = [
            f"host={os.getenv('PGHOST', 'localhost')}",
            f"port={os.getenv('PGPORT', '5432')}",
            f"dbname={pgdatabase}",
            f"user={pguser}",
        ]
        pgpassword = _resolve_pgpassword()
        if pgpassword:
            parts.append(f"password={pgpassword}")
        return " ".join(parts)

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

    def __init__(self, dsn: str = None, *, conn=None):
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
            self.dsn  = None
            self.conn = conn
        else:
            _require_psycopg2()
            self.dsn  = dsn or build_dsn_from_env()
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
        self.cursor_factory = psycopg2.extras.RealDictCursor

    # ──────────────────────────────────────────────────────────────────────────
    # GESTION DES TRANSACTIONS
    # ──────────────────────────────────────────────────────────────────────────

    def commit(self):
        """Valide (commit) la transaction courante.

        À appeler après un bloc d'opérations DML (INSERT/UPDATE/DELETE)
        qui ne sont pas encapsulées dans db.transaction().

        Usage typique : après ingest_dataset() dans ingestion.py.
        Préférer db.transaction() pour les blocs multi-opérations.
        """
        self.conn.commit()

    def rollback(self):
        """Annule (rollback) la transaction courante.

        À appeler dans les blocs except pour annuler les modifications
        partielles en cas d'erreur.

        Note : db.transaction() gère le rollback automatiquement via
        son bloc except — inutile de l'appeler manuellement dans ce cas.
        """
        self.conn.rollback()

    @contextlib.contextmanager
    def transaction(self):
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
            yield                  # Exécution du bloc with
            self.conn.commit()     # Validation si pas d'exception
        except Exception:
            self.conn.rollback()   # Annulation en cas d'erreur
            raise                  # Re-lever pour que l'appelant gère

    # ──────────────────────────────────────────────────────────────────────────
    # COMMANDES DML (Data Manipulation Language)
    # ──────────────────────────────────────────────────────────────────────────

    def execute(self, sql: str, params=()):
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

    def executescript(self, sql_script: str):
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

    def executemany(self, sql: str, params_seq):
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
            psycopg2.extras.execute_values(
                cur, sql, params_seq, page_size=_EXECUTE_VALUES_PAGE_SIZE
            )
            return cur

    # ──────────────────────────────────────────────────────────────────────────
    # REQUÊTES SELECT
    # ──────────────────────────────────────────────────────────────────────────

    def query(self, sql: str, params=()):
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
        with self.conn.cursor(cursor_factory=self.cursor_factory) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    # ──────────────────────────────────────────────────────────────────────────
    # CYCLE DE VIE
    # ──────────────────────────────────────────────────────────────────────────

    def close(self):
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

    def __init__(self, dsn: str = None, minconn: int = 1, maxconn: int = 10):
        _require_psycopg2()
        resolved_dsn = dsn or build_dsn_from_env()
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn, maxconn, resolved_dsn
        )
        logger.info(
            "DatabasePool initialisé : minconn=%d maxconn=%d", minconn, maxconn
        )

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
        db   = Database(conn=conn)
        try:
            yield db
        finally:
            # Restitution inconditionnelle (même en cas d'exception dans le with)
            # NE PAS appeler conn.close() — putconn() remet la connexion en pool
            try:
                conn.rollback()   # Annuler toute transaction pendante avant restitution
            except Exception:
                pass
            self._pool.putconn(conn)

    def close(self):
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
def safe_read(db, sql: str, params: tuple = (), default=None):
    """Exécute un SELECT en isolant ses échecs de la transaction courante.

    Sur un sous-ensemble de moteurs (base fraîche), une table ou une colonne d'un
    moteur désactivé peut être absente. Un SELECT direct lèverait alors une
    erreur qui met la transaction PostgreSQL en échec (``InFailedSqlTransaction``)
    et fait planter toute écriture en aval. ``safe_read`` :

      1. tente la lecture et renvoie son résultat (``list[dict]``) ;
      2. en cas d'échec, **annule la transaction** (``rollback``) pour la rendre
         de nouveau utilisable, puis renvoie ``default``.

    Couvre table absente ET colonne absente (contrairement à un simple test
    d'existence de table via ``to_regclass``). C'est l'unique point de robustesse
    partagé par la réconciliation, les contrôles, l'export CSV et le snapshot des
    règles (auparavant : deux mécanismes distincts).

    Le ``rollback`` est lui-même protégé : un objet ``db`` dépourvu de méthode
    ``rollback`` (faux objets de test) ne provoque pas d'erreur.
    """
    try:
        return db.query(sql, params)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return default
