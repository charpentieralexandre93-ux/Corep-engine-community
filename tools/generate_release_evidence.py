#!/usr/bin/env python3
"""Generate a machine-readable, auditable release evidence bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha(root: Path) -> Optional[str]:
    value = os.getenv("GITHUB_SHA")
    if value:
        return value
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _file_evidence(path: Optional[Path], root: Path) -> Optional[dict[str, Any]]:
    if path is None:
        return None
    resolved = path if path.is_absolute() else root / path
    if not resolved.is_file():
        return {"path": str(path), "status": "MISSING"}
    try:
        relative = resolved.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = str(resolved.resolve())
    return {
        "path": relative,
        "status": "PRESENT",
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _json_payload(path: Optional[Path], root: Path) -> Optional[dict[str, Any]]:
    """Load a JSON evidence document while preserving missing-file status."""
    if path is None:
        return None
    resolved = path if path.is_absolute() else root / path
    if not resolved.is_file():
        return {"path": str(path), "status": "MISSING"}
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    payload["path"] = resolved.resolve().relative_to(root.resolve()).as_posix()
    payload["status"] = "PRESENT"
    return payload


def build_evidence(
    *,
    root: Path,
    edition: str,
    version: str,
    postgres_e2e: str,
    test_summary: str,
    coverage_percent: Optional[float],
    postgres_version: Optional[str],
    manifest: Optional[Path],
    artifact: Optional[Path],
    sbom: Optional[Path],
    dependency_audit: str,
    branch_coverage_report: Optional[Path] = None,
) -> dict[str, Any]:
    edition_value = edition.strip().upper()
    if edition_value not in {"ENTERPRISE", "COMMUNITY"}:
        raise ValueError("edition doit valoir ENTERPRISE ou COMMUNITY")
    e2e_status = postgres_e2e.strip().upper()
    if e2e_status not in {"PASSED", "FAILED", "NOT_EXECUTED"}:
        raise ValueError("postgres_e2e doit valoir PASSED, FAILED ou NOT_EXECUTED")
    audit_status = dependency_audit.strip().upper()
    if audit_status not in {"PASSED", "FAILED", "NOT_EXECUTED"}:
        raise ValueError("dependency_audit doit valoir PASSED, FAILED ou NOT_EXECUTED")
    if not version or version.count(".") != 2:
        raise ValueError("version SemVer invalide")
    return {
        "schema_version": 1,
        "product_version": version,
        "edition": edition_value,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "commit_sha": _git_sha(root),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "verification": {
            "unit_and_integration_tests": test_summary,
            "coverage_percent": coverage_percent,
            "postgres_e2e": e2e_status,
            "postgres_version": postgres_version,
            "dependency_audit": audit_status,
            "branch_coverage": _json_payload(branch_coverage_report, root),
        },
        "artifacts": {
            "release_manifest": _file_evidence(manifest, root),
            "release_archive": _file_evidence(artifact, root),
            "sbom": _file_evidence(sbom, root),
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Génère la preuve technique d'une release")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--edition", required=True, choices=("ENTERPRISE", "COMMUNITY"))
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--postgres-e2e", required=True, choices=("PASSED", "FAILED", "NOT_EXECUTED")
    )
    parser.add_argument("--test-summary", required=True)
    parser.add_argument("--coverage-percent", type=float)
    parser.add_argument("--postgres-version")
    parser.add_argument("--manifest", type=Path, default=Path("RELEASE_MANIFEST.json"))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--sbom", type=Path)
    parser.add_argument(
        "--dependency-audit", default="NOT_EXECUTED", choices=("PASSED", "FAILED", "NOT_EXECUTED")
    )
    parser.add_argument("--branch-coverage-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload = build_evidence(
            root=args.root.resolve(),
            edition=args.edition,
            version=args.version,
            postgres_e2e=args.postgres_e2e,
            test_summary=args.test_summary,
            coverage_percent=args.coverage_percent,
            postgres_version=args.postgres_version,
            manifest=args.manifest,
            artifact=args.artifact,
            sbom=args.sbom,
            dependency_audit=args.dependency_audit,
            branch_coverage_report=args.branch_coverage_report,
        )
    except ValueError as exc:
        parser.error(str(exc))
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Release evidence written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
