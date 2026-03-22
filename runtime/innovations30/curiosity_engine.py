# SPDX-License-Identifier: Apache-2.0
"""Innovation #29 — Curiosity-Driven Exploration with Hard Stops.
Every 25 epochs: 3 epochs of inverted-fitness exploration.
Hard constitutional stops prevent catastrophic exploration.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CURIOSITY_INTERVAL: int = 25   # epochs between curiosity cycles
CURIOSITY_DURATION: int = 3    # epochs of inverted fitness per cycle
HARD_STOP_HEALTH: float = 0.50 # exit curiosity if health drops below
HARD_STOP_PATTERNS = frozenset([
    "runtime/governance/gate.py",
    "runtime/constitution.py",
    "security/ledger/journal.py",
    "HUMAN-0", "human_signoff",
])

@dataclass
class CuriosityState:
    active: bool = False
    epochs_remaining: int = 0
    cycle_number: int = 0
    total_curiosity_epochs: int = 0
    discoveries: list[str] = None

    def __post_init__(self):
        if self.discoveries is None:
            self.discoveries = []


class CuriosityEngine:
    """Manages bounded curiosity-driven exploration cycles."""

    def __init__(self, state_path: Path = Path("data/curiosity_state.json"),
                 interval: int = CURIOSITY_INTERVAL,
                 duration: int = CURIOSITY_DURATION):
        self.state_path = Path(state_path)
        self.interval = interval
        self.duration = duration
        self._state = CuriosityState()
        self._load()

    def should_enter_curiosity(self, epoch_seq: int) -> bool:
        return (not self._state.active
                and epoch_seq > 0
                and epoch_seq % self.interval == 0)

    def enter_curiosity(self, epoch_id: str) -> CuriosityState:
        self._state.active = True
        self._state.epochs_remaining = self.duration
        self._state.cycle_number += 1
        self._state.total_curiosity_epochs += self.duration
        self._save()
        return self._state

    def tick(self, epoch_id: str, health_score: float,
              proposed_files: list[str]) -> tuple[bool, str]:
        """
        Call each epoch. Returns (still_in_curiosity, reason_if_exited).
        """
        if not self._state.active:
            return False, ""

        # Hard stop: health too low
        if health_score < HARD_STOP_HEALTH:
            self._exit_curiosity(f"hard_stop_health_{health_score:.3f}")
            return False, f"Curiosity hard stop: health {health_score:.3f} < {HARD_STOP_HEALTH}"

        # Hard stop: touching protected files
        for f in proposed_files:
            if any(p in str(f) for p in HARD_STOP_PATTERNS):
                self._exit_curiosity(f"hard_stop_protected_file_{f}")
                return False, f"Curiosity hard stop: proposal touches protected path {f}"

        self._state.epochs_remaining -= 1
        if self._state.epochs_remaining <= 0:
            self._exit_curiosity("cycle_complete")
            return False, "Curiosity cycle complete"

        self._save()
        return True, ""

    @property
    def in_curiosity(self) -> bool:
        return self._state.active

    def invert_fitness(self, base_fitness: float) -> float:
        """During curiosity, invert fitness to reward unusual mutations."""
        if not self._state.active:
            return base_fitness
        # Reward divergence: high original fitness → low curiosity fitness
        return round(1.0 - base_fitness, 4)

    def _exit_curiosity(self, reason: str) -> None:
        self._state.active = False
        self._state.epochs_remaining = 0
        self._state.discoveries.append(reason)
        self._save()

    def state_summary(self) -> dict[str, Any]:
        import dataclasses
        return dataclasses.asdict(self._state)

    def _load(self) -> None:
        if self.state_path.exists():
            try:
                d = json.loads(self.state_path.read_text())
                self._state = CuriosityState(**d)
            except Exception:
                pass

    def _save(self) -> None:
        import dataclasses
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(
            dataclasses.asdict(self._state), indent=2))


__all__ = ["CuriosityEngine", "CuriosityState",
           "CURIOSITY_INTERVAL", "CURIOSITY_DURATION",
           "HARD_STOP_HEALTH", "HARD_STOP_PATTERNS"]
