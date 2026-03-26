# SPDX-License-Identifier: Apache-2.0
"""Parallel governance axis evaluator with deterministic result merge.

Extends the base :class:`~runtime.governance.gate.GovernanceGate` with a
parallel axis evaluation path.  Independent governance axes (e.g., entropy
check, constitution check, founder-law check) can run concurrently on a
thread pool while still producing a *deterministic*, canonical merged
decision — regardless of evaluation order.

Safety invariants
-----------------
1. Axis results are sorted by ``(axis, rule_id)`` before merge: evaluation
   order has no effect on the final ``GateDecision``.
2. The executor timeout is enforced per-axis; any axis that times out
   records a ``TIMEOUT`` reason and is treated as a failure.
3. A failed axis evaluation (exception or timeout) is fail-closed: the
   corresponding ``GateAxisResult`` records ``ok=False``.
4. The merged decision digest is computed over the *sorted* axis results
   payload, matching the serialization used by the serial
   :class:`~runtime.governance.gate.GovernanceGate`.

Thread safety
-------------
Each axis probe is a pure, stateless callable: ``() -> tuple[bool, str]``.
The caller is responsible for ensuring probes are thread-safe.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Callable, Sequence

from runtime.governance.gate import DeterministicAxisEvaluator, GateAxisResult, GateDecision
from runtime.governance.foundation.canonical import canonical_json
from runtime.governance.foundation.hashing import sha256_prefixed_digest
from runtime.founders_law import enforce_law
from security.ledger import journal

PARALLEL_GATE_VERSION = "v1.0.0"
DEFAULT_AXIS_TIMEOUT_SECONDS: float = 5.0
DEFAULT_MAX_WORKERS: int = 8


@dataclass(frozen=True)
class ParallelAxisSpec:
    """Specification for a single concurrently evaluated governance axis.

    Attributes
    ----------
    axis:
        Axis identifier (e.g., ``"entropy"``, ``"constitution"``).
    rule_id:
        Rule identifier within the axis (e.g., ``"entropy_budget_ok"``).
    probe:
        Callable with signature ``() -> tuple[bool, str]``.
        Must be thread-safe and side-effect-free.
    timeout_seconds:
        Per-axis evaluation timeout.  Defaults to ``DEFAULT_AXIS_TIMEOUT_SECONDS``.
    """

    axis: str
    rule_id: str
    probe: Callable[[], tuple[bool, str]]
    timeout_seconds: float = DEFAULT_AXIS_TIMEOUT_SECONDS


class ParallelGovernanceGate:
    """Governance gate with concurrent axis evaluation and deterministic merge.

    Parameters
    ----------
    max_workers:
        Maximum number of threads for axis evaluation.
    law_enforcer:
        Founders-law enforcement callable (injected for testability).
    tx_writer:
        Ledger transaction writer callable (injected for testability).

    Usage
    -----
    >>> from runtime.governance.parallel_gate import ParallelGovernanceGate, ParallelAxisSpec
    >>> gate = ParallelGovernanceGate()
    >>> specs = [
    ...     ParallelAxisSpec("entropy", "budget_ok", lambda: (True, "within_budget")),
    ...     ParallelAxisSpec("constitution", "tier_ok", lambda: (True, "tier_approved")),
    ... ]
    >>> decision = gate.approve_mutation_parallel(
    ...     mutation_id="mut_abc",
    ...     trust_mode="standard",
    ...     axis_specs=specs,
    ... )
    >>> decision.approved
    True
    """

    def __init__(
        self,
        *,
        max_workers: int = DEFAULT_MAX_WORKERS,
        law_enforcer=enforce_law,
        tx_writer=journal.append_tx,
    ) -> None:
        self._max_workers = max_workers
        self._law_enforcer = law_enforcer
        self._tx_writer = tx_writer

    def evaluate_axes_parallel(
        self,
        specs: Sequence[ParallelAxisSpec],
    ) -> list[GateAxisResult]:
        """Evaluate all axis specs concurrently, return sorted results.

        Evaluation order is non-deterministic; the returned list is always
        sorted by ``(axis, rule_id)`` for deterministic downstream merge.

        Axis probes that raise or time out produce ``ok=False`` results with
        a descriptive reason string.
        """
        futures_map: dict[concurrent.futures.Future, ParallelAxisSpec] = {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self._max_workers, max(1, len(specs)))
        ) as executor:
            for spec in specs:
                evaluator = DeterministicAxisEvaluator(
                    axis=spec.axis,
                    rule_id=spec.rule_id,
                    probe=spec.probe,
                )
                future = executor.submit(evaluator.evaluate)
                futures_map[future] = spec

            raw_results: list[GateAxisResult] = []
            for future, spec in futures_map.items():
                try:
                    result = future.result(timeout=spec.timeout_seconds)
                    raw_results.append(result)
                except concurrent.futures.TimeoutError:
                    raw_results.append(
                        GateAxisResult(
                            axis=spec.axis,
                            rule_id=spec.rule_id,
                            ok=False,
                            reason=f"axis_timeout:{spec.timeout_seconds}s",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    raw_results.append(
                        GateAxisResult(
                            axis=spec.axis,
                            rule_id=spec.rule_id,
                            ok=False,
                            reason=f"axis_exception:{type(exc).__name__}",
                        )
                    )

        # Deterministic sort: identical to serial GovernanceGate ordering
        return sorted(raw_results, key=lambda r: (r.axis, r.rule_id))

    def approve_mutation_parallel(
        self,
        *,
        mutation_id: str,
        trust_mode: str,
        axis_specs: Sequence[ParallelAxisSpec],
        human_override: bool = False,
    ) -> GateDecision:
        """Evaluate axes concurrently, then merge into a deterministic GateDecision.

        Parameters
        ----------
        mutation_id:
            Stable mutation identifier.
        trust_mode:
            Trust mode string (e.g., ``"standard"``, ``"elevated"``).
        axis_specs:
            Ordered (by intention) specs for axes to evaluate concurrently.
        human_override:
            When ``True``, a human has explicitly approved this mutation.
        """
        axis_results = self.evaluate_axes_parallel(axis_specs)

        failed = [r for r in axis_results if not r.ok]
        reason_codes = [r.reason for r in failed]
        failed_rules = [{"axis": r.axis, "rule_id": r.rule_id} for r in failed]
        checks = [
            {
                "rule_id": item.rule_id,
                "ok": item.ok,
                "reason": item.reason,
            }
            for item in axis_results
        ]

        law_context = {
            "mutation_id": mutation_id,
            "trust_mode": trust_mode,
            "checks": checks,
            "failed_rules": failed_rules,
            "human_override": human_override,
        }
        law_decision = self._law_enforcer(law_context)

        if not law_decision.passed:
            for code in law_decision.reason_codes:
                if code not in reason_codes:
                    reason_codes.append(code)
            existing_failed_rule_ids = {str(rule.get("rule_id", "")) for rule in failed_rules}
            for rule in law_decision.failed_rules:
                rule_id = str(rule.get("rule_id", ""))
                if rule_id in existing_failed_rule_ids:
                    continue
                if rule not in failed_rules:
                    failed_rules.append(rule)
                    existing_failed_rule_ids.add(rule_id)

        approved = (not failed) and law_decision.passed
        decision = "approve" if approved else "reject"
        if human_override and not approved:
            approved = True
            decision = "override_pass"
            if "human_override" not in reason_codes:
                reason_codes.append("human_override")

        decision_payload = {
            "mutation_id": mutation_id,
            "trust_mode": trust_mode,
            "approved": approved,
            "reason_codes": sorted(reason_codes),
            "failed_rules": sorted(failed_rules, key=lambda r: (r.get("axis", ""), r.get("rule_id", ""))),
            "axis_results": [
                {"axis": r.axis, "rule_id": r.rule_id, "ok": r.ok, "reason": r.reason}
                for r in axis_results
            ],
            "human_override": human_override,
            "gate_version": PARALLEL_GATE_VERSION,
        }
        decision_id = sha256_prefixed_digest(decision_payload)

        decision = GateDecision(
            approved=approved,
            decision=decision,
            mutation_id=mutation_id,
            trust_mode=trust_mode,
            reason_codes=sorted(reason_codes),
            failed_rules=sorted(
                failed_rules,
                key=lambda r: (r.get("axis", ""), r.get("rule_id", "")),
            ),
            axis_results=axis_results,
            human_override=human_override,
            decision_id=decision_id,
        )

        self._tx_writer(
            "mutation_parallel_gate_decision",
            decision.to_payload(),
        )

        return decision


__all__ = [
    "DEFAULT_AXIS_TIMEOUT_SECONDS",
    "DEFAULT_MAX_WORKERS",
    "PARALLEL_GATE_VERSION",
    "ParallelAxisSpec",
    "ParallelGovernanceGate",
]
