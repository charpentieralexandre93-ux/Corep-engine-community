"""Public runtime-readiness checks for the Community SA/SA-CCR edition."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Optional, Sequence

from . import __version__
from .db import Database, build_dsn_from_env
from .public_registry import PUBLIC_ENGINES


@dataclass(frozen=True)
class ReadinessCheck:
    code: str
    status: str
    message: str
    details: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ReadinessReport:
    generated_at: str
    engine_version: str
    checks: tuple[ReadinessCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every mandatory readiness check passed."""
        return not any(check.status == "FAIL" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this result into a plain dictionary."""
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


def _check(
    code: str,
    passed: bool,
    success: str,
    failure: str,
    details: Optional[dict[str, Any]] = None,
) -> ReadinessCheck:
    """Evaluate the requested readiness or integrity condition."""
    return ReadinessCheck(code, "PASS" if passed else "FAIL", success if passed else failure, details)


def _resource_exists(relative: str) -> bool:
    """Execute the resource exists helper used by the command workflow."""
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / relative).is_file():
        return True
    try:
        from importlib.resources import files

        package_root = files("corep_crr3")
        if relative.startswith("sql/"):
            target = package_root
            for part in PurePosixPath(relative).parts:
                target = target.joinpath(part)
            return target.is_file()
        if relative in {"LICENSE", "LICENSE-COMMUNITY.md", "NOTICE"}:
            return package_root.joinpath("resources").joinpath("legal").joinpath(relative).is_file()
        if relative == "RELEASE_MANIFEST.json":
            return package_root.joinpath("resources").joinpath("release").joinpath(relative).is_file()
    except (ImportError, ModuleNotFoundError, OSError):
        return False
    return False


_DEFAULT_REQUIRED_RELATIONS = (
    "meta.schema_migrations",
    "meta.batch_run_control",
    "ref.ref_regulatory_versions",
)


def _default_database_probe(required_relations: Iterable[str]) -> dict[str, Any]:
    """Execute the default database probe helper used by the command workflow."""
    db = Database(build_dsn_from_env())
    try:
        server = db.query("SELECT current_database() AS database_name, version() AS server_version")
        missing: list[str] = []
        for relation in required_relations:
            row = db.query("SELECT to_regclass(%s) AS relation_name", (relation,))
            if not row or row[0].get("relation_name") is None:
                missing.append(relation)
        if missing:
            raise RuntimeError("relations PostgreSQL obligatoires absentes: " + ", ".join(missing))
        migration_rows = db.query("SELECT COUNT(*) AS count FROM meta.schema_migrations")
        return {
            "database": server[0].get("database_name") if server else None,
            "server_version": server[0].get("server_version") if server else None,
            "applied_migrations": int(migration_rows[0].get("count", 0)) if migration_rows else 0,
            "required_relations": list(required_relations),
        }
    finally:
        db.close()


def run_readiness_checks(
    *,
    output_dir: Path,
    min_free_mb: int = 100,
    required_env: Iterable[str] = (),
    database_probe: Optional[Callable[[], Any]] = None,
    require_database: bool = True,
    required_db_relations: Iterable[str] = _DEFAULT_REQUIRED_RELATIONS,
    required_resources: Iterable[str] = (
        "sql/COMMUNITY_SQL_CONTRACT.json",
        "sql/ACTIVE_SQL_MANIFEST.txt",
        "LICENSE",
        "LICENSE-COMMUNITY.md",
        "NOTICE",
        "RELEASE_MANIFEST.json",
    ),
) -> ReadinessReport:
    """Execute the requested workflow step."""
    checks: list[ReadinessCheck] = []
    checks.append(
        _check(
            "PYTHON_VERSION",
            sys.version_info >= (3, 9),
            "Version Python supportée",
            "Python 3.9 ou supérieur est requis",
            {"python": platform.python_version()},
        )
    )
    version_parts = __version__.split(".")
    version_ok = len(version_parts) == 3 and all(part.isdigit() for part in version_parts)
    checks.append(
        _check(
            "ENGINE_VERSION",
            version_ok,
            "Version moteur cohérente",
            "Version moteur invalide",
            {"version": __version__},
        )
    )
    engines = sorted(PUBLIC_ENGINES)
    checks.append(
        _check(
            "PUBLIC_SCOPE",
            engines == ["SA", "SA_CCR"],
            "Périmètre public SA/SA-CCR conforme",
            "Le registre public contient un moteur non autorisé ou incomplet",
            {"engines": engines},
        )
    )
    missing = sorted(item for item in required_resources if not _resource_exists(item))
    checks.append(
        _check(
            "RUNTIME_RESOURCES",
            not missing,
            "Ressources runtime présentes",
            "Ressources runtime absentes",
            {"missing": missing},
        )
    )

    output = output_dir.resolve()
    writable = False
    error: Optional[str] = None
    try:
        output.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".corep-community-health-", dir=str(output))
        os.close(fd)
        Path(name).unlink()
        writable = True
    except OSError as exc:
        error = str(exc)
    checks.append(
        _check(
            "OUTPUT_WRITABLE",
            writable,
            "Répertoire de sortie accessible en écriture",
            "Répertoire de sortie non accessible en écriture",
            {"path": str(output), "error": error},
        )
    )

    disk_base = output if output.exists() else output.parent
    free_mb = shutil.disk_usage(disk_base).free // (1024 * 1024)
    checks.append(
        _check(
            "DISK_SPACE",
            free_mb >= min_free_mb,
            "Espace disque suffisant",
            f"Espace disque inférieur au seuil de {min_free_mb} MiB",
            {"free_mb": free_mb, "minimum_mb": min_free_mb},
        )
    )
    missing_env = sorted(name for name in required_env if not os.getenv(name))
    checks.append(
        _check(
            "REQUIRED_ENV",
            not missing_env,
            "Variables d'environnement obligatoires présentes",
            "Variables d'environnement obligatoires absentes",
            {"missing": missing_env},
        )
    )

    probe = database_probe
    if probe is None and require_database:
        relations = tuple(required_db_relations)
        probe = lambda: _default_database_probe(relations)
    if probe is not None:
        try:
            result = probe()
        except Exception as exc:  # boundary: operator/database integration
            checks.append(ReadinessCheck("DATABASE", "FAIL", f"Sonde PostgreSQL en échec: {exc}"))
        else:
            details = result if isinstance(result, dict) else {"result": str(result)}
            checks.append(ReadinessCheck("DATABASE", "PASS", "Sonde PostgreSQL réussie", details))
    else:
        checks.append(ReadinessCheck("DATABASE", "NOT_EXECUTED", "Sonde PostgreSQL explicitement désactivée"))
    return ReadinessReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        engine_version=__version__,
        checks=tuple(checks),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command entry point and return its process status."""
    parser = argparse.ArgumentParser(description="Diagnostic Community SA/SA-CCR")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--min-free-mb", type=int, default=100)
    parser.add_argument("--require-env", action="append", default=[])
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--skip-database", action="store_true", help="Désactive explicitement la sonde PostgreSQL (build uniquement)")
    args = parser.parse_args(argv)
    report = run_readiness_checks(
        output_dir=args.output_dir,
        min_free_mb=max(0, args.min_free_mb),
        required_env=args.require_env,
        require_database=not args.skip_database,
    )
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
