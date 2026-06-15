#!/usr/bin/env python3
"""
COREP Engine Community — centre de contrôle graphique.

L'interface reste strictement limitée au périmètre public SA / SA-CCR. Elle
configure PostgreSQL, expose le contrat SQL Community et lance le bootstrap sans
introduire de dépendance vers les moteurs Enterprise.
"""

from __future__ import annotations

import json
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from functools import partial
from datetime import datetime
from typing import Any, Iterable

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk
except Exception:  # pragma: no cover - serveur sans Tk
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    scrolledtext = None  # type: ignore[assignment]

from . import __version__ as VERSION
from .public_registry import PUBLIC_ENGINES

ENV_KEYS = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD")
EDITION = "Community"


@dataclass(frozen=True)
class CommunityPaths:
    project_root: pathlib.Path
    env_path: pathlib.Path
    env_example_path: pathlib.Path
    sql_dir: pathlib.Path
    contract_path: pathlib.Path
    backup_dir: pathlib.Path


@dataclass(frozen=True)
class EnvValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Handle the ok event for the graphical workflow."""
        return not self.errors


def resolve_project_root(start: pathlib.Path | None = None) -> pathlib.Path:
    """Resolve the requested path, resource, or implementation."""
    current = (start or pathlib.Path(__file__).resolve()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "sql").exists():
            return candidate
    return pathlib.Path(__file__).resolve().parents[2]


def get_community_paths(project_root: pathlib.Path | None = None) -> CommunityPaths:
    """Execute the get community paths helper used by the command workflow."""
    root = resolve_project_root(project_root)
    return CommunityPaths(
        project_root=root,
        env_path=root / ".env",
        env_example_path=root / ".env.example",
        sql_dir=root / "sql",
        contract_path=root / "sql" / "COMMUNITY_SQL_CONTRACT.json",
        backup_dir=root / "old" / "config_backups",
    )


def read_env_file(path: pathlib.Path) -> dict[str, str]:
    """Read the requested resource without altering it."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _timestamp() -> str:
    """Execute the timestamp helper used by the command workflow."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_file(path: pathlib.Path, backup_dir: pathlib.Path) -> pathlib.Path | None:
    """Create a timestamped backup before modification."""
    if not path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{path.name}_{_timestamp()}.bak"
    shutil.copy2(path, target)
    return target


def write_env_file(path: pathlib.Path, values: dict[str, str], backup_dir: pathlib.Path | None = None) -> pathlib.Path | None:
    """Write the requested release or configuration resource."""
    backup = backup_file(path, backup_dir) if backup_dir else None
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# COREP Engine Community — configuration PostgreSQL locale",
        f"# Générée par le GUI v{VERSION}. Ne pas versionner les secrets.",
        "",
    ]
    lines.extend(f"{key}={values.get(key, '')}" for key in ENV_KEYS)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return backup


def validate_env_values(values: dict[str, str]) -> EnvValidation:
    """Validate the supplied data and return structured findings."""
    errors: list[str] = []
    warnings: list[str] = []
    for key in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER"):
        if not values.get(key, "").strip():
            errors.append(f"{key} est obligatoire.")
    port = values.get("PGPORT", "").strip()
    if port:
        try:
            parsed = int(port)
            if not 1 <= parsed <= 65535:
                errors.append("PGPORT doit être compris entre 1 et 65535.")
        except ValueError:
            errors.append("PGPORT doit être numérique.")
    if not values.get("PGPASSWORD", ""):
        warnings.append("PGPASSWORD est vide : acceptable uniquement si PostgreSQL l'autorise.")
    return EnvValidation(tuple(errors), tuple(warnings))


def mask_secret(value: str) -> str:
    """Mask secret values before display or logging."""
    if not value:
        return ""
    if len(value) <= 2:
        return "**"
    return value[0] + "***" + value[-1]


def load_contract(path: pathlib.Path) -> dict[str, Any]:
    """Load and normalize the requested runtime data."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


