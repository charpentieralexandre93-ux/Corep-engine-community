#!/usr/bin/env python3
"""Génère le SBOM CycloneDX depuis le lockfile runtime — déterministe, hors-ligne.

v6_8_1 : le SBOM livré n'est plus une copie de release en release mais la
sortie reproductible de cet outil. Sources de vérité :
  - composants : requirements-runtime-py311-linux.lock (name==version) ;
  - application : pyproject.toml (name, version) ;
  - licences : reprises du SBOM précédent pour tout name@version identique
    (l'enrichissement initial vient de tools/enrich_sbom_licenses.py sur un
    runner connecté ; hors-ligne, les licences connues sont préservées et
    les composants nouveaux sont signalés pour enrichissement en CI).

Usage :
    python tools/generate_sbom_from_lock.py --edition ENTERPRISE \
        --output SBOM_Corep_Enterprise_vX.Y.Z.json [--licenses-from PREV.json]
    python tools/generate_sbom_from_lock.py --check --edition ENTERPRISE
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements-runtime-py311-linux.lock"


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path = LOCK) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ \\]+)", line.strip())
        if match:
            versions[match.group(1)] = match.group(2)
    return dict(sorted(versions.items(), key=lambda kv: _normalize(kv[0])))


def _license_map(previous: Path | None) -> dict[tuple[str, str], list]:
    if previous is None or not previous.exists():
        return {}
    payload = json.loads(previous.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], list] = {}
    meta_component = payload.get("metadata", {}).get("component")
    candidates = list(payload.get("components", []))
    if meta_component:
        # v6.10.1 itér. 11 : le composant applicatif porte une licence (EULA /
        # Apache-2.0, enrichissement P1) qui doit survivre à la régénération au
        # même titre que celles des bibliothèques — sinon `--check` ne peut
        # structurellement plus passer une fois l'enrichissement scellé.
        candidates.append(meta_component)
    for component in candidates:
        licenses = component.get("licenses")
        if licenses:
            out[(_normalize(str(component.get("name", ""))), str(component.get("version", "")))] = licenses
    return out


def _app_component(name: str, version: str, purl: str, lic: dict[tuple[str, str], list]) -> dict:
    component: dict = {"bom-ref": purl, "name": name, "purl": purl, "type": "application", "version": version}
    found = lic.get((_normalize(name), version))
    if found:
        component["licenses"] = found
    return component


def build_sbom(edition: str, licenses_from: Path | None) -> tuple[dict, list[str]]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = str(project["version"])
    app_purl = f"pkg:pypi/{project['name']}@{version}"
    lic = _license_map(licenses_from)
    components, missing = [], []
    for name, locked in read_lock().items():
        purl = f"pkg:pypi/{_normalize(name)}@{locked}"
        component: dict = {
            "bom-ref": purl,
            "name": name,
            "purl": purl,
            "type": "library",
            "version": locked,
        }
        found = lic.get((_normalize(name), locked))
        if found:
            component["licenses"] = found
        else:
            missing.append(f"{name}=={locked}")
        components.append(component)
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": _app_component(project["name"], version, app_purl, lic),
            "tools": [{"name": "generate_sbom_from_lock.py", "vendor": "corep-engine"}],
        },
        "components": components,
    }
    return sbom, missing


def render(sbom: dict) -> str:
    return json.dumps(sbom, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", required=True, choices=["ENTERPRISE", "COMMUNITY"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--licenses-from", type=Path, default=None)
    parser.add_argument(
        "--check", action="store_true", help="Vérifie que le SBOM courant == sortie de l'outil (reproductibilité)."
    )
    args = parser.parse_args(argv)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = str(project["version"])
    edition_name = "Enterprise" if args.edition == "ENTERPRISE" else "Community"
    default_target = ROOT / f"SBOM_Corep_{edition_name}_v{version}.json"
    licenses_from = args.licenses_from or (default_target if default_target.exists() else None)
    sbom, missing = build_sbom(args.edition, licenses_from)
    rendered = render(sbom)
    if args.check:
        current = default_target.read_text(encoding="utf-8") if default_target.exists() else ""
        if current != rendered:
            print(f"ERROR: {default_target.name} ne correspond pas à la sortie de l'outil", file=sys.stderr)
            return 1
        print(f"OK: {default_target.name} est reproductible depuis le lockfile")
        return 0
    target = args.output or default_target
    target.write_text(rendered, encoding="utf-8")
    print(f"SBOM généré: {target} ({len(sbom['components'])} composants)")
    if missing:
        print("Licences à enrichir en CI (tools/enrich_sbom_licenses.py) :", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
