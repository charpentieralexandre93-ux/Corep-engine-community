"""Couverture unitaire pure de ``protection_strategy`` (module CRM partagé).

Cible la dette de couverture identifiée à l'audit v6.5.0 : ce module partagé
réglementaire était couvert quasi exclusivement par l'E2E PostgreSQL. Ces tests
exercent ses fonctions **sans base de données**, via une fausse ``Database`` et
un ``evaluate_rule_set`` neutralisé par monkeypatch — le comportement métier
(tri d'allocation, défauts FCP/UFCP, groupement) est donc validé en unitaire.
"""

from __future__ import annotations

import pytest

from corep_crr3 import protection_strategy
from corep_crr3.protection_strategy import (
    _allocation_rank_sort_value,
    _enrich_protection_bucket,
    load_all_ranked_protections,
    load_ranked_protections,
)


class _FakeDatabase:
    """Fausse ``Database`` : renvoie des lignes prédéfinies pour ``query()``."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.queries: list[tuple] = []

    def query(self, sql: str, params: tuple | None = None) -> list[dict]:
        self.queries.append((sql, params))
        return [dict(r) for r in self._rows]


# --- _allocation_rank_sort_value : fonction pure ---


@pytest.mark.parametrize(
    "value, expected",
    [
        ("5", 5),
        (3, 3),
        ("  7  ", 7),
        ("", 9999),
        (None, 9999),
        ("abc", 9999),
        ("9999", 9999),
        ("-1", -1),
        (0, 0),
    ],
)
def test_allocation_rank_sort_value(value: object, expected: int) -> None:
    assert _allocation_rank_sort_value(value) == expected


# --- _enrich_protection_bucket : bucket via décision / défauts typés ---


def test_enrich_bucket_uses_decision_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        protection_strategy,
        "evaluate_rule_set",
        lambda *a, **k: {"result_value": "COLLATERAL_CASH"},
    )
    prot = {"exposure_id": "E1", "protection_id": "P1", "protection_type": "FCP"}
    out = _enrich_protection_bucket(object(), "B1", "v6.5.0", prot)
    assert out["bucket"] == "COLLATERAL_CASH"
    assert "bucket" not in prot  # l'entrée d'origine n'est pas mutée


def test_enrich_bucket_default_fcp_when_no_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protection_strategy, "evaluate_rule_set", lambda *a, **k: None)
    out = _enrich_protection_bucket(object(), "B1", "v6.5.0", {"protection_type": "FCP"})
    assert out["bucket"] == "DEFAULT_FCP"


def test_enrich_bucket_default_ufcp_when_no_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protection_strategy, "evaluate_rule_set", lambda *a, **k: None)
    out = _enrich_protection_bucket(object(), "B1", "v6.5.0", {"protection_type": "ufcp"})
    assert out["bucket"] == "DEFAULT_UFCP"


def test_enrich_bucket_generic_default_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    # un bucket générique "DEFAULT" ne doit plus être persisté (migration v4.2.3)
    monkeypatch.setattr(
        protection_strategy,
        "evaluate_rule_set",
        lambda *a, **k: {"result_value": "DEFAULT"},
    )
    out = _enrich_protection_bucket(object(), "B1", "v6.5.0", {"protection_type": "UFCP"})
    assert out["bucket"] == "DEFAULT_UFCP"


# --- load_all_ranked_protections : groupement + tri réglementaire ---


def test_load_all_groups_and_sorts_by_rank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protection_strategy, "evaluate_rule_set", lambda *a, **k: {"result_value": "B"})
    rows = [
        {"exposure_id": "E1", "protection_id": "P2", "allocation_rank": "2", "protection_type": "FCP"},
        {"exposure_id": "E1", "protection_id": "P1", "allocation_rank": "1", "protection_type": "FCP"},
        {"exposure_id": "E2", "protection_id": "P9", "allocation_rank": None, "protection_type": "FCP"},
    ]
    grouped = load_all_ranked_protections(_FakeDatabase(rows), "B1", "v6.5.0")
    assert set(grouped) == {"E1", "E2"}
    assert [p["protection_id"] for p in grouped["E1"]] == ["P1", "P2"]
    assert all("bucket" in p for ps in grouped.values() for p in ps)


def test_load_all_null_rank_sorted_last(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protection_strategy, "evaluate_rule_set", lambda *a, **k: None)
    rows = [
        {"exposure_id": "E1", "protection_id": "PB", "allocation_rank": None, "protection_type": "FCP"},
        {"exposure_id": "E1", "protection_id": "PA", "allocation_rank": "5", "protection_type": "FCP"},
    ]
    grouped = load_all_ranked_protections(_FakeDatabase(rows), "B1", "v6.5.0")
    assert [p["protection_id"] for p in grouped["E1"]] == ["PA", "PB"]


# --- load_ranked_protections : chemin unitaire rétrocompatible ---


def test_load_ranked_single_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        protection_strategy,
        "evaluate_rule_set",
        lambda *a, **k: {"result_value": "GUARANTEE_BANK"},
    )
    rows = [{"exposure_id": "E1", "protection_id": "P1", "allocation_rank": "1", "protection_type": "UFCP"}]
    db = _FakeDatabase(rows)
    out = load_ranked_protections(db, "B1", "v6.5.0", "E1")
    assert len(out) == 1
    assert out[0]["bucket"] == "GUARANTEE_BANK"
    # le paramètre exposure_id est bien transmis à la requête
    assert db.queries[0][1] == ("B1", "E1")