class CommunityGuiApp:
    """Cockpit Tkinter public, sans accès aux composants Enterprise."""

    BG = "#f4f6f8"
    SURFACE = "#ffffff"
    NAVY = "#17324d"
    BLUE = "#246b9e"
    BLUE_DARK = "#174f78"
    GREEN = "#198754"
    AMBER = "#b7791f"
    RED = "#c0392b"
    MUTED = "#627d98"

    def __init__(self, root: "tk.Tk", paths: CommunityPaths | None = None):
        """Initialize the CommunityGuiApp instance."""
        if tk is None or ttk is None or scrolledtext is None:
            raise RuntimeError("Tkinter n'est pas disponible dans cet environnement.")
        self.root = root
        self.paths = paths or get_community_paths()
        self.contract = load_contract(self.paths.contract_path)
        self.process_queue: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.current_process: subprocess.Popen[str] | None = None
        self._process_lock = threading.Lock()
        self._busy = False
        self._closing = False
        self.operation_buttons: list[Any] = []
        self.password_visible_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Prêt")
        self.env_vars = self._build_env_variables()
        self._configure_style()
        self._build_ui()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_env_variables(self) -> dict[str, Any]:
        """Build the requested CLI or GUI structure."""
        values = read_env_file(self.paths.env_path)
        if not values:
            values = read_env_file(self.paths.env_example_path)
        defaults = {
            "PGHOST": "localhost",
            "PGPORT": "5432",
            "PGDATABASE": "corep_crr3",
            "PGUSER": "corep_user",
            "PGPASSWORD": "",
        }
        return {key: tk.StringVar(value=values.get(key, defaults[key])) for key in ENV_KEYS}

    def _configure_style(self) -> None:
        """Execute the configure style helper used by the command workflow."""
        self.root.configure(background=self.BG)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:  # best-effort: cleanup or optional UI action may fail safely
            pass
        style.configure("TFrame", background=self.BG)
        style.configure("Surface.TFrame", background=self.SURFACE)
        style.configure("TLabel", background=self.BG, foreground=self.NAVY, font=("Segoe UI", 10))
        style.configure("Surface.TLabel", background=self.SURFACE, foreground=self.NAVY, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.SURFACE, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.SURFACE, foreground=self.NAVY, font=("Segoe UI Semibold", 15))
        style.configure("Metric.TLabel", background=self.SURFACE, foreground=self.BLUE, font=("Segoe UI Semibold", 22))
        style.configure("Section.TLabelframe", background=self.SURFACE)
        style.configure("Section.TLabelframe.Label", background=self.SURFACE, foreground=self.NAVY,
                        font=("Segoe UI Semibold", 10))
        style.configure("TCheckbutton", background=self.SURFACE, foreground=self.NAVY)
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8),
                        background=self.BLUE, foreground="white")
        style.map("Primary.TButton", background=[("active", self.BLUE_DARK), ("disabled", "#9fb3c8")])
        style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(10, 7),
                        background="#e8f1f8", foreground=self.NAVY)
        style.configure("Danger.TButton", font=("Segoe UI Semibold", 9), padding=(10, 7),
                        background="#fde8e7", foreground=self.RED)
        style.configure("TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(16, 9))
        style.configure("Horizontal.TProgressbar", background=self.BLUE, troughcolor="#e8edf2")

    def _build_ui(self) -> None:
        """Build the requested CLI or GUI structure."""
        self.root.title(f"COREP Engine Community — Control Center v{VERSION}")
        self.root.geometry("980x720")
        self.root.minsize(880, 640)
        self._build_header()

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=18, pady=(14, 8))
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)
        self.tab_home = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.tab_env = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.tab_ops = ttk.Frame(self.notebook, style="Surface.TFrame")
        self.notebook.add(self.tab_home, text="Vue d'ensemble")
        self.notebook.add(self.tab_env, text="PostgreSQL")
        self.notebook.add(self.tab_ops, text="Bootstrap & tests")
        self._build_home()
        self._build_env()
        self._build_operations()
        self._build_footer()

    def _build_header(self) -> None:
        """Build the requested CLI or GUI structure."""
        header = tk.Frame(self.root, bg=self.NAVY, height=88)
        header.pack(fill="x")
        header.pack_propagate(False)
        left = tk.Frame(header, bg=self.NAVY)
        left.pack(side="left", fill="y", padx=22, pady=13)
        tk.Label(left, text="COREP Engine", bg=self.NAVY, fg="white",
                 font=("Segoe UI Semibold", 20)).pack(anchor="w")
        tk.Label(left, text="Community Control Center", bg=self.NAVY, fg="#bcccdc",
                 font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(header, text=f"COMMUNITY  •  v{VERSION}", bg=self.BLUE, fg="white",
                 font=("Segoe UI Semibold", 9), padx=12, pady=6).pack(side="right", padx=22)

    def _build_home(self) -> None:
        """Build the requested CLI or GUI structure."""
        outer = ttk.Frame(self.tab_home, style="Surface.TFrame")
        outer.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(outer, text="Édition publique SA / SA-CCR", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Le cockpit n'expose que les moteurs et scripts inclus dans le contrat open-core Community.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        metrics = ttk.Frame(outer, style="Surface.TFrame")
        metrics.pack(fill="x")
        metrics.columnconfigure((0, 1, 2), weight=1)
        self._metric(metrics, 0, str(len(PUBLIC_ENGINES)), "Moteurs publics")
        self._metric(metrics, 1, str(self.contract.get("version", VERSION)), "Contrat SQL")
        steps = self.contract.get("steps", self.contract.get("files", []))
        self._metric(metrics, 2, str(len(steps) if isinstance(steps, list) else "—"), "Étapes SQL")

        engine_box = ttk.LabelFrame(outer, text="Périmètre disponible", style="Section.TLabelframe")
        engine_box.pack(fill="x", pady=(16, 10))
        descriptions = {
            "SA": "Risque de crédit — approche standard CRR3",
            "SA_CCR": "Risque de contrepartie — SA-CCR",
        }
        for idx, code in enumerate(PUBLIC_ENGINES):
            card = ttk.Frame(engine_box, style="Surface.TFrame", padding=14, relief="solid", borderwidth=1)
            card.grid(row=0, column=idx, sticky="nsew", padx=10, pady=12)
            engine_box.columnconfigure(idx, weight=1)
            ttk.Label(card, text=code.replace("_", "-"), style="Title.TLabel").pack(anchor="w")
            ttk.Label(card, text=descriptions.get(code, "Moteur public"), style="Muted.TLabel").pack(anchor="w", pady=(3, 0))

        boundary = ttk.LabelFrame(outer, text="Frontière produit", style="Section.TLabelframe")
        boundary.pack(fill="x", pady=8)
        ttk.Label(
            boundary,
            text="IRB, Market Risk, CVA, SFT, liquidité, titrisation et autres moteurs Enterprise ne sont ni importés ni accessibles depuis cette édition.",
            style="Surface.TLabel", wraplength=850, justify="left",
        ).pack(anchor="w", padx=14, pady=12)

        quick = ttk.Frame(outer, style="Surface.TFrame")
        quick.pack(fill="x", pady=8)
        ttk.Button(quick, text="Lister le plan SQL", command=lambda: self.run_command(
            [sys.executable, "-m", "corep_crr3.community_bootstrap", "--list"]
        ), style="Secondary.TButton").pack(side="left")
        ttk.Button(quick, text="Tester PostgreSQL", command=self.test_postgresql_connection,
                   style="Secondary.TButton").pack(side="left", padx=8)
        ttk.Button(quick, text="Lancer le bootstrap", command=lambda: self.run_command(
            [sys.executable, "-m", "corep_crr3.community_bootstrap"]
        ), style="Primary.TButton").pack(side="left")

    def _metric(self, parent: Any, column: int, value: str, label: str) -> None:
        """Execute the metric helper used by the command workflow."""
        frame = ttk.Frame(parent, style="Surface.TFrame", padding=14, relief="solid", borderwidth=1)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(frame, text=value, style="Metric.TLabel").pack(anchor="w")
        ttk.Label(frame, text=label, style="Muted.TLabel").pack(anchor="w")

    def _build_env(self) -> None:
        """Build the requested CLI or GUI structure."""
        outer = ttk.Frame(self.tab_env, style="Surface.TFrame")
        outer.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(outer, text="Connexion PostgreSQL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Les paramètres sont stockés dans .env et sauvegardés avant chaque écriture.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 14))

        form = ttk.LabelFrame(outer, text="Paramètres", style="Section.TLabelframe")
        form.pack(fill="x")
        labels = {"PGHOST": "Hôte", "PGPORT": "Port", "PGDATABASE": "Base",
                  "PGUSER": "Utilisateur", "PGPASSWORD": "Mot de passe"}
        self.env_entries: dict[str, Any] = {}
        for row, key in enumerate(ENV_KEYS):
            ttk.Label(form, text=labels[key], style="Surface.TLabel").grid(row=row, column=0, sticky="w", padx=14, pady=9)
            entry = ttk.Entry(form, textvariable=self.env_vars[key], show="•" if key == "PGPASSWORD" else "", width=68)
            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=9)
            self.env_entries[key] = entry
            if key == "PGPASSWORD":
                ttk.Checkbutton(form, text="Afficher", variable=self.password_visible_var,
                                command=self._toggle_password).grid(row=row, column=2, padx=(0, 14))
        form.columnconfigure(1, weight=1)

        controls = ttk.Frame(outer, style="Surface.TFrame")
        controls.pack(fill="x", pady=14)
        ttk.Button(controls, text="Tester la connexion", command=self.test_postgresql_connection,
                   style="Primary.TButton").pack(side="left")
        ttk.Button(controls, text="Sauvegarder .env", command=self.save_env,
                   style="Secondary.TButton").pack(side="left", padx=8)

    def _build_operations(self) -> None:
        """Build the requested CLI or GUI structure."""
        outer = ttk.Frame(self.tab_ops, style="Surface.TFrame")
        outer.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(outer, text="Bootstrap & tests", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Une seule commande peut être active ; le bouton Arrêter termine le processus courant.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        commands = ttk.LabelFrame(outer, text="Commandes Community", style="Section.TLabelframe")
        commands.pack(fill="x")
        actions = [
            ("Lister moteurs publics", [sys.executable, "-m", "corep_crr3.public_registry"]),
            ("Lister le plan SQL", [sys.executable, "-m", "corep_crr3.community_bootstrap", "--list"]),
            ("Régénérer le manifeste", [sys.executable, "-m", "corep_crr3.community_bootstrap", "--write-manifest"]),
            ("Lancer le bootstrap", [sys.executable, "-m", "corep_crr3.community_bootstrap"]),
            ("Smoke tests", [sys.executable, "-m", "pytest", "-q", "tests/test_community_smoke.py"]),
        ]
        for idx, (label, command) in enumerate(actions):
            button = ttk.Button(
                commands,
                text=label,
                command=partial(self.run_command, command),
                style="Primary.TButton" if label == "Lancer le bootstrap" else "Secondary.TButton",
            )
            button.grid(row=idx // 3, column=idx % 3, sticky="ew", padx=7, pady=7)
            self.operation_buttons.append(button)
        for col in range(3):
            commands.columnconfigure(col, weight=1)

        activity = ttk.Frame(outer, style="Surface.TFrame")
        activity.pack(fill="x", pady=(10, 6))
        self.progress = ttk.Progressbar(activity, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.stop_button = ttk.Button(activity, text="Arrêter", command=self.stop_current_process,
                                      style="Danger.TButton", state="disabled")
        self.stop_button.pack(side="right", padx=(10, 0))

        logs = ttk.LabelFrame(outer, text="Console", style="Section.TLabelframe")
        logs.pack(fill="both", expand=True)
        tools = ttk.Frame(logs, style="Surface.TFrame")
        tools.pack(fill="x", padx=8, pady=(6, 0))
        ttk.Button(tools, text="Effacer", command=self._clear_log, style="Secondary.TButton").pack(side="right")
        ttk.Button(tools, text="Exporter", command=self._export_log, style="Secondary.TButton").pack(side="right", padx=6)
        self.log_widget = scrolledtext.ScrolledText(
            logs, state="disabled", wrap="word", height=20, relief="flat",
            font=("Cascadia Mono", 9), background="#0b1f33", foreground="#d9e2ec",
            insertbackground="white", padx=10, pady=8,
        )
        self.log_widget.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_widget.tag_configure("success", foreground="#8bd49c")
        self.log_widget.tag_configure("warning", foreground="#ffd580")
        self.log_widget.tag_configure("error", foreground="#ff9b9b")
        self.log_widget.tag_configure("command", foreground="#82c7ff")
        self._append_log(f"COREP Engine Community Control Center v{VERSION} prêt.\n", "success")

    def _build_footer(self) -> None:
        """Build the requested CLI or GUI structure."""
        footer = ttk.Frame(self.root)
        footer.pack(fill="x", padx=18, pady=(0, 12))
        self.status_dot = tk.Label(footer, text="●", bg=self.BG, fg=self.GREEN, font=("Segoe UI", 10))
        self.status_dot.pack(side="left")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left", padx=5)
        ttk.Button(footer, text="Fermer", command=self._on_close, style="Secondary.TButton").pack(side="right")

    def _collect_env(self) -> dict[str, str]:
        """Execute the collect env helper used by the command workflow."""
        return {key: variable.get().strip() for key, variable in self.env_vars.items()}

    def _toggle_password(self) -> None:
        """Execute the toggle password helper used by the command workflow."""
        self.env_entries["PGPASSWORD"].configure(show="" if self.password_visible_var.get() else "•")

    def save_env(self) -> bool:
        """Persist the current configuration safely."""
        values = self._collect_env()
        result = validate_env_values(values)
        if not result.ok:
            for error in result.errors:
                self._append_log(f"ERREUR — {error}\n", "error")
            if messagebox:
                messagebox.showerror(".env", "Configuration PostgreSQL invalide.")
            return False
        backup = write_env_file(self.paths.env_path, values, self.paths.backup_dir)
        self._append_log(f".env sauvegardé. Backup : {backup or 'aucun fichier précédent'}\n", "success")
        self._set_status(".env sauvegardé", "success")
        return True

    def test_postgresql_connection(self) -> None:
        """Execute the test postgresql connection helper used by the command workflow."""
        if self._busy:
            self._append_log("Une opération est déjà en cours.\n", "warning")
            return
        values = self._collect_env()
        result = validate_env_values(values)
        if not result.ok:
            for error in result.errors:
                self._append_log(f"ERREUR — {error}\n", "error")
            return
        try:
            import psycopg2
        except Exception as exc:  # tolerated: optional/legacy path returns a controlled fallback
            self._append_log(f"psycopg2 indisponible : {exc}\n", "error")
            if messagebox:
                messagebox.showwarning("PostgreSQL", "Installez l'extra postgres : pip install -e .[postgres]")
            return
        masked = {**values, "PGPASSWORD": mask_secret(values.get("PGPASSWORD", ""))}
        self._append_log(f"Test PostgreSQL : {masked}\n", "command")
        self._set_busy(True, "Test PostgreSQL en cours")

        def worker() -> None:
            """Execute the worker helper used by the command workflow."""
            try:
                conn = psycopg2.connect(
                    host=values["PGHOST"], port=values["PGPORT"], dbname=values["PGDATABASE"],
                    user=values["PGUSER"], password=values["PGPASSWORD"], connect_timeout=5,
                )
                conn.close()
                self.process_queue.put(("db_result", True, "Connexion PostgreSQL OK."))
            except Exception as exc:  # boundary: broad external failure is converted to a controlled status
                self.process_queue.put(("db_result", False, f"Connexion PostgreSQL KO : {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def run_command(self, command: list[str]) -> bool:
        """Execute the requested workflow step."""
        if self._busy:
            self._append_log("Une opération est déjà active.\n", "warning")
            return False
        env = os.environ.copy()
        for key, value in self._collect_env().items():
            if value:
                env[key] = value
        env["PYTHONPATH"] = str(self.paths.project_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
        self._append_log(f"\n$ {' '.join(command)}\n", "command")
        self._set_busy(True, "Commande en cours")

        def worker() -> None:
            """Execute the worker helper used by the command workflow."""
            code = -1
            try:
                process = subprocess.Popen(
                    command, cwd=str(self.paths.project_root), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                )
                with self._process_lock:
                    self.current_process = process
                self.process_queue.put(("process_started",))
                assert process.stdout is not None
                for line in process.stdout:
                    self.process_queue.put(("log", line, "normal"))
                code = process.wait()
            except Exception as exc:  # boundary: broad external failure is converted to a controlled status
                self.process_queue.put(("log", f"[command failed] {exc}\n", "error"))
            finally:
                with self._process_lock:
                    self.current_process = None
                self.process_queue.put(("process_done", code))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def stop_current_process(self) -> None:
        """Execute the stop current process helper used by the command workflow."""
        with self._process_lock:
            process = self.current_process
        if process is None or process.poll() is not None:
            self._append_log("Aucun processus actif à arrêter.\n", "warning")
            return
        try:
            process.terminate()
            self._append_log("Demande d'arrêt envoyée.\n", "warning")
        except Exception as exc:  # boundary: broad external failure is converted to a controlled status
            self._append_log(f"Arrêt impossible : {exc}\n", "error")

    def _set_busy(self, busy: bool, status: str) -> None:
        """Execute the set busy helper used by the command workflow."""
        self._busy = busy
        for button in self.operation_buttons:
            button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.start(12)
            self._set_status(status, "busy")
        else:
            self.progress.stop()
            self.stop_button.configure(state="disabled")
            self._set_status(status, "success")

    def _poll_queue(self) -> None:
        """Execute the poll queue helper used by the command workflow."""
        while True:
            try:
                event = self.process_queue.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "log":
                self._append_log(str(event[1]), str(event[2]))
            elif kind == "process_started":
                self.stop_button.configure(state="normal")
            elif kind == "process_done":
                code = int(event[1])
                self._append_log(f"[process exited with code {code}]\n", "success" if code == 0 else "error")
                self._set_busy(False, "Traitement terminé" if code == 0 else f"Échec ({code})")
                if code != 0:
                    self._set_status(f"Échec ({code})", "error")
            elif kind == "db_result":
                ok, text = bool(event[1]), str(event[2])
                self._append_log(text + "\n", "success" if ok else "error")
                self._set_busy(False, "PostgreSQL connecté" if ok else "Connexion en échec")
                if not ok:
                    self._set_status("Connexion en échec", "error")
                if messagebox:
                    (messagebox.showinfo if ok else messagebox.showerror)("PostgreSQL", text)
        if not self._closing:
            self.root.after(120, self._poll_queue)

    def _set_status(self, text: str, level: str) -> None:
        """Execute the set status helper used by the command workflow."""
        self.status_var.set(text)
        colors = {"success": self.GREEN, "warning": self.AMBER, "error": self.RED, "busy": self.BLUE}
        if hasattr(self, "status_dot"):
            self.status_dot.configure(fg=colors.get(level, self.MUTED))

    def _append_log(self, text: str, tag: str = "normal") -> None:
        """Execute the append log helper used by the command workflow."""
        if not hasattr(self, "log_widget"):
            return
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", text, tag)
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _clear_log(self) -> None:
        """Execute the clear log helper used by the command workflow."""
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")

    def _export_log(self) -> pathlib.Path:
        """Execute the export log helper used by the command workflow."""
        log_dir = self.paths.project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"community_gui_{_timestamp()}.log"
        path.write_text(self.log_widget.get("1.0", "end-1c"), encoding="utf-8")
        self._append_log(f"Journal exporté : {path}\n", "success")
        return path

    def _on_close(self) -> None:
        """Handle the on close event for the graphical workflow."""
        with self._process_lock:
            process = self.current_process
        if process is not None and process.poll() is None:
            proceed = True
            if messagebox:
                proceed = messagebox.askyesno("Traitement actif", "Arrêter le traitement et fermer ?")
            if not proceed:
                return
            try:
                process.terminate()
            except Exception:  # best-effort: cleanup or optional UI action may fail safely
                pass
        self._closing = True
        self.root.destroy()


def main(argv: Iterable[str] | None = None) -> int:
    """Run the command entry point and return its process status."""
    _ = list(argv or [])
    if tk is None:
        raise RuntimeError("Tkinter n'est pas disponible. Installez le support Tk de Python.")
    root = tk.Tk()
    CommunityGuiApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
