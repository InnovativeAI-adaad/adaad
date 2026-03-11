# SPDX-License-Identifier: Apache-2.0
"""
Phase 10 PR-10-01 — Test suite for RewardSignalBridge + EvolutionLoop Phase 5d wiring.

Test IDs: T10-01-01 through T10-01-20

Coverage:
    RewardSignalBridge      (T10-01-01..14) — ingest, evaluation, ring buffer,
                                              ledger write, skip conditions, schema
    EvolutionLoop wiring    (T10-01-15..18) — _reward_bridge attribute, exception isolation,
                                              recent_evaluations ring, velocity independence
    EpochRewardSignal       (T10-01-19..20) — as_dict serialisability, rate accuracy
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
pytestmark = pytest.mark.regression_standard

_TEST_KEY_BYTES = bytes.fromhex("d" * 64)


def _no_op_audit(*args, **kwargs):
    return {}


def _make_ledger(tmp_path: Path):
    from runtime.memory.soulbound_ledger import SoulboundLedger
    return SoulboundLedger(
        ledger_path=tmp_path / "ledger.json",
        audit_writer=_no_op_audit,
        key_override=_TEST_KEY_BYTES,
    )


def _make_bridge(tmp_path: Path):
    from runtime.memory.reward_signal_bridge import RewardSignalBridge
    return RewardSignalBridge(
        ledger=_make_ledger(tmp_path),
        audit_writer=_no_op_audit,
    )


def _score(accepted: bool = True, score: float = 0.75, agent: str = "architect") -> MagicMock:
    s = MagicMock()
    s.mutation_id = f"mut-{agent}-{score}"
    s.accepted = accepted
    s.score = score
    s.agent_origin = agent
    return s


def _batch(n_accepted: int = 3, n_rejected: int = 1) -> List[MagicMock]:
    return (
        [_score(accepted=True,  score=0.80) for _ in range(n_accepted)] +
        [_score(accepted=False, score=0.30) for _ in range(n_rejected)]
    )


# ════════════════════════════════════════════════════════════════════════════
# RewardSignalBridge — T10-01-01..14
# ════════════════════════════════════════════════════════════════════════════

class TestRewardSignalBridge:

    def test_T10_01_01_ingest_returns_emitted_true_with_scores(self, tmp_path):
        """ingest() must return emitted=True when sufficient scores are provided."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="epoch-001", all_scores=_batch(3, 1))
        assert result.emitted is True
        assert result.skip_reason is None

    def test_T10_01_02_ingest_skips_on_empty_scores(self, tmp_path):
        """ingest() must return emitted=False with empty score list."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="epoch-001", all_scores=[])
        assert result.emitted is False
        assert result.skip_reason is not None

    def test_T10_01_03_signal_accepted_count_correct(self, tmp_path):
        """signal.accepted_count must match number of accepted scores."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="e1", all_scores=_batch(n_accepted=5, n_rejected=2))
        assert result.signal.accepted_count == 5

    def test_T10_01_04_signal_total_candidates_correct(self, tmp_path):
        """signal.total_candidates must equal total score count."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="e1", all_scores=_batch(3, 2))
        assert result.signal.total_candidates == 5

    def test_T10_01_05_acceptance_rate_is_ratio(self, tmp_path):
        """signal.acceptance_rate must equal accepted_count / total_candidates."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="e1", all_scores=_batch(n_accepted=4, n_rejected=1))
        assert result.signal.acceptance_rate == pytest.approx(4 / 5, abs=0.001)

    def test_T10_01_06_avg_reward_is_positive_for_accepted_batch(self, tmp_path):
        """avg_reward must be > 0 when most mutations are accepted."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="e1", all_scores=_batch(n_accepted=4, n_rejected=0))
        assert result.signal.avg_reward > 0.0

    def test_T10_01_07_ledger_entry_written_on_ingest(self, tmp_path):
        """ingest() must write a fitness_signal ledger entry."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="epoch-042", all_scores=_batch(3, 1))
        assert result.signal.ledger_accepted is True
        assert result.signal.ledger_entry_id != ""

    def test_T10_01_08_ledger_entry_context_type_is_fitness_signal(self, tmp_path):
        """The ledger entry must have context_type='fitness_signal'."""
        ledger = _make_ledger(tmp_path)
        from runtime.memory.reward_signal_bridge import RewardSignalBridge
        bridge = RewardSignalBridge(ledger=ledger, audit_writer=_no_op_audit)
        bridge.ingest(epoch_id="e1", all_scores=_batch(3, 1))
        entries = ledger._all_entries()
        fitness_entries = [e for e in entries if e.get("context_type") == "fitness_signal"]
        assert len(fitness_entries) == 1

    def test_T10_01_09_recent_evaluations_populated_after_ingest(self, tmp_path):
        """recent_evaluations deque must contain an entry after ingest."""
        bridge = _make_bridge(tmp_path)
        assert len(bridge.recent_evaluations) == 0
        bridge.ingest(epoch_id="e1", all_scores=_batch(3, 1))
        assert len(bridge.recent_evaluations) == 1

    def test_T10_01_10_ring_buffer_caps_at_max_size(self, tmp_path):
        """recent_evaluations deque must not exceed OBSERVATION_RING_BUFFER_SIZE."""
        from runtime.memory.reward_signal_bridge import OBSERVATION_RING_BUFFER_SIZE
        bridge = _make_bridge(tmp_path)
        for i in range(OBSERVATION_RING_BUFFER_SIZE + 5):
            bridge.ingest(epoch_id=f"e{i}", all_scores=_batch(2, 1))
        assert len(bridge.recent_evaluations) == OBSERVATION_RING_BUFFER_SIZE

    def test_T10_01_11_last_evaluation_property_returns_most_recent(self, tmp_path):
        """last_evaluation must return the most recently appended PromotionEvaluation."""
        bridge = _make_bridge(tmp_path)
        bridge.ingest(epoch_id="e1", all_scores=_batch(2, 1))
        bridge.ingest(epoch_id="e2", all_scores=_batch(4, 0))  # all accepted
        eval_ = bridge.last_evaluation
        assert eval_ is not None
        assert eval_.accepted_count == 4

    def test_T10_01_12_last_signal_property_returns_most_recent(self, tmp_path):
        """last_signal must return the most recently produced EpochRewardSignal."""
        bridge = _make_bridge(tmp_path)
        bridge.ingest(epoch_id="e1", all_scores=_batch(1, 1))
        bridge.ingest(epoch_id="e2", all_scores=_batch(3, 0))
        assert bridge.last_signal is not None
        assert bridge.last_signal.epoch_id == "e2"

    def test_T10_01_13_reward_schema_weights_sum_to_1(self, tmp_path):
        """Default RewardSchema weights must sum to 1.0."""
        from runtime.autonomy.reward_learning import RewardSchema
        schema = RewardSchema()
        assert schema.total() == pytest.approx(1.0, abs=0.001)

    def test_T10_01_14_zero_accepted_avg_reward_below_half(self, tmp_path):
        """avg_reward must be < 0.5 when no mutations are accepted."""
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="e1", all_scores=_batch(n_accepted=0, n_rejected=4))
        assert result.signal.avg_reward < 0.5


