from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).resolve().parent


class build_py(_build_py):
    """Embed public legal and release-integrity resources in the wheel."""

    def run(self) -> None:
        super().run()
        resources = Path(self.build_lib) / "corep_crr3" / "resources"
        legal = resources / "legal"
        legal.mkdir(parents=True, exist_ok=True)
        for filename in ("LICENSE", "LICENSE-COMMUNITY.md", "NOTICE"):
            source = ROOT / filename
            if not source.is_file():
                raise RuntimeError(f"Required Community legal document missing: {source}")
            shutil.copy2(source, legal / filename)
        release = resources / "release"
        release.mkdir(parents=True, exist_ok=True)
        manifest = ROOT / "RELEASE_MANIFEST.json"
        if not manifest.is_file():
            raise RuntimeError(
                "RELEASE_MANIFEST.json missing; run corep-community-release-verify --generate"
            )
        shutil.copy2(manifest, release / manifest.name)


setup(cmdclass={"build_py": build_py})
