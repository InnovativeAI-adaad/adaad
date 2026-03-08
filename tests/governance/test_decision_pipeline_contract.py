# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib
from typing import Any

from adaad.agents.mutation_request import MutationRequest, MutationTarget
from runtime import constitution
from runtime.governance.decision_contract import (
    CONTRACT_VERSION,
    constitutional_rule_registry,
    declared_artifact_rules,
    evaluation_order_for_tier,
)
from runtime.governance.decision_pipeline import evaluate_mutation_decision


def _request() -> MutationRequest:
    return MutationRequest(
        agent_id="pipeline-test-agent",
        generation_ts="now",
        intent="governance-contract-test",
        ops=[{"op": "replace", "path": "runtime/constitution.py"}],
        targets=[
            MutationTarget(
                agent_id="pipeline-test-agent",
                path="runtime/constitution.py",
                target_type="file",
                ops=[{"op": "replace", "path": "runtime/constitution.py"}],
            )
        ],
        signature="sig",
        nonce="nonce",
    )


def test_decision_pipeline_emits_contract_version_and_order() -> None:
    verdict = evaluate_mutation_decision(_request(), constitution.Tier.SANDBOX)
    assert verdict["contract_version"] == CONTRACT_VERSION
    assert isinstance(verdict["rule_evaluation_order"], list)
    assert verdict["rule_evaluation_order"]
    assert verdict["rule_evaluation_order"] == [row["rule"] for row in verdict["verdicts"]]


def test_constitutional_rules_map_to_executable_identifiers() -> None:
    registry = constitutional_rule_registry()
    assert registry
    assert set(registry) == {rule.name for rule in constitution.RULES}

    for _name, dotted in registry.items():
        module_name, attr_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_name)
        validator = getattr(module, attr_name)
        assert callable(validator)


def test_required_blocking_invariants_are_enforced_at_runtime(monkeypatch) -> None:
    required_rules = {"signature_required", "lineage_continuity"}
    patched = [rule for rule in constitution.RULES if rule.name in required_rules]
    assert {rule.name for rule in patched} == required_rules

    for rule in patched:
        def _fail_validator(_request: Any, *, _rule_name: str = rule.name) -> dict[str, Any]:
            return {"ok": False, "reason": f"forced_{_rule_name}_failure"}

        monkeypatch.setattr(rule, "validator", _fail_validator)

    verdict = evaluate_mutation_decision(_request(), constitution.Tier.PRODUCTION)
    assert verdict["passed"] is False
    for name in sorted(required_rules):
        row = next(item for item in verdict["verdicts"] if item["rule"] == name)
        assert row["passed"] is False
        assert name in verdict["blocking_failures"]


def test_policy_drift_declared_rules_match_runtime_registry() -> None:
    declared = declared_artifact_rules()
    runtime_registry = constitutional_rule_registry()

    declared_policy = set(declared["constitution_policy"])
    runtime_rules = set(runtime_registry)
    assert declared_policy == runtime_rules

    # Drift contract: every runtime-registered rule must be declared in applicability
    # or be explicitly exempted while rollout catches up.
    explicit_exemptions = {"deployment_authority_tier", "revenue_credit_floor", "reviewer_calibration"}
    missing_in_applicability = runtime_rules - set(declared["rule_applicability"])
    assert missing_in_applicability <= explicit_exemptions

    # Ensure policy artifact still declares mutation operations expected by runtime.
    assert set(declared["rego_operations"]) >= {"mutation.apply", "mutation.promote", "mutation.manifest.write"}


def test_evaluation_order_matches_dependency_ordering() -> None:
    expected = [rule.name for rule, _ in constitution._order_rules_with_dependencies(constitution.get_rules_for_tier(constitution.Tier.SANDBOX))]
    assert evaluation_order_for_tier(constitution.Tier.SANDBOX) == expected
