# SPDX-License-Identifier: Apache-2.0
"""Tests for GovernanceHealthAggregator — ADAAD Phase 8, PR-8-01.

Coverage:
  T8-01-01..05  Signal computation correctness per input.
  T8-01-06..10  Weight bound invariants.
  T8-01-11..15  GOVERNANCE_HEALTH_DEGRADED event emission when h < 0.60.
  T8-01-16..20  Determinism — identical inputs → identical h.
  T8-01-21..25  Edge cases: None dependencies, single-node federation, empty ledger.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from runtime.governance.health_aggregator import (
    HEALTH_DEGRADED_THRESHOLD,
    JOURNAL_EVENT_DEGRADED,
    JOURNAL_EVENT_SNAPSHOT,
    SIGNAL_WEIGHTS,
    GovernanceHealthAggregator,
    HealthSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reputation_ledger(scores: list[float]) -> MagicMock:
    ledger = MagicMock()

    class _Entry:
        def __init__(self, s):
            self.composite_score = s
            self.epoch_id = None

    ledger.get_all_entries.return_value = [_Entry(s) for s in scores]
    return ledger


def _make_amendment_engine(pending_count: int) -> MagicMock:
    engine = MagicMock()
    engine.list_pending.return_value = [MagicMock()] * pending_count
    return engine


def _make_evidence_matrix(divergence_count: int) -> MagicMock:
    matrix = MagicMock()
    matrix.divergence_count = divergence_count
    return matrix


def _make_epoch_telemetry(healthy: int, warning: int) -> MagicMock:
    telemetry = MagicMock()
    indicators = {}
    for i in range(healthy):
        indicators[f"h{i}"] = {"status": "healthy", "value": 0.5}
    for i in range(warning):
        indicators[f"w{i}"] = {"status": "warning", "value": 0.1}
    telemetry.health_indicators.return_value = indicators
    return telemetry


def _agg(**kwargs) -> GovernanceHealthAggregator:
    emitted = []
    return GovernanceHealthAggregator(
        journal_emit=lambda t, p: emitted.append((t, p)),
        **kwargs,
    ), emitted


# ---------------------------------------------------------------------------
# T8-01-01..05  Signal computation correctness
# ---------------------------------------------------------------------------

def test_T8_01_01_perfect_reputation_score():
    agg, _ = _agg(reviewer_reputation_ledger=_make_reputation_ledger([1.0, 1.0, 1.0]))
    snap = agg.compute("epoch-1")
    assert snap.signal_breakdown["avg_reviewer_reputation"] == pytest.approx(1.0)


def test_T8_01_02_zero_pending_amendments_gives_full_pass_rate():
    agg, _ = _agg(roadmap_amendment_engine=_make_amendment_engine(0))
    snap = agg.compute("epoch-1")
    assert snap.signal_breakdown["amendment_gate_pass_rate"] == pytest.approx(1.0)


def test_T8_01_03_pending_amendments_degrade_pass_rate():
    agg, _ = _agg(roadmap_amendment_engine=_make_amendment_engine(3))
    snap = agg.compute("epoch-1")
    # 1.0 - (3 * 0.20) = 0.40
    assert snap.signal_breakdown["amendment_gate_pass_rate"] == pytest.approx(0.40)


def test_T8_01_04_zero_federation_divergence_gives_clean_signal():
    agg, _ = _agg(federated_evidence_matrix=_make_evidence_matrix(0))
    snap = agg.compute("epoch-1")
    assert snap.signal_breakdown["federation_divergence_clean"] == pytest.approx(1.0)


def test_T8_01_05_nonzero_federation_divergence_gives_dirty_signal():
    agg, _ = _agg(federated_evidence_matrix=_make_evidence_matrix(2))
    snap = agg.compute("epoch-1")
    assert snap.signal_breakdown["federation_divergence_clean"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T8-01-06..10  Weight bound invariants
# ---------------------------------------------------------------------------

def test_T8_01_06_all_signals_full_gives_h_1():
    agg, _ = _agg(
        reviewer_reputation_ledger=_make_reputation_ledger([1.0]),
        roadmap_amendment_engine=_make_amendment_engine(0),
        federated_evidence_matrix=_make_evidence_matrix(0),
        epoch_telemetry=_make_epoch_telemetry(healthy=4, warning=0),
    )
    snap = agg.compute("epoch-1")
    assert snap.health_score == pytest.approx(1.0)
    assert not snap.degraded


def test_T8_01_07_all_signals_zero_gives_h_0():
    # Phase 25-27 added routing_health_score (0.13) and admission_rate_score (0.10)
    # which both default to 1.0 (fail-safe) when no tracker wired.
    # Expected h = 0*0.22 + 0*0.20 + 0*0.20 + 0*0.15 + 1.0*0.13 + 1.0*0.10 = 0.23
    agg, _ = _agg(
        reviewer_reputation_ledger=_make_reputation_ledger([0.0]),
        roadmap_amendment_engine=_make_amendment_engine(5),
        federated_evidence_matrix=_make_evidence_matrix(1),
        epoch_telemetry=_make_epoch_telemetry(healthy=0, warning=4),
    )
    snap = agg.compute("epoch-1")
    assert snap.health_score == pytest.approx(0.23)
    assert snap.degraded


def test_T8_01_08_weights_sum_to_1():
    assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9


def test_T8_01_09_single_signal_cannot_drive_h_to_1_alone():
    # After Phase 25-27 weight rebalance (6 signals):
    # rep=1.0*0.22 + fed(single-node)=1.0*0.20 + routing(fail-safe)=1.0*0.13 + admission(fail-safe)=1.0*0.10
    # amendment=None→0.0*0.20 + epoch=None→0.0*0.15 => h = 0.65
    agg, _ = _agg(reviewer_reputation_ledger=_make_reputation_ledger([1.0]))
    snap = agg.compute("epoch-1")
    assert snap.health_score == pytest.approx(0.65)
    assert snap.health_score < 1.0


def test_T8_01_10_weight_validation_rejects_bad_sum():
    with pytest.raises(ValueError, match="weights must sum to 1.0"):
        GovernanceHealthAggregator(weights={"a": 0.5, "b": 0.3})


# ---------------------------------------------------------------------------
# T8-01-11..15  GOVERNANCE_HEALTH_DEGRADED event emission
# ---------------------------------------------------------------------------

def test_T8_01_11_degraded_event_emitted_when_h_below_threshold():
    emitted = []
    agg = GovernanceHealthAggregator(
        reviewer_reputation_ledger=_make_reputation_ledger([0.1]),
        journal_emit=lambda t, p: emitted.append((t, p)),
    )
    snap = agg.compute("epoch-x")
    assert snap.degraded
    types = [e[0] for e in emitted]
    assert JOURNAL_EVENT_DEGRADED in types


def test_T8_01_12_degraded_event_not_emitted_when_h_above_threshold():
    emitted = []
    agg = GovernanceHealthAggregator(
        reviewer_reputation_ledger=_make_reputation_ledger([1.0]),
        roadmap_amendment_engine=_make_amendment_engine(0),
        federated_evidence_matrix=_make_evidence_matrix(0),
        epoch_telemetry=_make_epoch_telemetry(healthy=4, warning=0),
        journal_emit=lambda t, p: emitted.append((t, p)),
    )
    snap = agg.compute("epoch-x")
    assert not snap.degraded
    types = [e[0] for e in emitted]
    assert JOURNAL_EVENT_DEGRADED not in types


def test_T8_01_13_snapshot_event_always_emitted():
    emitted = []
    agg = GovernanceHealthAggregator(journal_emit=lambda t, p: emitted.append((t, p)))
    agg.compute("epoch-y")
    types = [e[0] for e in emitted]
    assert JOURNAL_EVENT_SNAPSHOT in types


def test_T8_01_14_degraded_event_contains_signal_breakdown():
    emitted = []
    agg = GovernanceHealthAggregator(
        reviewer_reputation_ledger=_make_reputation_ledger([0.0]),
        journal_emit=lambda t, p: emitted.append((t, p)),
    )
    agg.compute("epoch-z")
    degraded_payloads = [p for t, p in emitted if t == JOURNAL_EVENT_DEGRADED]
    assert degraded_payloads
    assert "signal_breakdown" in degraded_payloads[0]


def test_T8_01_15_snapshot_carries_weight_digest():
    emitted = []
    agg = GovernanceHealthAggregator(journal_emit=lambda t, p: emitted.append((t, p)))
    agg.compute("e1")
    snap_payloads = [p for t, p in emitted if t == JOURNAL_EVENT_SNAPSHOT]
    assert snap_payloads
    assert snap_payloads[0]["weight_snapshot_digest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# T8-01-16..20  Determinism
# ---------------------------------------------------------------------------

def test_T8_01_16_identical_inputs_produce_identical_score():
    def _make():
        return GovernanceHealthAggregator(
            reviewer_reputation_ledger=_make_reputation_ledger([0.75, 0.80]),
            roadmap_amendment_engine=_make_amendment_engine(1),
            federated_evidence_matrix=_make_evidence_matrix(0),
            epoch_telemetry=_make_epoch_telemetry(healthy=3, warning=1),
            journal_emit=lambda *a: None,
        )

    assert _make().compute("ep-42").health_score == _make().compute("ep-42").health_score


def test_T8_01_17_identical_inputs_produce_identical_breakdown():
    def _snap():
        return GovernanceHealthAggregator(
            reviewer_reputation_ledger=_make_reputation_ledger([0.60]),
            journal_emit=lambda *a: None,
        ).compute("ep-99")

    assert _snap().signal_breakdown == _snap().signal_breakdown


def test_T8_01_18_weight_digest_is_deterministic():
    a1 = GovernanceHealthAggregator(journal_emit=lambda *a: None)
    a2 = GovernanceHealthAggregator(journal_emit=lambda *a: None)
    assert a1._weight_digest == a2._weight_digest


def test_T8_01_19_different_epoch_ids_do_not_affect_score_for_same_data():
    def _snap(eid):
        return GovernanceHealthAggregator(
            reviewer_reputation_ledger=_make_reputation_ledger([0.50]),
            journal_emit=lambda *a: None,
        ).compute(eid)

    assert _snap("epoch-1").health_score == _snap("epoch-2").health_score


def test_T8_01_20_snapshot_constitution_version_matches_runtime():
    from runtime.constitution import CONSTITUTION_VERSION
    agg = GovernanceHealthAggregator(journal_emit=lambda *a: None)
    snap = agg.compute("e1")
    assert snap.constitution_version == CONSTITUTION_VERSION


# ---------------------------------------------------------------------------
# T8-01-21..25  Edge cases
# ---------------------------------------------------------------------------

def test_T8_01_21_all_none_dependencies_returns_h_near_zero():
    agg, _ = _agg()
    snap = agg.compute("epoch-none")
    # After Phase 25-27 rebalance: fed(single-node)=1.0*0.20 + routing(fail-safe)=1.0*0.13 + admission(fail-safe)=1.0*0.10 = 0.43
    # rep=None->0.0, amendment=None->0.0, epoch=None->0.0
    assert snap.health_score == pytest.approx(0.43)


def test_T8_01_22_single_node_federation_defaults_to_clean():
    agg, _ = _agg(federated_evidence_matrix=None)
    snap = agg.compute("epoch-sn")
    assert snap.signal_breakdown["federation_divergence_clean"] == pytest.approx(1.0)


def test_T8_01_23_empty_reputation_ledger_returns_zero():
    agg, _ = _agg(reviewer_reputation_ledger=_make_reputation_ledger([]))
    snap = agg.compute("epoch-empty")
    assert snap.signal_breakdown["avg_reviewer_reputation"] == pytest.approx(0.0)


def test_T8_01_24_five_or_more_pending_amendments_clamps_to_zero():
    agg, _ = _agg(roadmap_amendment_engine=_make_amendment_engine(5))
    snap = agg.compute("epoch-5")
    assert snap.signal_breakdown["amendment_gate_pass_rate"] == pytest.approx(0.0)


def test_T8_01_25_snapshot_dataclass_serialises_to_dict():
    agg, _ = _agg()
    snap = agg.compute("ep-serial")
    d = snap.as_dict()
    assert d["epoch_id"] == "ep-serial"
    assert "health_score" in d
    assert "signal_breakdown" in d
    assert json.dumps(d)  # must be JSON-serialisable
