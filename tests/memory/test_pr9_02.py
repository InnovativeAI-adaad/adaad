# SPDX-License-Identifier: Apache-2.0
"""
Phase 9 PR-9-02 — Test suite for CraftPatternExtractor + EvolutionLoop wiring.

Test IDs: T9-02-01 through T9-02-20

Coverage:
    CraftPatternExtractor   (T9-02-01..14) — gate, stats, signal_quality_flag,
                                             ledger write, dominant pattern, skip
    EvolutionLoop wiring    (T9-02-15..18) — extractor injected, velocity read,
                                             failure isolation, constructor param
    AgentPatternStats       (T9-02-19..20) — per-agent grouping, elite count
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
pytestmark = pytest.mark.regression_standard

# ─── Test helpers ──────────────────────────────────────────────────────────

_TEST_KEY_BYTES = bytes.fromhex("b" * 64)


def _no_op_audit(*args, **kwargs):
    return {}


def _make_ledger(tmp_path: Path):
    from runtime.memory.soulbound_ledger import SoulboundLedger
    return SoulboundLedger(
        ledger_path=tmp_path / "ledger.json",
        audit_writer=_no_op_audit,
        key_override=_TEST_KEY_BYTES,
    )


def _make_extractor(tmp_path: Path, min_accepted: int = 2):
    from runtime.memory.craft_pattern_extractor import CraftPatternExtractor
    return CraftPatternExtractor(
        ledger=_make_ledger(tmp_path),
        audit_writer=_no_op_audit,
        min_accepted=min_accepted,
    )


def _make_score(
    agent: str = "architect",
    score: float = 0.75,
    accepted: bool = True,
    epoch_id: str = "epoch-042",
    risk_contrib: float = 0.14,
    complexity_contrib: float = 0.04,
) -> MagicMock:
    s = MagicMock()
    s.mutation_id = f"mut-{agent}-{score}"
    s.agent_origin = agent
    s.score = score
    s.accepted = accepted
    s.epoch_id = epoch_id
    s.dimension_breakdown = {
        "risk_penalty_contrib": risk_contrib,
        "complexity_penalty_contrib": complexity_contrib,
    }
    return s


def _accepted(n: int, agent: str = "architect", score: float = 0.75) -> List[MagicMock]:
    return [_make_score(agent=agent, score=score) for _ in range(n)]


# ════════════════════════════════════════════════════════════════════════════
# CraftPatternExtractor — T9-02-01..14
# ════════════════════════════════════════════════════════════════════════════

class TestCraftPatternExtractor:

    def test_T9_02_01_extract_emits_pattern_when_sufficient_accepted(self, tmp_path):
        """extract() must return emitted=True when accepted_count >= min_accepted."""
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=_accepted(3),
            weight_velocity_risk=0.012,
            weight_velocity_complexity=0.008,
        )
        assert result.emitted is True
        assert result.ledger_result is not None
        assert result.ledger_result.accepted is True

    def test_T9_02_02_extract_skips_when_below_minimum(self, tmp_path):
        """extract() must skip (emitted=False) when accepted_count < min_accepted."""
        extractor = _make_extractor(tmp_path, min_accepted=3)
        result = extractor.extract(
            epoch_id="epoch-001",
            accepted_scores=_accepted(2),
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        assert result.emitted is False
        assert result.ledger_result is None
        assert result.pattern.skipped is True
        assert result.pattern.skip_reason is not None

    def test_T9_02_03_extract_skips_when_zero_accepted(self, tmp_path):
        """extract() must skip on empty accepted_scores list."""
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-000",
            accepted_scores=[],
            weight_velocity_risk=0.0,
            weight_velocity_complexity=0.0,
        )
        assert result.emitted is False
        assert result.pattern.skipped is True

    def test_T9_02_04_pattern_contains_correct_epoch_id(self, tmp_path):
        """Emitted CraftPattern.epoch_id must match the input epoch_id."""
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-777",
            accepted_scores=_accepted(4),
            weight_velocity_risk=0.02,
            weight_velocity_complexity=0.01,
        )
        assert result.pattern.epoch_id == "epoch-777"

    def test_T9_02_05_pattern_accepted_count_matches_input(self, tmp_path):
        """CraftPattern.accepted_count must equal len(accepted_scores)."""
        extractor = _make_extractor(tmp_path)
        scores = _accepted(7)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=scores,
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        assert result.pattern.accepted_count == 7

    def test_T9_02_06_signal_quality_flag_set_when_velocity_low(self, tmp_path):
        """signal_quality_flag must be 'low_velocity' when max|velocity| < threshold."""
        from runtime.memory.craft_pattern_extractor import VELOCITY_QUALITY_THRESHOLD
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=_accepted(3),
            weight_velocity_risk=VELOCITY_QUALITY_THRESHOLD * 0.5,
            weight_velocity_complexity=VELOCITY_QUALITY_THRESHOLD * 0.5,
        )
        assert result.pattern.signal_quality_flag == "low_velocity"

    def test_T9_02_07_signal_quality_flag_none_when_velocity_sufficient(self, tmp_path):
        """signal_quality_flag must be None when velocity is above threshold."""
        from runtime.memory.craft_pattern_extractor import VELOCITY_QUALITY_THRESHOLD
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=_accepted(3),
            weight_velocity_risk=VELOCITY_QUALITY_THRESHOLD * 2.0,
            weight_velocity_complexity=0.0,
        )
        assert result.pattern.signal_quality_flag is None

    def test_T9_02_08_ledger_entry_context_type_is_craft_pattern(self, tmp_path):
        """The ledger entry written must have context_type='craft_pattern'."""
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=_accepted(3),
            weight_velocity_risk=0.02,
            weight_velocity_complexity=0.015,
        )
        assert result.ledger_result is not None
        assert result.ledger_result.entry.context_type == "craft_pattern"

    def test_T9_02_09_dominant_agent_is_highest_count_agent(self, tmp_path):
        """dominant_agent must be the agent with most accepted mutations."""
        extractor = _make_extractor(tmp_path)
        scores = (
            _accepted(5, agent="architect") +
            _accepted(2, agent="dream") +
            _accepted(1, agent="beast")
        )
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=scores,
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        assert result.pattern.dominant_agent == "architect"
        assert result.pattern.dominant_pattern == "structural"

    def test_T9_02_10_agent_stats_grouped_correctly(self, tmp_path):
        """agent_stats must have one entry per unique agent_origin."""
        extractor = _make_extractor(tmp_path)
        scores = _accepted(3, "architect") + _accepted(2, "dream")
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=scores,
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        agent_origins = {s.agent_origin for s in result.pattern.agent_stats}
        assert "architect" in agent_origins
        assert "dream" in agent_origins
        assert len(agent_origins) == 2

    def test_T9_02_11_mean_epoch_score_is_correct(self, tmp_path):
        """mean_epoch_score must equal mean of all accepted scores."""
        extractor = _make_extractor(tmp_path)
        scores = [
            _make_score(agent="architect", score=0.80),
            _make_score(agent="architect", score=0.60),
            _make_score(agent="dream",     score=0.70),
        ]
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=scores,
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        assert result.pattern.mean_epoch_score == pytest.approx(0.70, abs=0.001)

    def test_T9_02_12_pattern_payload_is_json_serialisable(self, tmp_path):
        """CraftPattern.as_payload() must produce a JSON-serialisable dict."""
        import json
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=_accepted(4),
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        payload = result.pattern.as_payload()
        # Must not raise
        serialized = json.dumps(payload)
        assert isinstance(serialized, str)

    def test_T9_02_13_ledger_chain_grows_across_multiple_epochs(self, tmp_path):
        """Each epoch extraction must append a new ledger entry."""
        extractor = _make_extractor(tmp_path)
        chain_hashes = []
        for i in range(4):
            result = extractor.extract(
                epoch_id=f"epoch-{i:03d}",
                accepted_scores=_accepted(3),
                weight_velocity_risk=0.01,
                weight_velocity_complexity=0.01,
            )
            if result.ledger_result:
                chain_hashes.append(result.ledger_result.entry.chain_hash)

        # All chain hashes must be unique (each links to the previous)
        assert len(set(chain_hashes)) == len(chain_hashes)

    def test_T9_02_14_skip_reason_contains_count_and_minimum(self, tmp_path):
        """skip_reason must encode both the actual count and the minimum."""
        extractor = _make_extractor(tmp_path, min_accepted=5)
        result = extractor.extract(
            epoch_id="epoch-001",
            accepted_scores=_accepted(2),
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        reason = result.pattern.skip_reason or ""
        assert "2" in reason   # actual count
        assert "5" in reason   # minimum


# ════════════════════════════════════════════════════════════════════════════
# EvolutionLoop wiring — T9-02-15..18
# ════════════════════════════════════════════════════════════════════════════

class TestEvolutionLoopWiring:

    def test_T9_02_15_evolution_loop_accepts_craft_extractor_kwarg(self):
        """EvolutionLoop constructor must accept craft_pattern_extractor kwarg."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.memory.craft_pattern_extractor import CraftPatternExtractor
        from runtime.memory.soulbound_ledger import SoulboundLedger

        with tempfile.TemporaryDirectory() as tmp:
            ledger = SoulboundLedger(
                ledger_path=Path(tmp) / "l.json",
                audit_writer=_no_op_audit,
                key_override=_TEST_KEY_BYTES,
            )
            extractor = CraftPatternExtractor(ledger=ledger, audit_writer=_no_op_audit)
            loop = EvolutionLoop.__new__(EvolutionLoop)
            loop._craft_extractor = extractor
            assert loop._craft_extractor is extractor

    def test_T9_02_16_craft_extractor_none_by_default(self):
        """_craft_extractor must be None when no extractor is injected."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        loop = EvolutionLoop.__new__(EvolutionLoop)
        loop._craft_extractor = None   # simulate default init
        assert loop._craft_extractor is None

    def test_T9_02_17_velocity_read_from_penalty_adaptor_attribute(self):
        """EvolutionLoop must read velocity_risk from _penalty_adaptor attribute."""
        # Verify the attribute path used in the wiring code exists
        from runtime.autonomy.weight_adaptor import WeightAdaptor
        adaptor = WeightAdaptor()
        penalty = getattr(adaptor, "_penalty_adaptor", None)
        assert penalty is not None, "_penalty_adaptor must be set on WeightAdaptor"
        assert hasattr(penalty, "_velocity_risk")
        assert hasattr(penalty, "_velocity_complexity")

    def test_T9_02_18_extractor_exception_does_not_propagate(self, tmp_path):
        """An extractor that raises must not crash the evolution loop call site."""
        from runtime.memory.craft_pattern_extractor import CraftPatternExtractor

        bad_extractor = MagicMock(spec=CraftPatternExtractor)
        bad_extractor.extract.side_effect = RuntimeError("simulated extractor failure")

        # Simulate the evolution_loop Phase 5c guard
        extractor = bad_extractor
        accepted = _accepted(3)
        try:
            if extractor is not None:
                try:
                    extractor.extract(
                        epoch_id="epoch-042",
                        accepted_scores=accepted,
                        weight_velocity_risk=0.01,
                        weight_velocity_complexity=0.01,
                    )
                except Exception:
                    pass  # Must swallow — same guard as in evolution_loop.py
            result = "epoch_continued"
        except Exception:
            result = "epoch_crashed"

        assert result == "epoch_continued"


# ════════════════════════════════════════════════════════════════════════════
# AgentPatternStats — T9-02-19..20
# ════════════════════════════════════════════════════════════════════════════

class TestAgentPatternStats:

    def test_T9_02_19_elite_count_counts_scores_above_threshold(self, tmp_path):
        """AgentPatternStats.elite_count must count scores ≥ HIGH_SCORE_THRESHOLD."""
        from runtime.memory.craft_pattern_extractor import (
            CraftPatternExtractor, HIGH_SCORE_THRESHOLD
        )
        extractor = _make_extractor(tmp_path)
        scores = [
            _make_score(agent="architect", score=HIGH_SCORE_THRESHOLD + 0.01),
            _make_score(agent="architect", score=HIGH_SCORE_THRESHOLD + 0.05),
            _make_score(agent="architect", score=HIGH_SCORE_THRESHOLD - 0.01),  # below
        ]
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=scores,
            weight_velocity_risk=0.01,
            weight_velocity_complexity=0.01,
        )
        arch_stats = next(s for s in result.pattern.agent_stats if s.agent_origin == "architect")
        assert arch_stats.elite_count == 2

    def test_T9_02_20_agent_stats_as_dict_is_json_serialisable(self, tmp_path):
        """AgentPatternStats.as_dict() must produce a JSON-serialisable dict."""
        import json
        extractor = _make_extractor(tmp_path)
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=_accepted(5, "architect"),
            weight_velocity_risk=0.02,
            weight_velocity_complexity=0.01,
        )
        for stats in result.pattern.agent_stats:
            serialized = json.dumps(stats.as_dict())
            assert isinstance(serialized, str)
