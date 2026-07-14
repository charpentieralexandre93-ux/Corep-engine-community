"""v6.4.1 P1 completion guards."""

from __future__ import annotations

import json
from pathlib import Path

from corep_crr3 import regulatory_dossier

ROOT = Path(__file__).resolve().parents[1]


def test_v640_regulatory_dossier_declares_official_submission_scope() -> None:
    payload = json.loads((ROOT / "releases/evidence/regulatory_dossier_v6_4_1.json").read_text(encoding="utf-8"))
    assert regulatory_dossier.validate_dossier(payload) == ()
    assert regulatory_dossier.validate_official_submission_scope(payload) == ()
    assert payload["quality_status_summary"] == regulatory_dossier.quality_status_summary(payload)
    scope = payload["official_submission_scope"]
    included = set(scope["included_engine_modules"])
    excluded = {item["engine_module"] for item in scope["excluded_engine_modules"]}
    assert included.isdisjoint(excluded)
    if payload["edition"] == "COMMUNITY":
        assert excluded == set()
    else:
        assert {"sft_engine", "market_risk_engine", "finrep_excel_filler", "dpm_xbrl_exporter"}.issubset(excluded)


def test_v640_workflow_makes_postgres_e2e_mandatory() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "RUN_POSTGRES_E2E" in workflow
    assert "Appliquer le verdict PostgreSQL" in workflow
    assert 'test "${{ steps.postgres-tests.outcome }}" = "success"' in workflow
