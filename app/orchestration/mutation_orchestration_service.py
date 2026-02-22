from __future__ import annotations

from app.orchestration.contracts import StatusEnvelope


class MutationOrchestrationService:
    """Owns mutation enablement and transition decisions."""

    def evaluate_dream_tasks(self, tasks: list[str]) -> StatusEnvelope:
        if not tasks:
            return StatusEnvelope(status="warn", reason="no_tasks", evidence_refs=("dream.discover_tasks",), payload={"safe_boot": True})
        return StatusEnvelope(status="ok", reason="tasks_ready", evidence_refs=("dream.discover_tasks",), payload={"safe_boot": False})

    def choose_transition(
        self,
        *,
        mutation_enabled: bool,
        fail_closed: bool,
        governance_gate_passed: bool,
        exit_after_boot: bool,
    ) -> StatusEnvelope:
        if not mutation_enabled:
            return StatusEnvelope(status="ok", reason="mutation_disabled", payload={"run_cycle": False})
        if fail_closed:
            return StatusEnvelope(status="warn", reason="mutation_blocked_fail_closed", payload={"run_cycle": False})
        if not governance_gate_passed:
            return StatusEnvelope(status="warn", reason="governance_gate_failed", payload={"run_cycle": False})
        if exit_after_boot:
            return StatusEnvelope(status="ok", reason="exit_after_boot", payload={"run_cycle": False, "mutation_cycle_skipped": "exit_after_boot"})
        return StatusEnvelope(status="ok", reason="run_mutation_cycle", payload={"run_cycle": True})
