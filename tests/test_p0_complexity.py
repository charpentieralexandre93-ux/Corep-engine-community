from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path(__file__).parents[1] / "src" / "corep_crr3" / "standard_engine.py"
TARGETS = {
    "run_standard_engine", "_filter_standard_rows", "_sme_totals_by_obligor",
    "_load_standard_runtime", "_resolve_ccf", "_resolve_base_risk_weight",
    "_partition_protections", "_apply_funded_protections",
    "_apply_unfunded_protections", "_process_standard_exposure",
    "_persist_standard_batches", "_report_standard_anomalies",
}


def complexity(node: ast.AST) -> int:
    score = 1
    branches = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp,
        ast.ExceptHandler, ast.comprehension, ast.match_case,
    )
    for child in ast.walk(node):
        if isinstance(child, branches):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
    return score


def test_standard_p0_units_stay_below_cc_20() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert TARGETS <= functions.keys()
    assert {name: complexity(functions[name]) for name in TARGETS if complexity(functions[name]) >= 20} == {}
