# SPDX-License-Identifier: Apache-2.0
"""Phase 62 test suite — T62-FIT-01..10.

Invariants under test:
  FIT-BOUND-0  Weight validation at construction; composite bounded [0.0, 1.0].
  FIT-DET-0    Identical inputs → identical composite + score_hash.
  FIT-DIV-0    replay_result.diverged=True → composite=0.0; other signals computed.
  FIT-ARCH-0   architecture_active=False → architectural_fitness=0.5 (neutral).
"""

from __future__ import annotations

import os
import pytest

from runtime.evolution.fitness_v2 import (
    FitnessConfig,
    FitnessContext,
    FitnessEngineV2,
    FitnessScores,
    ReplayResult,
    _DEFAULT_WEIGHTS,
    _SIGNAL_KEYS,
    _WEIGHT_FLOOR,
    _WEIGHT_CEILING,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def default_engine(monkeypatch) -> FitnessEngineV2:
    """Engine with default config and arch signal OFF (FIT-ARCH-0)."""
    monkeypatch.delenv("PHASE62_ARCH_SIGNAL", raising=False)
    return FitnessEngineV2()


@pytest.fixture()
def arch_active_engine(monkeypatch) -> FitnessEngineV2:
    """Engine with arch signal activated."""
    monkeypatch.setenv("PHASE62_ARCH_SIGNAL", "true")
    return FitnessEngineV2()


@pytest.fixture()
def baseline_context() -> FitnessContext:
    return FitnessContext(
        epoch_id="epoch-test-001",
        test_fitness=0.8,
        complexity_fitness=0.7,
        performance_fitness=0.6,
        governance_compliance=0.9,
        architectural_fitness=0.75,
        determinism_fitness=1.0,
        net_node_additions=0,
        replay_result=ReplayResult(diverged=False),
        code_intel_model_hash="sha256:" + "a" * 64,
        epoch_memory_snapshot="snap-001",
        policy_config_hash="sha256:" + "b" * 64,
    )


# ---------------------------------------------------------------------------
# T62-FIT-01: All 7 signal sources instantiate; scores bounded [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestT62FIT01:
    def test_all_signals_present_and_bounded(self, default_engine, baseline_context):
        scores = default_engine.score(baseline_context)
        assert isinstance(scores, FitnessScores)
        for key in _SIGNAL_KEYS:
            value = getattr(scores, key)
            assert 0.0 <= value <= 1.0, f"signal {key}={value} outside [0.0, 1.0]"
        assert 0.0 <= scores.composite_score <= 1.0

    def test_score_hash_present(self, default_engine, baseline_context):
        scores = default_engine.score(baseline_context)
        assert scores.score_hash.startswith("sha256:")
        assert len(scores.score_hash) == len("sha256:") + 64


# ---------------------------------------------------------------------------
# T62-FIT-02: FIT-BOUND-0 — weight validation rejects out-of-range config
# ---------------------------------------------------------------------------

class TestT62FIT02:
    def test_weight_below_floor_rejected(self):
        bad_weights = dict(_DEFAULT_WEIGHTS)
        bad_weights["test_fitness"] = _WEIGHT_FLOOR - 0.01  # 0.04
        # rebalance sum (roughly) so only the floor violation triggers
        bad_weights["complexity_fitness"] = _DEFAULT_WEIGHTS["complexity_fitness"] + 0.01
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=bad_weights)

    def test_weight_above_ceiling_rejected(self):
        bad_weights = dict(_DEFAULT_WEIGHTS)
        bad_weights["test_fitness"] = _WEIGHT_CEILING + 0.01  # 0.71
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=bad_weights)

    def test_weight_sum_not_one_rejected(self):
        bad_weights = dict(_DEFAULT_WEIGHTS)
        bad_weights["test_fitness"] = 0.10  # forces sum != 1.0 without rebalancing
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=bad_weights)

    def test_missing_signal_key_rejected(self):
        bad_weights = {k: v for k, v in _DEFAULT_WEIGHTS.items() if k != "determinism_fitness"}
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=bad_weights)

    def test_unknown_signal_key_rejected(self):
        bad_weights = dict(_DEFAULT_WEIGHTS)
        bad_weights["unknown_signal"] = 0.01
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=bad_weights)

    def test_code_pressure_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=dict(_DEFAULT_WEIGHTS), code_pressure_multiplier=0.01)

    def test_code_pressure_too_negative_rejected(self):
        with pytest.raises(ValueError, match="FIT-BOUND-0"):
            FitnessConfig(weights=dict(_DEFAULT_WEIGHTS), code_pressure_multiplier=-0.20)


