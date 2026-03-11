# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.debt_ledger import GovernanceDebtLedger


def test_accumulation_applies_per_rule_weighting() -> None:
    ledger = GovernanceDebtLedger(warning_weights={"max_mutation_rate": 2.0, "import_smoke_test": 0.5}, decay_per_epoch=0.9, breach_threshold=10.0)

    snapshot = ledger.accumulate_epoch_verdicts(
        epoch_id="epoch-1",
        epoch_index=1,
        warning_verdicts=[{"rule": "max_mutation_rate"}, {"rule": "import_smoke_test"}],
    )

    assert snapshot.warning_weighted_sum == 2.5
    assert snapshot.compound_debt_score == 2.5
    assert snapshot.warning_count == 2


def test_decay_is_deterministic_by_epoch_count() -> None:
    ledger = GovernanceDebtLedger(warning_weights={"x": 2.0}, decay_per_epoch=0.5, breach_threshold=10.0)
    first = ledger.accumulate_epoch_verdicts(epoch_id="epoch-1", epoch_index=1, warning_verdicts=[{"rule": "x"}])
    second = ledger.accumulate_epoch_verdicts(epoch_id="epoch-3", epoch_index=3, warning_verdicts=[])

    assert first.compound_debt_score == 2.0
    assert second.applied_decay_epochs == 2
    assert second.decayed_prior_debt == 0.5
    assert second.compound_debt_score == 0.5


def test_threshold_breach_signaling() -> None:
    ledger = GovernanceDebtLedger(warning_weights={"x": 3.0}, decay_per_epoch=1.0, breach_threshold=2.0)
    snapshot = ledger.accumulate_epoch_verdicts(epoch_id="epoch-2", epoch_index=2, warning_verdicts=[{"rule": "x"}])
    assert snapshot.threshold_breached is True


def test_hash_chain_continuity() -> None:
    ledger = GovernanceDebtLedger(warning_weights={"x": 1.0}, decay_per_epoch=1.0, breach_threshold=100.0)
    first = ledger.accumulate_epoch_verdicts(epoch_id="epoch-1", epoch_index=1, warning_verdicts=[{"rule": "x"}])
    second = ledger.accumulate_epoch_verdicts(epoch_id="epoch-2", epoch_index=2, warning_verdicts=[{"rule": "x"}])

    assert first.snapshot_hash.startswith("sha256:")
    assert second.prev_snapshot_hash == first.snapshot_hash


def test_zero_warning_behavior() -> None:
    ledger = GovernanceDebtLedger(decay_per_epoch=1.0, breach_threshold=1.0)
    snapshot = ledger.accumulate_epoch_verdicts(epoch_id="epoch-0", epoch_index=0, warning_verdicts=[])

    assert snapshot.warning_count == 0
    assert snapshot.warning_weighted_sum == 0.0
    assert snapshot.compound_debt_score == 0.0
    assert snapshot.threshold_breached is False
