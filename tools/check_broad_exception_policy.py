#!/usr/bin/env python3
"""Reject undocumented ``except Exception`` handlers in production sources."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

_ALLOWED_MARKERS = (
    "fail-closed",
    "tolerated",
    "boundary",
    "best-effort",
    "compatibility",
    "optional",
    "fallback",
    "pragma",
    "robustesse",
    "relation optionnelle",
    "dataset optionnel",
    "référentiel optionnel",
    "moteur sft optionnel",
    "ancienne installation",
)


def undocumented_handlers(root: Path) -> list[str]:
    failures: list[str] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not isinstance(node.type, ast.Name) or node.type.id != "Exception":
                continue
            line = lines[node.lineno - 1]
            comment = line.split("#", 1)[1].strip().lower() if "#" in line else ""
            if len(comment) < 4:
                failures.append(f"{path.as_posix()}:{node.lineno}: undocumented broad exception")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("src/corep_crr3"))
    args = parser.parse_args()
    failures = undocumented_handlers(args.root)
    if failures:
        print("\n".join(failures))
        return 1
    print(f"PASS broad-exception policy: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
