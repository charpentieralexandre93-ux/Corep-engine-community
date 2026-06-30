"""Non-regression tests for the v6.3.1 P0/P1/P2 remediation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from corep_crr3.standard_engine import (
    FcpHaircutRuleBook,
    compile_fcp_haircut_rules,
    lookup_fcp_haircut_rate_from_rules,
    preload_fcp_haircut_rules,
)

ROOT = Path(__file__).resolve().parents[1]

RULES = [
    {
        "collateral_type": "BOND",
        "collateral_grade": "AA",
        "residual_maturity": ">5Y",
        "haircut_rate": 0.02,
    },
    {
        "collateral_type": "BOND",
        "collateral_grade": "AA",
        "residual_maturity": None,
        "haircut_rate": 0.03,
    },
    {
        "collateral_type": "BOND",
        "collateral_grade": None,
        "residual_maturity": None,
        "haircut_rate": 0.07,
    },
    {
        "collateral_type": "EQUITY",
        "collateral_grade": None,
        "residual_maturity": None,
        "haircut_rate": 0.15,
    },
]


def test_compiled_fcp_rulebook_is_equivalent_to_raw_rules() -> None:
    rule_book = compile_fcp_haircut_rules(RULES)
    assert isinstance(rule_book, FcpHaircutRuleBook)

    protections = [
        {"collateral_type": "bond", "collateral_grade": "aa", "maturity_months": 72},
        {"collateral_type": "bond", "collateral_grade": "aa", "maturity_months": 24},
        {"collateral_type": "bond", "collateral_grade": "bbb", "maturity_months": 24},
        {"collateral_type": "equity"},
        {"collateral_type": "gold"},
        {},
    ]
    for protection in protections:
        assert lookup_fcp_haircut_rate_from_rules(rule_book, protection) == (
            lookup_fcp_haircut_rate_from_rules(RULES, protection)
        )


def test_compiled_fcp_rulebook_preserves_first_equal_priority_rule() -> None:
    duplicate_priority = [
        {
            "collateral_type": "CASH",
            "collateral_grade": None,
            "residual_maturity": None,
            "haircut_rate": 0.01,
        },
        {
            "collateral_type": "CASH",
            "collateral_grade": None,
            "residual_maturity": None,
            "haircut_rate": 0.99,
        },
    ]
    rule_book = compile_fcp_haircut_rules(duplicate_priority)
    assert lookup_fcp_haircut_rate_from_rules(rule_book, {"collateral_type": "cash"}) == 0.01


def test_preload_returns_compiled_rulebook() -> None:
    class FakeDb:
        def query(self, sql: str, params: tuple[str]) -> list[dict]:
            assert "ref_collateral_haircuts" in sql
            assert params == ("CRR3_V9",)
            return RULES

    result = preload_fcp_haircut_rules(FakeDb(), "CRR3_V9")  # type: ignore[arg-type]
    assert isinstance(result, FcpHaircutRuleBook)
    assert (
        lookup_fcp_haircut_rate_from_rules(
            result,
            {"collateral_type": "BOND", "collateral_grade": "AA", "maturity_months": 72},
        )
        == 0.02
    )


def test_psycopg2_base_driver_survives_missing_optional_extensions(tmp_path: Path) -> None:
    """A minimal/fake driver without extensions.make_dsn remains usable."""
    package = tmp_path / "psycopg2"
    package.mkdir()
    (package / "__init__.py").write_text(
        "def connect(*args, **kwargs): return object()\n",
        encoding="utf-8",
    )
    (package / "extras.py").write_text(
        "class RealDictCursor: pass\ndef execute_values(*args, **kwargs): return None\n",
        encoding="utf-8",
    )
    (package / "pool.py").write_text(
        "class ThreadedConnectionPool: pass\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(tmp_path), str(ROOT / "src")))
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import corep_crr3.db as db; "
                "assert db.psycopg2 is not None; "
                "assert db._psycopg2_extras is not None; "
                "assert db._psycopg2_pool is not None; "
                "assert db._psycopg2_make_dsn is None"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr


def test_docker_image_contract_uses_deterministic_tag_not_compose_images_query() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "${COREP_IMAGE_TAG:-local}" in compose
    assert "COREP_IMAGE_TAG:" in ci
    assert "docker compose config --quiet" in ci
    assert 'docker image inspect "$IMAGE_REF"' in ci
    assert "docker compose images -q app" not in ci
