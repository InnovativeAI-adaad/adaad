# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import Iterable, Sequence

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
    def _normalize_tasks(tasks: Sequence[str] | Iterable[object]) -> tuple[str, ...]:
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

    def evaluate_dream_tasks(self, tasks: Sequence[str] | Iterable[object] | None) -> StatusEnvelope:
        """Evaluate dream tasks with fail-closed handling for malformed payloads.

        Rationale: safety-critical mutation orchestration should reject absent or
        structurally invalid task payloads before normalization. Invariant: invalid
        payloads always return a deterministic warn envelope with safe boot enabled.
        """

        if tasks is None or isinstance(tasks, (str, bytes)):
            return StatusEnvelope(
                status="warn",
                reason="invalid_tasks_payload",
                evidence_refs=("dream.discover_tasks",),
                payload={"safe_boot": True},
            )

        try:
            iterator = iter(tasks)
        except TypeError:
            return StatusEnvelope(
                status="warn",
                reason="invalid_tasks_payload",
                evidence_refs=("dream.discover_tasks",),
                payload={"safe_boot": True},
            )

        normalized_tasks = self._normalize_tasks(iterator)
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
