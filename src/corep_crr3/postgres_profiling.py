"""PostgreSQL EXPLAIN budget helpers for COREP E2E gates.

VERSION : 6.6.0
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class QueryBudget:
    """Budget attached to one PostgreSQL query plan."""

    name: str
    max_total_cost: float
    max_plan_rows: int
    max_execution_ms: float
    max_seq_scan_rows: int = 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "QueryBudget":
        """Create a budget from JSON evidence."""
        return cls(
            name=str(payload["name"]),
            max_total_cost=float(payload["max_total_cost"]),
            max_plan_rows=int(payload["max_plan_rows"]),
            max_execution_ms=float(payload["max_execution_ms"]),
            max_seq_scan_rows=int(payload.get("max_seq_scan_rows", 0)),
        )


def explain_sql(sql: str, *, analyze: bool = True) -> str:
    """Return the EXPLAIN statement used by CI and runbooks."""
    flags = "ANALYZE, BUFFERS, FORMAT JSON" if analyze else "FORMAT JSON"
    return f"EXPLAIN ({flags}) {sql.rstrip(';')};"


def _plan_root(payload: Any) -> Mapping[str, Any]:
    """Extract the root plan from EXPLAIN (FORMAT JSON) output."""
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, Mapping):
            plan = first.get("Plan", first)
            if isinstance(plan, Mapping):
                return plan
    if isinstance(payload, Mapping):
        plan = payload.get("Plan", payload)
        if isinstance(plan, Mapping):
            return plan
    raise ValueError("unsupported EXPLAIN JSON payload")


def _walk_nodes(plan: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """Yield one plan node and every nested child plan node."""
    yield plan
    for child in plan.get("Plans", []) or []:
        if isinstance(child, Mapping):
            yield from _walk_nodes(child)


def summarize_explain(payload: Any) -> dict[str, Any]:
    """Summarize a PostgreSQL JSON plan in a deterministic structure."""
    root = _plan_root(payload)
    nodes = tuple(_walk_nodes(root))
    seq_scan_rows = 0
    node_types: list[str] = []
    for node in nodes:
        node_type = str(node.get("Node Type", ""))
        node_types.append(node_type)
        if node_type == "Seq Scan":
            seq_scan_rows += int(float(node.get("Plan Rows", 0)))
    return {
        "node_count": len(nodes),
        "node_types": sorted(set(node_types)),
        "total_cost": float(root.get("Total Cost", 0.0)),
        "plan_rows": int(float(root.get("Plan Rows", 0))),
        "execution_ms": float(root.get("Actual Total Time", root.get("Execution Time", 0.0))),
        "seq_scan_rows": seq_scan_rows,
        "uses_index": any("Index" in item for item in node_types),
    }


def validate_summary(summary: Mapping[str, Any], budget: QueryBudget) -> tuple[str, ...]:
    """Validate one summarized plan against a query budget."""
    errors: list[str] = []
    total_cost = float(summary.get("total_cost", 0.0))
    plan_rows = int(summary.get("plan_rows", 0))
    execution_ms = float(summary.get("execution_ms", 0.0))
    seq_scan_rows = int(summary.get("seq_scan_rows", 0))
    if total_cost > budget.max_total_cost:
        errors.append(f"{budget.name}: total_cost {total_cost:.2f} > {budget.max_total_cost:.2f}")
    if plan_rows > budget.max_plan_rows:
        errors.append(f"{budget.name}: plan_rows {plan_rows} > {budget.max_plan_rows}")
    if execution_ms > budget.max_execution_ms:
        errors.append(f"{budget.name}: execution_ms {execution_ms:.2f} > {budget.max_execution_ms:.2f}")
    if seq_scan_rows > budget.max_seq_scan_rows:
        errors.append(f"{budget.name}: seq_scan_rows {seq_scan_rows} > {budget.max_seq_scan_rows}")
    return tuple(errors)


def load_budgets(path: Path) -> tuple[QueryBudget, ...]:
    """Load query budgets from JSON evidence."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    budgets = tuple(QueryBudget.from_mapping(item) for item in payload.get("query_budgets", []))
    names = [item.name for item in budgets]
    if len(names) != len(set(names)):
        raise ValueError("query budget names must be unique")
    return budgets


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Validate a JSON EXPLAIN summary against a named PostgreSQL query budget."""
    parser = argparse.ArgumentParser(description="Validate PostgreSQL EXPLAIN JSON budget")
    parser.add_argument("--budgets", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    budgets = {item.name: item for item in load_budgets(args.budgets)}
    budget = budgets.get(args.name)
    if budget is None:
        print(f"ERROR: unknown query budget {args.name}")
        return 1
    summary = summarize_explain(json.loads(args.plan.read_text(encoding="utf-8")))
    errors = validate_summary(summary, budget)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK PostgreSQL query budget {args.name}: cost={summary['total_cost']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
