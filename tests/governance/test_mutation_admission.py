# SPDX-License-Identifier: Apache-2.0
"""Tests for MutationAdmissionController — ADAAD Phase 25.

Test IDs: T25-01..32
"""

from __future__ import annotations

import hashlib
import json

import pytest

from runtime.governance.mutation_admission import (
    AMBER_FLOOR,
    CONTROLLER_VERSION,
    GREEN_FLOOR,
    RED_FLOOR,
    MutationAdmissionController,
    AdmissionDecision,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctrl() -> MutationAdmissionController:
    return MutationAdmissionController()


# ---------------------------------------------------------------------------
# T25-01..06 — GREEN band (h >= 0.80)
# ---------------------------------------------------------------------------

def test_green_low_risk_admitted(ctrl):                      # T25-01
    d = ctrl.evaluate(health_score=1.0, mutation_risk_score=0.10)
    assert d.admission_band == "green"
    assert d.admitted is True


def test_green_high_risk_admitted(ctrl):                     # T25-02
    d = ctrl.evaluate(health_score=0.90, mutation_risk_score=0.99)
    assert d.admission_band == "green"
    assert d.admitted is True


def test_green_admits_all_flag(ctrl):                        # T25-03
    d = ctrl.evaluate(health_score=0.80, mutation_risk_score=0.50)
    assert d.admits_all is True


def test_green_epoch_not_paused(ctrl):                       # T25-04
    d = ctrl.evaluate(health_score=0.95, mutation_risk_score=0.50)
    assert d.epoch_paused is False


def test_green_no_deferral_reason(ctrl):                     # T25-05
    d = ctrl.evaluate(health_score=1.0, mutation_risk_score=0.00)
    assert d.deferral_reason is None


def test_green_boundary(ctrl):                               # T25-06
    d = ctrl.evaluate(health_score=GREEN_FLOOR, mutation_risk_score=0.80)
    assert d.admission_band == "green"
    assert d.admitted is True


# ---------------------------------------------------------------------------
# T25-07..14 — AMBER band (0.60 <= h < 0.80)
# ---------------------------------------------------------------------------

def test_amber_low_risk_admitted(ctrl):                      # T25-07
    d = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.30)
    assert d.admission_band == "amber"
    assert d.admitted is True


def test_amber_high_risk_deferred(ctrl):                     # T25-08
    d = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.60)
    assert d.admission_band == "amber"
    assert d.admitted is False


def test_amber_risk_at_threshold_deferred(ctrl):             # T25-09
    """risk_threshold is exclusive upper bound."""
    d = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.60)
    assert d.admitted is False


def test_amber_risk_below_threshold_admitted(ctrl):          # T25-10
    d = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.5999)
    assert d.admitted is True


def test_amber_admits_all_false(ctrl):                       # T25-11
    d = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.30)
    assert d.admits_all is False


def test_amber_epoch_not_paused(ctrl):                       # T25-12
    d = ctrl.evaluate(health_score=0.65, mutation_risk_score=0.50)
    assert d.epoch_paused is False


def test_amber_deferral_reason_set(ctrl):                    # T25-13
    d = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.80)
    assert d.deferral_reason is not None
    assert "amber" in d.deferral_reason.lower()


def test_amber_boundary(ctrl):                               # T25-14
    d = ctrl.evaluate(health_score=AMBER_FLOOR, mutation_risk_score=0.30)
    assert d.admission_band == "amber"


# ---------------------------------------------------------------------------
# T25-15..21 — RED band (0.40 <= h < 0.60)
# ---------------------------------------------------------------------------

def test_red_low_risk_admitted(ctrl):                        # T25-15
    d = ctrl.evaluate(health_score=0.50, mutation_risk_score=0.20)
    assert d.admission_band == "red"
    assert d.admitted is True


def test_red_medium_risk_deferred(ctrl):                     # T25-16
    d = ctrl.evaluate(health_score=0.50, mutation_risk_score=0.35)
    assert d.admitted is False


