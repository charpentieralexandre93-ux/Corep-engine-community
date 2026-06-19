#!/usr/bin/env python3
"""Vérifie que le SBOM livré reflète exactement le lockfile runtime."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ \\]+)", line.strip())
        if match:
            versions[normalize(match.group(1))] = match.group(2)
    return versions


def check(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    package_name = str(project["name"])
    version = str(project["version"])
    candidates = sorted(root.glob(f"SBOM_Corep_*_v{version}.json"))
    if len(candidates) != 1:
        return [f"SBOM v{version} attendu une fois, trouvé: {[p.name for p in candidates]}"]
    sbom_path = candidates[0]
    payload: dict[str, Any] = json.loads(sbom_path.read_text(encoding="utf-8"))
    components = {normalize(str(component.get("name", ""))): component for component in payload.get("components", [])}
    for name, locked_version in read_lock_versions(root / "requirements-runtime-py311-linux.lock").items():
        component = components.get(name)
        if component is None:
            errors.append(f"composant runtime absent du SBOM: {name}=={locked_version}")
            continue
        actual = str(component.get("version", ""))
        if actual != locked_version:
            errors.append(f"version SBOM incorrecte: {name}={actual}, lock={locked_version}")
        purl = str(component.get("purl", ""))
        if purl and f"@{locked_version}" not in purl:
            errors.append(f"PURL SBOM incorrect: {name}: {purl}")
    metadata_component = payload.get("metadata", {}).get("component", {})
    expected_purl = f"pkg:pypi/{package_name}@{version}"
    if str(metadata_component.get("version", "")) != version:
        errors.append("version de l'application incorrecte dans metadata.component")
    if str(metadata_component.get("purl", "")) != expected_purl:
        errors.append(f"PURL application incorrect: {metadata_component.get('purl')!r}")
    if str(metadata_component.get("bom-ref", "")) != expected_purl:
        errors.append(f"bom-ref application incorrect: {metadata_component.get('bom-ref')!r}")
    return errors


def main() -> int:
    errors = check()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: SBOM, lockfile runtime et version package sont cohérents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
