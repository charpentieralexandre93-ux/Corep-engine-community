"""Non-régression du cockpit Community v5.0.5."""

from __future__ import annotations

import pathlib

from corep_crr3 import __version__, community_gui


def test_community_gui_import_is_side_effect_free_and_public_only():
    assert community_gui.VERSION == __version__
    assert community_gui.EDITION == "Community"
    assert set(community_gui.PUBLIC_ENGINES) == {"SA", "SA_CCR"}
    assert callable(community_gui.main)
    assert hasattr(community_gui, "CommunityGuiApp")


def test_community_env_roundtrip_backup_and_secret_mask(tmp_path: pathlib.Path):
    env_path = tmp_path / ".env"
    backups = tmp_path / "old" / "config_backups"
    env_path.write_text(
        "PGHOST=localhost\nPGPORT=5432\nPGDATABASE=corep\nPGUSER=user\nPGPASSWORD=old_secret\n",
        encoding="utf-8",
    )
    backup = community_gui.write_env_file(
        env_path,
        {
            "PGHOST": "127.0.0.1",
            "PGPORT": "5433",
            "PGDATABASE": "corep_test",
            "PGUSER": "tester",
            "PGPASSWORD": "new_secret",
        },
        backups,
    )
    assert backup is not None and backup.exists()
    values = community_gui.read_env_file(env_path)
    assert values["PGHOST"] == "127.0.0.1"
    assert values["PGPASSWORD"] == "new_secret"
    assert "new_secret" not in community_gui.mask_secret("new_secret")


def test_community_env_validation_rejects_invalid_port():
    result = community_gui.validate_env_values(
        {
            "PGHOST": "localhost",
            "PGPORT": "invalid",
            "PGDATABASE": "corep",
            "PGUSER": "user",
            "PGPASSWORD": "secret",
        }
    )
    assert not result.ok
    assert any("PGPORT" in error for error in result.errors)


def test_community_gui_refuses_overlapping_commands():
    app = object.__new__(community_gui.CommunityGuiApp)
    app._busy = True
    messages = []
    app._append_log = lambda text, tag="normal": messages.append((text, tag))
    assert app.run_command(["python", "-V"]) is False
    assert messages


def test_community_gui_entry_point_and_launchers_exist():
    pyproject = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'corep-community-gui = "corep_crr3.community_gui:main"' in pyproject
    assert pathlib.Path("launch_community_gui.bat").exists()
    assert pathlib.Path("scripts/launch_community_gui.py").exists()
