"""Non-régression v6.3.0 du contrat manifeste/ZIP source."""

from pathlib import Path

from corep_crr3.release_integrity import iter_release_files


def test_release_manifest_excludes_transient_build_outputs(tmp_path: Path) -> None:
    """Le manifeste doit couvrir exactement le payload du ZIP source."""
    persistent = tmp_path / "README.md"
    persistent.write_text("release payload\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("SAFE_EXAMPLE=1\n", encoding="utf-8")

    for name in (
        ".coverage",
        ".env.local",
        "coverage.json",
        "coverage.xml",
        "junit.xml",
        "package.whl",
        "source.tar.gz",
    ):
        (tmp_path / name).write_text("temporary output\n", encoding="utf-8")

    dist_a = tmp_path / "dist-a"
    dist_a.mkdir()
    (dist_a / "package.whl").write_text("temporary wheel\n", encoding="utf-8")

    selected = {path.relative_to(tmp_path).as_posix() for path in iter_release_files(tmp_path)}

    assert selected == {".env.example", "README.md"}
