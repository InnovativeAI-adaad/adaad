# SPDX-License-Identifier: Apache-2.0
"""INNOV-03 — Temporal Invariant Forecasting Engine (TIFE) test suite.

Tests T87-TIFE-01 through T87-TIFE-20.

Coverage
────────
  T87-TIFE-01  ISI = 1.0 for clean mutation across full horizon
  T87-TIFE-02  ISI below threshold triggers TIFE_ISI_BELOW_THRESHOLD
  T87-TIFE-03  TIFE_VIABLE on clean mutation with default horizon
  T87-TIFE-04  TemporalViabilityReport produced on VIABLE outcome
  T87-TIFE-05  TemporalViabilityReport produced on BLOCKED outcome
  T87-TIFE-06  Debt horizon breach triggers TIFE_DEBT_HORIZON_BREACH
  T87-TIFE-07  Dead-end path triggers TIFE_TRAJECTORY_DEAD_END
  T87-TIFE-08  Dead-end path → all epoch_reports have DEAD_END status
  T87-TIFE-09  Capability regression on non-redundant node triggers failure
  T87-TIFE-10  Redundant capability delta does NOT trigger regression
  T87-TIFE-11  Multiple failure codes accumulate on compound failure
  T87-TIFE-12  ISI computed as exact PASS ratio over horizon
  T87-TIFE-13  first_violation_epoch is the earliest failing epoch
  T87-TIFE-14  TemporalViabilityReport.content_hash is deterministic
  T87-TIFE-15  predecessor_hash is threaded into report
  T87-TIFE-16  forecast_horizon determines number of epoch_reports
  T87-TIFE-17  analyse_isi_trend: 'degrading' when second half drops
  T87-TIFE-18  analyse_isi_trend: 'stable' on flat history
  T87-TIFE-19  analyse_isi_trend: alert fires when mean below threshold
  T87-TIFE-20  Full end-to-end: 3-class mutation, 10-epoch horizon → VIABLE
"""

import pytest

from runtime.evolution.tife_engine import (
    DEFAULT_FORECAST_HORIZON,
    DEBT_HORIZON_BREACH_THRESHOLD,
    ISI_PASS_THRESHOLD,
    TIFE_CAPABILITY_REGRESSION,
    TIFE_DEBT_HORIZON_BREACH,
    TIFE_ISI_BELOW_THRESHOLD,
    TIFE_TRAJECTORY_DEAD_END,
    CapabilityGraphSnapshot,
    CapabilityNode,
    EpochProjectionStatus,
    TIFEMutationInput,
    TIFEOutcome,
    VisionProjection,
    analyse_isi_trend,
    evaluate_tife_gate_0,
)

pytestmark = pytest.mark.phase87_innov03

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

GENESIS = ""  # valid predecessor for first report


def _vision(
    dead_ends: frozenset | None = None,
    cap_deltas: dict | None = None,
    horizon: int = DEFAULT_FORECAST_HORIZON,
    debt_traj: tuple | None = None,
) -> VisionProjection:
    if debt_traj is None:
        debt_traj = tuple(0.1 for _ in range(horizon))
    return VisionProjection(
        projection_id="vision-test-001",
        dead_end_paths=dead_ends or frozenset(),
        capability_deltas=cap_deltas or {},
        horizon_epochs=horizon,
        debt_trajectory=debt_traj,
    )


def _graph(nodes: list | None = None) -> CapabilityGraphSnapshot:
    if nodes is None:
        nodes = [CapabilityNode("cap-A", is_redundant=False, depends_on=())]
    return CapabilityGraphSnapshot(snapshot_id="snap-001", nodes=tuple(nodes))


def _mutation(
    mutation_id: str = "mut-tife-001",
    classes: tuple = ("HARD",),
    cap_delta: dict | None = None,
    debt: float = 0.05,
    dead_end: bool = False,
) -> TIFEMutationInput:
    return TIFEMutationInput(
        mutation_id=mutation_id,
        lineage_digest="tife" + "a" * 60,
        epoch_id="epoch-tife-001",
        touched_invariant_classes=classes,
        fitness_thresholds={"fitness": 0.9},
        capability_delta=cap_delta or {},
        proposed_governance_debt=debt,
        touches_dead_end_path=dead_end,
    )


# ---------------------------------------------------------------------------
# T87-TIFE-01: ISI = 1.0 for clean mutation
# ---------------------------------------------------------------------------


def test_t87_tife_01_isi_one_clean_mutation():
    """T87-TIFE-01: Clean mutation with low debt → ISI = 1.0."""
    mutation = _mutation(debt=0.0)
    result = evaluate_tife_gate_0(mutation, _vision(), _graph(), GENESIS)
    assert result.report is not None
    assert result.report.isi == 1.0
    assert result.outcome == TIFEOutcome.VIABLE


