from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

from tools.build_source_archive import build_source_archive, verify_source_archive
from tools.check_sbom_lock_sync import check as check_sbom

ROOT = Path(__file__).resolve().parents[1]


def test_archived_sbom_matches_runtime_lock_and_package() -> None:
    assert check_sbom(ROOT) == []


def test_current_release_contract_is_green() -> None:
    subprocess.run([sys.executable, "tools/bump_version.py", "--check"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "tools/check_release_contract.py"], cwd=ROOT, check=True)


def test_docker_is_explicitly_one_shot() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" not in dockerfile
    assert 'CMD ["corep-community"]' in dockerfile


def test_public_source_archive_is_byte_reproducible_and_cache_free(tmp_path: Path) -> None:
    archive_a = tmp_path / "source-a.zip"
    archive_b = tmp_path / "source-b.zip"
    prefix = "Corep_engine_community_v6.10.0"
    build_source_archive(ROOT, archive_a, prefix=prefix)
    build_source_archive(ROOT, archive_b, prefix=prefix)
    verify_source_archive(archive_a, expected_prefix=prefix)
    assert hashlib.sha256(archive_a.read_bytes()).digest() == hashlib.sha256(archive_b.read_bytes()).digest()
    with zipfile.ZipFile(archive_a) as archive:
        names = archive.namelist()
    assert names
    assert not any("/.hypothesis/" in name or "/__pycache__/" in name for name in names)
    assert not any(name.endswith((".pyc", ".whl", ".zip")) for name in names)
