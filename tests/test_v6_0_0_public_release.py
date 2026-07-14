from __future__ import annotations

from pathlib import Path

import pytest

from corep_crr3.operational_readiness import run_readiness_checks
from corep_crr3.public_registry import PUBLIC_ENGINES
from corep_crr3.release_integrity import (
    ReleaseIntegrityError,
    create_manifest,
    verify_manifest,
)


def test_public_registry_remains_strictly_sa_and_saccr() -> None:
    assert sorted(PUBLIC_ENGINES) == ["SA", "SA_CCR"]


def test_release_manifest_detects_tampering(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "public.txt"
    target.write_text("stable", encoding="utf-8")
    manifest = create_manifest(tmp_path, version="6.0.0", edition="COMMUNITY")
    verify_manifest(tmp_path, manifest, expected_version="6.0.0")
    target.write_text("tampered", encoding="utf-8")
    with pytest.raises(ReleaseIntegrityError, match="Intégrité"):
        verify_manifest(tmp_path, manifest, expected_version="6.0.0")


def test_readiness_passes_with_explicit_test_resources(tmp_path: Path) -> None:
    report = run_readiness_checks(
        output_dir=tmp_path / "output",
        min_free_mb=0,
        required_resources=(),
        database_probe=lambda: {"database": "test", "applied_migrations": 1},
    )
    assert report.passed
    assert {check.code for check in report.checks} >= {
        "PYTHON_VERSION",
        "ENGINE_VERSION",
        "PUBLIC_SCOPE",
        "OUTPUT_WRITABLE",
    }


def test_readiness_fails_when_resource_is_missing(tmp_path: Path) -> None:
    report = run_readiness_checks(
        output_dir=tmp_path / "output",
        min_free_mb=0,
        required_resources=("missing.resource",),
    )
    assert not report.passed
    resource_check = next(check for check in report.checks if check.code == "RUNTIME_RESOURCES")
    assert resource_check.status == "FAIL"


def test_release_manifest_rejects_new_undeclared_public_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "stable.py").write_text("VALUE = 1\n", encoding="utf-8")
    manifest = create_manifest(tmp_path, version="6.0.0", edition="COMMUNITY")
    (tmp_path / "src" / "unexpected.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(ReleaseIntegrityError, match="non déclarés"):
        verify_manifest(tmp_path, manifest, expected_version="6.0.0")
