#!/usr/bin/env python3
"""Verify Apache licensing, runtime resources and the strict public boundary."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

FORBIDDEN = (
    "irb_engine.py",
    "cva_engine.py",
    "sft_engine.py",
    "liquidity_engine.py",
    "market_risk_engine.py",
    "operational_risk_engine.py",
    "own_funds_engine.py",
    "dpm_xbrl_exporter.py",
    "eba_xbrl_csv.py",
    "regulatory_release.py",
    "submission_governance.py",
    "stress_testing_engine.py",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.wheel) as archive:
        names = set(archive.namelist())
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise RuntimeError("METADATA wheel introuvable ou ambigu")
        text = archive.read(metadata[0]).decode("utf-8", errors="replace")
    required = {
        "corep_crr3/sql/COMMUNITY_SQL_CONTRACT.json",
        "corep_crr3/sql/ACTIVE_SQL_MANIFEST.txt",
        "corep_crr3/py.typed",
        "corep_crr3/resources/legal/LICENSE",
        "corep_crr3/resources/legal/LICENSE-COMMUNITY.md",
        "corep_crr3/resources/legal/NOTICE",
        "corep_crr3/resources/release/RELEASE_MANIFEST.json",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Ressources Community absentes du wheel : {missing}")
    leaks = sorted(name for name in names if name.endswith(FORBIDDEN))
    if leaks:
        raise RuntimeError(f"Fuite Enterprise dans le wheel public : {leaks}")
    if "License: Apache-2.0" not in text and "License-Expression: Apache-2.0" not in text:
        raise RuntimeError("Métadonnée de licence Apache-2.0 absente")
    print(f"OK: {args.wheel.name} reste public SA/SA-CCR et embarque ses preuves de release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
