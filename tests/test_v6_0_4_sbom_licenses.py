from __future__ import annotations

from tools.enrich_sbom_licenses import _cyclonedx_license_entry, enrich


def _runtime_payload() -> dict[str, object]:
    return {
        "components": [
            {"name": "numpy", "version": "2.4.6", "type": "library"},
            {"name": "psycopg2-binary", "version": "2.9.11", "type": "library"},
        ]
    }


def test_runtime_licenses_are_deterministic_across_installed_metadata(monkeypatch):
    monkeypatch.setattr(
        "tools.enrich_sbom_licenses._metadata_license",
        lambda name: "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0" if name == "numpy" else None,
    )
    payload = _runtime_payload()
    enriched, unresolved = enrich(payload, {"numpy", "psycopg2-binary"})
    assert enriched == 2
    assert unresolved == []
    assert payload["components"][0]["licenses"] == [{"license": {"id": "BSD-3-Clause"}}]
    assert payload["components"][1]["licenses"] == [{"license": {"id": "LGPL-3.0-or-later"}}]


def test_distribution_names_are_pep503_normalized():
    payload = {
        "components": [
            {"name": "NumPy", "version": "2.4.6", "type": "library"},
            {"name": "PSYCOPG2_BINARY", "version": "2.9.11", "type": "library"},
        ]
    }
    enriched, unresolved = enrich(payload, {"numpy", "psycopg2.binary"})
    assert enriched == 2
    assert unresolved == []


def test_runtime_enrichment_is_idempotent():
    payload = _runtime_payload()
    assert enrich(payload, {"numpy", "psycopg2-binary"}) == (2, [])
    assert enrich(payload, {"numpy", "psycopg2-binary"}) == (0, [])


def test_single_identifier_uses_license_id():
    assert _cyclonedx_license_entry("MIT") == {"license": {"id": "MIT"}}


def test_composite_spdx_value_uses_expression_not_license_id():
    value = "BSD-3-Clause AND MIT"
    assert _cyclonedx_license_entry(value) == {"expression": value}


def test_unknown_required_distribution_remains_unresolved():
    payload = {"components": [{"name": "unknown-package", "type": "library"}]}
    enriched, unresolved = enrich(payload, {"unknown-package"})
    assert enriched == 0
    assert unresolved == ["unknown-package"]
