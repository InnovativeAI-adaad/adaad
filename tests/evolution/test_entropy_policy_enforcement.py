# SPDX-License-Identifier: Apache-2.0

import pytest

from runtime.evolution.entropy_policy import (
    ENTROPY_REASON_TAXONOMY,
    EntropyAnomalyThresholds,
    EntropyPolicy,
    EntropyPolicyViolation,
)


def test_entropy_policy_enforce_passes_at_limit() -> None:
    policy = EntropyPolicy("p-at-limit", per_mutation_ceiling_bits=16, per_epoch_ceiling_bits=32)

    verdict = policy.enforce(mutation_bits=16, declared_bits=12, observed_bits=4, epoch_bits=32)

    assert verdict["passed"] is True
    assert verdict["reason"] == "ok"
    assert verdict["declared_bits"] == 12
    assert verdict["observed_bits"] == 4
    assert verdict["mutation_bits"] == 16
    assert verdict["epoch_bits"] == 32


def test_entropy_policy_enforce_raises_on_over_limit_with_deterministic_detail() -> None:
    policy = EntropyPolicy("p-over", per_mutation_ceiling_bits=15, per_epoch_ceiling_bits=30)

    with pytest.raises(EntropyPolicyViolation) as exc_info:
        policy.enforce(mutation_bits=16, declared_bits=12, observed_bits=4, epoch_bits=31)

    violation = exc_info.value
    assert violation.reason == "mutation_and_epoch_entropy_budget_exceeded"
    assert violation.detail["policy_id"] == "p-over"
    assert violation.detail["policy_hash"] == policy.policy_hash
    assert violation.detail["declared_bits"] == 12
    assert violation.detail["observed_bits"] == 4
    assert violation.detail["mutation_bits"] == 16
    assert violation.detail["epoch_bits"] == 31


def test_entropy_policy_enforce_treats_non_positive_ceiling_as_disabled() -> None:
    policy = EntropyPolicy("p-disabled", per_mutation_ceiling_bits=0, per_epoch_ceiling_bits=0)

    verdict = policy.enforce(mutation_bits=999, declared_bits=500, observed_bits=499, epoch_bits=2048)

    assert verdict["passed"] is True
    assert verdict["reason"] == "entropy_policy_disabled"
    assert verdict["policy_id"] == "p-disabled"


def test_entropy_policy_enforce_defaults_declared_bits_to_mutation_bits_when_omitted() -> None:
    policy = EntropyPolicy("p-default-declared", per_mutation_ceiling_bits=20, per_epoch_ceiling_bits=40)

    verdict = policy.enforce(mutation_bits=10, observed_bits=3, epoch_bits=13)

    assert verdict["passed"] is True
    assert verdict["declared_bits"] == 10
    assert verdict["observed_bits"] == 3
    assert verdict["mutation_bits"] == 13


def test_entropy_anomaly_thresholds_classify_deterministically() -> None:
    thresholds = EntropyAnomalyThresholds(monitor_bits=1, investigate_bits=5, block_bits=9)

    assert thresholds.classify(observed_bits=0) == {"triage_level": "none", "triage_reason": "anomaly_not_detected"}
    assert thresholds.classify(observed_bits=1) == {
        "triage_level": "monitor",
        "triage_reason": "anomaly_observed_bits_monitor_threshold_reached",
    }
    assert thresholds.classify(observed_bits=5) == {
        "triage_level": "investigate",
        "triage_reason": "anomaly_observed_bits_investigate_threshold_reached",
    }
    assert thresholds.classify(observed_bits=9) == {
        "triage_level": "block",
        "triage_reason": "anomaly_observed_bits_block_threshold_reached",
    }


def test_entropy_reason_taxonomy_contains_policy_and_triage_reasons() -> None:
    expected = {
        "ok",
        "entropy_policy_disabled",
        "entropy_budget_exceeded",
        "epoch_entropy_budget_exceeded",
        "mutation_and_epoch_entropy_budget_exceeded",
        "anomaly_not_detected",
        "anomaly_observed_bits_monitor_threshold_reached",
        "anomaly_observed_bits_investigate_threshold_reached",
        "anomaly_observed_bits_block_threshold_reached",
    }

    assert expected.issubset(ENTROPY_REASON_TAXONOMY)
