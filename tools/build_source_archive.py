#!/usr/bin/env python3
"""Build and verify deterministic source ZIP archives.

The archive is allow-by-default for source files and explicitly rejects local
caches, build outputs, secrets and nested binary artefacts.  Every entry uses a
stable timestamp, ordering and POSIX mode so two builds from the same tree are
byte-identical.
"""

from __future__ import annotations

import argparse
import os
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional, Sequence

DEFAULT_SOURCE_DATE_EPOCH = 1781481600
EXCLUDED_PARTS = {
    ".git",
    ".hypothesis",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    ".eggs",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "output",
    "outputs",
    "logs",
    ".tox",
    ".nox",
}
EXCLUDED_NAMES = {
    ".coverage",
    "coverage.json",
    "coverage.xml",
    "junit.xml",
    "pytest-report.xml",
    ".env",
    ".DS_Store",
    "Thumbs.db",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".bak",
    ".whl",
    ".zip",
    ".tar",
    ".gz",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}


class SourceArchiveError(RuntimeError):
    """The source archive violates the release contract."""


def _is_distributable(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name.startswith(".env.") and path.name != ".env.example":
        return False
    return path.is_file() and not path.is_symlink()


def iter_source_files(root: Path) -> Iterable[Path]:
    """Yield source files in stable archive order."""
    root = root.resolve()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise SourceArchiveError(f"Lien symbolique interdit dans une archive source: {path}")
        if _is_distributable(path, root):
            yield path


def _archive_datetime(epoch: int) -> tuple[int, int, int, int, int, int]:
    # ZIP cannot represent dates before 1980 and stores seconds with a 2-second granularity.
    dt = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc)
    if dt.year > 2107:
        raise SourceArchiveError("SOURCE_DATE_EPOCH dépasse la plage supportée par ZIP")
    return dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second - (dt.second % 2)


def _validated_prefix(prefix: str) -> str:
    candidate = PurePosixPath(prefix)
    if not prefix or candidate.is_absolute() or len(candidate.parts) != 1 or prefix in {".", ".."}:
        raise SourceArchiveError(f"Préfixe ZIP non sûr: {prefix!r}")
    return prefix


def build_source_archive(
    root: Path,
    output: Path,
    *,
    prefix: str,
    source_date_epoch: Optional[int] = None,
) -> Path:
    """Create a deterministic source ZIP and verify it immediately."""
    root = root.resolve()
    output = output.resolve()
    if not root.is_dir():
        raise SourceArchiveError(f"Racine source introuvable: {root}")
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise SourceArchiveError("Le ZIP de sortie doit être créé hors de la racine source")

    prefix = _validated_prefix(prefix)
    epoch = source_date_epoch
    if epoch is None:
        epoch = int(os.environ.get("SOURCE_DATE_EPOCH", str(DEFAULT_SOURCE_DATE_EPOCH)))
    timestamp = _archive_datetime(epoch)
    files = tuple(iter_source_files(root))
    if not files:
        raise SourceArchiveError("Aucun fichier source sélectionné")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for path in files:
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=timestamp)
                info.create_system = 3
                mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                info.external_attr = (stat.S_IFREG | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                info.flag_bits = 0x800  # UTF-8 filenames.
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    verify_source_archive(output, expected_prefix=prefix)
    return output


def verify_source_archive(archive_path: Path, *, expected_prefix: Optional[str] = None) -> None:
    """Reject unsafe paths, caches, duplicates and unexpected top-level layouts."""
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise SourceArchiveError(f"Archive introuvable: {archive_path}")
    seen: set[str] = set()
    prefixes: set[str] = set()
    timestamps: set[tuple[int, int, int, int, int, int]] = set()
    with zipfile.ZipFile(archive_path) as archive:
        bad_crc = archive.testzip()
        if bad_crc:
            raise SourceArchiveError(f"CRC invalide dans {bad_crc}")
        for info in archive.infolist():
            name = info.filename
            if name in seen:
                raise SourceArchiveError(f"Entrée ZIP dupliquée: {name}")
            seen.add(name)
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
                raise SourceArchiveError(f"Chemin ZIP non sûr: {name}")
            prefixes.add(path.parts[0])
            timestamps.add(info.date_time)
            relative_parts = path.parts[1:]
            if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in relative_parts):
                raise SourceArchiveError(f"Cache ou sortie de build présent dans le ZIP: {name}")
            leaf = relative_parts[-1]
            if leaf in EXCLUDED_NAMES or PurePosixPath(leaf).suffix.lower() in EXCLUDED_SUFFIXES:
                raise SourceArchiveError(f"Fichier local ou binaire interdit dans le ZIP: {name}")
            if leaf.startswith(".env.") and leaf != ".env.example":
                raise SourceArchiveError(f"Secret local interdit dans le ZIP: {name}")
        if not seen:
            raise SourceArchiveError("Archive source vide")
    if len(prefixes) != 1:
        raise SourceArchiveError(f"Plusieurs racines dans le ZIP: {sorted(prefixes)}")
    actual_prefix = next(iter(prefixes))
    if expected_prefix is not None and actual_prefix != _validated_prefix(expected_prefix):
        raise SourceArchiveError(f"Racine ZIP {actual_prefix!r} != racine attendue {expected_prefix!r}")
    if len(timestamps) != 1:
        raise SourceArchiveError("Les timestamps ZIP ne sont pas déterministes")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Construit ou vérifie un ZIP source déterministe")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prefix")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            verify_source_archive(args.verify, expected_prefix=args.prefix)
            print(f"OK archive source: {args.verify}")
            return 0
        if not args.output or not args.prefix:
            parser.error("--output et --prefix sont requis pour construire l'archive")
        result = build_source_archive(args.root, args.output, prefix=args.prefix)
    except (OSError, ValueError, zipfile.BadZipFile, SourceArchiveError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"OK archive source déterministe: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
