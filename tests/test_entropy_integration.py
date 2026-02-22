# SPDX-License-Identifier: Apache-2.0

from app.agents.mutation_request import MutationRequest
from runtime import constitution


def test_entropy_budget_limit_rejection_includes_required_fields(monkeypatch):
    validator = constitution.VALIDATOR_REGISTRY["entropy_budget_limit"]
    monkeypatch.setenv("ADAAD_MAX_MUTATION_ENTROPY_BITS", "1")
    request = MutationRequest(
        agent_id="agent",
        generation_ts="2026-01-01T00:00:00+00:00",
        intent="entropy-heavy",
        ops=[{"op": "set", "path": "x", "value": "y"}],
        signature="sig",
        nonce="nonce",
    )

    with constitution.deterministic_envelope_scope({"tier": "STABLE", "epoch_entropy_bits": 64, "observed_entropy_bits": 0}):
        verdict = validator(request)

    assert verdict["ok"] is False
    assert "max_mutation_entropy_bits" in verdict["details"]
    assert "epoch_entropy_bits" in verdict["details"]
