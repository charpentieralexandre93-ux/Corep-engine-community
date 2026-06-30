"""SQL migration plan governance for deterministic COREP bootstrap.

VERSION : 6.6.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

STAGE_ORDER = ("00_reset", "01_schema", "02_seeds", "03_mapping", "04_post_seed")
MIGRATION_STATE_SCHEMA = "meta"
MIGRATION_STATE_TABLE = "corep_schema_migrations"


@dataclass(frozen=True)
class MigrationStep:
    """One SQL file in the ordered bootstrap plan."""

    order: int
    stage: str
    path: str
    sha256: str
    destructive: bool = False


@dataclass(frozen=True)
class AppliedMigration:
    """One migration already recorded in the database state table."""

    path: str
    sha256: str
    applied_order: int


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum for one migration file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stage(relative: Path) -> str:
    """Map a SQL relative path to a normalized bootstrap stage."""
    first = relative.parts[0]
    if first.startswith("00_"):
        return "00_reset"
    if first in STAGE_ORDER:
        return first
    return "99_other"


def _stage_rank(stage: str) -> int:
    """Return the deterministic sort rank for a migration stage."""
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else len(STAGE_ORDER)


def discover_plan(sql_root: Path, *, include_reset: bool = False) -> tuple[MigrationStep, ...]:
    """Discover the deterministic SQL execution plan.

    The migration state table has a unique index on ``applied_order``.  Earlier
    builds used the stage rank itself as the order, which made every file in
    the same stage share the same value.  The production plan now sorts by
    stage and relative path first, then assigns a contiguous global sequence
    (1..N), so the plan remains deterministic and can be recorded safely.
    """
    root = sql_root.resolve()
    candidates: list[tuple[int, str, str, Path, bool]] = []
    for path in sorted(root.rglob("*.sql")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        stage = _stage(relative)
        destructive = relative.parts[0].startswith("00_") or "reset" in path.name.lower()
        if destructive and not include_reset:
            continue
        candidates.append((_stage_rank(stage), relative.as_posix(), stage, path, destructive))

    steps: list[MigrationStep] = []
    for order, (_, relative, stage, path, destructive) in enumerate(sorted(candidates), start=1):
        steps.append(
            MigrationStep(
                order=order,
                stage=stage,
                path=relative,
                sha256=_sha256(path),
                destructive=destructive,
            )
        )
    return tuple(steps)


def validate_plan(plan: Iterable[MigrationStep], *, production: bool = True) -> tuple[str, ...]:
    """Validate ordering, duplicates and production safety."""
    steps = tuple(plan)
    errors: list[str] = []
    paths = [step.path for step in steps]
    orders = [step.order for step in steps]
    if len(paths) != len(set(paths)):
        errors.append("duplicate SQL migration path")
    if len(orders) != len(set(orders)):
        errors.append("duplicate SQL migration applied_order")
    if orders and orders != list(range(1, len(orders) + 1)):
        errors.append("SQL migration applied_order must be a contiguous 1..N sequence")
    if paths != [step.path for step in sorted(steps, key=lambda item: (item.order, item.path))]:
        errors.append("SQL migration plan is not sorted deterministically")
    if production and any(step.destructive for step in steps):
        errors.append("destructive reset SQL is forbidden in production plans")
    stages = {step.stage for step in steps}
    for required in ("01_schema", "02_seeds", "03_mapping", "04_post_seed"):
        if required not in stages:
            errors.append(f"missing required SQL stage: {required}")
    return tuple(errors)


def state_table_ddl(*, schema: str = MIGRATION_STATE_SCHEMA, table: str = MIGRATION_STATE_TABLE) -> str:
    """Return the idempotent SQL state-table DDL used by migration runners."""
    qualified = f"{schema}.{table}"
    return "\n".join(
        [
            f"CREATE SCHEMA IF NOT EXISTS {schema};",
            f"CREATE TABLE IF NOT EXISTS {qualified} (",
            "    applied_order integer NOT NULL,",
            "    path text PRIMARY KEY,",
            "    sha256 char(64) NOT NULL,",
            "    stage text NOT NULL,",
            "    applied_at timestamptz NOT NULL DEFAULT now(),",
            "    applied_by text NOT NULL DEFAULT current_user,",
            "    CONSTRAINT ck_corep_schema_migrations_sha CHECK (sha256 ~ '^[0-9a-f]{64}$')",
            ");",
            f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_order ON {qualified}(applied_order);",
        ]
    )


def record_step_sql(
    step: MigrationStep,
    *,
    schema: str = MIGRATION_STATE_SCHEMA,
    table: str = MIGRATION_STATE_TABLE,
) -> str:
    """Return the SQL statement recording one applied migration checksum."""
    qualified = f"{schema}.{table}"
    path = step.path.replace("'", "''")
    sha256 = step.sha256.replace("'", "''")
    stage = step.stage.replace("'", "''")
    return (
        f"INSERT INTO {qualified}(applied_order, path, sha256, stage) "
        f"VALUES ({step.order}, '{path}', '{sha256}', '{stage}') "
        "ON CONFLICT (path) DO UPDATE SET "
        "applied_order = EXCLUDED.applied_order, "
        "sha256 = EXCLUDED.sha256, "
        "stage = EXCLUDED.stage "
        f"WHERE {qualified}.sha256 = EXCLUDED.sha256;"
    )


def build_apply_manifest(plan: Iterable[MigrationStep], *, version: str, edition: str) -> dict[str, object]:
    """Build a runner-friendly migration manifest with state-table and rollback policy."""
    steps = tuple(plan)
    return {
        "schema_version": 2,
        "product_version": version,
        "edition": edition.upper(),
        "state_table": f"{MIGRATION_STATE_SCHEMA}.{MIGRATION_STATE_TABLE}",
        "state_table_ddl": state_table_ddl(),
        "rollback_policy": "forward-only; compensating SQL must be reviewed and signed separately",
        "steps": [
            {
                **asdict(step),
                "record_sql": record_step_sql(step),
            }
            for step in steps
        ],
    }


def normalize_applied_records(records: Iterable[Mapping[str, object]]) -> tuple[AppliedMigration, ...]:
    """Normalize database rows from the migration state table."""
    normalized: list[AppliedMigration] = []
    for item in records:
        normalized.append(
            AppliedMigration(
                path=str(item.get("path", "")),
                sha256=str(item.get("sha256", "")),
                applied_order=int(item.get("applied_order", -1)),
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.applied_order))


def validate_applied_records(plan: Iterable[MigrationStep], records: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    """Compare expected migration checksums with records read from a database."""
    expected = {step.path: step for step in plan}
    applied = {record.path: record for record in normalize_applied_records(records)}
    errors: list[str] = []
    for path, step in expected.items():
        record = applied.get(path)
        if record is None:
            errors.append(f"missing applied migration: {path}")
            continue
        if record.sha256 != step.sha256:
            errors.append(f"checksum drift for {path}: database={record.sha256} source={step.sha256}")
        if record.applied_order != step.order:
            errors.append(f"order drift for {path}: database={record.applied_order} source={step.order}")
    unexpected = sorted(set(applied) - set(expected))
    for path in unexpected:
        errors.append(f"unexpected applied migration: {path}")
    return tuple(errors)


def build_rollback_template(plan: Iterable[MigrationStep], *, ticket: str = "CHANGE-ID") -> str:
    """Return a non-destructive rollback template for change-management review."""
    lines = [
        "-- COREP rollback template — manual review required",
        f"-- Ticket: {ticket}",
        "-- Policy: no automatic destructive rollback is generated by the engine.",
        "-- Each compensating statement must be reviewed, signed and tested separately.",
        "",
    ]
    for step in reversed(tuple(plan)):
        lines.append(f"-- Review compensating action for {step.path} ({step.sha256})")
    return "\n".join(lines) + "\n"


def write_plan(plan: Iterable[MigrationStep], output: Path, *, version: str, edition: str) -> Path:
    """Write a machine-readable migration evidence file."""
    payload = build_apply_manifest(plan, version=version, edition=edition)
    payload["stages"] = list(STAGE_ORDER)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI validator for the SQL bootstrap plan."""
    parser = argparse.ArgumentParser(description="Validate ordered SQL migration plan")
    parser.add_argument("--sql-root", type=Path, default=Path("sql"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--edition", required=True, choices=("COMMUNITY", "ENTERPRISE"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rollback-template", type=Path)
    parser.add_argument("--include-reset", action="store_true")
    parser.add_argument("--allow-destructive", action="store_true")
    args = parser.parse_args(argv)
    plan = discover_plan(args.sql_root, include_reset=args.include_reset)
    errors = validate_plan(plan, production=not args.allow_destructive)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.output:
        write_plan(plan, args.output, version=args.version, edition=args.edition)
    if args.rollback_template:
        args.rollback_template.parent.mkdir(parents=True, exist_ok=True)
        args.rollback_template.write_text(build_rollback_template(plan), encoding="utf-8")
    print(f"OK SQL migration plan {args.edition} v{args.version}: {len(plan)} step(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