# ---------------------------------------------------------------------------
# T62-FIT-03: FIT-BOUND-0 — valid config passes; composite in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestT62FIT03:
    def test_default_config_valid(self):
        config = FitnessConfig.default()
        assert config is not None

    def test_composite_bounded(self, default_engine, baseline_context):
        scores = default_engine.score(baseline_context)
        assert 0.0 <= scores.composite_score <= 1.0

    def test_composite_bounded_extreme_inputs(self, default_engine):
        ctx_high = FitnessContext(
            epoch_id="extreme-high",
            test_fitness=1.0, complexity_fitness=1.0, performance_fitness=1.0,
            governance_compliance=1.0, architectural_fitness=1.0, determinism_fitness=1.0,
            net_node_additions=0,
        )
        ctx_low = FitnessContext(
            epoch_id="extreme-low",
            test_fitness=0.0, complexity_fitness=0.0, performance_fitness=0.0,
            governance_compliance=0.0, architectural_fitness=0.0, determinism_fitness=0.0,
            net_node_additions=0,
        )
        high_scores = default_engine.score(ctx_high)
        low_scores = default_engine.score(ctx_low)
        assert high_scores.composite_score <= 1.0
        assert low_scores.composite_score >= 0.0


# ---------------------------------------------------------------------------
# T62-FIT-04: FIT-DIV-0 — diverged replay forces composite to 0.0
# ---------------------------------------------------------------------------

class TestT62FIT04:
    def test_diverged_replay_forces_zero_composite(self, default_engine):
        ctx = FitnessContext(
            epoch_id="div-test",
            test_fitness=0.9,
            complexity_fitness=0.9,
            performance_fitness=0.9,
            governance_compliance=0.9,
            architectural_fitness=0.9,
            determinism_fitness=0.9,
            replay_result=ReplayResult(diverged=True, divergence_class="drift_local_digest_mismatch"),
        )
        scores = default_engine.score(ctx)
        assert scores.composite_score == 0.0
        assert scores.determinism_override is True

    def test_non_diverged_replay_normal_composite(self, default_engine, baseline_context):
        scores = default_engine.score(baseline_context)
        assert scores.determinism_override is False
        assert scores.composite_score > 0.0


# ---------------------------------------------------------------------------
# T62-FIT-05: FIT-DIV-0 — all signal scores computed even when overridden
# ---------------------------------------------------------------------------

class TestT62FIT05:
    def test_signals_still_computed_on_divergence(self, default_engine):
        ctx = FitnessContext(
            epoch_id="div-signals-test",
            test_fitness=0.8,
            complexity_fitness=0.7,
            performance_fitness=0.6,
            governance_compliance=0.9,
            architectural_fitness=0.5,
            determinism_fitness=1.0,
            replay_result=ReplayResult(diverged=True),
        )
        scores = default_engine.score(ctx)
        # Composite overridden to 0.0 by FIT-DIV-0
        assert scores.composite_score == 0.0
        assert scores.determinism_override is True
        # But individual signals are still computed and logged
        assert scores.test_fitness == pytest.approx(0.8)
        assert scores.complexity_fitness == pytest.approx(0.7)
        assert scores.performance_fitness == pytest.approx(0.6)
        assert scores.governance_compliance == pytest.approx(0.9)
        assert scores.determinism_fitness == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T62-FIT-06: FIT-DET-0 — identical inputs → identical composite + score_hash
# ---------------------------------------------------------------------------

