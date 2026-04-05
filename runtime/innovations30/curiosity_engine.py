# SPDX-License-Identifier: Apache-2.0
"""Innovation #29 — Curiosity-Driven Exploration with Hard Stops (CURIOSITY).
Every 25 epochs: 3 epochs of inverted-fitness exploration.
Hard constitutional stops prevent catastrophic exploration.

Constitutional invariants:
    CURIOSITY-0       — invert_fitness() MUST return 1.0 - base_fitness when active;
                        base_fitness MUST be in [0.0, 1.0]
    CURIOSITY-STOP-0  — tick() MUST exit curiosity immediately when health < HARD_STOP_HEALTH
                        or when any proposed file matches HARD_STOP_PATTERNS
    CURIOSITY-AUDIT-0 — every state transition MUST append a reason to CuriosityState.discoveries
                        and persist state

Additions (v1.1 — Phase 114):
    CURIOSITY_INVARIANTS    — Hard-class invariant registry
    curiosity_guard()       — fail-closed enforcement helper
    CuriosityEvent          — structured audit record per tick/transition
"""
from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Constitutional constants ─────────────────────────────────────────────────
CURIOSITY_INTERVAL: int = 25
CURIOSITY_DURATION: int = 3
HARD_STOP_HEALTH: float = 0.50

HARD_STOP_PATTERNS: frozenset[str] = frozenset([
    "runtime/governance/gate.py",
    "runtime/constitution.py",
    "security/ledger/journal.py",
    "HUMAN-0",
    "human_signoff",
])

CURIOSITY_INVARIANTS: dict[str, str] = {
    "CURIOSITY-0": (
        "invert_fitness() MUST return round(1.0 - base_fitness, 4) when active. "
        "base_fitness MUST be in [0.0, 1.0]; violation raises RuntimeError."
    ),
    "CURIOSITY-STOP-0": (
        "tick() MUST exit curiosity immediately when health_score < HARD_STOP_HEALTH "
        "or any proposed file matches HARD_STOP_PATTERNS. No exceptions."
    ),
    "CURIOSITY-AUDIT-0": (
        "Every state transition (enter, exit, tick) MUST append a reason to "
        "CuriosityState.discoveries and persist state to disk."
    ),
}


@dataclass
class CuriosityState:
    active: bool = False
    epochs_remaining: int = 0
    cycle_number: int = 0
    total_curiosity_epochs: int = 0
    discoveries: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.discoveries is None:
            self.discoveries = []


