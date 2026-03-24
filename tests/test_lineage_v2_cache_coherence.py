# SPDX-License-Identifier: Apache-2.0
"""LINEAGE-CACHE-01: verify_integrity(max_lines=N) cache coherence tests.

Invariants tested:
  CACHE-01: After verify_integrity(max_lines=K), _verified_tail_hash is not None.
  CACHE-02: After verify_integrity(max_lines=K), subsequent append_event() does
            NOT trigger a full re-scan (warm cache is valid).
  CACHE-03: verify_integrity() with no max_lines sets tail to full-chain tip.
  CACHE-04: Truncated tail hash differs from full tail hash when K < total lines.
"""
import pytest
from pathlib import Path
from runtime.evolution.lineage_v2 import LineageLedgerV2


def _populate_ledger(ledger: LineageLedgerV2, n: int) -> list[str]:
    """Write n entries, return list of their hashes in order."""
    hashes = []
    for i in range(n):
        entry = ledger.append_event("TestEvent", {"seq": i, "data": f"payload_{i}"})
        hashes.append(entry["hash"])
    return hashes


@pytest.mark.autonomous_critical
def test_cache_coherence_after_truncated_verify(tmp_path: Path) -> None:
    """CACHE-01: _verified_tail_hash must not be None after truncated verify."""
    ledger = LineageLedgerV2(tmp_path / "lineage.jsonl")
    _populate_ledger(ledger, 5)

    # Reset instance to clear warm cache — simulates cold start
    ledger2 = LineageLedgerV2(tmp_path / "lineage.jsonl")
    assert ledger2._verified_tail_hash is None, "pre-condition: cold start"

    ledger2.verify_integrity(max_lines=3)
    # CACHE-01: must not be None after any non-raising verify_integrity call
    assert ledger2._verified_tail_hash is not None, (
        "LINEAGE-CACHE-01: verify_integrity(max_lines=3) left _verified_tail_hash=None; "
        "subsequent _last_hash() will trigger full O(n) re-scan"
    )


@pytest.mark.autonomous_critical
def test_no_double_scan_after_truncated_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CACHE-02: append_event after truncated verify must not trigger re-scan."""
    ledger = LineageLedgerV2(tmp_path / "lineage.jsonl")
    _populate_ledger(ledger, 5)

    ledger2 = LineageLedgerV2(tmp_path / "lineage.jsonl")
    ledger2.verify_integrity(max_lines=3)

    scan_count = {"n": 0}
    original_verify = ledger2.verify_integrity

    def counting_verify(*args, **kwargs):
        scan_count["n"] += 1
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(ledger2, "verify_integrity", counting_verify)

    # append_event calls _last_hash() which should NOT call verify_integrity
    # because _verified_tail_hash is warm from the truncated verify above
    ledger2.append_event("PostTruncEvent", {"data": "after_truncation"})

    assert scan_count["n"] == 0, (
        f"LINEAGE-CACHE-01: append_event triggered {scan_count['n']} re-scan(s) "
        "after truncated verify — warm cache was not preserved"
    )


@pytest.mark.autonomous_critical
def test_full_verify_sets_full_tip(tmp_path: Path) -> None:
    """CACHE-03: Full verify_integrity sets tail to the last entry hash."""
    ledger = LineageLedgerV2(tmp_path / "lineage.jsonl")
    hashes = _populate_ledger(ledger, 4)

    ledger2 = LineageLedgerV2(tmp_path / "lineage.jsonl")
    ledger2.verify_integrity()

    assert ledger2._verified_tail_hash == hashes[-1], (
        "Full verify must set _verified_tail_hash to the last entry hash"
    )


@pytest.mark.autonomous_critical
def test_truncated_tail_differs_from_full_tail(tmp_path: Path) -> None:
    """CACHE-04: Partial-scan tail must differ from full-chain tail when K < N."""
    ledger = LineageLedgerV2(tmp_path / "lineage.jsonl")
    hashes = _populate_ledger(ledger, 5)

    ledger2 = LineageLedgerV2(tmp_path / "lineage.jsonl")
    ledger2.verify_integrity(max_lines=2)
    partial_tail = ledger2._verified_tail_hash

    ledger3 = LineageLedgerV2(tmp_path / "lineage.jsonl")
    ledger3.verify_integrity()
    full_tail = ledger3._verified_tail_hash

    assert partial_tail != full_tail, (
        "Truncated verify tail should differ from full-chain tail (K=2 < N=5)"
    )
    assert partial_tail == hashes[1], (
        "Truncated verify tail should equal the hash of the 2nd entry"
    )
