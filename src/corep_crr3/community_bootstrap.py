"""Bootstrap PostgreSQL autonome de l'édition Community SA / SA-CCR.

Le périmètre SQL est défini dans ``COMMUNITY_SQL_CONTRACT.json`` et embarqué
comme ressource du package. Le bootstrap est relançable : chaque script est
identifié par son chemin relatif et son checksum SHA-256 dans
``meta.schema_migrations``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple, cast

from . import __version__
from .db import Database, build_dsn_from_env

logger = logging.getLogger(__name__)

_CONTRACT_NAME = "COMMUNITY_SQL_CONTRACT.json"
_MANIFEST_NAME = "ACTIVE_SQL_MANIFEST.txt"
_RESET_CONFIRMATION = "RESET"
_ALLOWED_GROUPS = {"always", "run_sa", "run_saccr", "post_seed"}
_ENGINE_GROUPS = ("run_sa", "run_saccr")
_FORBIDDEN_SQL_TOKENS = (
    "irb",
    "sft",
    "cva",
    "liquidity",
    "irrbb",
    "market_risk",
    "operational_risk",
    "own_funds",
    "securitisation",
    "large_exposures",
    "crypto_assets",
    "frtb",
    "output_floor",
    "dpm_xbrl",
    "finrep",
)


def _candidate_sql_dirs() -> Iterable[Path]:
    """Retourne les emplacements SQL supportés, du plus robuste au fallback."""
    env_dir = os.getenv("COREP_COMMUNITY_SQL_DIR")
    if env_dir:
        yield Path(env_dir).expanduser().resolve()

    # Ressources incluses dans le package installé / éditable.
    yield Path(__file__).resolve().parent / "sql"

    # Layout source : <racine>/src/corep_crr3/community_bootstrap.py + <racine>/sql.
    yield Path(__file__).resolve().parents[2] / "sql"


def resolve_sql_dir(explicit: Optional[Path] = None) -> Path:
    """Résout le répertoire SQL Community et valide la présence du contrat."""
    candidates = [explicit.resolve()] if explicit is not None else list(_candidate_sql_dirs())
    for candidate in candidates:
        if (candidate / _CONTRACT_NAME).is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"Répertoire SQL Community introuvable ou contrat absent. Emplacements contrôlés : {searched}"
    )


def load_sql_contract(sql_dir: Path) -> dict[str, Any]:
    """Charge et valide le contrat SQL distribué avec l'édition Community."""
    contract_path = sql_dir / _CONTRACT_NAME
    raw = json.loads(contract_path.read_text(encoding="utf-8"))
    if raw.get("version") != __version__:
        raise ValueError(
            f"Version du contrat SQL Community ({raw.get('version')!r}) != version du package ({__version__!r})."
        )
    if raw.get("edition") != "Community":
        raise ValueError(f"Contrat SQL inattendu : edition={raw.get('edition')!r}")
    if raw.get("engines") != ["SA", "SA_CCR"]:
        raise ValueError("Le contrat SQL Community doit exposer exactement SA et SA_CCR.")
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Le contrat SQL Community ne contient aucune étape.")

    seen_paths: set[str] = set()
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"Étape SQL #{index} invalide.")
        for key in ("path", "group", "description"):
            if not isinstance(step.get(key), str) or not step[key].strip():
                raise ValueError(f"Étape SQL #{index} : champ {key!r} invalide.")
        rel_path_value = step["path"]
        rel_path = Path(rel_path_value)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError(f"Étape SQL #{index} : chemin non sûr {rel_path_value!r}.")
        if rel_path_value in seen_paths:
            raise ValueError(f"Étape SQL dupliquée : {rel_path_value}")
        seen_paths.add(rel_path_value)
        if step["group"] not in _ALLOWED_GROUPS:
            raise ValueError(f"Étape SQL #{index} : groupe non autorisé {step['group']!r}.")
        normalized = rel_path_value.lower()
        leaked = sorted(token for token in _FORBIDDEN_SQL_TOKENS if token in normalized)
        if leaked:
            raise ValueError(f"Étape SQL #{index} hors périmètre Community : {', '.join(leaked)}.")
    return cast(dict[str, Any], raw)


def _normalize_engine_filter(engines: Optional[Sequence[str]]) -> tuple[str, ...]:
    """Validate optional Community engine filter."""
    if not engines:
        return ()
    selected = tuple(dict.fromkeys(str(engine) for engine in engines))
    unknown = sorted(set(selected) - set(_ENGINE_GROUPS))
    if unknown:
        raise ValueError("Moteur Community inconnu : " + ", ".join(unknown))
    return selected


