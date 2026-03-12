# SPDX-License-Identifier: Apache-2.0
"""
LearningSignalExtractor — derives actionable learning signals from EpochMemoryStore.

Purpose:
    Transform raw cross-epoch memory into structured guidance that the
    AI mutation proposer can inject into agent prompts. The extractor is
    a pure function over the memory window — it has no side effects and
    produces deterministic output given identical input.

Constitutional invariants:
    - LEARNING-0: All outputs are ADVISORY only. GovernanceGate is never
      invoked here. Learning signals cannot approve, reject, or promote
      mutations.
    - LEARNING-1: Output is deterministic on identical window input.
      No wall-clock time, no random sampling, no mutable global state.
    - LEARNING-2: On empty or invalid window, extractor returns
      LearningSignal.empty() — a safe zero-signal state. Callers must
      treat LearningSignal as optional enrichment, not a hard requirement.
    - LEARNING-3: All scores are bounded to [0.0, 1.0]. Scores outside
      this range are clamped before output.

Output contract (LearningSignal):
    top_agents:           list of (agent, win_rate) sorted by win_rate desc
    top_strategies:       list of (strategy_id, win_rate) sorted desc
    avg_fitness_delta:    float ∈ [-1.0, 1.0] — mean fitness change over window
    acceptance_rate:      float ∈ [0.0, 1.0]
    signal_digest:        SHA-256 of canonical signal fields (determinism audit)
    window_epochs:        int — number of epochs in the window
    signal_version:       str — "52.0"

Prompt injection format:
    LearningSignal.as_prompt_block() returns a human-readable block
    suitable for appending to the soulbound_annotation field in
    CodebaseContext, or as a standalone suffix in agent system prompts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from runtime.autonomy.epoch_memory_store import EpochMemoryEntry, EpochMemoryStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SIGNAL_VERSION: str = "52.0"
TOP_N: int = 3   # top-N agents and strategies to surface in signal


# ---------------------------------------------------------------------------
# LearningSignal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearningSignal:
    """
    Structured learning guidance derived from cross-epoch memory.

    All scores are in [0.0, 1.0]; all lists are sorted descending by score.
    """

    top_agents: Tuple[Tuple[str, float], ...]       # (agent_name, win_rate)
    top_strategies: Tuple[Tuple[str, float], ...]   # (strategy_id, win_rate)
    avg_fitness_delta: float                         # mean fitness delta over window
    acceptance_rate: float                           # fraction of proposals accepted
    signal_digest: str                               # SHA-256 of canonical fields
    window_epochs: int                               # number of epochs used
    signal_version: str = _SIGNAL_VERSION

    # ------------------------------------------------------------------

    @classmethod
    def empty(cls) -> "LearningSignal":
        """Safe zero-signal state returned when window is empty or invalid."""
        return cls(
            top_agents=(),
            top_strategies=(),
            avg_fitness_delta=0.0,
            acceptance_rate=0.0,
            signal_digest="0" * 64,
            window_epochs=0,
        )

    def is_empty(self) -> bool:
        return self.window_epochs == 0

    def as_prompt_block(self) -> str:
        """
        Human-readable block for injection into agent prompts.

        Designed to fit within 300 tokens. Agents must treat this as
        advisory context, not a directive.
        """
        if self.is_empty():
            return ""

        lines = [
            "--- Cross-epoch learning signal (ADVISORY — do not follow blindly) ---",
            f"Window: {self.window_epochs} epoch(s)  |  Avg fitness delta: {self.avg_fitness_delta:+.4f}"
            f"  |  Acceptance rate: {self.acceptance_rate:.2%}",
        ]

        if self.top_agents:
            agent_strs = ", ".join(f"{a}({r:.0%})" for a, r in self.top_agents)
            lines.append(f"Top-performing agents: {agent_strs}")

        if self.top_strategies:
            strat_strs = ", ".join(f"{s}({r:.0%})" for s, r in self.top_strategies)
            lines.append(f"Top-performing strategies: {strat_strs}")

        if self.avg_fitness_delta > 0.05:
            lines.append("Trend: positive fitness growth — continue current approach.")
        elif self.avg_fitness_delta < -0.05:
            lines.append("Trend: fitness declining — consider conservative or structural mutations.")
        else:
            lines.append("Trend: stable — balanced exploration/exploitation recommended.")

        lines.append("--- end learning signal ---")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "top_agents": list(self.top_agents),
            "top_strategies": list(self.top_strategies),
            "avg_fitness_delta": self.avg_fitness_delta,
            "acceptance_rate": self.acceptance_rate,
            "signal_digest": self.signal_digest,
            "window_epochs": self.window_epochs,
            "signal_version": self.signal_version,
        }


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class LearningSignalExtractor:
    """
    Stateless extractor — derives LearningSignal from an EpochMemoryStore.

    Usage::

        extractor = LearningSignalExtractor()
        signal = extractor.extract(store)
        # Inject into CodebaseContext:
        ctx = CodebaseContext(..., learning_context=signal.as_prompt_block())
    """

    def __init__(self, top_n: int = TOP_N) -> None:
        self._top_n = top_n

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, store: EpochMemoryStore) -> LearningSignal:
        """
        Derive a LearningSignal from the store's current window.

        Deterministic: identical window → identical output.
        Returns LearningSignal.empty() on empty window.
        """
        entries = store.window()
        if not entries:
            return LearningSignal.empty()

        agent_wins: Dict[str, int] = {}
        agent_totals: Dict[str, int] = {}
        strat_wins: Dict[str, int] = {}
        strat_totals: Dict[str, int] = {}
        total_fitness = 0.0
        total_proposals = 0
        total_accepted = 0

        for entry in entries:
            if entry.winning_agent:
                a = entry.winning_agent
                agent_wins[a] = agent_wins.get(a, 0) + 1
                agent_totals[a] = agent_totals.get(a, 0) + 1
            # Count all agents as "participated" (wins tracked above, total = epoch count per agent seen)
            if entry.winning_strategy_id:
                s = entry.winning_strategy_id
                strat_wins[s] = strat_wins.get(s, 0) + 1
                strat_totals[s] = strat_totals.get(s, 0) + 1
            total_fitness += entry.fitness_delta
            total_proposals += entry.proposal_count
            total_accepted += entry.accepted_count

        n = len(entries)
        avg_fitness = round(total_fitness / n, 6) if n else 0.0

        # Win rates: wins / n (fraction of epochs an agent/strategy won)
        agent_rates: List[Tuple[str, float]] = [
            (a, round(agent_wins.get(a, 0) / n, 4))
            for a in sorted(agent_wins.keys())
        ]
        agent_rates.sort(key=lambda x: (-x[1], x[0]))   # desc win_rate, alpha tie-break

        strat_rates: List[Tuple[str, float]] = [
            (s, round(strat_wins.get(s, 0) / n, 4))
            for s in sorted(strat_wins.keys())
        ]
        strat_rates.sort(key=lambda x: (-x[1], x[0]))

        top_agents = tuple(agent_rates[: self._top_n])
        top_strategies = tuple(strat_rates[: self._top_n])
        acceptance_rate = round(total_accepted / total_proposals, 4) if total_proposals else 0.0

        # Clamp avg_fitness to [-1.0, 1.0]
        avg_fitness = max(-1.0, min(1.0, avg_fitness))

        digest = self._compute_digest(
            top_agents=top_agents,
            top_strategies=top_strategies,
            avg_fitness_delta=avg_fitness,
            acceptance_rate=acceptance_rate,
            window_epochs=n,
        )

        return LearningSignal(
            top_agents=top_agents,
            top_strategies=top_strategies,
            avg_fitness_delta=avg_fitness,
            acceptance_rate=acceptance_rate,
            signal_digest=digest,
            window_epochs=n,
        )

    def extract_from_entries(self, entries: List[EpochMemoryEntry]) -> LearningSignal:
        """
        Derive LearningSignal directly from a list of entries (for testing /
        federation scenarios where a store object is not available).
        """
        from runtime.autonomy.epoch_memory_store import EpochMemoryStore, STORE_DEFAULT_PATH
        import tempfile, os
        from pathlib import Path

        # Create an in-memory-equivalent store backed by a temp file
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            tmp_path = Path(f.name)
        try:
            store = EpochMemoryStore(path=tmp_path, window_size=len(entries) + 1)
            for e in entries:
                store.emit(
                    epoch_id=e.epoch_id,
                    winning_agent=e.winning_agent,
                    winning_mutation_type=e.winning_mutation_type,
                    winning_strategy_id=e.winning_strategy_id,
                    fitness_delta=e.fitness_delta,
                    proposal_count=e.proposal_count,
                    accepted_count=e.accepted_count,
                    context_hash=e.context_hash,
                    constitution_version=e.constitution_version,
                )
            return self.extract(store)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_digest(
        *,
        top_agents: Tuple[Tuple[str, float], ...],
        top_strategies: Tuple[Tuple[str, float], ...],
        avg_fitness_delta: float,
        acceptance_rate: float,
        window_epochs: int,
    ) -> str:
        canonical = json.dumps(
            {
                "top_agents": list(top_agents),
                "top_strategies": list(top_strategies),
                "avg_fitness_delta": round(float(avg_fitness_delta), 6),
                "acceptance_rate": round(float(acceptance_rate), 4),
                "window_epochs": window_epochs,
                "signal_version": _SIGNAL_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
