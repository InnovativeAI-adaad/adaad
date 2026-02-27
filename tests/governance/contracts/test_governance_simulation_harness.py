# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from runtime import constitution
from tools.simulate_governance_harness import _load_scenarios, run_simulation


def test_governance_simulation_harness_smoke() -> None:
    scenarios = _load_scenarios(Path("tools/governance_scenarios.json"))
    summary = run_simulation(
        count=10,
        tier=constitution.Tier.SANDBOX,
        scenario=scenarios["benign_baseline"],
        concurrent_streams=1,
        seed=11,
        window_size=5,
    )
    assert summary.total_requests == 10
    assert summary.per_policy["baseline"].passed >= 0
    assert summary.unique_envelope_digests >= 1
