# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.entropy_policy import EntropyAnomalyTriageThresholds, EntropyPolicy


def test_entropy_triage_classifies_warning_escalate_critical_deterministically() -> None:
    policy = EntropyPolicy(
        "p-triage",
        per_mutation_ceiling_bits=100,
        per_epoch_ceiling_bits=200,
        anomaly_triage=EntropyAnomalyTriageThresholds(warning_ratio=0.70, escalate_ratio=0.90, critical_ratio=1.00),
    )

    warning = policy.enforce(mutation_bits=70, declared_bits=70, observed_bits=0, epoch_bits=100)
    escalate = policy.enforce(mutation_bits=90, declared_bits=90, observed_bits=0, epoch_bits=100)

    assert warning["triage_level"] == "warning"
    assert escalate["triage_level"] == "escalate"

    # Equality at the configured critical threshold is critical by design.
    critical = policy.enforce(mutation_bits=100, declared_bits=100, observed_bits=0, epoch_bits=100)
    assert critical["triage_level"] == "critical"


def test_entropy_triage_disabled_when_policy_disabled() -> None:
    policy = EntropyPolicy("p-disabled-triage", per_mutation_ceiling_bits=0, per_epoch_ceiling_bits=0)

    verdict = policy.enforce(mutation_bits=10_000, declared_bits=5_000, observed_bits=5_000, epoch_bits=10_000)

    assert verdict["passed"] is True
    assert verdict["reason"] == "entropy_policy_disabled"
    assert verdict["triage_level"] == "disabled"


def test_entropy_triage_uses_highest_utilization_ratio() -> None:
    policy = EntropyPolicy(
        "p-ratio",
        per_mutation_ceiling_bits=100,
        per_epoch_ceiling_bits=1000,
        anomaly_triage=EntropyAnomalyTriageThresholds(warning_ratio=0.5, escalate_ratio=0.8, critical_ratio=0.95),
    )

    verdict = policy.enforce(mutation_bits=85, declared_bits=85, observed_bits=0, epoch_bits=100)

    assert verdict["triage_level"] == "escalate"
    assert verdict["mutation_utilization_ratio"] == 0.85
    assert verdict["epoch_utilization_ratio"] == 0.1
