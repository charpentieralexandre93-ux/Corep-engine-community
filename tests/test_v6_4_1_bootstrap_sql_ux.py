from pathlib import Path

from corep_crr3 import community_bootstrap

ROOT = Path(__file__).resolve().parent.parent


def test_community_bootstrap_engine_filter_keeps_only_requested_public_engine():
    steps = community_bootstrap.sql_steps(engines=("run_saccr",))
    paths = [step["path"] for step in steps]
    groups = {step["group"] for step in steps}
    assert "01_schema/engines/schema_saccr.sql" in paths
    assert "02_seeds/02_seed_saccr.sql" in paths
    assert "03_mapping/02_mapping_saccr.sql" in paths
    assert "01_schema/engines/schema_credit_standard.sql" not in paths
    assert groups <= {"always", "run_saccr", "post_seed"}


def test_community_bootstrap_engine_manifest_is_specific(tmp_path):
    target = tmp_path / "community_saccr_manifest.txt"
    written = community_bootstrap.write_sql_manifest(engines=("run_saccr",), output_path=target)
    text = written.read_text(encoding="utf-8")
    assert written == target
    assert "run_saccr" in text
    assert "schema_saccr.sql" in text
    assert "schema_credit_standard.sql" not in text


def test_community_bootstrap_sql_documentation_exists_and_mentions_engine_cli():
    doc = (ROOT / "docs/BOOTSTRAP_SQL.md").read_text(encoding="utf-8")
    assert "community_bootstrap --engine run_saccr --list" in doc
    assert "schema + seed + mapping" in doc
