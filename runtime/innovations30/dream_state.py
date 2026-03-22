# SPDX-License-Identifier: Apache-2.0
"""Innovation #11 — Cross-Epoch Dream State.

Between active epochs, replays past mutations in novel combinations
to discover improvements not available at the time.
Memory consolidation for software evolution.
"""
from __future__ import annotations
import hashlib, json, random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DREAM_DEPTH: int = 100       # how many past epochs to dream from
DREAM_CANDIDATES: int = 5    # number of dream candidates per cycle
DREAM_MIN_SCORE: float = 0.60


@dataclass
class DreamCandidate:
    candidate_id: str
    source_epochs: list[str]     # which epochs were combined
    combined_intent: str
    recombined_ops: list[dict[str, Any]]
    predicted_fitness: float
    novelty_score: float          # how different from recent proposals
    genesis_digest: str = ""

    def __post_init__(self):
        if not self.genesis_digest:
            payload = json.dumps({"id": self.candidate_id,
                                   "epochs": self.source_epochs}, sort_keys=True)
            self.genesis_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class DreamStateEngine:
    """Generates novel proposals by recombining successful past mutations."""

    def __init__(self, state_path: Path = Path("data/dream_candidates.jsonl"),
                 depth: int = DREAM_DEPTH, seed: int | None = None):
        self.state_path = Path(state_path)
        self.depth = depth
        self._rng = random.Random(seed or 42)  # deterministic by default

    def dream(self, epoch_memory: list[dict[str, Any]],
               epoch_id: str) -> list[DreamCandidate]:
        """
        epoch_memory: list of EpochMemoryEntry dicts with keys:
            epoch_id, winning_agent, winning_mutation_type, fitness_delta, ...
        """
        if len(epoch_memory) < 3:
            return []

        pool = epoch_memory[-self.depth:]
        successful = [e for e in pool if e.get("fitness_delta", 0) > 0]
        if len(successful) < 2:
            return []

        candidates = []
        seen_combos: set[str] = set()

        for _ in range(DREAM_CANDIDATES * 3):  # overshoot, filter later
            if len(candidates) >= DREAM_CANDIDATES:
                break
            # Pick 2 random successful epochs to combine
            pair = self._rng.sample(successful, 2)
            combo_key = "|".join(sorted(e["epoch_id"] for e in pair))
            if combo_key in seen_combos:
                continue
            seen_combos.add(combo_key)

            combined_intent = self._combine_intents(pair)
            predicted = min(1.0, (pair[0].get("fitness_delta", 0) +
                                   pair[1].get("fitness_delta", 0)) * 0.7)
            if predicted < DREAM_MIN_SCORE * 0.5:
                continue

            novelty = self._compute_novelty(pair, successful)
            cid = f"DREAM-{epoch_id[:8]}-{len(candidates):02d}"
            c = DreamCandidate(
                candidate_id=cid,
                source_epochs=[e["epoch_id"] for e in pair],
                combined_intent=combined_intent,
                recombined_ops=self._recombine_ops(pair),
                predicted_fitness=round(predicted, 4),
                novelty_score=round(novelty, 4),
            )
            candidates.append(c)

        # Sort by predicted * novelty
        candidates.sort(key=lambda c: c.predicted_fitness * c.novelty_score, reverse=True)
        self._persist(candidates)
        return candidates[:DREAM_CANDIDATES]

    def _combine_intents(self, pair: list[dict]) -> str:
        intents = [e.get("winning_mutation_type", "unknown") for e in pair]
        strategies = [e.get("winning_strategy_id", "") for e in pair]
        return f"Dream combination: {intents[0]} + {intents[1]} ({strategies[0]}→{strategies[1]})"

    def _recombine_ops(self, pair: list[dict]) -> list[dict[str, Any]]:
        return [{"op": "dream_combine",
                  "source_a": pair[0]["epoch_id"],
                  "source_b": pair[1]["epoch_id"],
                  "mutation_type_a": pair[0].get("winning_mutation_type"),
                  "mutation_type_b": pair[1].get("winning_mutation_type")}]

    def _compute_novelty(self, pair: list[dict], all_recent: list[dict]) -> float:
        """How different is this combination from what was recently tried?"""
        pair_types = {e.get("winning_mutation_type") for e in pair}
        recent_types = {e.get("winning_mutation_type") for e in all_recent[-10:]}
        overlap = len(pair_types & recent_types) / max(1, len(pair_types))
        return 1.0 - (overlap * 0.5)

    def _persist(self, candidates: list[DreamCandidate]) -> None:
        import dataclasses
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("a") as f:
            for c in candidates:
                f.write(json.dumps(dataclasses.asdict(c)) + "\n")


__all__ = ["DreamStateEngine", "DreamCandidate",
           "DREAM_DEPTH", "DREAM_CANDIDATES", "DREAM_MIN_SCORE"]
