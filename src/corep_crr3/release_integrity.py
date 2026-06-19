"""Deterministic source/runtime manifest generation and verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    ".hypothesis",
    ".venv",
    "venv",
    ".eggs",
    "htmlcov",
    "output",
    "outputs",
    "logs",
    ".tox",
    ".nox",
}


class ReleaseIntegrityError(RuntimeError):
    """The release manifest is invalid or no longer matches the artefacts."""


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    product_version: str
    edition: str
    entries: tuple[ManifestEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize this result into a plain dictionary."""
        return {
            "schema_version": self.schema_version,
            "product_version": self.product_version,
            "edition": self.edition,
            "entries": [asdict(entry) for entry in self.entries],
        }


def _sha256(path: Path) -> str:
    """Execute the sha256 helper used by the command workflow."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_allowed(path: Path, root: Path, manifest_path: Optional[Path]) -> bool:
    """Execute the is allowed helper used by the command workflow."""
    relative = path.relative_to(root)
    if any(part in _EXCLUDED_PARTS or part.endswith(".egg-info") for part in relative.parts):
        return False
    if manifest_path is not None and path.resolve() == manifest_path.resolve():
        return False
    if path.name in {".coverage", ".env"} or path.suffix in {".pyc", ".pyo", ".log"}:
        return False
    return path.is_file()


def iter_release_files(root: Path, manifest_path: Optional[Path] = None) -> Iterable[Path]:
    """Yield every distributable file under ``root``.

    Release integrity is allow-by-default at the file level and deny-by-name for
    generated caches, build outputs and local secrets.  This makes the manifest
    cover the complete ZIP payload instead of only a hand-maintained subset of
    directories.
    """
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if _is_allowed(path, root, manifest_path):
            yield path


def create_manifest(
    root: Path,
    *,
    version: str,
    edition: str,
    manifest_path: Optional[Path] = None,
) -> ReleaseManifest:
    """Create the requested release artifact."""
    root = root.resolve()
    if not _SEMVER_RE.fullmatch(version):
        raise ReleaseIntegrityError(f"Version invalide: {version!r}")
    edition_value = edition.strip().upper()
    if edition_value not in {"ENTERPRISE", "COMMUNITY"}:
        raise ReleaseIntegrityError("edition doit valoir ENTERPRISE ou COMMUNITY")
    entries = tuple(
        ManifestEntry(path.relative_to(root).as_posix(), _sha256(path), path.stat().st_size)
        for path in iter_release_files(root, manifest_path)
    )
    if not entries:
        raise ReleaseIntegrityError("Aucun artefact sélectionné pour le manifeste")
    return ReleaseManifest(1, version, edition_value, entries)


def write_manifest(manifest: ReleaseManifest, output: Path) -> Path:
    """Write the requested release or configuration resource."""
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=str(output.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()
    return output


def load_manifest(path: Path) -> ReleaseManifest:
    """Load and normalize the requested runtime data."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = tuple(
            ManifestEntry(str(item["path"]), str(item["sha256"]), int(item["size"])) for item in payload["entries"]
        )
        return ReleaseManifest(
            schema_version=int(payload["schema_version"]),
            product_version=str(payload["product_version"]),
            edition=str(payload["edition"]),
            entries=entries,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReleaseIntegrityError(f"Manifeste illisible: {path}: {exc}") from exc


def verify_manifest(
    root: Path,
    manifest: ReleaseManifest,
    *,
    expected_version: Optional[str] = None,
) -> None:
    """Verify the requested artifact against its contract."""
    root = root.resolve()
    if manifest.schema_version != 1:
        raise ReleaseIntegrityError(f"Version de schéma de manifeste non supportée: {manifest.schema_version}")
    if expected_version is not None and manifest.product_version != expected_version:
        raise ReleaseIntegrityError(
            f"Version du manifeste {manifest.product_version} != version attendue {expected_version}"
        )
    declared = {entry.path: entry for entry in manifest.entries}
    if len(declared) != len(manifest.entries):
        raise ReleaseIntegrityError("Chemin dupliqué dans le manifeste")
    failures: list[str] = []
    current = {path.relative_to(root).as_posix() for path in iter_release_files(root, root / "RELEASE_MANIFEST.json")}
    undeclared = sorted(current - set(declared))
    if undeclared:
        failures.append("artefacts non déclarés: " + ", ".join(undeclared[:20]))
    for relative, entry in sorted(declared.items()):
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            failures.append(f"chemin hors racine: {relative}")
            continue
        if not path.is_file():
            failures.append(f"fichier absent: {relative}")
            continue
        if path.stat().st_size != entry.size:
            failures.append(f"taille différente: {relative}")
            continue
        if _sha256(path) != entry.sha256:
            failures.append(f"SHA-256 différent: {relative}")
    if failures:
        raise ReleaseIntegrityError("Intégrité de release invalide: " + "; ".join(failures[:20]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command entry point and return its process status."""
    parser = argparse.ArgumentParser(description="Génère ou vérifie RELEASE_MANIFEST.json")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=Path("RELEASE_MANIFEST.json"))
    parser.add_argument("--version")
    parser.add_argument("--edition", choices=("ENTERPRISE", "COMMUNITY"))
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    try:
        if args.generate:
            if not args.version or not args.edition:
                parser.error("--version et --edition sont requis avec --generate")
            manifest = create_manifest(root, version=args.version, edition=args.edition, manifest_path=manifest_path)
            write_manifest(manifest, manifest_path)
        manifest = load_manifest(manifest_path)
        verify_manifest(root, manifest, expected_version=args.version)
    except ReleaseIntegrityError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"OK: {manifest.edition} {manifest.product_version}, {len(manifest.entries)} artefacts vérifiés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
