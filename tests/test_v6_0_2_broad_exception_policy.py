from pathlib import Path

from tools.check_broad_exception_policy import undocumented_handlers


def test_all_production_broad_exceptions_are_documented():
    assert undocumented_handlers(Path("src/corep_crr3")) == []
