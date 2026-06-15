from tools.enrich_sbom_licenses import enrich


def test_runtime_licenses_are_added_and_strict_set_resolves():
    payload = {
        "components": [
            {"name": "numpy", "version": "2.4.6", "type": "library"},
            {"name": "psycopg2-binary", "version": "2.9.11", "type": "library"},
        ]
    }
    enriched, unresolved = enrich(payload, {"numpy", "psycopg2-binary"})
    assert enriched == 2
    assert unresolved == []
    assert payload["components"][0]["licenses"][0]["license"]["id"] == "BSD-3-Clause"
    assert payload["components"][1]["licenses"][0]["license"]["id"] == "LGPL-3.0-or-later"