# ---------------------------------------------------------------------------
# T87-TIFE-02: ISI below threshold
# ---------------------------------------------------------------------------


def test_t87_tife_02_isi_below_threshold():
    """T87-TIFE-02: High debt trajectory pushes ISI below 0.85."""
    # Dead-end forces all epochs to fail → ISI = 0.0
    mutation = _mutation(dead_end=True, debt=0.0)
    result = evaluate_tife_gate_0(mutation, _vision(), _graph(), GENESIS)
    assert result.report is not None
    assert result.report.isi == 0.0
    assert TIFE_ISI_BELOW_THRESHOLD in result.failure_codes


# ---------------------------------------------------------------------------
# T87-TIFE-03: TIFE_VIABLE on clean mutation with default horizon
# ---------------------------------------------------------------------------


def test_t87_tife_03_viable_default_horizon():
    """T87-TIFE-03: TIFE_VIABLE on no-dead-end, low-debt mutation."""
    result = evaluate_tife_gate_0(_mutation(), _vision(), _graph(), GENESIS)
    assert result.outcome == TIFEOutcome.VIABLE
    assert result.failure_codes == []


# ---------------------------------------------------------------------------
# T87-TIFE-04: TemporalViabilityReport produced on VIABLE
# ---------------------------------------------------------------------------


def test_t87_tife_04_report_produced_on_viable():
    """T87-TIFE-04: Report is not None and has correct structure on VIABLE."""
    result = evaluate_tife_gate_0(_mutation(), _vision(), _graph(), GENESIS)
    rpt = result.report
    assert rpt is not None
    assert rpt.outcome == TIFEOutcome.VIABLE
    assert rpt.forecast_horizon == DEFAULT_FORECAST_HORIZON
    assert len(rpt.epoch_reports) == DEFAULT_FORECAST_HORIZON
    assert rpt.first_violation_epoch is None


# ---------------------------------------------------------------------------
# T87-TIFE-05: TemporalViabilityReport produced on BLOCKED
# ---------------------------------------------------------------------------


def test_t87_tife_05_report_produced_on_blocked():
    """T87-TIFE-05: Report is not None and has failure codes on BLOCKED."""
    mutation = _mutation(dead_end=True)
    result = evaluate_tife_gate_0(mutation, _vision(), _graph(), GENESIS)
    rpt = result.report
    assert rpt is not None
    assert rpt.outcome == TIFEOutcome.BLOCKED
    assert rpt.failure_codes  # at least one code
    assert rpt.first_violation_epoch is not None


# ---------------------------------------------------------------------------
# T87-TIFE-06: Debt horizon breach
# ---------------------------------------------------------------------------


def test_t87_tife_06_debt_horizon_breach():
    """T87-TIFE-06: mutation.proposed_governance_debt drives debt over 0.70."""
    # proposed_debt=0.9 means by epoch 1 the total approaches breach threshold
    mutation = _mutation(debt=0.9, dead_end=False)
    # Baseline debt already at 0.4 to ensure breach quickly
    debt_traj = tuple(0.4 for _ in range(DEFAULT_FORECAST_HORIZON))
    vision = _vision(debt_traj=debt_traj)
    result = evaluate_tife_gate_0(mutation, vision, _graph(), GENESIS)
    assert TIFE_DEBT_HORIZON_BREACH in result.failure_codes


# ---------------------------------------------------------------------------
# T87-TIFE-07: Dead-end path triggers TIFE_TRAJECTORY_DEAD_END
# ---------------------------------------------------------------------------


def test_t87_tife_07_dead_end_triggers_failure():
    """T87-TIFE-07: touches_dead_end_path=True produces TIFE_TRAJECTORY_DEAD_END."""
    mutation = _mutation(dead_end=True)
    result = evaluate_tife_gate_0(mutation, _vision(), _graph(), GENESIS)
    assert TIFE_TRAJECTORY_DEAD_END in result.failure_codes
    assert result.outcome == TIFEOutcome.BLOCKED


# ---------------------------------------------------------------------------
# T87-TIFE-08: Dead-end → all epoch_reports have DEAD_END status
# ---------------------------------------------------------------------------


def test_t87_tife_08_dead_end_all_epochs_fail():
    """T87-TIFE-08: Every epoch has DEAD_END status when mutation targets dead-end path."""
    mutation = _mutation(dead_end=True)
    result = evaluate_tife_gate_0(mutation, _vision(), _graph(), GENESIS)
    assert result.report is not None
    for rpt in result.report.epoch_reports:
        assert rpt.status == EpochProjectionStatus.DEAD_END