class TestT62FIT06:
    def test_identical_inputs_identical_scores(self, monkeypatch):
        monkeypatch.delenv("PHASE62_ARCH_SIGNAL", raising=False)
        ctx = FitnessContext(
            epoch_id="det-test",
            test_fitness=0.75,
            complexity_fitness=0.65,
            performance_fitness=0.55,
            governance_compliance=0.85,
            architectural_fitness=0.5,
            determinism_fitness=1.0,
            net_node_additions=5,
            replay_result=ReplayResult(diverged=False),
            code_intel_model_hash="sha256:" + "c" * 64,
            epoch_memory_snapshot="snap-det",
            policy_config_hash="sha256:" + "d" * 64,
        )
        # Two independent engine instances with same config
        engine_a = FitnessEngineV2()
        engine_b = FitnessEngineV2()
        scores_a = engine_a.score(ctx)
        scores_b = engine_b.score(ctx)
        assert scores_a.composite_score == scores_b.composite_score
        assert scores_a.score_hash == scores_b.score_hash

    def test_different_epoch_ids_different_hashes(self, default_engine):
        ctx_a = FitnessContext(epoch_id="epoch-a", test_fitness=0.8, complexity_fitness=0.7,
                               performance_fitness=0.6, governance_compliance=0.9,
                               architectural_fitness=0.5, determinism_fitness=1.0)
        ctx_b = FitnessContext(epoch_id="epoch-b", test_fitness=0.8, complexity_fitness=0.7,
                               performance_fitness=0.6, governance_compliance=0.9,
                               architectural_fitness=0.5, determinism_fitness=1.0)
        scores_a = default_engine.score(ctx_a)
        scores_b = default_engine.score(ctx_b)
        # Different epoch_ids must produce different score_hashes
        assert scores_a.score_hash != scores_b.score_hash


# ---------------------------------------------------------------------------
# T62-FIT-07: FIT-ARCH-0 — inactive flag returns 0.5 for architectural signal
# ---------------------------------------------------------------------------

class TestT62FIT07:
    def test_arch_inactive_returns_neutral(self, default_engine):
        assert default_engine.architecture_active is False
        ctx = FitnessContext(
            epoch_id="arch-inactive",
            architectural_fitness=0.9,  # caller-provided value should be overridden
        )
        scores = default_engine.score(ctx)
        assert scores.architectural_fitness == pytest.approx(0.5)
        assert scores.architecture_active is False

    def test_arch_inactive_does_not_block_mutations(self, default_engine):
        """FIT-ARCH-0: neutral 0.5 must not penalise; composite should be reasonable."""
        ctx = FitnessContext(
            epoch_id="arch-no-block",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.0,  # would penalise if active
            determinism_fitness=1.0,
        )
        scores = default_engine.score(ctx)
        # architectural_fitness forced to 0.5 — composite must be > what 0.0 would give
        assert scores.architectural_fitness == pytest.approx(0.5)
        assert scores.composite_score > 0.5  # healthy composite despite caller passing 0.0


# ---------------------------------------------------------------------------
# T62-FIT-08: FIT-ARCH-0 — active flag computes from caller-provided signal
# ---------------------------------------------------------------------------

class TestT62FIT08:
    def test_arch_active_uses_caller_value(self, arch_active_engine):
        assert arch_active_engine.architecture_active is True
        ctx = FitnessContext(
            epoch_id="arch-active",
            architectural_fitness=0.9,
        )
        scores = arch_active_engine.score(ctx)
        assert scores.architectural_fitness == pytest.approx(0.9)
        assert scores.architecture_active is True

    def test_arch_active_low_value_affects_composite(self, arch_active_engine, monkeypatch):
        ctx_high_arch = FitnessContext(
            epoch_id="arch-high",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=1.0, determinism_fitness=1.0,
        )
        ctx_low_arch = FitnessContext(
            epoch_id="arch-low",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.0, determinism_fitness=1.0,
        )
        s_high = arch_active_engine.score(ctx_high_arch)
        s_low = arch_active_engine.score(ctx_low_arch)
        assert s_high.composite_score > s_low.composite_score


# ---------------------------------------------------------------------------
# T62-FIT-09: Code pressure modifier behaviour
# ---------------------------------------------------------------------------

