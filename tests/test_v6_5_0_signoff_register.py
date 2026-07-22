"""v6.5.0 — registre de sign-off réglementaire nominatif (P0-1)."""

from __future__ import annotations

import json
from pathlib import Path

from corep_crr3 import regulatory_dossier as rd

ROOT = Path(__file__).resolve().parents[1]


def test_generated_dossier_has_full_unsigned_register_and_stays_no_go():
    d = rd.build_fail_closed_dossier(version="6.5.0", edition="COMMUNITY")
    register = d["signoff_register"]
    assert {e["gate"] for e in register} == set(rd.REQUIRED_GATES)
    assert all(e["signature_status"] == "NOT_SIGNED" for e in register)
    assert all(e["accountable_owner"] and e["required_signatory_role"] for e in register)
    assert d["submission_readiness"] == "NO_GO"
    assert rd.validate_dossier(d) == ()
    assert rd.validate_signoff_register(d) == ()


def test_committed_v642_evidence_validates_with_register():
    payload = json.loads((ROOT / "releases/evidence/regulatory_dossier_v6_5_0.json").read_text(encoding="utf-8"))
    assert "signoff_register" in payload
    assert rd.validate_dossier(payload) == ()


def test_go_requires_every_signoff_signed():
    d = rd.build_fail_closed_dossier(version="6.5.0", edition="COMMUNITY")
    d["submission_readiness"] = "GO"
    # unsigned register + GO must fail
    assert rd.validate_signoff_register(d)


def test_signed_register_passes_with_complete_evidence():
    d = rd.build_fail_closed_dossier(version="6.5.0", edition="COMMUNITY")
    for entry in d["signoff_register"]:
        entry.update(
            signature_status="SIGNED",
            signatory="J. Reviewer",
            signature_date="2026-06-29",
            evidence_sha256="a" * 64,
        )
    d["submission_readiness"] = "GO"
    assert rd.validate_signoff_register(d) == ()


def test_signed_entry_requires_valid_evidence_hash_and_date():
    d = rd.build_fail_closed_dossier(version="6.5.0", edition="COMMUNITY")
    entry = d["signoff_register"][0]
    entry.update(signature_status="SIGNED", signatory="X", signature_date="29/06/2026", evidence_sha256="short")
    errors = rd.validate_signoff_register(d)
    assert any("evidence_sha256" in e for e in errors)
    assert any("signature_date" in e for e in errors)


def test_register_is_backward_compatible_when_absent():
    d = rd.build_fail_closed_dossier(version="6.5.0", edition="COMMUNITY")
    del d["signoff_register"]
    assert rd.validate_signoff_register(d) == ()
    assert rd.validate_dossier(d) == ()
