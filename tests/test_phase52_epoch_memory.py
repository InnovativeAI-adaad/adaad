# SPDX-License-Identifier: Apache-2.0
"""
Phase 52 tests — EpochMemoryStore & LearningSignalExtractor

Test IDs: T52-M01..M15 (memory store), T52-L01..L10 (learning signal)
"""

from __future__ import annotations

import hashlib
import logging
import json
import tempfile
import os
from pathlib import Path
from typing import Optional

import pytest

from runtime.autonomy.epoch_memory_store import (
    EpochMemoryEntry,
    EpochMemoryStore,
    GENESIS_DIGEST,
    MEMORY_WINDOW_SIZE,
)
from runtime.autonomy.learning_signal_extractor import (
    LearningSignal,
    LearningSignalExtractor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_store(window_size: int = 10) -> EpochMemoryStore:
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)  # store will create it
    return EpochMemoryStore(path=Path(path), window_size=window_size)


def _emit_n(store: EpochMemoryStore, n: int, *, agent: str = "architect") -> None:
    for i in range(n):
        store.emit(
            epoch_id=f"epoch-{i:04d}",
            winning_agent=agent,
            winning_mutation_type="structural",
            winning_strategy_id="adaptive_self_mutate",
            fitness_delta=0.10,
            proposal_count=9,
            accepted_count=1,
            context_hash="aabbccdd",
            constitution_version="0.7.0",
        )


# ===========================================================================
# T52-M: EpochMemoryStore
# ===========================================================================