def test_red_risk_below_threshold_admitted(ctrl):            # T25-17
    d = ctrl.evaluate(health_score=0.50, mutation_risk_score=0.3499)
    assert d.admitted is True


def test_red_admits_all_false(ctrl):                         # T25-18
    d = ctrl.evaluate(health_score=0.55, mutation_risk_score=0.10)
    assert d.admits_all is False


def test_red_epoch_not_paused(ctrl):                         # T25-19
    d = ctrl.evaluate(health_score=0.55, mutation_risk_score=0.10)
    assert d.epoch_paused is False


def test_red_deferral_reason_set(ctrl):                      # T25-20
    d = ctrl.evaluate(health_score=0.50, mutation_risk_score=0.90)
    assert d.deferral_reason is not None
    assert "red" in d.deferral_reason.lower()


def test_red_boundary(ctrl):                                 # T25-21
    d = ctrl.evaluate(health_score=RED_FLOOR, mutation_risk_score=0.10)
    assert d.admission_band == "red"


# ---------------------------------------------------------------------------
# T25-22..27 — HALT band (h < 0.40)
# ---------------------------------------------------------------------------

def test_halt_no_admission(ctrl):                            # T25-22
    d = ctrl.evaluate(health_score=0.20, mutation_risk_score=0.05)
    assert d.admission_band == "halt"
    assert d.admitted is False


def test_halt_epoch_paused(ctrl):                            # T25-23
    d = ctrl.evaluate(health_score=0.10, mutation_risk_score=0.05)
    assert d.epoch_paused is True


def test_halt_admits_all_false(ctrl):                        # T25-24
    d = ctrl.evaluate(health_score=0.00, mutation_risk_score=0.00)
    assert d.admits_all is False


def test_halt_deferral_reason_set(ctrl):                     # T25-25
    d = ctrl.evaluate(health_score=0.20, mutation_risk_score=0.05)
    assert d.deferral_reason is not None
    assert "halt" in d.deferral_reason.lower() or "catastrophic" in d.deferral_reason.lower()


def test_halt_zero_health(ctrl):                             # T25-26
    d = ctrl.evaluate(health_score=0.00, mutation_risk_score=1.00)
    assert d.epoch_paused is True
    assert d.admitted is False


def test_halt_boundary_exclusive(ctrl):                      # T25-27
    """h=0.40 is RED, not HALT."""
    d = ctrl.evaluate(health_score=0.40, mutation_risk_score=0.10)
    assert d.admission_band == "red"
    assert d.epoch_paused is False


# ---------------------------------------------------------------------------
# T25-28..32 — Structural invariants and determinism
# ---------------------------------------------------------------------------

def test_advisory_only_always_true(ctrl):                    # T25-28
    for h, r in [(1.0, 0.0), (0.70, 0.50), (0.50, 0.50), (0.20, 0.05)]:
        d = ctrl.evaluate(health_score=h, mutation_risk_score=r)
        assert d.advisory_only is True, f"advisory_only must be True for h={h}"


def test_digest_deterministic(ctrl):                         # T25-29
    d1 = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.40)
    d2 = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.40)
    assert d1.decision_digest == d2.decision_digest


def test_digest_changes_on_different_inputs(ctrl):           # T25-30
    d1 = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.40)
    d2 = ctrl.evaluate(health_score=0.70, mutation_risk_score=0.41)
    assert d1.decision_digest != d2.decision_digest


def test_out_of_range_inputs_clamped(ctrl):                  # T25-31
    d_low  = ctrl.evaluate(health_score=-0.5, mutation_risk_score=-1.0)
    d_high = ctrl.evaluate(health_score=2.0,  mutation_risk_score=5.0)
    assert d_low.health_score  == 0.0
    assert d_low.mutation_risk_score  == 0.0
    assert d_high.health_score == 1.0
    assert d_high.mutation_risk_score == 1.0


def test_controller_version(ctrl):                           # T25-32
    d = ctrl.evaluate(health_score=0.90, mutation_risk_score=0.10)
    assert d.controller_version == CONTROLLER_VERSION
    assert d.controller_version == "25.0"
