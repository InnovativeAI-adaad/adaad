# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from runtime import constitution
from tools.simulate_governance_harness import _load_scenarios, run_simulation


def _write_scenarios(path: Path) -> None:
    path.write_text(
        """
{
  "scenarios": [
    {"name": "benign_case", "kind": "benign", "description": "All-valid traffic.", "config": {}},
    {
      "name": "adversarial_signatures",
      "kind": "malformed_signatures",
      "description": "Frequent malformed signatures.",
      "config": {"malformed_ratio": 0.6}
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )


def test_benign_scenario_summary_is_reproducible(tmp_path: Path) -> None:
    scenario_file = tmp_path / "scenarios.json"
    _write_scenarios(scenario_file)
    scenarios = _load_scenarios(scenario_file)

    first = run_simulation(
        count=30,
        tier=constitution.Tier.SANDBOX,
        scenario=scenarios["benign_case"],
        concurrent_streams=3,
        seed=17,
        window_size=10,
    )
    second = run_simulation(
        count=30,
        tier=constitution.Tier.SANDBOX,
        scenario=scenarios["benign_case"],
        concurrent_streams=3,
        seed=17,
        window_size=10,
    )

    assert first == second
    assert first.per_policy["baseline"].total_requests == 30
    assert first.candidate_regression_delta == {}


def test_adversarial_scenario_candidate_policy_delta(tmp_path: Path) -> None:
    scenario_file = tmp_path / "scenarios.json"
    _write_scenarios(scenario_file)
    scenarios = _load_scenarios(scenario_file)

    candidate_policy = tmp_path / "candidate_constitution.yaml"
    policy_text = constitution.POLICY_PATH.read_text(encoding="utf-8")
    candidate_policy.write_text(policy_text.replace('"severity": "blocking"', '"severity": "warning"', 1), encoding="utf-8")

    summary = run_simulation(
        count=40,
        tier=constitution.Tier.STABLE,
        scenario=scenarios["adversarial_signatures"],
        concurrent_streams=2,
        seed=23,
        window_size=10,
        baseline_policy=constitution.POLICY_PATH,
        candidate_policy=candidate_policy,
    )

    assert "candidate" in summary.per_policy
    assert summary.candidate_regression_delta["pass_rate_delta"] >= 0
    assert summary.per_policy["baseline"].blocked >= 1