def sql_steps(sql_dir: Optional[Path] = None, engines: Optional[Sequence[str]] = None) -> Tuple[dict[str, str], ...]:
    """Retourne la séquence SQL du contrat Community, optionnellement filtrée."""
    resolved = resolve_sql_dir(sql_dir)
    contract = load_sql_contract(resolved)
    selected = set(_normalize_engine_filter(engines))
    if not selected:
        return tuple(contract["steps"])
    return tuple(
        step for step in contract["steps"] if step["group"] in {"always", "post_seed"} or step["group"] in selected
    )


def _profile_manifest_name(engines: Optional[Sequence[str]]) -> str:
    """Return default or engine-specific manifest file name."""
    selected = _normalize_engine_filter(engines)
    if not selected:
        return _MANIFEST_NAME
    return "ACTIVE_SQL_MANIFEST_engine_" + "_".join(selected) + ".txt"


def render_sql_manifest(sql_dir: Optional[Path] = None, engines: Optional[Sequence[str]] = None) -> str:
    """Génère le manifeste lisible à partir du contrat distribué."""
    resolved = resolve_sql_dir(sql_dir)
    contract = load_sql_contract(resolved)
    selected = _normalize_engine_filter(engines)
    scope = " + ".join(selected) if selected else "SA + SA-CCR"
    lines = [
        f"# ACTIVE_SQL_MANIFEST — Corep Engine Community v{contract['version']}",
        f"# Périmètre public strict : {scope}.",
        "# Source d'exécution : COMMUNITY_SQL_CONTRACT.json.",
        "",
        "# Ordre SQL effectif",
    ]
    for index, step in enumerate(sql_steps(resolved, engines=selected), start=1):
        lines.append(f"{index:02d} | {step['group']:<10s} | {step['path']} | {step['description']}")
    return "\n".join(lines) + "\n"