@dataclass
class CuriosityEvent:
    """Structured audit record per curiosity transition [CURIOSITY-AUDIT-0]."""
    event_type: str          # "enter" | "tick" | "hard_stop_health" | "hard_stop_file" | "cycle_complete"
    epoch_id: str
    cycle_number: int
    epochs_remaining: int
    health_score: float
    reason: str
    timestamp_utc: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    innovation: str = "INNOV-29"
    phase: int = 114

    def to_ledger_row(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


def curiosity_guard(state: CuriosityState, base_fitness: float | None = None) -> None:
    """Fail-closed enforcement for curiosity constitutional constraints [CURIOSITY-0].

    Raises RuntimeError on invariant violations.
    """
    if base_fitness is not None and not (0.0 <= base_fitness <= 1.0):
        raise RuntimeError(
            f"CURIOSITY-0: base_fitness={base_fitness} outside [0.0, 1.0]."
        )
    if state.epochs_remaining < 0:
        raise RuntimeError(
            f"CURIOSITY-0: epochs_remaining={state.epochs_remaining} is negative."
        )
    if state.active and state.epochs_remaining == 0:
        raise RuntimeError(
            "CURIOSITY-0: state.active=True but epochs_remaining=0 — "
            "inconsistent curiosity state."
        )


class CuriosityEngine:
    """Manages bounded curiosity-driven exploration cycles.

    Constitutional guarantees (Phase 114):
        CURIOSITY-0     : invert_fitness validated; base_fitness bounds enforced
        CURIOSITY-STOP-0: health/file hard stops enforced in tick()
        CURIOSITY-AUDIT-0: all transitions logged to discoveries and persisted
    """

    def __init__(
        self,
        state_path: Path = Path("data/curiosity_state.json"),
        interval: int = CURIOSITY_INTERVAL,
        duration: int = CURIOSITY_DURATION,
    ) -> None:
        self.state_path = Path(state_path)
        self.interval = interval
        self.duration = duration
        self._state = CuriosityState()
        self._load()

    def should_enter_curiosity(self, epoch_seq: int) -> bool:
        return (
            not self._state.active
            and epoch_seq > 0
            and epoch_seq % self.interval == 0
        )

    def enter_curiosity(self, epoch_id: str) -> CuriosityState:
        """Begin a curiosity cycle [CURIOSITY-AUDIT-0]."""
        self._state.active = True
        self._state.epochs_remaining = self.duration
        self._state.cycle_number += 1
        self._state.total_curiosity_epochs += self.duration
        self._state.discoveries.append(f"enter:cycle_{self._state.cycle_number}:{epoch_id}")
        self._save()
        return self._state

    def tick(
        self,
        epoch_id: str,
        health_score: float,
        proposed_files: list[str],
    ) -> tuple[bool, str]:
        """Advance one epoch. Returns (still_in_curiosity, exit_reason).

        [CURIOSITY-STOP-0] — hard stops enforced before any other logic.
        [CURIOSITY-AUDIT-0] — every exit appends to discoveries.
        """
        if not self._state.active:
            return False, ""

        # [CURIOSITY-STOP-0] health hard stop
        if health_score < HARD_STOP_HEALTH:
            reason = f"hard_stop_health:{health_score:.3f}<{HARD_STOP_HEALTH}"
            self._exit_curiosity(reason)
            return False, f"Curiosity hard stop: health {health_score:.3f} < {HARD_STOP_HEALTH}"

        # [CURIOSITY-STOP-0] protected file hard stop
        for f in proposed_files:
            if any(p in str(f) for p in HARD_STOP_PATTERNS):
                reason = f"hard_stop_file:{f}"
                self._exit_curiosity(reason)
                return False, f"Curiosity hard stop: proposal touches protected path {f}"

        self._state.epochs_remaining -= 1
        if self._state.epochs_remaining <= 0:
            self._exit_curiosity("cycle_complete")
            return False, "Curiosity cycle complete"

        self._state.discoveries.append(f"tick:epoch_{epoch_id}:remaining_{self._state.epochs_remaining}")
        self._save()
        return True, ""

    @property
    def in_curiosity(self) -> bool:
        return self._state.active

    def invert_fitness(self, base_fitness: float) -> float:
        """Invert fitness during curiosity to reward unusual mutations [CURIOSITY-0].

        base_fitness MUST be in [0.0, 1.0].
        """
        if not (0.0 <= base_fitness <= 1.0):
            raise RuntimeError(
                f"CURIOSITY-0: base_fitness={base_fitness} outside [0.0, 1.0]."
            )
        if not self._state.active:
            return base_fitness
        return round(1.0 - base_fitness, 4)

    def state_summary(self) -> dict[str, Any]:
        return dataclasses.asdict(self._state)

    def _exit_curiosity(self, reason: str) -> None:
        self._state.active = False
        self._state.epochs_remaining = 0
        self._state.discoveries.append(f"exit:{reason}")
        self._save()

    def _load(self) -> None:
        if self.state_path.exists():
            try:
                d = json.loads(self.state_path.read_text())
                if "discoveries" not in d:
                    d["discoveries"] = []
                self._state = CuriosityState(**d)
            except Exception:
                pass

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(dataclasses.asdict(self._state), indent=2)
        )


__all__ = [
    "CuriosityEngine", "CuriosityState", "CuriosityEvent", "curiosity_guard",
    "CURIOSITY_INVARIANTS", "CURIOSITY_INTERVAL", "CURIOSITY_DURATION",
    "HARD_STOP_HEALTH", "HARD_STOP_PATTERNS",
]
