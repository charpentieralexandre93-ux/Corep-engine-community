"""Product-surface tests for Community v6.2.0."""

from __future__ import annotations

import json
from pathlib import Path

from corep_crr3.community_gui import (
    ENV_KEYS,
    get_community_paths,
    load_contract,
    mask_secret,
    read_env_file,
    validate_env_values,
    write_env_file,
)


def test_environment_helpers_round_trip_and_mask_secrets(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    backup_dir = tmp_path / "backups"
    values = {
        "PGHOST": "localhost",
        "PGPORT": "5432",
        "PGDATABASE": "corep_crr3",
        "PGUSER": "corep_user",
        "PGPASSWORD": "secret",
    }

    assert write_env_file(env_path, values, backup_dir) is None
    assert read_env_file(env_path) == values
    backup = write_env_file(env_path, {**values, "PGPORT": "5433"}, backup_dir)
    assert backup is not None and backup.is_file()
    assert read_env_file(env_path)["PGPORT"] == "5433"
    assert mask_secret("") == ""
    assert mask_secret("x") == "**"
    assert mask_secret("secret") == "s***t"
    assert tuple(read_env_file(env_path)) == ENV_KEYS


def test_environment_validation_reports_errors_and_warnings() -> None:
    invalid = validate_env_values({"PGPORT": "70000"})
    assert not invalid.ok
    assert "PGHOST est obligatoire." in invalid.errors
    assert "PGPORT doit être compris entre 1 et 65535." in invalid.errors
    assert invalid.warnings

    non_numeric = validate_env_values({"PGHOST": "db", "PGPORT": "abc", "PGDATABASE": "corep", "PGUSER": "user"})
    assert "PGPORT doit être numérique." in non_numeric.errors

    valid = validate_env_values(
        {
            "PGHOST": "db",
            "PGPORT": "5432",
            "PGDATABASE": "corep",
            "PGUSER": "user",
            "PGPASSWORD": "pw",
        }
    )
    assert valid.ok
    assert not valid.warnings


def test_contract_and_project_paths_are_fail_safe(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "sql").mkdir(parents=True)
    (project / "pyproject.toml").write_text('[project]\nname="community"\n', encoding="utf-8")
    contract_path = project / "sql" / "COMMUNITY_SQL_CONTRACT.json"
    contract_path.write_text(json.dumps({"version": "6.2.0", "engines": ["SA", "SA_CCR"]}), encoding="utf-8")

    paths = get_community_paths(project)
    assert paths.project_root == project
    assert paths.contract_path == contract_path
    assert load_contract(contract_path)["engines"] == ["SA", "SA_CCR"]

    contract_path.write_text("not-json", encoding="utf-8")
    assert load_contract(contract_path) == {}
    contract_path.unlink()
    assert load_contract(contract_path) == {}


class _Value:
    def __init__(self, value: object = "") -> None:
        self.value = value

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.value = value


class _Widget:
    def __init__(self, text: str = "") -> None:
        self.config: list[dict[str, object]] = []
        self.text = text
        self.started = False

    def configure(self, **kwargs: object) -> None:
        self.config.append(kwargs)

    def start(self, _interval: int) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def insert(self, _where: str, text: str, _tag: str = "normal") -> None:
        self.text += text

    def see(self, _where: str) -> None:
        return None

    def delete(self, _start: str, _end: str) -> None:
        self.text = ""

    def get(self, _start: str, _end: str) -> str:
        return self.text


class _Root:
    def __init__(self) -> None:
        self.after_calls = 0
        self.destroyed = False

    def after(self, _delay: int, _callback: object) -> None:
        self.after_calls += 1

    def destroy(self) -> None:
        self.destroyed = True


def _headless_app(tmp_path: Path):
    import queue
    import threading

    from corep_crr3.community_gui import CommunityGuiApp, CommunityPaths

    app = CommunityGuiApp.__new__(CommunityGuiApp)
    app.paths = CommunityPaths(
        project_root=tmp_path,
        env_path=tmp_path / ".env",
        env_example_path=tmp_path / ".env.example",
        sql_dir=tmp_path / "sql",
        contract_path=tmp_path / "sql" / "COMMUNITY_SQL_CONTRACT.json",
        backup_dir=tmp_path / "backups",
    )
    app.env_vars = {
        "PGHOST": _Value("localhost"),
        "PGPORT": _Value("5432"),
        "PGDATABASE": _Value("corep"),
        "PGUSER": _Value("user"),
        "PGPASSWORD": _Value("secret"),
    }
    app.env_entries = {"PGPASSWORD": _Widget()}
    app.password_visible_var = _Value(False)
    app.operation_buttons = [_Widget(), _Widget()]
    app.progress = _Widget()
    app.stop_button = _Widget()
    app.status_var = _Value("Prêt")
    app.status_dot = _Widget()
    app.log_widget = _Widget()
    app.root = _Root()
    app.process_queue = queue.Queue()
    app._process_lock = threading.Lock()
    app.current_process = None
    app._busy = False
    app._closing = False
    return app


def test_headless_gui_configuration_status_and_logs(tmp_path: Path, monkeypatch) -> None:
    import corep_crr3.community_gui as gui

    monkeypatch.setattr(gui, "messagebox", None)
    app = _headless_app(tmp_path)
    assert app._collect_env()["PGPASSWORD"] == "secret"

    app.password_visible_var.set(True)
    app._toggle_password()
    assert app.env_entries["PGPASSWORD"].config[-1] == {"show": ""}

    assert app.save_env()
    assert app.paths.env_path.is_file()
    assert "sauvegardé" in app.log_widget.text

    app.env_vars["PGPORT"].set("invalid")
    assert not app.save_env()
    assert "PGPORT doit être numérique" in app.log_widget.text

    app._set_busy(True, "Calcul")
    assert app._busy and app.progress.started
    assert all(widget.config[-1]["state"] == "disabled" for widget in app.operation_buttons)
    app._set_busy(False, "Terminé")
    assert not app._busy and not app.progress.started
    assert app.status_var.get() == "Terminé"

    app._clear_log()
    assert app.log_widget.text == ""
    app.log_widget.text = "trace"
    exported = app._export_log()
    assert exported.read_text(encoding="utf-8") == "trace"


def test_headless_gui_command_queue_and_process_control(tmp_path: Path, monkeypatch) -> None:
    import corep_crr3.community_gui as gui

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target
            self.daemon = daemon

        def start(self) -> None:
            self.target()

    class Process:
        def __init__(self, *args, **kwargs) -> None:
            self.stdout = iter(["line one\n", "line two\n"])
            self.terminated = False

        def wait(self) -> int:
            return 0

        def poll(self):
            return None

        def terminate(self) -> None:
            self.terminated = True

    monkeypatch.setattr(gui.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(gui.subprocess, "Popen", Process)
    monkeypatch.setattr(gui, "messagebox", None)

    app = _headless_app(tmp_path)
    assert app.run_command(["python", "--version"])
    app._poll_queue()
    assert "line one" in app.log_widget.text
    assert "process exited with code 0" in app.log_widget.text
    assert app.root.after_calls == 1

    app._busy = True
    assert not app.run_command(["ignored"])
    app._busy = False
    app.stop_current_process()
    assert "Aucun processus actif" in app.log_widget.text

    active = Process()
    app.current_process = active
    app.stop_current_process()
    assert active.terminated

    app._on_close()
    assert app._closing and app.root.destroyed


def test_headless_gui_poll_queue_failure_and_database_result(tmp_path: Path, monkeypatch) -> None:
    import corep_crr3.community_gui as gui

    monkeypatch.setattr(gui, "messagebox", None)
    app = _headless_app(tmp_path)
    app.process_queue.put(("process_started",))
    app.process_queue.put(("process_done", 2))
    app.process_queue.put(("db_result", False, "database unavailable"))
    app._poll_queue()

    assert app.stop_button.config
    assert "process exited with code 2" in app.log_widget.text
    assert "database unavailable" in app.log_widget.text
    assert app.status_var.get() == "Connexion en échec"