class TestEpochMemoryStoreT52M:

    def test_T52_M01_emit_single_entry(self):
        """T52-M01: single emit returns valid EpochMemoryEntry."""
        store = _tmp_store()
        entry = store.emit(
            epoch_id="epoch-0001",
            winning_agent="architect",
            winning_mutation_type="structural",
            winning_strategy_id="adaptive_self_mutate",
            fitness_delta=0.12,
            proposal_count=9,
            accepted_count=1,
            context_hash="abcd1234",
            constitution_version="0.7.0",
        )
        assert entry.seq == 0
        assert entry.epoch_id == "epoch-0001"
        assert entry.winning_agent == "architect"
        assert entry.fitness_delta == pytest.approx(0.12)
        assert entry.prev_digest == GENESIS_DIGEST

    def test_T52_M02_entry_digest_valid(self):
        """T52-M02: emitted entry passes integrity check."""
        store = _tmp_store()
        entry = store.emit(
            epoch_id="epoch-0002",
            winning_agent="dream",
            winning_mutation_type="behavioral",
            winning_strategy_id=None,
            fitness_delta=0.0,
            proposal_count=3,
            accepted_count=0,
            context_hash="ff00ff00",
            constitution_version="0.7.0",
        )
        assert entry.verify_integrity()

    def test_T52_M03_chain_links_correctly(self):
        """T52-M03: second entry prev_digest == first entry digest."""
        store = _tmp_store()
        e1 = store.emit(
            epoch_id="epoch-0001",
            winning_agent="beast",
            winning_mutation_type="coverage",
            winning_strategy_id="test_coverage_expansion",
            fitness_delta=0.05,
            proposal_count=6,
            accepted_count=1,
            context_hash="11223344",
            constitution_version="0.7.0",
        )
        e2 = store.emit(
            epoch_id="epoch-0002",
            winning_agent="architect",
            winning_mutation_type="structural",
            winning_strategy_id="structural_refactor",
            fitness_delta=0.08,
            proposal_count=9,
            accepted_count=1,
            context_hash="55667788",
            constitution_version="0.7.0",
        )
        assert e2.prev_digest == e1.entry_digest

    def test_T52_M04_chain_valid_after_multiple_emits(self):
        """T52-M04: chain_valid() True after 5 emits."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 5)
        assert store.chain_valid()

    def test_T52_M05_window_rolling_eviction(self):
        """T52-M05: window stays ≤ window_size after overflow."""
        store = _tmp_store(window_size=5)
        _emit_n(store, 8)
        assert len(store.window()) == 5

    def test_T52_M06_anchor_carried_on_eviction(self):
        """T52-M06: anchor digest is carried forward after eviction."""
        store = _tmp_store(window_size=3)
        _emit_n(store, 5)
        # Window has 3 entries; anchor is not GENESIS after 5 emits
        assert store._anchor_digest != GENESIS_DIGEST

    def test_T52_M07_persist_and_reload(self):
        """T52-M07: persisted entries load correctly in a new store instance."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        os.unlink(path)
        path = Path(path)

        store1 = EpochMemoryStore(path=path, window_size=10)
        _emit_n(store1, 4, agent="dream")

        store2 = EpochMemoryStore(path=path, window_size=10)
        assert len(store2.window()) == 4
        assert store2.window()[0].winning_agent == "dream"

    def test_T52_M08_reload_chain_valid(self):
        """T52-M08: reloaded store passes chain_valid()."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        os.unlink(path)
        path = Path(path)

        store1 = EpochMemoryStore(path=path, window_size=10)
        _emit_n(store1, 6)

        store2 = EpochMemoryStore(path=path, window_size=10)
        assert store2.chain_valid()

    def test_T52_M09_head_returns_last_entry(self):
        """T52-M09: head() returns most recent entry."""
        store = _tmp_store()
        _emit_n(store, 3)
        head = store.head()
        assert head is not None
        assert head.seq == 2

    def test_T52_M10_head_none_on_empty(self):
        """T52-M10: head() returns None on empty store."""
        store = _tmp_store()
        assert store.head() is None

    def test_T52_M11_stats_correct(self):
        """T52-M11: stats() returns accurate counts."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 5, agent="architect")
        stats = store.stats()
        assert stats["count"] == 5
        assert stats["total_proposals"] == 45  # 5 * 9
        assert stats["total_accepted"] == 5    # 5 * 1
        assert stats["acceptance_rate"] == pytest.approx(5 / 45, rel=1e-4)
        assert stats["agent_win_counts"]["architect"] == 5
        assert stats["chain_valid"] is True

    def test_T52_M12_export_window_serialisable(self):
        """T52-M12: export_window() produces JSON-serialisable list."""
        store = _tmp_store()
        _emit_n(store, 3)
        exported = store.export_window()
        assert len(exported) == 3
        # Must be JSON-serialisable
        json.dumps(exported)

    def test_T52_M13_null_winning_agent_allowed(self):
        """T52-M13: winning_agent=None is a valid state (epoch with no winner)."""
        store = _tmp_store()
        entry = store.emit(
            epoch_id="epoch-null",
            winning_agent=None,
            winning_mutation_type=None,
            winning_strategy_id=None,
            fitness_delta=0.0,
            proposal_count=3,
            accepted_count=0,
            context_hash="00000000",
            constitution_version="0.7.0",
        )
        assert entry.winning_agent is None

    def test_T52_M13B_from_dict_dual_reads_context_hash_v2(self):
        """T52-M13B: from_dict accepts context_hash_v2 when context_hash is absent."""
        raw = {
            "seq": 7,
            "epoch_id": "epoch-v2-hash",
            "winning_agent": "architect",
            "winning_mutation_type": "structural",
            "winning_strategy_id": "adaptive_self_mutate",
            "fitness_delta": 0.1,
            "proposal_count": 3,
            "accepted_count": 1,
            "context_hash_v2": "0123456789abcdef",
            "constitution_version": "0.9.0",
            "entry_version": "52.0",
            "entry_digest": "a" * 64,
            "prev_digest": GENESIS_DIGEST,
        }
        entry = EpochMemoryEntry.from_dict(raw)
        assert entry.context_hash == "0123456789abcdef"

    def test_T52_M14_seq_monotonically_increasing(self):
        """T52-M14: seq numbers are monotonically increasing."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 5)
        seqs = [e.seq for e in store.window()]
        assert seqs == sorted(seqs)
        assert seqs == list(range(5))

    def test_T52_M15_determinism_identical_inputs(self):
        """T52-M15: identical inputs produce identical entry_digest (determinism invariant)."""
        kwargs = dict(
            seq=0,
            epoch_id="epoch-det",
            winning_agent="architect",
            winning_mutation_type="structural",
            winning_strategy_id="adaptive_self_mutate",
            fitness_delta=0.10,
            proposal_count=9,
            accepted_count=1,
            context_hash="aabbccdd",
            constitution_version="0.7.0",
        )
        d1 = EpochMemoryEntry.compute_digest(**kwargs)
        d2 = EpochMemoryEntry.compute_digest(**kwargs)
        assert d1 == d2


    def test_T52_M16_reload_tampered_entry_digest_degrades_with_signal(self, caplog):
        """T52-M16: tampered entry_digest triggers deterministic reset + warning event."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        os.unlink(path)
        path = Path(path)

        store1 = EpochMemoryStore(path=path, window_size=10)
        _emit_n(store1, 2)

        lines = path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[2])
        entry["entry_digest"] = "f" * 64
        lines[2] = json.dumps(entry, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            store2 = EpochMemoryStore(path=path, window_size=10)

        assert store2.window() == []
        assert store2.head() is None
        assert any("epoch_memory_store_load_degraded.v1" in r.message for r in caplog.records)
        assert any("epoch_memory_integrity_broken" in r.message for r in caplog.records)

    def test_T52_M17_reload_broken_prev_digest_degrades_with_signal(self, caplog):
        """T52-M17: broken prev_digest linkage triggers deterministic reset + warning event."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        os.unlink(path)
        path = Path(path)

        store1 = EpochMemoryStore(path=path, window_size=10)
        _emit_n(store1, 2)

        lines = path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[2])
        entry["prev_digest"] = "1" * 64
        lines[2] = json.dumps(entry, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            store2 = EpochMemoryStore(path=path, window_size=10)

        assert store2.window() == []
        assert store2.head() is None
        assert any("epoch_memory_store_load_degraded.v1" in r.message for r in caplog.records)
        assert any("epoch_memory_integrity_broken" in r.message for r in caplog.records)

    def test_T52_M18_reload_malformed_json_degrades_with_parse_signal(self, caplog):
        """T52-M18: malformed JSON line triggers deterministic reset + parse warning event."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        os.unlink(path)
        path = Path(path)

        store1 = EpochMemoryStore(path=path, window_size=10)
        _emit_n(store1, 1)

        content = path.read_text(encoding="utf-8") + "{not-json}\n"
        path.write_text(content, encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            store2 = EpochMemoryStore(path=path, window_size=10)

        assert store2.window() == []
        assert store2.head() is None
        assert any("epoch_memory_store_load_degraded.v1" in r.message for r in caplog.records)
        assert any("epoch_memory_load_parse_error" in r.message for r in caplog.records)


# ===========================================================================
# T52-L: LearningSignalExtractor
# ===========================================================================


class TestLearningSignalExtractorT52L:

    def test_T52_L01_empty_store_returns_empty_signal(self):
        """T52-L01: empty store → LearningSignal.empty()."""
        store = _tmp_store()
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        assert signal.is_empty()
        assert signal.window_epochs == 0

    def test_T52_L02_top_agents_sorted_desc(self):
        """T52-L02: top_agents sorted by win_rate descending."""
        store = _tmp_store(window_size=20)
        # architect wins 3, dream wins 1
        _emit_n(store, 3, agent="architect")
        _emit_n(store, 1, agent="dream")
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        assert len(signal.top_agents) >= 1
        rates = [r for _, r in signal.top_agents]
        assert rates == sorted(rates, reverse=True)

    def test_T52_L03_acceptance_rate_correct(self):
        """T52-L03: acceptance_rate = total_accepted / total_proposals."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 4)  # each: 9 proposals, 1 accepted → 4/36
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        assert signal.acceptance_rate == pytest.approx(4 / 36, rel=1e-4)

    def test_T52_L04_avg_fitness_delta_correct(self):
        """T52-L04: avg_fitness_delta = mean of fitness_delta values."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 4)  # each fitness_delta=0.10
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        assert signal.avg_fitness_delta == pytest.approx(0.10, rel=1e-4)

    def test_T52_L05_signal_digest_deterministic(self):
        """T52-L05: identical window → identical signal_digest."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        os.unlink(path)
        path = Path(path)

        store1 = EpochMemoryStore(path=path, window_size=10)
        _emit_n(store1, 3)
        extractor = LearningSignalExtractor()
        sig1 = extractor.extract(store1)

        store2 = EpochMemoryStore(path=path, window_size=10)
        sig2 = extractor.extract(store2)

        assert sig1.signal_digest == sig2.signal_digest

    def test_T52_L06_signal_advisory_only_flag(self):
        """T52-L06: signal carries signal_version marker (identity invariant)."""
        store = _tmp_store()
        _emit_n(store, 1)
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        assert signal.signal_version == "52.0"

    def test_T52_L07_prompt_block_not_empty_when_signal_present(self):
        """T52-L07: as_prompt_block() returns non-empty string when window non-empty."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 3)
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        block = signal.as_prompt_block()
        assert len(block) > 0
        assert "ADVISORY" in block

    def test_T52_L08_empty_signal_prompt_block_is_empty_string(self):
        """T52-L08: LearningSignal.empty().as_prompt_block() returns ''."""
        assert LearningSignal.empty().as_prompt_block() == ""

    def test_T52_L09_avg_fitness_clamped(self):
        """T52-L09: avg_fitness_delta clamped to [-1.0, 1.0]."""
        store = _tmp_store(window_size=20)
        # Emit with extreme fitness delta
        store.emit(
            epoch_id="extreme",
            winning_agent="architect",
            winning_mutation_type="structural",
            winning_strategy_id=None,
            fitness_delta=999.0,
            proposal_count=1,
            accepted_count=1,
            context_hash="00000000",
            constitution_version="0.7.0",
        )
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        assert signal.avg_fitness_delta <= 1.0
        assert signal.avg_fitness_delta >= -1.0

    def test_T52_L10_to_dict_json_serialisable(self):
        """T52-L10: signal.to_dict() is JSON-serialisable."""
        store = _tmp_store(window_size=20)
        _emit_n(store, 3)
        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        d = signal.to_dict()
        json.dumps(d)  # must not raise
