"""Typed access to versioned regulatory runtime parameters.

``ref.ref_runtime_parameters`` is the single database source for runtime
switches and scalar parameters that must be auditable by regulatory version.
Missing *rows* may use an explicit caller-provided default; database/schema
errors are never hidden.
"""
from __future__ import annotations

from typing import Any, Mapping, TypeVar, cast

from .db import Database

T = TypeVar("T")


class RuntimeParameterError(ValueError):
    """Raised when a stored runtime parameter cannot be converted safely."""


def _cast_parameter(value: Any, parameter_type: str, *, name: str) -> Any:
    normalized_type = (parameter_type or "TEXT").strip().upper()
    try:
        if normalized_type in {"INT", "INTEGER"}:
            return int(value)
        if normalized_type in {"REAL", "FLOAT", "NUMERIC", "DECIMAL"}:
            return float(value)
        if normalized_type in {"BOOL", "BOOLEAN"}:
            normalized = str(value).strip().upper()
            if normalized in {"Y", "YES", "TRUE", "1", "ON"}:
                return True
            if normalized in {"N", "NO", "FALSE", "0", "OFF"}:
                return False
            raise ValueError(f"boolean value {value!r} is invalid")
        return str(value) if value is not None else ""
    except (TypeError, ValueError) as exc:
        raise RuntimeParameterError(
            f"Paramètre runtime {name!r} invalide pour le type {normalized_type}: {value!r}"
        ) from exc


def get_parameters(
    db: Database,
    regulatory_version_id: str,
    parameter_names: tuple[str, ...] | list[str] | set[str],
) -> dict[str, Any]:
    """Load and cast multiple parameters in one query.

    The function intentionally does not catch database exceptions: a missing
    mandatory table, a permission problem or a broken SQL contract must fail the
    calling engine instead of silently applying Python constants.
    """
    names = tuple(dict.fromkeys(str(name) for name in parameter_names if str(name)))
    if not names:
        return {}
    rows = db.query(
        """
        SELECT parameter_name, parameter_value, parameter_type
        FROM ref.ref_runtime_parameters
        WHERE regulatory_version_id = %s
          AND parameter_name = ANY(%s)
        """,
        (regulatory_version_id, list(names)),
    )
    values: dict[str, Any] = {}
    for row in rows:
        name = str(row.get("parameter_name") or "")
        if not name:
            continue
        values[name] = _cast_parameter(
            row.get("parameter_value"),
            str(row.get("parameter_type") or "TEXT"),
            name=name,
        )
    return values


def get_parameter(
    db: Database,
    regulatory_version_id: str,
    parameter_name: str,
    default: T,
) -> T:
    """Return one typed runtime parameter or the explicit default if absent."""
    values = get_parameters(db, regulatory_version_id, (parameter_name,))
    if parameter_name not in values:
        return default
    return cast(T, values[parameter_name])


def merge_parameters(defaults: Mapping[str, T], overrides: Mapping[str, Any]) -> dict[str, T]:
    """Return defaults updated only for known keys, preserving their value type."""
    result = dict(defaults)
    for key in result:
        if key in overrides:
            result[key] = cast(T, overrides[key])
    return result
