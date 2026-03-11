# SPDX-License-Identifier: Apache-2.0
"""Tests for AdmissionRateTracker — ADAAD Phase 26.

Test IDs: T26-01..26
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.admission_tracker import (
    TRACKER_VERSION,
    AdmissionRateTracker,
    AdmissionRateReport,
)


@pytest.fixture
def tracker() -> AdmissionRateTracker:
    return AdmissionRateTracker()


# ---------------------------------------------------------------------------
# T26-01..04 — Empty tracker defaults
# ---------------------------------------------------------------------------

def test_empty_score_is_one(tracker):                          # T26-01
    assert tracker.admission_rate_score() == 1.0


def test_empty_report_defaults(tracker):                       # T26-02
    r = tracker.generate_report()
    assert r.admitted_count == 0
    assert r.total_count == 0
    assert r.epochs_in_window == 0
    assert r.admission_rate_score == 1.0


def test_empty_digest_present(tracker):                        # T26-03
    r = tracker.generate_report()
    assert r.report_digest.startswith("sha256:")


def test_empty_tracker_version(tracker):                       # T26-04
    r = tracker.generate_report()
    assert r.tracker_version == TRACKER_VERSION == "26.0"


# ---------------------------------------------------------------------------
# T26-05..10 — Single epoch admission rate
# ---------------------------------------------------------------------------

def test_all_admitted(tracker):                                # T26-05
    for _ in range(5):
        tracker.record_decision(epoch_id="e1", admitted=True)
    r = tracker.generate_report()
    assert r.admission_rate_score == pytest.approx(1.0)
    assert r.admitted_count == 5
    assert r.total_count == 5


def test_all_deferred(tracker):                                # T26-06
    for _ in range(4):
        tracker.record_decision(epoch_id="e1", admitted=False)
    r = tracker.generate_report()
    assert r.admission_rate_score == pytest.approx(0.0)
    assert r.admitted_count == 0
    assert r.total_count == 4


def test_mixed_rate(tracker):                                  # T26-07
    tracker.record_decision(epoch_id="e1", admitted=True)
    tracker.record_decision(epoch_id="e1", admitted=True)
    tracker.record_decision(epoch_id="e1", admitted=False)
    tracker.record_decision(epoch_id="e1", admitted=False)
    r = tracker.generate_report()
    assert r.admission_rate_score == pytest.approx(0.5)


def test_single_admitted(tracker):                             # T26-08
    tracker.record_decision(epoch_id="e1", admitted=True)
    assert tracker.admission_rate_score() == pytest.approx(1.0)


def test_single_deferred(tracker):                             # T26-09
    tracker.record_decision(epoch_id="e1", admitted=False)
    assert tracker.admission_rate_score() == pytest.approx(0.0)


def test_epochs_in_window_single(tracker):                     # T26-10
    for i in range(3):
        tracker.record_decision(epoch_id="e1", admitted=True)
    r = tracker.generate_report()
    assert r.epochs_in_window == 1


# ---------------------------------------------------------------------------
# T26-11..16 — Rolling window across epochs
# ---------------------------------------------------------------------------

def test_multiple_epochs_window(tracker):                      # T26-11
    for eid in ["e1", "e2", "e3"]:
        tracker.record_decision(epoch_id=eid, admitted=True)
    r = tracker.generate_report()
    assert r.epochs_in_window == 3
    assert r.total_count == 3


def test_window_max_epochs_respected():                        # T26-12
    t = AdmissionRateTracker(max_epochs=3)
    for eid in ["e1", "e2", "e3", "e4", "e5"]:
        t.record_decision(epoch_id=eid, admitted=False)
    r = t.generate_report()
    assert r.epochs_in_window <= 3


def test_old_epoch_evicted():                                  # T26-13
    t = AdmissionRateTracker(max_epochs=2)
    # e1: 1 admitted, e2: 1 admitted, e3: 1 deferred — e1 evicted
    t.record_decision(epoch_id="e1", admitted=True)
    t.record_decision(epoch_id="e2", admitted=True)
    t.record_decision(epoch_id="e3", admitted=False)
    r = t.generate_report()
    assert r.epochs_in_window == 2
    # window should be e2 (admitted) + e3 (deferred) = 1/2 = 0.5
    assert r.total_count == 2
    assert r.admitted_count == 1


def test_max_epochs_default_is_10(tracker):                    # T26-14
    assert tracker._max_epochs == 10


def test_max_epochs_config():                                  # T26-15
    t = AdmissionRateTracker(max_epochs=5)
    r = t.generate_report()
    assert r.max_epochs == 5


def test_max_epochs_invalid():                                  # T26-16
    with pytest.raises(ValueError, match="max_epochs"):
        AdmissionRateTracker(max_epochs=0)


# ---------------------------------------------------------------------------
# T26-17..22 — Determinism
# ---------------------------------------------------------------------------

def test_digest_deterministic(tracker):                        # T26-17
    tracker.record_decision(epoch_id="e1", admitted=True)
    r1 = tracker.generate_report()
    r2 = tracker.generate_report()
    assert r1.report_digest == r2.report_digest


def test_digest_changes_on_new_decision(tracker):              # T26-18
    r1 = tracker.generate_report()
    tracker.record_decision(epoch_id="e1", admitted=True)
    r2 = tracker.generate_report()
    assert r1.report_digest != r2.report_digest


def test_identical_sequences_identical_digest():               # T26-19
    t1 = AdmissionRateTracker()
    t2 = AdmissionRateTracker()
    for _ in range(3):
        t1.record_decision(epoch_id="e1", admitted=True)
        t2.record_decision(epoch_id="e1", admitted=True)
    assert t1.generate_report().report_digest == t2.generate_report().report_digest


def test_score_clamped_to_range(tracker):                      # T26-20
    """rate derived from counts is always in [0, 1]."""
    for i in range(10):
        tracker.record_decision(epoch_id="e1", admitted=bool(i % 2))
    r = tracker.generate_report()
    assert 0.0 <= r.admission_rate_score <= 1.0


def test_report_is_frozen():                                   # T26-21
    t = AdmissionRateTracker()
    t.record_decision(epoch_id="e1", admitted=True)
    r = t.generate_report()
    with pytest.raises((AttributeError, TypeError)):
        r.admission_rate_score = 0.0  # type: ignore[misc]


def test_generate_report_type(tracker):                        # T26-22
    tracker.record_decision(epoch_id="e1", admitted=True)
    assert isinstance(tracker.generate_report(), AdmissionRateReport)


# ---------------------------------------------------------------------------
# T26-23..26 — GovernanceHealthAggregator integration
# ---------------------------------------------------------------------------

def test_aggregator_accepts_admission_tracker():               # T26-23
    from runtime.governance.health_aggregator import GovernanceHealthAggregator
    t = AdmissionRateTracker()
    agg = GovernanceHealthAggregator(admission_tracker=t)
    snap = agg.compute("epoch-test")
    assert "admission_rate_score" in snap.signal_breakdown


def test_aggregator_no_tracker_defaults_to_1():                # T26-24
    from runtime.governance.health_aggregator import GovernanceHealthAggregator
    agg = GovernanceHealthAggregator()
    snap = agg.compute("epoch-test")
    assert snap.signal_breakdown["admission_rate_score"] == pytest.approx(1.0)


def test_aggregator_admission_report_populated():              # T26-25
    from runtime.governance.health_aggregator import GovernanceHealthAggregator
    t = AdmissionRateTracker()
    t.record_decision(epoch_id="e1", admitted=True)
    t.record_decision(epoch_id="e1", admitted=False)
    agg = GovernanceHealthAggregator(admission_tracker=t)
    snap = agg.compute("e1")
    assert snap.admission_rate_report is not None
    assert snap.admission_rate_report["admission_rate_score"] == pytest.approx(0.5)


def test_aggregator_weights_sum_to_one():                      # T26-26
    from runtime.governance.health_aggregator import SIGNAL_WEIGHTS
    assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9
    assert "admission_rate_score" in SIGNAL_WEIGHTS
