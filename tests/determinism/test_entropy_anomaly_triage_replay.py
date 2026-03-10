# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.entropy_policy import EntropyPolicy, enforce_entropy_policy
from runtime.governance.foundation import sha256_prefixed_digest


REPLAY_ANOMALY_FIXTURES = [
    # triage_level is now set by EntropyAnomalyTriageThresholds.classify() (Phase 34),
    # which uses utilisation ratios ("ok"/"warning"/"escalate"/"critical") and overrides
    # the old EntropyAnomalyThresholds bit-threshold values ("none"/"monitor"/"investigate"/"block").
    # triage_reason retains the old bit-threshold taxonomy from anomaly_thresholds.classify().
    {
        "fixture_id": "none",
        "mutation_bits": 8,
        "declared_bits": 8,
        "observed_bits": 0,
        "epoch_bits": 8,
        "expected_passed": True,
        "expected_triage_level": "ok",         # ratio 0.50 < warning_ratio 0.70
        "expected_triage_reason": "anomaly_not_detected",
        "expected_reason": "ok",
    },
    {
        "fixture_id": "monitor",
        "mutation_bits": 9,
        "declared_bits": 8,
        "observed_bits": 1,
        "epoch_bits": 9,
        "expected_passed": True,
        "expected_triage_level": "ok",         # ratio 0.5625 < warning_ratio 0.70
        "expected_triage_reason": "anomaly_observed_bits_monitor_threshold_reached",
        "expected_reason": "ok",
    },
    {
        "fixture_id": "investigate",
        "mutation_bits": 16,
        "declared_bits": 8,
        "observed_bits": 8,
        "epoch_bits": 16,
        "expected_passed": True,
        "expected_triage_level": "critical",   # ratio 1.00 >= critical_ratio 1.00
        "expected_triage_reason": "anomaly_observed_bits_investigate_threshold_reached",
        "expected_reason": "ok",
    },
    {
        "fixture_id": "block_fail_closed",
        "mutation_bits": 32,
        "declared_bits": 8,
        "observed_bits": 24,
        "epoch_bits": 32,
        "expected_passed": False,
        "expected_triage_level": "critical",   # ratio 2.00 >= critical_ratio 1.00
        "expected_triage_reason": "anomaly_observed_bits_block_threshold_reached",
        "expected_reason": "entropy_ceiling_exceeded",
        "expected_violation_reason": "entropy_budget_exceeded",
    },
]


def _run_fixture(fixture: dict[str, object]) -> dict[str, object]:
    policy = EntropyPolicy("entropy-triage-replay", per_mutation_ceiling_bits=16, per_epoch_ceiling_bits=64)
    return enforce_entropy_policy(
        policy=policy,
        mutation_bits=int(fixture["mutation_bits"]),
        declared_bits=int(fixture["declared_bits"]),
        observed_bits=int(fixture["observed_bits"]),
        epoch_bits=int(fixture["epoch_bits"]),
    )


def test_entropy_triage_fixtures_are_replay_deterministic() -> None:
    for fixture in REPLAY_ANOMALY_FIXTURES:
        first = _run_fixture(fixture)
        second = _run_fixture(fixture)
        assert first == second
        assert first["passed"] is fixture["expected_passed"]
        assert first["triage_level"] == fixture["expected_triage_level"]
        assert first["triage_reason"] == fixture["expected_triage_reason"]
        assert first["reason"] == fixture["expected_reason"]
        if not bool(fixture["expected_passed"]):
            assert first["violation_reason"] == fixture["expected_violation_reason"]


def test_entropy_triage_fixture_digest_is_stable_for_replay_audits() -> None:
    replay_results = []
    for fixture in REPLAY_ANOMALY_FIXTURES:
        result = _run_fixture(fixture)
        replay_results.append(
            {
                "fixture_id": fixture["fixture_id"],
                "passed": result["passed"],
                "reason": result["reason"],
                "triage_level": result["triage_level"],
                "triage_reason": result["triage_reason"],
            }
        )

    digest_a = sha256_prefixed_digest(replay_results)
    digest_b = sha256_prefixed_digest(replay_results)
    assert digest_a == digest_b
