"""Registre public limité aux moteurs SA et SA-CCR."""

from __future__ import annotations

from .saccr_engine import run_saccr_engine
from .standard_engine import run_standard_engine

PUBLIC_ENGINES = {
    "SA": run_standard_engine,
    "SA_CCR": run_saccr_engine,
}


def get_engine(engine_code: str):
    """Retourne un moteur public ou refuse explicitement tout autre domaine."""
    code = str(engine_code).strip().upper().replace("-", "_")
    try:
        return PUBLIC_ENGINES[code]
    except KeyError as exc:
        raise ValueError(
            f"Moteur indisponible dans l'édition Community : {engine_code}"
        ) from exc


def main() -> None:
    print("Moteurs disponibles :", ", ".join(PUBLIC_ENGINES))
