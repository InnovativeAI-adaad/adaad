# SPDX-License-Identifier: Apache-2.0
"""Constitutional amendment phase orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from security.ledger import journal


@dataclass(frozen=True)
class AmendmentPhaseResult:
    proposal_status: str
    effectuation_applied: bool


class AmendmentPipeline:
    """Runs amendment phases in fail-closed order and appends phase ledger entries."""

    COMMENT_WINDOW = "comment_window"
    SIMULATION_GATE = "simulation_gate"
    QUORUM_VOTE = "quorum_vote"
    EFFECTUATION = "effectuation"
    ARCHIVE = "archive"

    def __init__(
        self,
        *,
        required_approvals: int,
        rejection_threshold: int,
        proposal_id: str,
        transition_log: list[dict[str, Any]],
        ensure_comment_window: Callable[[], None] | None = None,
        run_simulation_gate: Callable[[], dict[str, Any]],
        apply_effectuation: Callable[[], bool],
    ) -> None:
        self.required_approvals = required_approvals
        self.rejection_threshold = rejection_threshold
        self.proposal_id = proposal_id
        self.transition_log = transition_log
        self.ensure_comment_window = ensure_comment_window or (lambda: None)
        self.run_simulation_gate = run_simulation_gate
        self.apply_effectuation = apply_effectuation

    def run(self, *, approvals: int, rejections: int, status: str) -> AmendmentPhaseResult:
        if status not in {"pending", "approved"}:
            return AmendmentPhaseResult(proposal_status=status, effectuation_applied=False)

        self.ensure_comment_window()
        self._append_transition(self.COMMENT_WINDOW, "complete", {"approvals": approvals, "rejections": rejections})

        simulation = self.run_simulation_gate()
        sim_ok = bool(simulation.get("ok"))
        self._append_transition(self.SIMULATION_GATE, "passed" if sim_ok else "failed", simulation)
        if not sim_ok:
            return AmendmentPhaseResult(proposal_status="pending", effectuation_applied=False)

        quorum_reached = approvals >= self.required_approvals
        rejection_triggered = rejections >= self.rejection_threshold
        vote_payload = {
            "approvals": approvals,
            "rejections": rejections,
            "required_approvals": self.required_approvals,
            "rejection_threshold": self.rejection_threshold,
            "quorum_reached": quorum_reached,
            "rejection_threshold_triggered": rejection_triggered,
        }
        vote_state = "rejected" if rejection_triggered else ("approved" if quorum_reached else "pending")
        self._append_transition(self.QUORUM_VOTE, vote_state, vote_payload)
        if rejection_triggered:
            self._append_transition(self.ARCHIVE, "rejected", {})
            return AmendmentPhaseResult(proposal_status="rejected", effectuation_applied=False)
        if not quorum_reached:
            return AmendmentPhaseResult(proposal_status="pending", effectuation_applied=False)

        applied = self.apply_effectuation()
        effect_state = "applied" if applied else "amendment_already_effective"
        self._append_transition(self.EFFECTUATION, effect_state, {"idempotent_noop": not applied})

        self._append_transition(self.ARCHIVE, "completed", {"final_status": "approved"})
        return AmendmentPhaseResult(proposal_status="approved", effectuation_applied=applied)

    def _append_transition(self, phase: str, state: str, payload: dict[str, Any]) -> None:
        previous = self.transition_log[-1] if self.transition_log else None
        previous_hash = str((previous or {}).get("tx_hash") or "0" * 64)
        tx_payload = {
            "proposal_id": self.proposal_id,
            "phase": phase,
            "state": state,
            "prev_phase_hash": previous_hash,
            **payload,
        }
        tx = journal.append_tx(tx_type="constitutional_amendment_phase", payload=tx_payload)
        entry = {
            "phase": phase,
            "state": state,
            "prev_phase_hash": previous_hash,
            "tx_hash": tx.get("hash") or tx.get("tx") or "",
        }
        self.transition_log.append(entry)

