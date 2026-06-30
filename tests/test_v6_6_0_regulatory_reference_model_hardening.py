"""v6.6.0 Regulatory Reference Model Hardening guards."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.6.0"
VERSION_U = "6_6_0"
SQL_REL = "04_post_seed/99_regulatory_reference_model_hardening_v6_6_0.sql"


def test_v660_current_version_artifacts_are_present() -> None:
    assert (ROOT / f"CHANGELOG_v{VERSION_U}.md").is_file()
    assert (ROOT / f"VALIDATION_v{VERSION_U}.md").is_file()
    assert (ROOT / f"RELEASE_REPORT_v{VERSION_U}.md").is_file()
    assert (ROOT / f"docs/REGULATORY_REFERENCE_MODEL_HARDENING_v{VERSION_U}.md").is_file()
    assert (ROOT / f"evidence/coverage_baseline_v{VERSION_U}.json").is_file()
    assert (ROOT / f"SBOM_Corep_Community_v{VERSION}.json").is_file()


def test_v660_reference_model_sql_is_non_destructive() -> None:
    sql = (ROOT / "sql" / SQL_REL).read_text(encoding="utf-8")
    lowered = sql.lower()
    assert "create table if not exists meta.reference_model_assertions" in lowered
    assert "create table if not exists ref.ref_reference_tables" in lowered
    assert "ref.v_reference_model_hardening_status" in lowered
    assert "drop table" not in lowered
    assert "drop schema" not in lowered
    assert "drop column" not in lowered


def test_v660_sql_plan_includes_reference_hardening_before_final_constraints() -> None:
    manifest = (ROOT / "sql/ACTIVE_SQL_MANIFEST.txt").read_text(encoding="utf-8")
    assert SQL_REL in manifest
    assert manifest.index("04_post_seed/99_bcnf_hardening_v6_6_0.sql") < manifest.index(SQL_REL)
    assert manifest.index(SQL_REL) < manifest.index("99_post_seed_constraints")
    contract = json.loads((ROOT / "sql/COMMUNITY_SQL_CONTRACT.json").read_text(encoding="utf-8"))
    assert any(step["path"] == SQL_REL for step in contract["steps"])


def test_v660_evidence_is_version_aligned() -> None:
    payload = json.loads((ROOT / f"evidence/coverage_baseline_v{VERSION_U}.json").read_text(encoding="utf-8"))
    assert payload["product_version"] == VERSION
