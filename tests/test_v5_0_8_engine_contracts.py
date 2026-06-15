"""Contrat moteur public v5.0.8 — compatibilité SA / SA-CCR."""

from __future__ import annotations

from corep_crr3.engine_contracts import (
    EngineContext,
    EngineProfiler,
    FunctionEngineAdapter,
    RegulatoryEngine,
)
from corep_crr3.public_registry import (
    PUBLIC_ENGINES,
    PUBLIC_REGULATORY_ENGINES,
    get_engine,
    get_regulatory_engine,
    run_engine,
)
from corep_crr3.saccr_engine import run_saccr_engine
from corep_crr3.standard_engine import run_standard_engine


def test_legacy_public_registry_identity_is_preserved():
    assert get_engine("SA") is run_standard_engine
    assert get_engine("sa-ccr") is run_saccr_engine
    assert PUBLIC_ENGINES == {"SA": run_standard_engine, "SA_CCR": run_saccr_engine}


def test_public_registry_exposes_normalised_protocol_adapters():
    sa = get_regulatory_engine("SA")
    saccr = get_regulatory_engine("sa-ccr")
    assert isinstance(sa, RegulatoryEngine)
    assert isinstance(saccr, RegulatoryEngine)
    assert isinstance(sa, FunctionEngineAdapter)
    assert sa.function is run_standard_engine
    assert saccr.function is run_saccr_engine
    assert set(PUBLIC_REGULATORY_ENGINES) == {"SA", "SA_CCR"}


def test_run_engine_uses_context_and_optional_profiler(monkeypatch):
    calls = []

    def fake_engine(db, batch_id, version, reporting_date, **kwargs):
        calls.append((db, batch_id, version, reporting_date, kwargs))
        return 9

    adapter = FunctionEngineAdapter(fake_engine, name="SA")
    monkeypatch.setitem(PUBLIC_REGULATORY_ENGINES, "SA", adapter)
    context = EngineContext(
        db=object(),
        batch_id="B1",
        regulatory_version_id="CRR3_V9",
        reporting_date="2026-03-31",
        runtime_kwargs={"strict": True},
    )
    profiler = EngineProfiler(enabled=True, slow_threshold_seconds=999.0)

    result = run_engine("sa", context, profiler)
    assert result.processed_rows == 9
    assert calls[0][1:] == ("B1", "CRR3_V9", "2026-03-31", {"strict": True})
    assert profiler.profiles[0].engine_key == "run_sa"
