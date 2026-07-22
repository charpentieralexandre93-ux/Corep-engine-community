from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8", errors="ignore")


def test_windows_user_scripts_exist_and_keep_current_version() -> None:
    expected = [
        "INSTALL_WINDOWS.bat",
        "RUN_GUI_WINDOWS.bat",
        "BOOTSTRAP_SQL_WINDOWS.bat",
        "launch_community_gui.bat",
    ]
    for script in expected:
        assert (ROOT / script).is_file(), script
    combined = "\n".join(_text(script) for script in expected)
    assert "v6.10.1" in combined
    assert "v6.4.0" not in combined
    assert "v3.3.0" not in combined
    assert "v4.2.5" not in combined


def test_community_user_scripts_follow_one_click_flow() -> None:
    install = _text("INSTALL_WINDOWS.bat")
    gui = _text("RUN_GUI_WINDOWS.bat")
    bootstrap = _text("BOOTSTRAP_SQL_WINDOWS.bat")
    assert 'python -m pip install -e ".[postgres]"' in install
    assert "scripts\\launch_community_gui.py" in gui
    assert "corep_crr3.community_bootstrap --list" in bootstrap
    assert "corep_crr3.community_bootstrap --write-manifest" in bootstrap
    assert (ROOT / "docs" / "INSTALLATION_UTILISATEUR.md").is_file()
