# SPDX-License-Identifier: Apache-2.0

"""Deterministic governance gate evaluation and decision shaping."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Protocol, Sequence

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from runtime.founders_law import enforce_law
from security.ledger import journal


class LawDecisionLike(Protocol):
    passed: bool
    decision: str
    reason_codes: list[str]
    failed_rules: list[dict[str, str]]


@dataclass(frozen=True)
class GateAxisResult:
    axis: str
    rule_id: str
    ok: bool
    reason: str


@dataclass(frozen=True)
class GateDecision:
    approved: bool
    decision: str
    mutation_id: str
    trust_mode: str
    reason_codes: list[str]
    failed_rules: list[dict[str, str]]
    axis_results: list[GateAxisResult]
    human_override: bool
    decision_id: str
    gate_mode: str = "serial"  # PR-PHASE4-06: 'serial' | 'parallel'

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["axis_results"] = [asdict(axis) for axis in self.axis_results]
        return payload


@dataclass(frozen=True)
class DeterministicAxisEvaluator:
    axis: str
    rule_id: str
    probe: Callable[[], tuple[bool, str]]

    def evaluate(self) -> GateAxisResult:
        ok, reason = self.probe()
        normalized_reason = str(reason or "ok")
        return GateAxisResult(axis=self.axis, rule_id=self.rule_id, ok=bool(ok), reason=normalized_reason)


class GovernanceGate:
    def __init__(
        self,
        *,
        law_enforcer: Callable[[dict[str, object]], LawDecisionLike] = enforce_law,
        tx_writer: Callable[[str, dict[str, object]], dict[str, object]] = journal.append_tx,
    ) -> None:
        self._law_enforcer = law_enforcer
        self._tx_writer = tx_writer

    def approve_mutation(
        self,
        *,
        mutation_id: str,
        trust_mode: str,
        axis_results: Sequence[GateAxisResult],
        human_override: bool = False,
        parallel: bool = False,  # PR-PHASE4-06: delegate to ParallelGovernanceGate
    ) -> GateDecision:
        # PR-PHASE4-06: parallel path
        if parallel:
            try:
                from runtime.governance.parallel_gate import (
                    ParallelGovernanceGate,
                    ParallelAxisSpec,
                )
                _axis_specs = [
                    ParallelAxisSpec(
                        axis=item.axis,
                        rule_id=item.rule_id,
                        probe=lambda _ok=item.ok, _r=item.reason: (_ok, _r),
                    )
                    for item in axis_results
                ]
                _pgate = ParallelGovernanceGate(
                    law_enforcer=self._law_enforcer,
                    tx_writer=self._tx_writer,
                )
                _pdecision = _pgate.approve_mutation_parallel(
                    mutation_id=mutation_id,
                    trust_mode=trust_mode,
                    axis_specs=_axis_specs,
                    human_override=human_override,
                )
                # Re-build with gate_mode='parallel' (frozen dataclass — use replace pattern)
                import dataclasses as _dc
                return _dc.replace(_pdecision, gate_mode="parallel")
            except Exception:  # noqa: BLE001 — fall through to serial on any failure
                pass

        ordered_axis = sorted(axis_results, key=lambda item: (item.axis, item.rule_id))
        law_context = {
            "mutation_id": mutation_id,
            "trust_mode": trust_mode,
            "checks": [
                {
                    "rule_id": item.rule_id,
                    "ok": item.ok,
                    "reason": item.reason,
                }
                for item in ordered_axis
            ],
        }
        law_decision = self._law_enforcer(law_context)
        approved = bool(law_decision.passed)
        decision = str(law_decision.decision)
        reason_codes = list(law_decision.reason_codes)
        failed_rules = list(law_decision.failed_rules)

        if human_override and not approved:
            approved = True
            decision = "override_pass"
            reason_codes = reason_codes + ["human_override"]

        identity_payload = {
            "approved": approved,
            "decision": decision,
            "mutation_id": mutation_id,
            "trust_mode": trust_mode,
            "reason_codes": reason_codes,
            "failed_rules": failed_rules,
            "human_override": human_override,
            "axis_results": [asdict(item) for item in ordered_axis],
        }
        decision_id = sha256_prefixed_digest(canonical_json(identity_payload))

        gate_decision = GateDecision(
            approved=approved,
            decision=decision,
            mutation_id=mutation_id,
            trust_mode=trust_mode,
            reason_codes=reason_codes,
            failed_rules=failed_rules,
            axis_results=list(ordered_axis),
            human_override=human_override,
            decision_id=decision_id,
            gate_mode="serial",
        )

        self._tx_writer("governance_gate_decision.v1", gate_decision.to_payload())
        if human_override:
            self._tx_writer(
                "governance_gate_human_override.v1",
                {
                    "decision_id": decision_id,
                    "mutation_id": mutation_id,
                    "trust_mode": trust_mode,
                    "reason_codes": reason_codes,
                },
            )

        return gate_decision


__all__ = [
    "DeterministicAxisEvaluator",
    "GateAxisResult",
    "GateDecision",
    "GovernanceGate",
]
