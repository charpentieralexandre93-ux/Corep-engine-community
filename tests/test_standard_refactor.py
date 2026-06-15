from __future__ import annotations

from contextlib import contextmanager

from corep_crr3 import standard_engine as sa


class EmptyDB:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple | None]] = []
        self.batches: list[tuple[str, list[tuple]]] = []

    def execute(self, sql: str, params=None):
        self.executed.append((sql, params))

    def query(self, sql: str, params=None):
        return []

    def executemany(self, sql: str, values):
        self.batches.append((sql, list(values)))

    @contextmanager
    def transaction(self):
        yield self


def test_standard_engine_empty_batch_is_idempotent() -> None:
    db = EmptyDB()
    assert sa.run_standard_engine(db, "batch", "CRR3", "2026-03-31") == 0
    assert len(db.executed) == 3
    assert db.batches == []


def test_partition_protections_is_order_stable_and_counts_unknown() -> None:
    stats = sa._StandardFallbackStats()
    protections = [
        {"protection_id": "u1", "protection_type": " UFCP "},
        {"protection_id": "x", "protection_type": "other"},
        {"protection_id": "f1", "protection_type": "fcp"},
        {"protection_id": "f2", "protection_type": "FCP"},
    ]
    funded, unfunded = sa._partition_protections(protections, "e1", stats)
    assert [p["protection_id"] for p in funded] == ["f1", "f2"]
    assert [p["protection_id"] for p in unfunded] == ["u1"]
    assert stats.ignored_protection_count == 1
    assert stats.ignored_protections == ["x"]


def test_sme_totals_are_aggregated_by_obligor() -> None:
    rows = [
        {"counterparty_id": "A", "supporting_sme_flag": True, "exposure_amount": 100, "provision_amount": 10},
        {"counterparty_id": "A", "supporting_sme_flag": "Y", "exposure_amount": 50, "provision_amount": 0},
        {"counterparty_id": "B", "supporting_sme_flag": False, "exposure_amount": 999, "provision_amount": 0},
    ]
    assert sa._sme_totals_by_obligor(rows) == {"A": 140.0}