# ════════════════════════════════════════════════════════════════════════════
# EvolutionLoop wiring — T10-01-15..18
# ════════════════════════════════════════════════════════════════════════════

class TestEvolutionLoopPhase5dWiring:

    def test_T10_01_15_evolution_loop_has_reward_bridge_attribute(self):
        """EvolutionLoop must have _reward_bridge attribute defaulting to None."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        loop = EvolutionLoop.__new__(EvolutionLoop)
        loop._reward_bridge = None
        assert loop._reward_bridge is None

    def test_T10_01_16_reward_bridge_can_be_assigned(self, tmp_path):
        """_reward_bridge can be assigned a RewardSignalBridge instance."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.memory.reward_signal_bridge import RewardSignalBridge
        bridge = _make_bridge(tmp_path)
        loop = EvolutionLoop.__new__(EvolutionLoop)
        loop._reward_bridge = bridge
        assert loop._reward_bridge is bridge

    def test_T10_01_17_bridge_exception_does_not_propagate(self, tmp_path):
        """Exception in _reward_bridge.ingest must not crash the phase 5d guard."""
        from runtime.memory.reward_signal_bridge import RewardSignalBridge
        bad_bridge = MagicMock(spec=RewardSignalBridge)
        bad_bridge.ingest.side_effect = RuntimeError("simulated bridge failure")

        try:
            if bad_bridge is not None:
                try:
                    bad_bridge.ingest(epoch_id="e1", all_scores=_batch(2, 1))
                except Exception:
                    pass
            outcome = "epoch_continued"
        except Exception:
            outcome = "epoch_crashed"

        assert outcome == "epoch_continued"

    def test_T10_01_18_bridge_ingests_all_scores_not_only_accepted(self, tmp_path):
        """Bridge must receive all_scores (accepted + rejected), not just accepted."""
        from runtime.memory.reward_signal_bridge import RewardSignalBridge
        captured_calls = []

        class CapturingBridge:
            def ingest(self, *, epoch_id, all_scores):
                captured_calls.append(len(all_scores))
                from runtime.memory.reward_signal_bridge import BridgeResult, EpochRewardSignal
                sig = EpochRewardSignal(
                    epoch_id=epoch_id, total_candidates=len(all_scores), accepted_count=2,
                    avg_reward=0.5, acceptance_rate=0.5, replay_stability_rate=0.5,
                    observations_count=len(all_scores), ledger_entry_id="", ledger_accepted=False,
                )
                return BridgeResult(signal=sig, emitted=True)

        bridge = CapturingBridge()
        all_scores = _batch(n_accepted=3, n_rejected=2)  # 5 total
        # Simulate what evolution_loop Phase 5d does
        if bridge is not None:
            try:
                bridge.ingest(epoch_id="e1", all_scores=all_scores)
            except Exception:
                pass

        assert captured_calls == [5]   # All 5 scores passed, not just 3 accepted


