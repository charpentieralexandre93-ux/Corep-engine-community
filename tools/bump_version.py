#!/usr/bin/env python3
"""Gestion centralisée de la version — empêche toute dérive entre fichiers.

Le bug historique (`!= "4.2.8"` resté en dur pendant que le contrat passait en
4.3.0) venait d'un bump manuel partiel que *rien* ne contrôlait. Ce script
résout la cause racine : il **découvre** tous les emplacements de version sous
la racine du dépôt (pas de liste figée à maintenir), peut les **aligner** d'un
coup, et surtout les **vérifie** (mode CI).

Emplacements gérés (découverte par motif) :

  CRITIQUES (doivent tous être identiques ; toute divergence = échec) :
    - `__version__ = "x.y.z"`            dans **/__init__.py
    - `version = "x.y.z"`                dans **/pyproject.toml
    - `"version": "x.y.z"`               dans **/*contract*.json
    - `__version__ == "x.y.z"`           dans **/test*.py (assertions de smoke)
    - en-tête de version                 dans **/ACTIVE_SQL_MANIFEST.txt

  COSMÉTIQUES (alignés sur la version canonique ; vérifiés aussi) :
    - en-têtes `VERSION : x.y.z`         dans **/*.py et **/*.sql
        exception : un fichier dont le nom encode `_vMAJ_MIN_PATCH`
        (ex. migration `..._v4_2_7.sql`) conserve la version de son nom —
        c'est un label d'introduction, pas la version courante.
    - titre `Corep Engine Community vx.y.z — validation finale` dans **/*.sql

Usage :
    python tools/bump_version.py --check            # CI : échoue si dérive
    python tools/bump_version.py --set 4.3.1         # aligne tout
    python tools/bump_version.py --set 4.3.1 --dry-run   # aperçu sans écrire
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

SEMVER = r"\d+\.\d+\.\d+"
SEMVER_FULL = re.compile(rf"^{SEMVER}$")
MIGRATION_RE = re.compile(r"_v(\d+)_(\d+)_(\d+)")
EXCLUDE_DIRS = {
    ".git", "__pycache__", "old", "input.bak", "build", "dist",
    "node_modules", ".hypothesis", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".venv", "venv", ".eggs",
}
SCAN_SUFFIXES = {".py", ".toml", ".json", ".txt", ".sql"}


@dataclass(frozen=True)
class Rule:
    name: str
    critical: bool
    match_file: Callable[[Path], bool]
    regex: "re.Pattern[str]"


RULES: tuple[Rule, ...] = (
    Rule("__version__", True, lambda p: p.name == "__init__.py",
         re.compile(rf'__version__\s*=\s*["\'](?P<v>{SEMVER})["\']')),
    Rule("pyproject", True, lambda p: p.name == "pyproject.toml",
         re.compile(rf'(?m)^\s*version\s*=\s*["\'](?P<v>{SEMVER})["\']')),
    Rule("contract", True, lambda p: p.suffix == ".json" and "contract" in p.name.lower(),
         re.compile(rf'"version"\s*:\s*"(?P<v>{SEMVER})"')),
    Rule("smoke_assert", True, lambda p: p.suffix == ".py" and "test" in p.name.lower(),
         re.compile(rf'__version__\s*==\s*["\'](?P<v>{SEMVER})["\']')),
    Rule("manifest", True, lambda p: p.name == "ACTIVE_SQL_MANIFEST.txt",
         re.compile(rf'ACTIVE_SQL_MANIFEST[^\n]*?\bv(?P<v>{SEMVER})\b')),
    Rule("version_header", False, lambda p: p.suffix in {".py", ".sql"},
         re.compile(rf'VERSION\s*:\s*(?P<v>{SEMVER})')),
    Rule("sql_title", False, lambda p: p.suffix == ".sql",
         re.compile(rf'Corep Engine Community v(?P<v>{SEMVER})\s*—\s*validation finale')),
)


@dataclass
class Finding:
    rule: Rule
    path: Path
    version: str


def filename_version(path: Path) -> Optional[str]:
    """Version encodée dans le nom de fichier (label de migration), sinon None."""
    m = MIGRATION_RE.search(path.stem)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else None


def iter_files(root: Path, self_path: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.resolve() == self_path:
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix not in SCAN_SUFFIXES:
            continue
        yield p


def collect(root: Path, self_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for p in iter_files(root, self_path):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for rule in RULES:
            if not rule.match_file(p):
                continue
            for m in rule.regex.finditer(text):
                findings.append(Finding(rule, p, m.group("v")))
    return findings


def expected_for(finding: Finding, canonical: str) -> str:
    """Version attendue : version du nom de fichier pour les en-têtes de
    migration, version canonique partout ailleurs."""
    if finding.rule.name == "version_header":
        fv = filename_version(finding.path)
        if fv is not None:
            return fv
    return canonical


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def cmd_check(root: Path, self_path: Path) -> int:
    findings = collect(root, self_path)
    if not findings:
        print("✗ Aucun emplacement de version trouvé sous", root)
        return 1

    crit = [f for f in findings if f.rule.critical]
    crit_versions = sorted({f.version for f in crit})
    print(f"Emplacements analysés : {len(findings)} "
          f"({len(crit)} critiques, {len(findings) - len(crit)} cosmétiques)")

    ok = True
    if len(crit_versions) != 1:
        ok = False
        print("\n✗ DÉRIVE sur des champs CRITIQUES (versions différentes) :")
        for v in crit_versions:
            files = sorted({rel(f.path, root) for f in crit if f.version == v})
            print(f"    {v} :")
            for fp in files:
                print(f"        - {fp}")
        canonical = None
    else:
        canonical = crit_versions[0]
        print(f"✓ Champs critiques cohérents : {canonical}")

    if canonical is not None:
        mism = [f for f in findings
                if not f.rule.critical and f.version != expected_for(f, canonical)]
        if mism:
            ok = False
            print("\n✗ En-têtes cosmétiques désalignés :")
            for f in mism:
                exp = expected_for(f, canonical)
                print(f"    {rel(f.path, root)} [{f.rule.name}] : "
                      f"{f.version} (attendu {exp})")
        else:
            print("✓ En-têtes cosmétiques alignés (exceptions migrations respectées)")

    print("\n" + ("✅ Cohérence de version : OK" if ok
                  else "❌ Cohérence de version : ÉCHEC"))
    return 0 if ok else 1


def cmd_set(root: Path, self_path: Path, target: str, dry_run: bool) -> int:
    if not SEMVER_FULL.match(target):
        print(f"✗ Version invalide : {target!r} (attendu MAJ.MIN.PATCH)")
        return 2

    changes: list[tuple[str, str, str, str]] = []  # (fichier, règle, ancien, nouveau)
    for p in iter_files(root, self_path):
        text = p.read_text(encoding="utf-8")
        new_text = text
        for rule in RULES:
            if not rule.match_file(p):
                continue
            # En-têtes de migration : on ne touche pas (label d'introduction).
            if rule.name == "version_header" and filename_version(p) is not None:
                continue

            def repl(m: "re.Match[str]") -> str:
                whole, off = m.group(0), m.start(0)
                a, b = m.start("v") - off, m.end("v") - off
                if m.group("v") != target:
                    changes.append((rel(p, root), rule.name, m.group("v"), target))
                return whole[:a] + target + whole[b:]

            new_text = rule.regex.sub(repl, new_text)
        if new_text != text and not dry_run:
            p.write_text(new_text, encoding="utf-8")

    if not changes:
        print(f"Rien à changer : tout est déjà en {target}.")
    else:
        verb = "À CHANGER (dry-run)" if dry_run else "Modifié"
        print(f"{verb} → {target} : {len(changes)} occurrence(s)")
        for fp, rule_name, old, new in changes:
            print(f"    {fp} [{rule_name}] : {old} → {new}")

    if dry_run:
        return 0
    print()
    return cmd_check(root, self_path)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cohérence de version (check/set).")
    parser.add_argument("--root", type=Path, default=None,
                        help="Racine du dépôt (défaut : parent de tools/).")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="Vérifie la cohérence (CI).")
    g.add_argument("--set", metavar="X.Y.Z", help="Aligne tous les emplacements.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Avec --set : montre les changements sans écrire.")
    args = parser.parse_args(argv)

    self_path = Path(__file__).resolve()
    root = (args.root or self_path.parents[1]).resolve()

    if args.check:
        return cmd_check(root, self_path)
    return cmd_set(root, self_path, args.set, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
