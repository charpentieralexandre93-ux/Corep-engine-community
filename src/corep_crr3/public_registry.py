"""Registre public limité aux moteurs SA et SA-CCR."""

from __future__ import annotations

from typing import Optional

from .engine_contracts import (
    EngineContext,
    EngineProfiler,
    EngineResult,
    FunctionEngineAdapter,
    RegulatoryEngine,
)
from .saccr_engine import run_saccr_engine
from .standard_engine import run_standard_engine

# API historique conservée : plusieurs intégrations et tests comparent encore
# directement l'identité des fonctions publiques.
PUBLIC_ENGINES = {
    "SA": run_standard_engine,
    "SA_CCR": run_saccr_engine,
}

# Nouveau contrat normalisé, additif et sans rupture de PUBLIC_ENGINES.
PUBLIC_REGULATORY_ENGINES = {
    code: FunctionEngineAdapter(function, name=code)
    for code, function in PUBLIC_ENGINES.items()
}


def _normalize_code(engine_code: str) -> str:
    """Execute the normalize code helper used by the command workflow."""
    return str(engine_code).strip().upper().replace("-", "_")


def get_engine(engine_code: str):
    """Retourne la fonction legacy ou refuse explicitement un domaine privé."""
    code = _normalize_code(engine_code)
    try:
        return PUBLIC_ENGINES[code]
    except KeyError as exc:
        raise ValueError(
            f"Moteur indisponible dans l'édition Community : {engine_code}"
        ) from exc


def get_regulatory_engine(engine_code: str) -> RegulatoryEngine:
    """Retourne un moteur conforme au protocole ``RegulatoryEngine``."""
    code = _normalize_code(engine_code)
    try:
        return PUBLIC_REGULATORY_ENGINES[code]
    except KeyError as exc:
        raise ValueError(
            f"Moteur indisponible dans l'édition Community : {engine_code}"
        ) from exc


def run_engine(
    engine_code: str,
    context: EngineContext,
    profiler: Optional[EngineProfiler] = None,
) -> EngineResult:
    """Exécute un moteur public via le contrat commun, avec profiling optionnel."""
    engine = get_regulatory_engine(engine_code)
    if profiler is None:
        return engine.run(context)
    code = _normalize_code(engine_code)
    return profiler.run(
        engine,
        context,
        engine_key=f"run_{code.lower()}",
        engine_label=code.replace("_", "-"),
    )


def main() -> None:
    """Run the command entry point and return its process status."""
    print("Moteurs disponibles :", ", ".join(PUBLIC_ENGINES))


__all__ = [
    "PUBLIC_ENGINES",
    "PUBLIC_REGULATORY_ENGINES",
    "get_engine",
    "get_regulatory_engine",
    "run_engine",
]
