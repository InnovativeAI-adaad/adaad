# SPDX-License-Identifier: Apache-2.0
"""Unit tests for GovernanceDebtLedger service layer — ADAAD Phase 31.

Tests the snapshot computation, decay, breach detection, and hash chaining
exposed by GovernanceDebtLedger, as well as the endpoint integration.

Test IDs: T31-01 through T31-06
"""

from __future__ import annotations

import pytest

from runtime.governance.debt_ledger import (
    DEBT_LEDGER_SCHEMA_VERSION,
    DEFAULT_WARNING_WEIGHTS,
    GovernanceDebtLedger,
    GovernanceDebtSnapshot,
)


# ---------------------------------------------------------------------------
# T31-01 — Zero-state snapshot
# ---------------------------------------------------------------------------

class TestZeroState:
    def test_T31_01_01_no_warnings_zero_debt(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0, warning_verdicts=[]
        )
        assert snap.compound_debt_score == pytest.approx(0.0)

    def test_T31_01_02_threshold_not_breached_at_zero(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0, warning_verdicts=[]
        )
        assert snap.threshold_breached is False

    def test_T31_01_03_snapshot_hash_is_sha256_prefixed(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0, warning_verdicts=[]
        )
        assert snap.snapshot_hash.startswith("sha256:")

    def test_T31_01_04_schema_version(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0, warning_verdicts=[]
        )
        assert snap.schema_version == DEBT_LEDGER_SCHEMA_VERSION == "1.0"

    def test_T31_01_05_last_snapshot_none_before_first_epoch(self):
        assert GovernanceDebtLedger().last_snapshot is None


# ---------------------------------------------------------------------------
# T31-02 — Warning accumulation
# ---------------------------------------------------------------------------

class TestAccumulation:
    def test_T31_02_01_single_warning_weighted(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1,
            warning_verdicts=[{"rule": "max_mutation_rate"}],
        )
        # Default weight for max_mutation_rate = 1.25
        assert snap.warning_weighted_sum == pytest.approx(1.25)
        assert snap.compound_debt_score == pytest.approx(1.25)

    def test_T31_02_02_unknown_rule_uses_default_weight_1(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1,
            warning_verdicts=[{"rule": "unknown_rule_xyz"}],
        )
        assert snap.warning_weighted_sum == pytest.approx(1.0)

    def test_T31_02_03_multiple_warnings_summed(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1,
            warning_verdicts=[
                {"rule": "max_mutation_rate"},    # 1.25
                {"rule": "import_smoke_test"},    # 1.0
            ],
        )
        assert snap.warning_weighted_sum == pytest.approx(2.25)

    def test_T31_02_04_warning_count_correct(self):
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1,
            warning_verdicts=[{"rule": "a"}, {"rule": "b"}, {"rule": "c"}],
        )
        assert snap.warning_count == 3


# ---------------------------------------------------------------------------
# T31-03 — Decay
# ---------------------------------------------------------------------------

class TestDecay:
    def test_T31_03_01_debt_decays_across_epochs(self):
        ledger = GovernanceDebtLedger(decay_per_epoch=0.9)
        snap1 = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0,
            warning_verdicts=[{"rule": "max_mutation_rate"}],  # 1.25
        )
        snap2 = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1, warning_verdicts=[]
        )
        expected_decayed = round(1.25 * 0.9, 6)
        assert snap2.decayed_prior_debt == pytest.approx(expected_decayed)
        assert snap2.compound_debt_score == pytest.approx(expected_decayed)

    def test_T31_03_02_multi_epoch_gap_applies_compounded_decay(self):
        ledger = GovernanceDebtLedger(decay_per_epoch=0.9)
        ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0,
            warning_verdicts=[{"rule": "import_smoke_test"}],  # 1.0
        )
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-5", epoch_index=5, warning_verdicts=[]
        )
        # 5 epochs decay: 1.0 * 0.9^5
        expected = round(1.0 * (0.9 ** 5), 6)
        assert snap.decayed_prior_debt == pytest.approx(expected, abs=1e-5)
        assert snap.applied_decay_epochs == 5

    def test_T31_03_03_zero_decay_retains_full_debt(self):
        ledger = GovernanceDebtLedger(decay_per_epoch=0.0)
        ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0,
            warning_verdicts=[{"rule": "import_smoke_test"}],
        )
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1, warning_verdicts=[]
        )
        assert snap.decayed_prior_debt == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T31-04 — Breach detection
# ---------------------------------------------------------------------------

class TestBreachDetection:
    def test_T31_04_01_breach_at_threshold(self):
        ledger = GovernanceDebtLedger(breach_threshold=2.0)
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1,
            warning_verdicts=[
                {"rule": "max_mutation_rate"},    # 1.25
                {"rule": "import_smoke_test"},    # 1.0 → total 2.25 ≥ 2.0
            ],
        )
        assert snap.threshold_breached is True

    def test_T31_04_02_no_breach_below_threshold(self):
        ledger = GovernanceDebtLedger(breach_threshold=5.0)
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1,
            warning_verdicts=[{"rule": "import_smoke_test"}],  # 1.0 < 5.0
        )
        assert snap.threshold_breached is False

    def test_T31_04_03_breach_threshold_stored_in_snapshot(self):
        ledger = GovernanceDebtLedger(breach_threshold=4.5)
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1, warning_verdicts=[]
        )
        assert snap.breach_threshold == pytest.approx(4.5)


# ---------------------------------------------------------------------------
# T31-05 — Hash chaining
# ---------------------------------------------------------------------------

class TestHashChaining:
    def test_T31_05_01_prev_hash_is_zero_hash_for_first(self):
        from runtime.governance.foundation import ZERO_HASH
        ledger = GovernanceDebtLedger()
        snap = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0, warning_verdicts=[]
        )
        assert snap.prev_snapshot_hash == ZERO_HASH

    def test_T31_05_02_second_snapshot_prev_matches_first_hash(self):
        ledger = GovernanceDebtLedger()
        snap1 = ledger.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0, warning_verdicts=[]
        )
        snap2 = ledger.accumulate_epoch_verdicts(
            epoch_id="e-1", epoch_index=1, warning_verdicts=[]
        )
        assert snap2.prev_snapshot_hash == snap1.snapshot_hash

    def test_T31_05_03_identical_inputs_identical_hash(self):
        ledger1 = GovernanceDebtLedger()
        ledger2 = GovernanceDebtLedger()
        snap1 = ledger1.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0,
            warning_verdicts=[{"rule": "import_smoke_test"}],
        )
        snap2 = ledger2.accumulate_epoch_verdicts(
            epoch_id="e-0", epoch_index=0,
            warning_verdicts=[{"rule": "import_smoke_test"}],
        )
        assert snap1.snapshot_hash == snap2.snapshot_hash


# ---------------------------------------------------------------------------
# T31-06 — Default warning weights
# ---------------------------------------------------------------------------

class TestDefaultWeights:
    def test_T31_06_01_all_expected_rules_present(self):
        for rule in (
            "max_mutation_rate", "import_smoke_test", "coverage_regression",
            "resource_bounds", "entropy_budget_limit", "governance_drift_detected",
        ):
            assert rule in DEFAULT_WARNING_WEIGHTS

    def test_T31_06_02_entropy_budget_highest_weight(self):
        assert DEFAULT_WARNING_WEIGHTS["entropy_budget_limit"] == pytest.approx(1.5)

    def test_T31_06_03_resource_bounds_lowest_weight(self):
        assert DEFAULT_WARNING_WEIGHTS["resource_bounds"] == pytest.approx(0.75)
