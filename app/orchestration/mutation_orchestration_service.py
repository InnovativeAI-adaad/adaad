from __future__ import annotations

from app.orchestration.contracts import StatusEnvelope


class MutationOrchestrationService:
    """Owns mutation enablement and transition decisions."""

    _RUN_CYCLE_FALSE = {"run_cycle": False}

    @classmethod
    def _blocked_payload(cls) -> dict[str, bool]:
        """Return an isolated blocked payload dictionary.

        Rationale: callers may mutate payloads after envelope emission. Returning
        a fresh copy preserves fail-closed semantics across independent calls.
        Invariant: payload always contains exactly `run_cycle=False` for blocked
        transitions.
        """

        return cls._RUN_CYCLE_FALSE.copy()

    @staticmethod
    def _normalize_tasks(tasks: list[str]) -> tuple[str, ...]:
        """Return deterministic, non-empty task labels.

        Rationale: mutation boot decisions should not depend on duplicate/whitespace
        task records or malformed non-string entries. Invariants: returned tasks are
        stripped, non-empty, unique, and keep first-seen order to preserve
        deterministic replay behavior.
        """

        normalized: list[str] = []
        seen: set[str] = set()
        for task in tasks:
            if not isinstance(task, str):
                continue
            candidate = task.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return tuple(normalized)

    def evaluate_dream_tasks(self, tasks: list[str]) -> StatusEnvelope:
        normalized_tasks = self._normalize_tasks(tasks)
        if not normalized_tasks:
            return StatusEnvelope(status="warn", reason="no_tasks", evidence_refs=("dream.discover_tasks",), payload={"safe_boot": True})
        return StatusEnvelope(
            status="ok",
            reason="tasks_ready",
            evidence_refs=("dream.discover_tasks",),
            payload={"safe_boot": False, "task_count": len(normalized_tasks)},
        )

    def choose_transition(
        self,
        *,
        mutation_enabled: bool,
        fail_closed: bool,
        governance_gate_passed: bool,
        exit_after_boot: bool,
    ) -> StatusEnvelope:
        if not mutation_enabled:
            return StatusEnvelope(status="ok", reason="mutation_disabled", payload=self._blocked_payload())
        if fail_closed:
            return StatusEnvelope(status="warn", reason="mutation_blocked_fail_closed", payload=self._blocked_payload())
        if not governance_gate_passed:
            return StatusEnvelope(status="warn", reason="governance_gate_failed", payload=self._blocked_payload())
        if exit_after_boot:
            return StatusEnvelope(status="ok", reason="exit_after_boot", payload={"run_cycle": False, "mutation_cycle_skipped": "exit_after_boot"})
        return StatusEnvelope(status="ok", reason="run_mutation_cycle", payload={"run_cycle": True})
