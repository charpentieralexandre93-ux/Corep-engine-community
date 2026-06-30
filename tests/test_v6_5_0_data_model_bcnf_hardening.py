"""v6.5.0 Data Model BCNF Hardening guards."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.5.0"
VERSION_U = "6_5_0"


def test_v650_current_version_artifacts_are_present() -> None:
    assert (ROOT / f"CHANGELOG_v{VERSION_U}.md").is_file()
    assert (ROOT / f"VALIDATION_v{VERSION_U}.md").is_file()
    assert (ROOT / f"RELEASE_REPORT_v{VERSION_U}.md").is_file()
    assert (ROOT / f"docs/DATA_MODEL_BCNF_HARDENING_v{VERSION_U}.md").is_file()
    assert (ROOT / f"evidence/coverage_baseline_v{VERSION_U}.json").is_file()


def test_v650_bcnf_hardening_sql_is_non_destructive() -> None:
    sql = (ROOT / "sql/04_post_seed/99_bcnf_hardening_v6_5_0.sql").read_text(encoding="utf-8")
    lowered = sql.lower()
    assert "create table if not exists ref.ref_condition_fields" in lowered
    assert "fk_ref_rule_conditions_condition_field_v650" in lowered
    assert "fk_ref_mapping_rule_conditions_condition_field_v650" in lowered
    assert "fk_ref_template_mapping_rule_conditions_condition_field_v650" in lowered
    assert "create or replace view ref.v_ref_mapping_rules_authoring" in lowered
    assert "drop table" not in lowered
    assert "drop schema" not in lowered
    assert "drop column" not in lowered


def test_v650_sql_plan_includes_bcnf_hardening_before_final_constraints() -> None:
    manifest = (ROOT / "sql/ACTIVE_SQL_MANIFEST.txt").read_text(encoding="utf-8")
    candidates = (
        "04_post_seed/99_bcnf_hardening_v6_5_0.sql",
        "04_post_seed/99_bcnf_hardening_v6_6_0.sql",
    )
    hardening = next(path for path in candidates if path in manifest)
    assert manifest.index(hardening) < manifest.index("99_post_seed_constraints")


def test_v650_evidence_is_version_aligned() -> None:
    payload = json.loads((ROOT / f"evidence/coverage_baseline_v{VERSION_U}.json").read_text(encoding="utf-8"))
    assert payload["product_version"] == VERSION
