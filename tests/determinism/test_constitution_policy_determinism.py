# SPDX-License-Identifier: Apache-2.0

# ADAAD-LANE: determinism-replay

from pathlib import Path
import pytest
from adaad.agents.mutation_request import MutationRequest, MutationTarget
from runtime import constitution
pytestmark = pytest.mark.autonomous_critical

def _write_policy(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
def test_entropy_budget_validator_contract() -> None:
    validator = constitution.VALIDATOR_REGISTRY["entropy_budget_limit"]
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[{"op": "replace"}],
        signature="",
        nonce="n",
    )
    with constitution.deterministic_envelope_scope({"tier": "STABLE", "observed_entropy_bits": 5, "epoch_entropy_bits": 9}):
        result = validator(request)
    assert isinstance(result, dict)
    assert "ok" in result
    assert "reason" in result
    assert "details" in result
    assert result["details"]["mutation_bits"] >= result["details"]["declared_bits"]
    assert "epoch_entropy_bits" in result["details"]
def test_evaluate_mutation_restores_prior_envelope_state() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="",
        nonce="n",
    )
    with constitution.deterministic_envelope_scope({"custom": "value"}):
        _ = constitution.evaluate_mutation(request, constitution.Tier.STABLE)
        state = constitution.get_deterministic_envelope_state()
        assert state.get("custom") == "value"
        assert "tier" not in state
def test_replay_determinism_resource_accounting_and_verdict_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="",
        nonce="n",
    )
    monkeypatch.setenv("ADAAD_RESOURCE_MEMORY_MB", "50")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")

    with constitution.deterministic_envelope_scope(
        {
            "agent_id": request.agent_id,
            "epoch_id": "epoch-deterministic",
            "resource_measurements": {"peak_rss_mb": 64.0, "cpu_seconds": 1.0, "wall_seconds": 1.0},
        }
    ):
        first = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)
    with constitution.deterministic_envelope_scope(
        {
            "agent_id": request.agent_id,
            "epoch_id": "epoch-deterministic",
            "resource_measurements": {"peak_rss_mb": 64.0, "cpu_seconds": 1.0, "wall_seconds": 1.0},
        }
    ):
        second = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)

    first_resource = next(item for item in first["verdicts"] if item["rule"] == "resource_bounds")
    second_resource = next(item for item in second["verdicts"] if item["rule"] == "resource_bounds")
    assert first_resource["details"].get("details", {}).get("resource_usage_snapshot") == second_resource["details"].get("details", {}).get("resource_usage_snapshot")
    assert first_resource["passed"] == second_resource["passed"]
def test_domain_classification_is_deterministic_for_mixed_targets() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="",
        nonce="n",
        targets=[
            MutationTarget(agent_id="test_subject", path="docs/guide.md", target_type="file", ops=[]),
            MutationTarget(agent_id="test_subject", path="security/policy.py", target_type="file", ops=[]),
        ],
    )

    first = constitution._classify_request_domains(request)
    second = constitution._classify_request_domains(request)

    assert first == second
    assert first["domains"] == ["docs", "security"]
    assert first["path_domains"][0]["domain"] == "docs"
    assert first["path_domains"][1]["domain"] == "security"
def test_governance_envelope_digest_is_stable_over_100_identical_evaluations() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="cryovant-dev-test",
        nonce="n",
        epoch_id="epoch-stability-100",
        targets=[MutationTarget(agent_id="test_subject", path="app/agents/test_subject/agent.py", target_type="file", ops=[])],
    )

    digests = []
    for _ in range(100):
        with constitution.deterministic_envelope_scope(
            {
                "tier": constitution.Tier.SANDBOX.name,
                "epoch_id": "epoch-stability-100",
                "window_start_ts": 111.0,
                "window_end_ts": 222.0,
                "rate_per_hour": 1.0,
                "resource_measurements": {"peak_rss_mb": 32.0, "cpu_seconds": 0.1, "wall_seconds": 0.2},
            }
        ):
            verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)
        digests.append(verdict["governance_envelope"]["digest"])

    assert len(set(digests)) == 1
def test_evaluation_envelope_includes_policy_hash() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="cryovant-dev-test",
        nonce="n",
    )

    verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)

    assert verdict["governance_envelope"]["policy_hash"] == constitution.POLICY_HASH
def test_advisory_validators_do_not_mutate_envelope_state() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="cryovant-dev-test",
        nonce="n",
    )
    initial_state = {
        "tier": constitution.Tier.SANDBOX.name,
        "deployment_authority_tier": {"allowed": {"stable", "sandbox"}},
        "revenue_credit_floor": {"min": 100, "currency": "USD"},
        "reviewer_calibration": {"weights": ("latency", "alignment")},
    }

    with constitution.deterministic_envelope_scope(initial_state):
        before = constitution.get_deterministic_envelope_state()
        _ = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)
        after = constitution.get_deterministic_envelope_state()

    assert after == before
def test_cross_environment_digest_stability_with_equivalent_envelope_state() -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="cryovant-dev-test",
        nonce="n",
        epoch_id="epoch-cross-env",
    )

    linux_state = {
        "tier": constitution.Tier.SANDBOX.name,
        "epoch_id": "epoch-cross-env",
        "reviewer_calibration": {"weights": {"alignment", "latency"}},
        "revenue_credit_floor": {"currency": "USD", "min": 50},
    }
    android_state = {
        "epoch_id": "epoch-cross-env",
        "tier": constitution.Tier.SANDBOX.name,
        "revenue_credit_floor": {"min": 50, "currency": "USD"},
        "reviewer_calibration": {"weights": {"latency", "alignment"}},
    }

    with constitution.deterministic_envelope_scope(linux_state):
        linux_digest = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)["governance_envelope"]["digest"]
    with constitution.deterministic_envelope_scope(android_state):
        android_digest = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)["governance_envelope"]["digest"]

    assert linux_digest == android_digest