class TestT62FIT09:
    def test_positive_additions_reduce_composite(self, default_engine):
        ctx_no_add = FitnessContext(
            epoch_id="pressure-zero",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.8, determinism_fitness=1.0,
            net_node_additions=0,
        )
        ctx_with_add = FitnessContext(
            epoch_id="pressure-positive",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.8, determinism_fitness=1.0,
            net_node_additions=10,
        )
        s0 = default_engine.score(ctx_no_add)
        s1 = default_engine.score(ctx_with_add)
        assert s0.composite_score > s1.composite_score

    def test_zero_additions_no_pressure(self, default_engine):
        ctx = FitnessContext(
            epoch_id="pressure-none",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.8, determinism_fitness=1.0,
            net_node_additions=0,
        )
        scores = default_engine.score(ctx)
        assert scores.code_pressure_adjustment == pytest.approx(0.0)

    def test_deletions_not_penalised(self, default_engine):
        """Negative net_node_additions (deletions) should not incur a penalty."""
        ctx = FitnessContext(
            epoch_id="pressure-deletion",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.8, determinism_fitness=1.0,
            net_node_additions=-10,  # net deletions
        )
        scores = default_engine.score(ctx)
        # Deletions should not be penalised (adjustment = 0.0, not positive)
        assert scores.code_pressure_adjustment == pytest.approx(0.0)

    def test_pressure_bounded(self, default_engine):
        """code_pressure_adjustment must stay >= -0.15 even for huge additions."""
        ctx = FitnessContext(
            epoch_id="pressure-huge",
            test_fitness=0.8, complexity_fitness=0.8, performance_fitness=0.8,
            governance_compliance=0.8, architectural_fitness=0.8, determinism_fitness=1.0,
            net_node_additions=100_000,
        )
        scores = default_engine.score(ctx)
        assert scores.code_pressure_adjustment >= -0.15


# ---------------------------------------------------------------------------
# T62-FIT-10: Full integration — FitnessEngineV2 produces complete FitnessScores
# ---------------------------------------------------------------------------

class TestT62FIT10:
    def test_full_scores_all_fields_populated(self, default_engine, baseline_context):
        scores = default_engine.score(baseline_context)
        assert scores.epoch_id == baseline_context.epoch_id
        assert scores.score_hash.startswith("sha256:")
        # All six signal fields must be present
        for key in _SIGNAL_KEYS:
            assert hasattr(scores, key)
            assert 0.0 <= getattr(scores, key) <= 1.0
        assert isinstance(scores.code_pressure_adjustment, float)
        assert isinstance(scores.composite_score, float)
        assert isinstance(scores.determinism_override, bool)
        assert isinstance(scores.architecture_active, bool)

    def test_score_hash_deterministic_full_context(self, monkeypatch):
        monkeypatch.delenv("PHASE62_ARCH_SIGNAL", raising=False)
        ctx = FitnessContext(
            epoch_id="full-det-test",
            test_fitness=0.75, complexity_fitness=0.65, performance_fitness=0.55,
            governance_compliance=0.85, architectural_fitness=0.75, determinism_fitness=1.0,
            net_node_additions=3,
            replay_result=ReplayResult(diverged=False, divergence_class="none"),
            code_intel_model_hash="sha256:" + "e" * 64,
            epoch_memory_snapshot="epoch-snap-full",
            policy_config_hash="sha256:" + "f" * 64,
        )
        e1 = FitnessEngineV2()
        e2 = FitnessEngineV2()
        s1 = e1.score(ctx)
        s2 = e2.score(ctx)
        assert s1.score_hash == s2.score_hash
        assert s1.composite_score == s2.composite_score
        assert s1.to_dict() == s2.to_dict()

    def test_to_dict_round_trip(self, default_engine, baseline_context):
        scores = default_engine.score(baseline_context)
        d = scores.to_dict()
        assert d["epoch_id"] == baseline_context.epoch_id
        assert d["score_hash"] == scores.score_hash
        assert d["composite_score"] == scores.composite_score
        assert d["determinism_override"] is False
