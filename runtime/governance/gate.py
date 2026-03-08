# SPDX-License-Identifier: Apache-2.0

"""Deterministic governance gate evaluation and decision shaping."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict, dataclass
from typing import Any, Callable, Protocol, Sequence

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from runtime import constitution
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


GOVERNANCE_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "approved",
        "decision",
        "mutation_id",
        "trust_mode",
        "reason_codes",
        "failed_rules",
        "axis_results",
        "human_override",
        "decision_id",
        "gate_mode",
    ],
}


def canonical_evaluator_order(items: Sequence[DeterministicAxisEvaluator]) -> list[DeterministicAxisEvaluator]:
    """Return deterministic evaluator ordering for governance decision execution."""
    return sorted(items, key=lambda item: (item.axis, item.rule_id))


def declared_policy_artifact_rule_ids(base_path: Path = Path("runtime/governance")) -> set[str]:
    """Collect declared rule identifiers from runtime governance artifacts."""
    rule_ids: set[str] = set()
    for artifact in sorted(base_path.glob("*.json")) + sorted(base_path.glob("*.yaml")) + sorted(base_path.glob("*.rego")):
        if artifact.suffix == ".rego":
            for line in artifact.read_text(encoding="utf-8").splitlines():
                token = line.strip().strip(',').strip('"')
                if token and token.startswith("mutation."):
                    rule_ids.add(token)
            continue

        raw = artifact.read_text(encoding="utf-8")
        try:
            parsed = constitution.yaml.safe_load(raw)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        for row in parsed.get("rules", []):
            if isinstance(row, dict):
                value = row.get("name") or row.get("rule_id")
                if isinstance(value, str) and value.strip():
                    rule_ids.add(value.strip())
        for row in parsed.get("clauses", []):
            if isinstance(row, dict):
                value = row.get("clause_id")
                if isinstance(value, str) and value.strip():
                    rule_ids.add(value.strip())
    return rule_ids


def registered_runtime_check_ids() -> set[str]:
    """Identifiers with runtime evaluator implementations."""
    checks = {rule.name for rule in constitution.RULES}

    founders_law = json.loads(Path("runtime/governance/founders_law.json").read_text(encoding="utf-8"))
    checks.update(
        str(row.get("rule_id", "")).strip()
        for row in founders_law.get("rules", [])
        if isinstance(row, dict) and str(row.get("rule_id", "")).strip()
    )

    canon_law = constitution.yaml.safe_load(Path("runtime/governance/canon_law_v1.yaml").read_text(encoding="utf-8"))
    if isinstance(canon_law, dict):
        checks.update(
            str(row.get("clause_id", "")).strip()
            for row in canon_law.get("clauses", [])
            if isinstance(row, dict) and str(row.get("clause_id", "")).strip()
        )
    return checks


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
        trust_mode: str = "standard",
        axis_results: Sequence[GateAxisResult] | None = None,
        mutation_payload: dict[str, object] | None = None,
        mutation_context: dict[str, object] | None = None,
        human_override: bool = False,
        parallel: bool = False,  # PR-PHASE4-06: delegate to ParallelGovernanceGate
    ) -> GateDecision:
        context = dict(mutation_context or {})
        payload = dict(mutation_payload or {})
        declared_overrides = context.get("rule_outcomes", {})

        evaluator_specs: list[DeterministicAxisEvaluator]
        if axis_results is None:
            evaluator_specs = []
            for rule_id in sorted(registered_runtime_check_ids()):
                override_row = declared_overrides.get(rule_id, {}) if isinstance(declared_overrides, dict) else {}
                evaluator_specs.append(
                    DeterministicAxisEvaluator(
                        axis="runtime_check",
                        rule_id=rule_id,
                        probe=lambda _override=override_row: (
                            bool(_override.get("ok", True)) if isinstance(_override, dict) else True,
                            str(_override.get("reason", "ok")) if isinstance(_override, dict) else "ok",
                        ),
                    )
                )
            ordered_evaluators = canonical_evaluator_order(evaluator_specs)
            axis_results = [item.evaluate() for item in ordered_evaluators]
        else:
            axis_results = list(axis_results)

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
            "mutation_payload": payload,
            "mutation_context": context,
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
    "GOVERNANCE_DECISION_SCHEMA",
    "canonical_evaluator_order",
    "declared_policy_artifact_rule_ids",
    "DeterministicAxisEvaluator",
    "GateAxisResult",
    "GateDecision",
    "GovernanceGate",
    "registered_runtime_check_ids",
]
