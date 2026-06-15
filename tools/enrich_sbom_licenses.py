#!/usr/bin/env python3
"""Enrich a CycloneDX JSON SBOM with normalized SPDX license identifiers.

The generator sometimes emits components without ``licenses`` when it is fed a
hash-pinned requirements file. This post-processor resolves licenses from a
reviewed runtime policy first, then from local package metadata. In strict mode,
every package named by the runtime lock must end with a resolved license.

CycloneDX distinguishes a single SPDX identifier (``license.id``) from a
compound SPDX expression (``expression``). This module keeps those two forms
separate and never stores an expression in ``license.id``.
"""
from __future__ import annotations

import argparse
import json
import re
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

_REVIEWED_RUNTIME_LICENSES: dict[str, str] = {
    "defusedxml": "PSF-2.0",
    "et-xmlfile": "MIT",
    "numpy": "BSD-3-Clause",
    "openpyxl": "MIT",
    "psycopg2-binary": "LGPL-3.0-or-later",
    "pyyaml": "MIT",
    "scipy": "BSD-3-Clause",
    "typing-extensions": "PSF-2.0",
}

_CLASSIFIER_TO_SPDX = {
    "Apache Software License": "Apache-2.0",
    "BSD License": "BSD-3-Clause",
    "GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0-or-later",
    "MIT License": "MIT",
    "Python Software Foundation License": "PSF-2.0",
}

_SPDX_EXPRESSION_RE = re.compile(r"(?:^|\s)(?:AND|OR|WITH)(?:\s|$)|[()]", re.IGNORECASE)


def _normalise(name: str) -> str:
    """Return the canonical PEP 503 distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower().strip()


def _names_from_lock(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "--")) or line.startswith("\\"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:==|>=|<=|~=|!=|>|<)", line)
        if match:
            names.add(_normalise(match.group(1)))
    return names


def _metadata_license(name: str) -> str | None:
    try:
        package = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return None
    expression = (package.get("License-Expression") or "").strip()
    if expression and expression.upper() not in {"UNKNOWN", "NONE"}:
        return expression
    short_license = (package.get("License") or "").strip()
    if short_license in {"MIT", "PSFL", "Apache-2.0", "BSD-3-Clause"}:
        return {"PSFL": "PSF-2.0"}.get(short_license, short_license)
    for classifier in package.get_all("Classifier", []):
        prefix = "License :: OSI Approved :: "
        if classifier.startswith(prefix):
            resolved = _CLASSIFIER_TO_SPDX.get(classifier[len(prefix):])
            if resolved:
                return resolved
    return None


def _cyclonedx_license_entry(value: str) -> dict[str, Any]:
    """Serialize a single SPDX identifier or expression for CycloneDX."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("SPDX license value cannot be empty")
    if _SPDX_EXPRESSION_RE.search(normalized):
        return {"expression": normalized}
    return {"license": {"id": normalized}}


def _component_license_ids(component: dict[str, Any]) -> list[str]:
    resolved: list[str] = []
    for item in component.get("licenses") or []:
        if not isinstance(item, dict):
            continue
        license_payload = item.get("license")
        if isinstance(license_payload, dict):
            value = license_payload.get("id") or license_payload.get("name")
            if value:
                resolved.append(str(value))
        expression = item.get("expression")
        if expression:
            resolved.append(str(expression))
    return resolved


def enrich(payload: dict[str, Any], required_names: Iterable[str] = ()) -> tuple[int, list[str]]:
    """Enrich SBOM components and report unresolved required distributions.

    Reviewed runtime mappings take precedence over mutable local metadata. This
    makes release output deterministic across Python environments (notably for
    NumPy 2.4+, whose metadata can expose a bundled-license expression).
    """
    required = {_normalise(name) for name in required_names}
    seen: set[str] = set()
    enriched = 0
    components = payload.get("components") or []

    for component in components:
        if not isinstance(component, dict):
            continue
        name = _normalise(str(component.get("name") or ""))
        if not name:
            continue
        seen.add(name)

        reviewed = _REVIEWED_RUNTIME_LICENSES.get(name)
        if name in required and reviewed:
            desired = [_cyclonedx_license_entry(reviewed)]
            if component.get("licenses") != desired:
                component["licenses"] = desired
                enriched += 1
            continue

        if _component_license_ids(component):
            continue

        resolved = reviewed or _metadata_license(name)
        if resolved:
            component["licenses"] = [_cyclonedx_license_entry(resolved)]
            enriched += 1

    unresolved = sorted(
        name
        for name in required
        if name not in seen
        or not any(
            _normalise(str(component.get("name") or "")) == name
            and _component_license_ids(component)
            for component in components
            if isinstance(component, dict)
        )
    )
    return enriched, unresolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sbom", type=Path)
    parser.add_argument("--required-lock", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.sbom.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("SBOM CycloneDX invalide: objet JSON attendu")
    required = _names_from_lock(args.required_lock) if args.required_lock else set()
    enriched, unresolved = enrich(payload, required)
    args.sbom.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SBOM licences: {enriched} composant(s) enrichi(s)")
    if unresolved:
        print("Licences runtime non résolues: " + ", ".join(unresolved))
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
