from __future__ import annotations

from dataclasses import dataclass

from runtime.governance.gate import GateAxisResult, GovernanceGate


@dataclass(frozen=True)
class _LawDecisionStub:
    passed: bool
    decision: str
    reason_codes: list[str]
    failed_rules: list[dict[str, str]]


def test_governance_gate_decision_schema_and_ledger_event() -> None:
    writes: list[tuple[str, dict[str, object]]] = []

    gate = GovernanceGate(
        law_enforcer=lambda _ctx: _LawDecisionStub(
            passed=True,
            decision="pass",
            reason_codes=["pass"],
            failed_rules=[],
        ),
        tx_writer=lambda tx_type, payload: writes.append((tx_type, payload)) or {"type": tx_type, "payload": payload},
    )

    decision = gate.approve_mutation(
        mutation_id="governance-gate-epoch-1",
        trust_mode="dev",
        axis_results=[
            GateAxisResult(axis="constitution_version", rule_id="rule.constitution", ok=True, reason="ok"),
            GateAxisResult(axis="ledger_integrity", rule_id="rule.ledger", ok=True, reason="ok"),
        ],
    )

    payload = decision.to_payload()
    assert decision.approved is True
    assert decision.decision == "pass"
    assert payload["mutation_id"] == "governance-gate-epoch-1"
    assert payload["trust_mode"] == "dev"
    assert payload["reason_codes"] == ["pass"]
    assert isinstance(payload["axis_results"], list)
    assert payload["axis_results"][0]["axis"] == "constitution_version"
    assert payload["axis_results"][1]["axis"] == "ledger_integrity"
    assert len(decision.decision_id) == 71

    assert [entry[0] for entry in writes] == ["governance_gate_decision.v1"]


def test_governance_gate_human_override_writes_override_tx() -> None:
    writes: list[tuple[str, dict[str, object]]] = []

    gate = GovernanceGate(
        law_enforcer=lambda _ctx: _LawDecisionStub(
            passed=False,
            decision="fail",
            reason_codes=["blocked"],
            failed_rules=[{"rule_id": "rule.ledger", "reason": "corrupt"}],
        ),
        tx_writer=lambda tx_type, payload: writes.append((tx_type, payload)) or {"type": tx_type, "payload": payload},
    )

    decision = gate.approve_mutation(
        mutation_id="governance-gate-epoch-2",
        trust_mode="prod",
        axis_results=[GateAxisResult(axis="ledger_integrity", rule_id="rule.ledger", ok=False, reason="corrupt")],
        human_override=True,
    )

    assert decision.approved is True
    assert decision.decision == "override_pass"
    assert "human_override" in decision.reason_codes
    assert [entry[0] for entry in writes] == [
        "governance_gate_decision.v1",
        "governance_gate_human_override.v1",
    ]


def test_governance_gate_decision_id_is_deterministic_for_same_inputs() -> None:
    gate = GovernanceGate(
        law_enforcer=lambda _ctx: _LawDecisionStub(
            passed=True,
            decision="pass",
            reason_codes=["pass"],
            failed_rules=[],
        ),
        tx_writer=lambda _tx_type, _payload: {},
    )

    axes_a = [
        GateAxisResult(axis="warm_pool", rule_id="rule.warm_pool", ok=True, reason="ok"),
        GateAxisResult(axis="constitution_version", rule_id="rule.constitution", ok=True, reason="ok"),
    ]
    axes_b = list(reversed(axes_a))

    first = gate.approve_mutation(mutation_id="governance-gate-epoch-3", trust_mode="audit", axis_results=axes_a)
    second = gate.approve_mutation(mutation_id="governance-gate-epoch-3", trust_mode="audit", axis_results=axes_b)

    assert first.to_payload() == second.to_payload()
    assert first.decision_id == second.decision_id
