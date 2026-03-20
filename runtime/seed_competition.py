# SPDX-License-Identifier: Apache-2.0
"""Phase 80 — SeedCompetitionOrchestrator.

Multi-seed competitive evaluation: ranks candidate seeds by fitness score,
enforces population-level GovernanceGate evaluation, and writes a
SeedCompetitionEpochEvent to LineageLedgerV2 *before* any candidate is promoted.

Constitutional Invariants
─────────────────────────
  SEED-COMP-0    No seed is promoted without passing competitive ranking
                 against all candidates in the same epoch window.
  SEED-RANK-0    Fitness ranking is deterministic — equal inputs produce
                 identical rank orderings. Ties broken lexicographically by
                 candidate_id.
  COMP-GOV-0     GovernanceGate evaluates all candidates before any single
                 candidate advances.
  COMP-LEDGER-0  SeedCompetitionEpochEvent written to LineageLedgerV2 before
                 any promotion.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / phase metadata
# ---------------------------------------------------------------------------

_PHASE = 80
_VERSION_FILE = "VERSION"


def _read_version() -> str:
    try:
        from pathlib import Path

        vf = Path(__file__).parent.parent / _VERSION_FILE
        return vf.read_text().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedCandidate:
    """A single seed candidate entering competition.

    Attributes
    ----------
    candidate_id:   Unique identifier for this seed (stable across calls).
    fitness_context: Mapping passed verbatim to FitnessOrchestrator.score().
    metadata:       Arbitrary governance metadata (e.g. origin epoch, agent_id).
    """

    candidate_id: str
    fitness_context: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompetitionResult:
    """Outcome of one competitive epoch.

    Attributes
    ----------
    epoch_id:        Unique competition epoch ID.
    winner_id:       candidate_id of the promoted seed.
    ranked_ids:      All candidate IDs sorted highest→lowest fitness.
    fitness_scores:  Mapping candidate_id → float score.
    gate_verdict:    'pass' | 'fail' | 'deferred'.
    ledger_entry:    Raw dict written to LineageLedgerV2.
    competition_digest: SHA-256 hex of canonical scoring inputs.
    """

    epoch_id: str
    winner_id: str
    ranked_ids: List[str]
    fitness_scores: Dict[str, float]
    gate_verdict: str
    ledger_entry: Dict[str, Any]
    competition_digest: str


# ---------------------------------------------------------------------------
# Digest helpers  (SEED-RANK-0 determinism)
# ---------------------------------------------------------------------------


def _competition_digest(
    candidate_ids: List[str], fitness_scores: Dict[str, float]
) -> str:
    """Deterministic SHA-256 of competition inputs.

    Canonical form: sorted candidate_ids + sorted fitness_scores mapping.
    Equal inputs → identical digest (SEED-RANK-0).
    """
    payload = {
        "candidate_ids": sorted(candidate_ids),
        "fitness_scores": {k: fitness_scores[k] for k in sorted(fitness_scores)},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _rank_candidates(fitness_scores: Dict[str, float]) -> List[str]:
    """Return candidate_ids sorted highest-score first; ties broken by id asc.

    SEED-RANK-0: deterministic — equal inputs → identical ordering.
    """
    return sorted(
        fitness_scores.keys(),
        key=lambda cid: (-fitness_scores[cid], cid),
    )


# ---------------------------------------------------------------------------
# GovernanceGate protocol (injectable for testing)
# ---------------------------------------------------------------------------

GateEvaluateFn = Callable[[str, Dict[str, Any]], str]
"""Signature: (candidate_id, candidate_metadata) → 'pass' | 'fail' | 'deferred'."""


def _default_gate_fn(candidate_id: str, metadata: Dict[str, Any]) -> str:  # noqa: ARG001
    """Permissive default used when no GovernanceGate is wired.

    Production callers must inject a real gate.
    """
    log.warning(
        "COMP-GOV-0: no GovernanceGate injected; using permissive default. "
        "Inject a real gate before production use."
    )
    return "pass"


# ---------------------------------------------------------------------------
# SeedCompetitionOrchestrator
# ---------------------------------------------------------------------------


class SeedCompetitionOrchestrator:
    """Phase 80 population-level competition runner.

    Lifecycle per epoch
    ───────────────────
    1. Accept N SeedCandidates.
    2. Score all candidates via FitnessOrchestrator (COMP-GOV-0 pre-condition).
    3. Rank by fitness score (SEED-RANK-0).
    4. Evaluate all candidates through GovernanceGate (COMP-GOV-0).
    5. Write SeedCompetitionEpochEvent to LineageLedgerV2 (COMP-LEDGER-0).
    6. Return CompetitionResult — winner = highest-ranked candidate that passed gate.

    Raises
    ------
    ValueError  If candidates list is empty.
    RuntimeError  If all candidates fail GovernanceGate (no winner resolvable).
    """

    def __init__(
        self,
        *,
        fitness_orchestrator: Optional[Any] = None,
        ledger: Optional[Any] = None,
        gate_fn: Optional[GateEvaluateFn] = None,
        epoch_id_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        """
        Parameters
        ----------
        fitness_orchestrator: FitnessOrchestrator instance. Instantiated if None.
        ledger:               LineageLedgerV2 instance. Instantiated if None.
        gate_fn:              Callable(candidate_id, metadata) → verdict.
                              Defaults to permissive stub; wire real gate in prod.
        epoch_id_factory:     Callable → epoch_id string. Defaults to uuid4.
        """
        if fitness_orchestrator is None:
            from runtime.evolution.fitness_orchestrator import FitnessOrchestrator

            fitness_orchestrator = FitnessOrchestrator()

        if ledger is None:
            from runtime.evolution.lineage_v2 import LineageLedgerV2

            ledger = LineageLedgerV2()

        self._orchestrator = fitness_orchestrator
        self._ledger = ledger
        self._gate_fn: GateEvaluateFn = gate_fn or _default_gate_fn
        self._epoch_id_factory = epoch_id_factory or (lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_epoch(self, candidates: Sequence[SeedCandidate]) -> CompetitionResult:
        """Execute one competitive epoch across all candidates.

        Invariants enforced:
          SEED-COMP-0  — all candidates scored before any promotion decision
          SEED-RANK-0  — deterministic ranking
          COMP-GOV-0   — gate evaluates every candidate before winner selected
          COMP-LEDGER-0 — ledger entry written before winner returned
        """
        if not candidates:
            raise ValueError("SEED-COMP-0: candidates list must not be empty")

        epoch_id = self._epoch_id_factory()
        log.info("COMP: starting competition epoch %s with %d candidates", epoch_id, len(candidates))

        # ── Step 1: Score all candidates (SEED-COMP-0) ──────────────────────
        fitness_scores: Dict[str, float] = {}
        for c in candidates:
            result = self._orchestrator.score(c.fitness_context)
            fitness_scores[c.candidate_id] = float(result.total_score)
            log.debug("COMP: candidate %s score=%.4f", c.candidate_id, fitness_scores[c.candidate_id])

        # ── Step 2: Rank (SEED-RANK-0 deterministic) ────────────────────────
        candidate_ids = [c.candidate_id for c in candidates]
        ranked_ids = _rank_candidates(fitness_scores)
        digest = _competition_digest(candidate_ids, fitness_scores)

        # ── Step 3: Gate all candidates (COMP-GOV-0) ────────────────────────
        meta_map: Dict[str, Dict[str, Any]] = {c.candidate_id: c.metadata for c in candidates}
        gate_verdicts: Dict[str, str] = {}
        for cid in ranked_ids:
            verdict = self._gate_fn(cid, meta_map.get(cid, {}))
            gate_verdicts[cid] = verdict
            log.debug("COMP: gate verdict for %s: %s", cid, verdict)

        # ── Step 4: Select winner (highest-ranked passer / deferred) ──────
        winner_id: Optional[str] = None
        deferred_winner: Optional[str] = None
        overall_verdict = "fail"
        for cid in ranked_ids:
            if gate_verdicts[cid] == "pass":
                winner_id = cid
                overall_verdict = "pass"
                break
            if gate_verdicts[cid] == "deferred" and deferred_winner is None:
                deferred_winner = cid

        if winner_id is None and deferred_winner is not None:
            # No outright pass — top-ranked deferred candidate advances tentatively
            winner_id = deferred_winner
            overall_verdict = "deferred"

        if winner_id is None:
            # All candidates failed gate — write ledger before raising (COMP-LEDGER-0)
            winner_id = ranked_ids[0]  # record top candidate even in failure
            overall_verdict = "fail"
            log.error(
                "COMP-GOV-0: all candidates failed gate in epoch %s — no promotion",
                epoch_id,
            )

        # ── Step 5: Write ledger (COMP-LEDGER-0) — before any return ────────
        from runtime.evolution.lineage_v2 import SeedCompetitionEpochEvent

        event = SeedCompetitionEpochEvent(
            epoch_id=epoch_id,
            candidate_ids=sorted(candidate_ids),
            ranked_ids=ranked_ids,
            winner_id=winner_id,
            fitness_scores=fitness_scores,
            gate_verdict=overall_verdict,
            competition_digest=digest,
            phase=_PHASE,
            version=_read_version(),
        )
        ledger_entry = self._ledger.append_competition_epoch(event)
        log.info(
            "COMP-LEDGER-0: wrote SeedCompetitionEpochEvent epoch=%s winner=%s verdict=%s",
            epoch_id, winner_id, overall_verdict,
        )

        # ── Step 6: Raise if all failed (after ledger write) ─────────────────
        if overall_verdict == "fail":
            raise RuntimeError(
                f"COMP-GOV-0: all candidates failed GovernanceGate in epoch {epoch_id}. "
                "No seed promoted. Ledger entry written."
            )

        return CompetitionResult(
            epoch_id=epoch_id,
            winner_id=winner_id,
            ranked_ids=ranked_ids,
            fitness_scores=fitness_scores,
            gate_verdict=overall_verdict,
            ledger_entry=ledger_entry,
            competition_digest=digest,
        )