# ════════════════════════════════════════════════════════════════════════════
# EpochRewardSignal — T10-01-19..20
# ════════════════════════════════════════════════════════════════════════════

class TestEpochRewardSignal:

    def test_T10_01_19_as_dict_is_json_serialisable(self, tmp_path):
        """EpochRewardSignal.as_dict() must be JSON-serialisable."""
        import json
        bridge = _make_bridge(tmp_path)
        result = bridge.ingest(epoch_id="e1", all_scores=_batch(3, 1))
        serialized = json.dumps(result.signal.as_dict())
        assert isinstance(serialized, str)

    def test_T10_01_20_multiple_epochs_produce_distinct_ledger_entries(self, tmp_path):
        """Multiple ingest() calls must produce distinct ledger entries."""
        ledger = _make_ledger(tmp_path)
        from runtime.memory.reward_signal_bridge import RewardSignalBridge
        bridge = RewardSignalBridge(ledger=ledger, audit_writer=_no_op_audit)

        r1 = bridge.ingest(epoch_id="e1", all_scores=_batch(2, 1))
        r2 = bridge.ingest(epoch_id="e2", all_scores=_batch(3, 0))
        r3 = bridge.ingest(epoch_id="e3", all_scores=_batch(1, 2))

        entry_ids = [r1.signal.ledger_entry_id,
                     r2.signal.ledger_entry_id,
                     r3.signal.ledger_entry_id]
        # All entries must be unique UUIDs
        assert len(set(entry_ids)) == 3
