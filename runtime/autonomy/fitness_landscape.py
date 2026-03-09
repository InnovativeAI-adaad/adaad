# SPDX-License-Identifier: Apache-2.0
"""
FitnessLandscape — persistent per-mutation-type win/loss tracker.

Purpose:
- Records win/loss counts per mutation_type after each epoch.
- Computes per-type win rates for strategic agent selection.
- Detects fitness plateaus (all tracked types below 20% win rate).
- Recommends the best-fit agent persona for the next epoch.

State is persisted to JSON for cross-epoch continuity.

Phase 2 (active):
  recommended_agent() now uses BanditSelector (UCB1) when total_pulls >= 10.
  Falls back to the v1 decision tree on sparse data (< 10 pulls).
  See docs/EVOLUTION_ARCHITECTURE.md §4.1 and runtime/autonomy/bandit_selector.py.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from runtime.autonomy.bandit_selector import BanditSelector, ThompsonBanditSelector, MIN_PULLS_FOR_BANDIT, AGENTS
from runtime.autonomy.non_stationarity_detector import NonStationarityDetector
# Phase 11-A: AgentBanditSelector override (PR-11-A-02)
from runtime.autonomy.agent_bandit_selector import (
    BanditAgentRecommendation,
    BANDIT_CONFIDENCE_FLOOR,
)

DEFAULT_LANDSCAPE_PATH = Path("data/fitness_landscape_state.json")

PLATEAU_WIN_RATE_THRESHOLD = 0.20   # Below this = type is stagnant
MIN_ATTEMPTS_FOR_PLATEAU   = 3      # Never declare plateau on sparse data


# ---------------------------------------------------------------------------
# TypeRecord
# ---------------------------------------------------------------------------


@dataclass
class TypeRecord:
    """Win/loss ledger for a single mutation_type."""
    mutation_type: str
    wins:          int   = 0
    losses:        int   = 0

    @property
    def attempts(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return round(self.wins / self.attempts, 4)


# ---------------------------------------------------------------------------
# FitnessLandscape
# ---------------------------------------------------------------------------


class FitnessLandscape:
    """
    Strategic memory for the evolution loop.

    Usage:
        landscape = FitnessLandscape()
        landscape.record(mutation_type='structural', won=True)
        agent = landscape.recommended_agent()   # 'architect' | 'dream' | 'beast'
        plateau = landscape.is_plateau()        # True if all types are stagnant
    """

    def __init__(self, state_path: Path = DEFAULT_LANDSCAPE_PATH) -> None:
        self._path    = state_path
        self._records: Dict[str, TypeRecord] = {}
        self._bandit: BanditSelector = BanditSelector()
        self._detector: NonStationarityDetector = NonStationarityDetector()
        self._thompson_active: bool = False
        self._load()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, mutation_type: str, won: bool) -> None:
        """Update win/loss for the given mutation_type."""
        if mutation_type not in self._records:
            self._records[mutation_type] = TypeRecord(mutation_type=mutation_type)
        rec = self._records[mutation_type]
        if won:
            rec.wins += 1
        else:
            rec.losses += 1
        # Feed outcome into bandit arms via type→agent mapping
        from runtime.autonomy.bandit_selector import AGENTS
        _TYPE_TO_AGENT = {"structural": "architect", "performance": "beast", "coverage": "beast"}
        agent_arm = _TYPE_TO_AGENT.get(mutation_type, "dream")
        self._bandit.record(agent_arm, won=won)
        # Feed live win rates into non-stationarity detector every record
        live_rates = {
            agent: self._bandit._arms[agent].win_rate
            for agent in AGENTS
            if agent in self._bandit._arms
        }
        if live_rates:
            self._detector.record(live_rates)
        # Escalate to Thompson Sampling if shift detected
        if self._detector.is_non_stationary() and self._bandit.is_active:
            self._thompson_active = True
        self._save()

    # ------------------------------------------------------------------
    # Strategy queries
    # ------------------------------------------------------------------

    def is_plateau(self, min_attempts: int = MIN_ATTEMPTS_FOR_PLATEAU) -> bool:
        """
        Return True when ALL tracked mutation types with >= min_attempts
        attempts have a win_rate below PLATEAU_WIN_RATE_THRESHOLD.

        Returns False when no types have been tracked enough — plateau is
        never declared prematurely on sparse data.
        """
        tracked = [r for r in self._records.values() if r.attempts >= min_attempts]
        if not tracked:
            return False
        return all(r.win_rate < PLATEAU_WIN_RATE_THRESHOLD for r in tracked)

    def best_mutation_type(self) -> Optional[str]:
        """Return the mutation_type with the highest win_rate, or None."""
        if not self._records:
            return None
        best = max(self._records.values(), key=lambda r: r.win_rate)
        return best.mutation_type if best.attempts > 0 else None

    def recommended_agent(
        self,
        bandit_rec: "Optional[BanditAgentRecommendation]" = None,
    ) -> str:
        """
        Return the recommended agent persona for the next epoch.

        Phase 11-A extension (Phase 0d override):
          0. If bandit_rec is provided and is_active=True and confidence >= BANDIT_CONFIDENCE_FLOOR:
             AgentBanditSelector (float reward) overrides all lower tiers.

        Phase 2 (UCB1 active when total_pulls >= MIN_PULLS_FOR_BANDIT):
          1. Plateau check always takes precedence — return 'dream' for max exploration.
          2. If bandit is active: delegate to BanditSelector.select() (UCB1).
          3. If bandit is inactive (sparse data): v1 decision tree fallback.

        UCB1 algorithm:
          score(agent) = win_rate(agent) + sqrt(2) × sqrt(ln(total_pulls) / pulls(agent))
          Unpulled arms score +inf (guaranteed exploration).
        """
        # Phase 11-A: reward-profile bandit override (PR-11-A-02)
        if (
            bandit_rec is not None
            and bandit_rec.is_active
            and bandit_rec.confidence >= BANDIT_CONFIDENCE_FLOOR
            and bandit_rec.agent in AGENTS
        ):
            return bandit_rec.agent

        if self.is_plateau():
            return "dream"

        # Phase 3: Thompson Sampling when non-stationarity detected
        if self._thompson_active and self._bandit.is_active:
            import hashlib, random
            # Deterministic rng seeded from current arm state hash
            state_seed = abs(hash(str(sorted(
                (a, arm.wins, arm.losses)
                for a, arm in self._bandit._arms.items()
            )))) % (2**31)
            rng = random.Random(state_seed)
            thompson = ThompsonBanditSelector(rng=rng)
            for agent, arm in self._bandit._arms.items():
                for _ in range(arm.wins):
                    thompson.record(agent, won=True)
                for _ in range(arm.losses):
                    thompson.record(agent, won=False)
            return thompson.select()

        # Phase 2: UCB1 bandit when enough data has been collected
        if self._bandit.is_active:
            return self._bandit.select()

        # Phase 1 fallback: deterministic decision tree (sparse data guard)
        best_type = self.best_mutation_type()
        if best_type == "structural":
            return "architect"
        if best_type in ("performance", "coverage"):
            return "beast"
        return "beast"

    def summary(self) -> Dict[str, object]:
        """Return a serialisable summary for logging and health endpoints."""
        return {
            "types": {
                t: {"wins": r.wins, "losses": r.losses, "win_rate": r.win_rate}
                for t, r in self._records.items()
            },
            "is_plateau":           self.is_plateau(),
            "recommended_agent":    self.recommended_agent(),
            "best_mutation_type":   self.best_mutation_type(),
            "bandit":               self._bandit.summary(),
            "non_stationarity":     self._detector.arm_statistics(),
            "thompson_active":      self._thompson_active,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "records": {
                t: {"wins": r.wins, "losses": r.losses}
                for t, r in self._records.items()
            },
            "bandit": self._bandit.to_state(),
            "thompson_active": self._thompson_active,
            "saved_at": time.time(),
        }
        self._path.write_text(json.dumps(state, indent=2))

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            state = json.loads(self._path.read_text())
            for mut_type, data in state.get("records", {}).items():
                rec = TypeRecord(mutation_type=mut_type)
                rec.wins   = int(data.get("wins",   0))
                rec.losses = int(data.get("losses", 0))
                self._records[mut_type] = rec
            if "bandit" in state:
                try:
                    self._bandit = BanditSelector.from_state(state["bandit"])
                except Exception:  # pragma: no cover — corrupt bandit state, reset
                    self._bandit = BanditSelector()
            self._thompson_active = bool(state.get("thompson_active", False))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Corrupt state — start fresh
