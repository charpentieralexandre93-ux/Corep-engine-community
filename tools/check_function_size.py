#!/usr/bin/env python3
"""Fail when a production function grows beyond the approved size budget."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


def oversized_functions(root: Path, max_lines: int) -> list[str]:
    """Return stable descriptions for functions exceeding ``max_lines``."""
    failures: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.end_lineno is None:
                continue
            length = node.end_lineno - node.lineno + 1
            if length > max_lines:
                failures.append(f"{path}:{node.lineno} {node.name}={length} lines (maximum {max_lines})")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("src"))
    parser.add_argument("--max-lines", type=int, default=200)
    args = parser.parse_args()
    failures = oversized_functions(args.root, args.max_lines)
    if failures:
        print("Functions exceeding the maintainability budget:")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"Function-size guard passed: no function exceeds {args.max_lines} lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
