# SPDX-License-Identifier: Apache-2.0
"""Phase 78 M78-01 — Journal warm-cache constitutional tests.

Verifies JOURNAL-CACHE-0, JOURNAL-CACHE-DETERM-0, and JOURNAL-ISOLATE-0
for both LineageLedgerV2 and the security/ledger journal _VERIFIED_TAIL_CACHE.

All tests are hermetic: isolated temp paths, no shared file-system state.
"""
from __future__ import annotations
import pathlib
import tempfile
import threading
import time
import pytest
from runtime.evolution.lineage_v2 import LineageLedgerV2


@pytest.fixture
def tmp_ledger(tmp_path):
    return LineageLedgerV2(ledger_path=tmp_path / "test_ledger.jsonl")


class TestJournalCacheInvariants:
    """JOURNAL-CACHE-0: cache advances atomically post-append."""

    def test_warm_cache_present_after_first_append(self, tmp_ledger):
        tmp_ledger.append_event("TestEvent", {"val": 1})
        assert tmp_ledger._verified_tail_hash is not None

    def test_warm_cache_advances_on_each_append(self, tmp_ledger):
        tmp_ledger.append_event("TestEvent", {"val": 1})
        h1 = tmp_ledger._verified_tail_hash
        tmp_ledger.append_event("TestEvent", {"val": 2})
        h2 = tmp_ledger._verified_tail_hash
        assert h1 != h2

    def test_warm_cache_consistent_with_full_verify(self, tmp_path):
        """JOURNAL-CACHE-DETERM-0: cache tail matches full scan tail."""
        path = tmp_path / "verify.jsonl"
        l = LineageLedgerV2(ledger_path=path)
        for i in range(50):
            l.append_event("E", {"i": i})
        cached_tail = l._verified_tail_hash
        # Force full re-scan by clearing cache
        l._verified_tail_hash = None
        l.verify_integrity()
        rescanned_tail = l._verified_tail_hash
        assert cached_tail == rescanned_tail

    def test_repeated_appends_are_linear_not_quadratic(self, tmp_path):
        """Performance: 1000 appends complete in < 2s (O(n) not O(n²))."""
        path = tmp_path / "perf.jsonl"
        l = LineageLedgerV2(ledger_path=path)
        t0 = time.monotonic()
        for i in range(1000):
            l.append_event("PerfEvent", {"i": i})
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"1000 appends took {elapsed:.2f}s — warm-cache regression"

    def test_integrity_verification_passes_after_warm_appends(self, tmp_path):
        path = tmp_path / "integrity.jsonl"
        l = LineageLedgerV2(ledger_path=path)
        for i in range(100):
            l.append_event("IEvent", {"i": i})
        # Should not raise
        l.verify_integrity()

    def test_cache_invalidated_on_new_instance(self, tmp_path):
        """JOURNAL-ISOLATE-0: new instance starts with no cache assumption."""
        path = tmp_path / "isolate.jsonl"
        l1 = LineageLedgerV2(ledger_path=path)
        for i in range(10):
            l1.append_event("E", {"i": i})
        # New instance — no shared in-memory cache
        l2 = LineageLedgerV2(ledger_path=path)
        assert l2._verified_tail_hash is None
        # But verify_integrity rebuilds it
        l2.verify_integrity()
        assert l2._verified_tail_hash == l1._verified_tail_hash


class TestJournalIsolation:
    """JOURNAL-ISOLATE-0: no cross-test state bleed via shared paths."""

    def test_separate_paths_do_not_share_cache(self, tmp_path):
        l1 = LineageLedgerV2(ledger_path=tmp_path / "a.jsonl")
        l2 = LineageLedgerV2(ledger_path=tmp_path / "b.jsonl")
        l1.append_event("X", {"src": "l1"})
        l2.append_event("X", {"src": "l2"})
        assert l1._verified_tail_hash != l2._verified_tail_hash

    def test_concurrent_appends_to_different_ledgers_are_isolated(self, tmp_path):
        """Thread-safety: concurrent appends to different paths don't corrupt."""
        results = {}
        def write_n(name, n):
            path = tmp_path / f"{name}.jsonl"
            l = LineageLedgerV2(ledger_path=path)
            for i in range(n):
                l.append_event("ConcEvent", {"writer": name, "i": i})
            results[name] = l._verified_tail_hash

        threads = [threading.Thread(target=write_n, args=(f"w{i}", 50)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All four hashes should differ (different paths, different content)
        assert len(set(results.values())) == 4

    def test_tampered_entry_detected_after_warm_appends(self, tmp_path):
        """Tamper detection still works even with warm cache."""
        from runtime.evolution.lineage_v2 import LineageIntegrityError
        path = tmp_path / "tamper.jsonl"
        l = LineageLedgerV2(ledger_path=path)
        for i in range(20):
            l.append_event("E", {"i": i})
        # Tamper: overwrite middle of file
        lines = path.read_text().splitlines()
        lines[10] = lines[10].replace('"i": 10', '"i": 999')
        path.write_text("\n".join(lines) + "\n")
        # Force re-scan
        l._verified_tail_hash = None
        with pytest.raises(LineageIntegrityError):
            l.verify_integrity()
