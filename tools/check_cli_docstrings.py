#!/usr/bin/env python3
"""Enforce a minimum function-docstring ratio on user-facing entry points."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Iterable

SCRIPT_RE = re.compile(r'^([A-Za-z0-9_.-]+)\s*=\s*["\']([A-Za-z0-9_.]+):([A-Za-z0-9_]+)["\']\s*$')


def _script_targets(pyproject: Path) -> list[Path]:
    """Resolve Python modules declared in the ``[project.scripts]`` table."""
    root = pyproject.parent
    targets: list[Path] = []
    in_scripts = False
    for raw in pyproject.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_scripts = line == "[project.scripts]"
            continue
        if not in_scripts or not line or line.startswith("#"):
            continue
        match = SCRIPT_RE.match(line)
        if match:
            module = match.group(2)
            targets.append(root / "src" / Path(*module.split(".")).with_suffix(".py"))
    for extra in (root / "batch" / "run_batch.py", root / "launcher.py"):
        if extra.is_file():
            targets.append(extra)
    return list(dict.fromkeys(targets))


def _functions(path: Path) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every function and method defined in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def analyse(root: Path) -> dict[str, object]:
    """Return per-module and aggregate docstring metrics for CLI entry points."""
    modules: dict[str, dict[str, object]] = {}
    total = documented = 0
    for path in _script_targets(root / "pyproject.toml"):
        functions = list(_functions(path))
        with_doc = [node for node in functions if ast.get_docstring(node) is not None]
        missing = [node.name for node in functions if ast.get_docstring(node) is None]
        count = len(functions)
        ratio = 100.0 if count == 0 else 100.0 * len(with_doc) / count
        modules[path.relative_to(root).as_posix()] = {
            "functions": count,
            "documented": len(with_doc),
            "percent": round(ratio, 2),
            "missing": missing,
        }
        total += count
        documented += len(with_doc)
    aggregate = 100.0 if total == 0 else 100.0 * documented / total
    return {
        "functions": total,
        "documented": documented,
        "percent": round(aggregate, 2),
        "modules": modules,
    }


def main() -> int:
    """Run the docstring quality gate and return a shell-compatible status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--min-percent", type=float, default=85.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    payload = analyse(root)
    payload["minimum_percent"] = args.min_percent
    payload["status"] = "PASSED" if payload["percent"] >= args.min_percent else "FAILED"
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"CLI docstrings: {payload['documented']}/{payload['functions']} "
        f"({payload['percent']:.2f} %, minimum {args.min_percent:.2f} %)"
    )
    if payload["status"] != "PASSED":
        for module, metrics in payload["modules"].items():
            if metrics["missing"]:
                print(f"- {module}: {', '.join(metrics['missing'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