# ---------------------------------------------------------------------------
# T87-TIFE-09: Capability regression on non-redundant node
# ---------------------------------------------------------------------------


def test_t87_tife_09_capability_regression_non_redundant():
    """T87-TIFE-09: Negative delta on non-redundant capability → TIFE_CAPABILITY_REGRESSION."""
    nodes = [CapabilityNode("cap-X", is_redundant=False, depends_on=())]
    graph = CapabilityGraphSnapshot("snap", tuple(nodes))
    mutation = _mutation(cap_delta={"cap-X": -0.5})
    result = evaluate_tife_gate_0(mutation, _vision(), graph, GENESIS)
    assert TIFE_CAPABILITY_REGRESSION in result.failure_codes
    assert "cap-X" in result.report.capability_regression


# ---------------------------------------------------------------------------
# T87-TIFE-10: Redundant capability does NOT trigger regression
# ---------------------------------------------------------------------------


def test_t87_tife_10_redundant_capability_no_regression():
    """T87-TIFE-10: Negative delta on redundant capability is allowed."""
    nodes = [CapabilityNode("cap-R", is_redundant=True, depends_on=())]
    graph = CapabilityGraphSnapshot("snap", tuple(nodes))
    mutation = _mutation(cap_delta={"cap-R": -0.9})
    result = evaluate_tife_gate_0(mutation, _vision(), graph, GENESIS)
    assert TIFE_CAPABILITY_REGRESSION not in result.failure_codes


# ---------------------------------------------------------------------------
# T87-TIFE-11: Multiple failure codes accumulate
# ---------------------------------------------------------------------------


def test_t87_tife_11_compound_failure_codes():
    """T87-TIFE-11: Dead-end + capability regression both recorded."""
    nodes = [CapabilityNode("cap-Y", is_redundant=False, depends_on=())]
    graph = CapabilityGraphSnapshot("snap", tuple(nodes))
    mutation = _mutation(dead_end=True, cap_delta={"cap-Y": -1.0})
    result = evaluate_tife_gate_0(mutation, _vision(), graph, GENESIS)
    assert TIFE_TRAJECTORY_DEAD_END in result.failure_codes
    assert TIFE_CAPABILITY_REGRESSION in result.failure_codes
    assert TIFE_ISI_BELOW_THRESHOLD in result.failure_codes


# ---------------------------------------------------------------------------
# T87-TIFE-12: ISI is exact PASS ratio
# ---------------------------------------------------------------------------


def test_t87_tife_12_isi_exact_ratio():
    """T87-TIFE-12: ISI = pass_epochs / total_epochs exactly."""
    # 5 epochs, high debt from epoch 3 onward (debt forces breach after half-way)
    debt_traj = (0.1, 0.1, 0.1, 0.8, 0.8)
    mutation = _mutation(debt=0.0, dead_end=False)
    vision = _vision(debt_traj=debt_traj, horizon=5)
    result = evaluate_tife_gate_0(mutation, vision, _graph(), GENESIS, forecast_horizon=5)
    rpt = result.report
    assert rpt is not None
    pass_count = sum(1 for r in rpt.epoch_reports if r.status == EpochProjectionStatus.PASS)
    assert rpt.isi == pass_count / 5


# ---------------------------------------------------------------------------
# T87-TIFE-13: first_violation_epoch is earliest failing epoch
# ---------------------------------------------------------------------------


def test_t87_tife_13_first_violation_epoch():
    """T87-TIFE-13: first_violation_epoch points to the first failing epoch."""
    debt_traj = (0.1, 0.1, 0.8, 0.8, 0.8)
    mutation = _mutation(debt=0.0, dead_end=False)
    vision = _vision(debt_traj=debt_traj, horizon=5)
    result = evaluate_tife_gate_0(mutation, vision, _graph(), GENESIS, forecast_horizon=5)
    rpt = result.report
    assert rpt is not None
    # Epoch 2 has baseline debt 0.8 > 0.7 threshold
    assert rpt.first_violation_epoch == 2


# ---------------------------------------------------------------------------
# T87-TIFE-14: content_hash deterministic
# ---------------------------------------------------------------------------


def test_t87_tife_14_content_hash_deterministic():
    """T87-TIFE-14: content_hash() returns same value on repeated calls."""
    result = evaluate_tife_gate_0(_mutation(), _vision(), _graph(), GENESIS)
    rpt = result.report
    assert rpt is not None
    assert rpt.content_hash() == rpt.content_hash()
    assert len(rpt.content_hash()) == 64