def write_sql_manifest(
    sql_dir: Optional[Path] = None,
    engines: Optional[Sequence[str]] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Réécrit le manifeste par défaut ou un manifeste moteur dans le répertoire SQL résolu."""
    resolved = resolve_sql_dir(sql_dir)
    path = output_path or resolved / _profile_manifest_name(engines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sql_manifest(resolved, engines=engines), encoding="utf-8")
    return path


def _resolved_scripts(sql_dir: Path, steps: Sequence[dict[str, str]]) -> list[tuple[Path, dict[str, str]]]:
    """Execute the resolved scripts helper used by the command workflow."""
    resolved: list[tuple[Path, dict[str, str]]] = []
    missing: list[str] = []
    for step in steps:
        candidate = sql_dir / step["path"]
        if candidate.is_file():
            sql_text = candidate.read_text(encoding="utf-8").lower()
            leaked = sorted(token for token in _FORBIDDEN_SQL_TOKENS if token in sql_text)
            if leaked:
                raise ValueError(f"Contenu SQL hors périmètre Community dans {step['path']} : " + ", ".join(leaked))
            resolved.append((candidate, step))
        else:
            missing.append(step["path"])
    if missing:
        raise FileNotFoundError("Scripts SQL Community manquants : " + ", ".join(missing))
    return resolved


def _ensure_migration_table(db: Database) -> None:
    """Execute the ensure migration table helper used by the command workflow."""
    db.executescript(
        """
        CREATE SCHEMA IF NOT EXISTS meta;
        CREATE TABLE IF NOT EXISTS meta.schema_migrations (
            script_name VARCHAR(255) PRIMARY KEY,
            checksum_sha256 VARCHAR(64) NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            notes TEXT
        );
        """
    )


def _is_applied(db: Database, script_name: str, checksum: str) -> bool:
    """Execute the is applied helper used by the command workflow."""
    rows = db.query(
        """
        SELECT 1
        FROM meta.schema_migrations
        WHERE script_name = %s
          AND checksum_sha256 = %s
        """,
        (script_name, checksum),
    )
    return bool(rows)


def _record_applied(db: Database, script_name: str, checksum: str) -> None:
    """Execute the record applied helper used by the command workflow."""
    db.execute(
        """
        INSERT INTO meta.schema_migrations
            (script_name, checksum_sha256, applied_at, notes)
        VALUES (%s, %s, NOW(), %s)
        ON CONFLICT (script_name) DO UPDATE
        SET checksum_sha256 = EXCLUDED.checksum_sha256,
            applied_at = EXCLUDED.applied_at,
            notes = EXCLUDED.notes
        """,
        (script_name, checksum, f"Applied by Community bootstrap v{__version__}"),
    )
    db.commit()


def bootstrap_postgresql(db: Database, sql_dir: Optional[Path] = None, engines: Optional[Sequence[str]] = None) -> int:
    """Applique le bootstrap SA / SA-CCR et renvoie le nombre de scripts joués."""
    resolved_dir = resolve_sql_dir(sql_dir)
    steps = sql_steps(resolved_dir, engines=engines)
    scripts = _resolved_scripts(resolved_dir, steps)
    _ensure_migration_table(db)

    applied_count = 0
    for sql_file, step in scripts:
        script_id = sql_file.relative_to(resolved_dir).as_posix()
        sql_text = sql_file.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
        if _is_applied(db, script_id, checksum):
            logger.info("Community bootstrap : %s déjà appliqué → SKIP", script_id)
            continue
        logger.info(
            "Community bootstrap : exécution de %s [%s] — %s",
            script_id,
            step["group"],
            step["description"],
        )
        try:
            db.executescript(sql_text)
            _record_applied(db, script_id, checksum)
        except Exception:  # fail-closed: error is re-raised or translated after cleanup
            try:
                db.rollback()
            except Exception:  # best-effort: cleanup or optional UI action may fail safely
                pass
            raise
        applied_count += 1
    return applied_count


def _reset_database(db: Database, sql_dir: Path, confirmation: Optional[str]) -> None:
    """Execute the reset database helper used by the command workflow."""
    allowed_by_env = os.getenv("COREP_ALLOW_DESTRUCTIVE_RESET") == "1"
    if confirmation != _RESET_CONFIRMATION and not allowed_by_env:
        raise ValueError(
            "Reset refusé. Ajouter --confirm-reset RESET ou définir "
            "COREP_ALLOW_DESTRUCTIVE_RESET=1 dans un environnement éphémère."
        )
    contract = load_sql_contract(sql_dir)
    reset_path = sql_dir / str(contract["reset_sql"])
    if not reset_path.is_file():
        raise FileNotFoundError(f"Script de reset introuvable : {reset_path}")
    logger.warning("RESET DESTRUCTIF Community : %s", reset_path)
    db.executescript(reset_path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    """Build the requested CLI or GUI structure."""
    parser = argparse.ArgumentParser(
        description="Bootstrap PostgreSQL Corep Engine Community — SA et SA-CCR",
    )
    parser.add_argument("--dsn", help="DSN PostgreSQL. Défaut : DATABASE_URL / variables PG*.")
    parser.add_argument("--sql-dir", type=Path, help="Répertoire SQL alternatif.")
    parser.add_argument(
        "--engine",
        action="append",
        choices=_ENGINE_GROUPS,
        help="Limite le bootstrap Community à un moteur public. Option répétable.",
    )
    parser.add_argument("--list", action="store_true", help="Liste les scripts sans connexion.")
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Régénère ACTIVE_SQL_MANIFEST.txt ou un manifeste moteur depuis le contrat.",
    )
    parser.add_argument("--manifest-output", type=Path, help="Chemin de sortie explicite du manifeste SQL généré.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DESTRUCTIF : supprime les schémas applicatifs avant le bootstrap.",
    )
    parser.add_argument(
        "--confirm-reset",
        help="Confirmation obligatoire : saisir exactement RESET.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command entry point and return its process status."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    args = _build_parser().parse_args(argv)
    try:
        resolved_dir = resolve_sql_dir(args.sql_dir)
        engine_filter = tuple(args.engine or ()) or None
        if args.list:
            for step in sql_steps(resolved_dir, engines=engine_filter):
                print(f"{step['group']:10s} {step['path']}")
            return 0
        if args.write_manifest:
            path = write_sql_manifest(resolved_dir, engines=engine_filter, output_path=args.manifest_output)
            print(f"✓ Manifeste SQL Community généré : {path}")
            return 0

        dsn = args.dsn or build_dsn_from_env()
        db = Database(dsn)
        try:
            if args.reset:
                _reset_database(db, resolved_dir, args.confirm_reset)
                print("✓ Reset Community exécuté.")
            count = bootstrap_postgresql(db, resolved_dir, engines=engine_filter)
        finally:
            db.close()
        print(f"✓ Bootstrap Community terminé : {count} script(s) appliqué(s).")
        return 0
    except Exception as exc:  # tolerated: optional/legacy path returns a controlled fallback
        logger.error("Bootstrap Community en échec : %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
