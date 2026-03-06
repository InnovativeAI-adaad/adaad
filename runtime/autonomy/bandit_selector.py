# SPDX-License-Identifier: Apache-2.0
"""
BanditSelector — UCB1 multi-armed bandit agent selection for ADAAD Phase 2.

Purpose:
    Replace the FitnessLandscape decision tree with a principled exploration/
    exploitation strategy. UCB1 (Upper Confidence Bound) balances:
      - Exploitation: prefer agents with high observed win rates.
      - Exploration:  guarantee under-sampled agents are tried.

Algorithm (UCB1):
    score(agent) = win_rate(agent) + C × sqrt(ln(total_pulls) / pulls(agent))

    where C is the exploration constant (default: sqrt(2) ≈ 1.4142).
    An agent with zero pulls receives +inf score (forced exploration).

Activation contract:
    - BanditSelector activates when total_pulls >= MIN_PULLS_FOR_BANDIT (10).
    - Below threshold, FitnessLandscape falls back to the v1 decision tree.
    - This prevents premature bandit lock-in on sparse data.

Determinism contract:
    - All arithmetic uses only float operations on deterministic inputs.
    - No random sampling in UCB1 mode (Thompson Sampling is a separate path).
    - select() is a pure function: identical inputs → identical output.

Constitutional invariant:
    - BanditSelector is ADVISORY only. GovernanceGate is never invoked here.
    - Agent recommendation is an input to EvolutionLoop; it does not approve
      or execute mutations.

Extension point (Phase 3):
    ThompsonBanditSelector (see docstring below) — samples from Beta(α, β)
    per agent; higher variance exploration suitable for non-stationary reward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

# --- Constants ----------------------------------------------------------------

EXPLORATION_CONSTANT: float = math.sqrt(2)   # UCB1 standard value
MIN_PULLS_FOR_BANDIT: int   = 10             # Minimum total pulls before activation
AGENTS: tuple[str, ...] = ("architect", "dream", "beast")


# --- Arm state ----------------------------------------------------------------

@dataclass
class ArmState:
    """Win/loss state for one bandit arm (agent persona)."""
    agent:   str
    wins:    int = 0
    losses:  int = 0

    @property
    def pulls(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        if self.pulls == 0:
            return 0.0
        return self.wins / self.pulls

    def ucb1_score(self, total_pulls: int, exploration_c: float = EXPLORATION_CONSTANT) -> float:
        """
        Compute UCB1 score.

        Unpulled arms return +inf to guarantee they are explored first.
        Total pulls = 0 returns 0 (degenerate — should not occur post-activation).
        """
        if self.pulls == 0:
            return float("inf")
        if total_pulls <= 0:
            return self.win_rate
        exploration_bonus = exploration_c * math.sqrt(math.log(total_pulls) / self.pulls)
        return self.win_rate + exploration_bonus

    def to_dict(self) -> dict:
        return {
            "agent":    self.agent,
            "wins":     self.wins,
            "losses":   self.losses,
            "pulls":    self.pulls,
            "win_rate": round(self.win_rate, 4),
        }


# --- BanditSelector -----------------------------------------------------------

class BanditSelector:
    """
    UCB1 multi-armed bandit for agent persona selection.

    Usage:
        bandit = BanditSelector()
        agent  = bandit.select()           # 'architect' | 'dream' | 'beast'
        bandit.record('architect', won=True)
        summary = bandit.summary()

    Seeding from existing FitnessLandscape records:
        bandit = BanditSelector.from_landscape_records({
            'structural': {'wins': 5, 'losses': 3},
            ...
        }, agent_type_map={'structural': 'architect', ...})
    """

    def __init__(
        self,
        exploration_c: float = EXPLORATION_CONSTANT,
        agents: Sequence[str] = AGENTS,
    ) -> None:
        self._c = exploration_c
        self._arms: Dict[str, ArmState] = {
            a: ArmState(agent=a) for a in agents
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def total_pulls(self) -> int:
        return sum(arm.pulls for arm in self._arms.values())

    @property
    def is_active(self) -> bool:
        """True when enough data has been collected for reliable bandit selection."""
        return self.total_pulls >= MIN_PULLS_FOR_BANDIT

    def record(self, agent: str, won: bool) -> None:
        """Record an outcome for the given agent arm."""
        if agent not in self._arms:
            self._arms[agent] = ArmState(agent=agent)
        arm = self._arms[agent]
        if won:
            arm.wins += 1
        else:
            arm.losses += 1

    def select(self) -> str:
        """
        Return the agent with the highest UCB1 score.

        Tie-breaking: alphabetical order (deterministic).
        If below MIN_PULLS threshold: returns None (caller falls back to v1).
        """
        n = self.total_pulls
        scored = sorted(
            self._arms.values(),
            key=lambda arm: (-arm.ucb1_score(n, self._c), arm.agent),
        )
        return scored[0].agent

    def best_exploit(self) -> str:
        """Return the agent with the highest raw win_rate (pure exploitation)."""
        best = max(self._arms.values(), key=lambda arm: (arm.win_rate, -arm.pulls))
        return best.agent

    def ucb1_scores(self) -> Dict[str, float]:
        """Return current UCB1 score for every arm. Pure exploitation check."""
        n = self.total_pulls
        return {
            agent: round(arm.ucb1_score(n, self._c), 6)
            for agent, arm in self._arms.items()
        }

    def summary(self) -> dict:
        """Serialisable state snapshot for logging and health endpoints."""
        return {
            "algorithm":      "ucb1",
            "exploration_c":  round(self._c, 6),
            "total_pulls":    self.total_pulls,
            "is_active":      self.is_active,
            "min_pulls":      MIN_PULLS_FOR_BANDIT,
            "selected":       self.select() if self.total_pulls > 0 else None,
            "ucb1_scores":    self.ucb1_scores(),
            "arms":           {a: arm.to_dict() for a, arm in self._arms.items()},
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_state(self) -> dict:
        """Export state for JSON persistence alongside FitnessLandscape."""
        return {
            "algorithm":     "ucb1",
            "exploration_c": self._c,
            "arms": {
                agent: {"wins": arm.wins, "losses": arm.losses}
                for agent, arm in self._arms.items()
            },
        }

    @classmethod
    def from_state(cls, state: dict, agents: Sequence[str] = AGENTS) -> "BanditSelector":
        """Restore from persisted state dict."""
        selector = cls(
            exploration_c=float(state.get("exploration_c", EXPLORATION_CONSTANT)),
            agents=agents,
        )
        for agent, data in state.get("arms", {}).items():
            if agent in selector._arms:
                selector._arms[agent].wins   = int(data.get("wins",   0))
                selector._arms[agent].losses = int(data.get("losses", 0))
        return selector

    @classmethod
    def from_landscape_records(
        cls,
        records: Dict[str, Dict[str, int]],
        agent_type_map: Optional[Dict[str, str]] = None,
    ) -> "BanditSelector":
        """
        Bootstrap a BanditSelector from FitnessLandscape TypeRecord data.

        agent_type_map maps mutation_type → agent persona. Default mapping:
            'structural' → 'architect'
            'performance', 'coverage' → 'beast'
            everything else → 'dream'
        """
        default_map: Dict[str, str] = {
            "structural":  "architect",
            "performance": "beast",
            "coverage":    "beast",
        }
        amap = {**default_map, **(agent_type_map or {})}
        selector = cls()
        for mut_type, data in records.items():
            agent = amap.get(mut_type, "dream")
            wins   = int(data.get("wins",   0))
            losses = int(data.get("losses", 0))
            for _ in range(wins):
                selector.record(agent, won=True)
            for _ in range(losses):
                selector.record(agent, won=False)
        return selector


# --- ThompsonBanditSelector (Phase 3 extension point) -----------------------

class ThompsonBanditSelector:
    """
    Thompson Sampling bandit selector — Phase 3 extension point.

    Samples from Beta(wins+1, losses+1) per agent and selects the highest
    sample. More adaptive than UCB1 for non-stationary reward distributions.

    NOTE: Thompson Sampling uses random sampling (rng parameter). To preserve
    determinism, callers MUST supply a seeded random.Random instance derived
    from the epoch_id:

        import random, hashlib
        seed = int(hashlib.sha256(epoch_id.encode()).hexdigest(), 16) % (2**31)
        rng  = random.Random(seed)
        bandit = ThompsonBanditSelector(rng=rng)

    This class is NOT activated in v2.0.0. It is present as a verified
    extension point pending Phase 3 ArchitectAgent approval.
    """

    def __init__(self, rng: "random.Random", agents: Sequence[str] = AGENTS) -> None:  # type: ignore[name-defined]
        self._rng  = rng
        self._arms: Dict[str, ArmState] = {a: ArmState(agent=a) for a in agents}

    def record(self, agent: str, won: bool) -> None:
        if agent not in self._arms:
            self._arms[agent] = ArmState(agent=agent)
        arm = self._arms[agent]
        if won:
            arm.wins += 1
        else:
            arm.losses += 1

    def select(self) -> str:
        """Sample from Beta(α, β) per arm; return arm with highest sample."""
        # betavariate(alpha, beta): alpha = wins+1, beta = losses+1
        samples = {
            agent: self._rng.betavariate(arm.wins + 1, arm.losses + 1)
            for agent, arm in self._arms.items()
        }
        return max(samples, key=lambda a: (samples[a], a))


__all__ = [
    "ArmState",
    "BanditSelector",
    "ThompsonBanditSelector",
    "EXPLORATION_CONSTANT",
    "MIN_PULLS_FOR_BANDIT",
    "AGENTS",
]