# ---------------------------------------------------------------------------
# T87-TIFE-15: predecessor_hash threaded into report
# ---------------------------------------------------------------------------


def test_t87_tife_15_predecessor_hash_threading():
    """T87-TIFE-15: predecessor_hash arg appears in TemporalViabilityReport."""
    pred = "c" * 64
    result = evaluate_tife_gate_0(_mutation(), _vision(), _graph(), pred)
    assert result.report is not None
    assert result.report.predecessor_hash == pred


# ---------------------------------------------------------------------------
# T87-TIFE-16: forecast_horizon determines epoch_reports length
# ---------------------------------------------------------------------------


def test_t87_tife_16_forecast_horizon_controls_epoch_count():
    """T87-TIFE-16: epoch_reports length == forecast_horizon argument."""
    for horizon in (3, 7, 15):
        result = evaluate_tife_gate_0(
            _mutation(), _vision(horizon=horizon), _graph(), GENESIS,
            forecast_horizon=horizon,
        )
        assert result.report is not None
        assert len(result.report.epoch_reports) == horizon


# ---------------------------------------------------------------------------
# T87-TIFE-17: analyse_isi_trend: 'degrading'
# ---------------------------------------------------------------------------


def test_t87_tife_17_isi_trend_degrading():
    """T87-TIFE-17: ISI dropping in second half → 'degrading' trend."""
    history = [0.95, 0.94, 0.93, 0.80, 0.78]
    result = analyse_isi_trend(history, window=5)
    assert result["trend"] == "degrading"


# ---------------------------------------------------------------------------
# T87-TIFE-18: analyse_isi_trend: 'stable'
# ---------------------------------------------------------------------------


def test_t87_tife_18_isi_trend_stable():
    """T87-TIFE-18: Flat ISI history → 'stable' trend."""
    history = [0.92, 0.92, 0.92, 0.92, 0.92]
    result = analyse_isi_trend(history, window=5)
    assert result["trend"] == "stable"


# ---------------------------------------------------------------------------
# T87-TIFE-19: analyse_isi_trend: alert fires below threshold
# ---------------------------------------------------------------------------


def test_t87_tife_19_isi_trend_alert():
    """T87-TIFE-19: Sustained ISI < 0.90 over full window → alert=True."""
    history = [0.84, 0.83, 0.82, 0.83, 0.84]
    result = analyse_isi_trend(history, window=5)
    assert result["alert"] is True
    assert result["isi_mean"] < 0.90


# ---------------------------------------------------------------------------
# T87-TIFE-20: Full end-to-end with 3 classes, 10-epoch horizon → VIABLE
# ---------------------------------------------------------------------------


def test_t87_tife_20_full_end_to_end_viable():
    """T87-TIFE-20: Multi-class mutation with redundant caps → TIFE_VIABLE."""
    mutation = TIFEMutationInput(
        mutation_id="mut-e2e-tife-001",
        lineage_digest="e2e" + "b" * 61,
        epoch_id="epoch-e2e-tife-001",
        touched_invariant_classes=("HARD", "CSAP-0", "ACSE-0"),
        fitness_thresholds={"fitness": 0.91, "coverage": 0.93},
        capability_delta={"cap-redundant": -0.1, "cap-growing": 0.3},
        proposed_governance_debt=0.03,
        touches_dead_end_path=False,
    )
    nodes = [
        CapabilityNode("cap-redundant", is_redundant=True, depends_on=()),
        CapabilityNode("cap-growing", is_redundant=False, depends_on=()),
    ]
    graph = CapabilityGraphSnapshot("snap-e2e", tuple(nodes))
    debt_traj = tuple(0.05 for _ in range(DEFAULT_FORECAST_HORIZON))
    vision = VisionProjection(
        projection_id="vision-e2e-001",
        dead_end_paths=frozenset(),
        capability_deltas={"cap-growing": 0.3},
        horizon_epochs=DEFAULT_FORECAST_HORIZON,
        debt_trajectory=debt_traj,
    )
    predecessor = "d" * 64

    result = evaluate_tife_gate_0(mutation, vision, graph, predecessor)

    assert result.outcome == TIFEOutcome.VIABLE
    assert result.failure_codes == []

    rpt = result.report
    assert rpt is not None
    assert rpt.isi == 1.0
    assert rpt.first_violation_epoch is None
    assert rpt.dead_end_detected is False
    assert rpt.capability_regression == []
    assert rpt.predecessor_hash == predecessor
    assert len(rpt.epoch_reports) == DEFAULT_FORECAST_HORIZON
    assert len(rpt.content_hash()) == 64
