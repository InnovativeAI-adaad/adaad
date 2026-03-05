# SPDX-License-Identifier: Apache-2.0
"""DarwinianSelectionPipeline — ADAAD-11 PR-11-02.

Post-fitness hook that couples FitnessOrchestrator scores to BudgetArbitrator,
completing the Darwinian selection loop:

  FitnessOrchestrator.score(context)   ← live market signal (ADAAD-10)
         │
         ▼
  DarwinianSelectionPipeline.run(epoch_fitness_map)
         │  Softmax over agent fitness scores + market pressure scalar
         ▼
  BudgetArbitrator.arbitrate(pool, scores, market_scalar)
         │  reallocates shares; starves/evicts low-fitness agents
         ▼
  CompetitionLedger.record_arbitration(result)
         │  append-only audit trail; sha256 digest per event
         ▼
  Governance journal: darwinian_selection_complete.v1

Authority invariant: pipeline reallocates budget; it never approves or
executes mutations. Budget share is an advisory resource signal only —
the constitutional evaluation gate remains the sole execution authority.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from runtime.evolution.budget.arbitrator import BudgetArbitrator, ArbitrationResult
from runtime.evolution.budget.competition_ledger import CompetitionLedger
from runtime.evolution.budget.pool import AgentBudgetPool

log = logging.getLogger(__name__)

_EVENT_TYPE = "darwinian_selection_complete.v1"


@dataclass(frozen=True)
class SelectionSummary:
    epoch_id:       str
    agent_count:    int
    evicted:        List[str]
    starved:        List[str]
    winner:         Optional[str]
    winner_share:   float
    market_scalar:  float
    completed_at:   float


class DarwinianSelectionPipeline:
    """Runs the complete Darwinian selection cycle for one epoch.

    Usage::

        pipeline = DarwinianSelectionPipeline(pool=pool, arbitrator=arb, ledger=ledger)
        summary  = pipeline.run(
            epoch_id="epoch-042",
            fitness_scores={"agent-A": 0.88, "agent-B": 0.61, "agent-C": 0.23},
            market_scalar=1.2,   # from MarketFitnessIntegrator.composite_score()
        )
    """

    def __init__(
        self,
        *,
        pool:       AgentBudgetPool,
        arbitrator: BudgetArbitrator,
        ledger:     CompetitionLedger,
        journal_fn: Any = None,
    ) -> None:
        self._pool       = pool
        self._arb        = arbitrator
        self._ledger     = ledger
        self._journal_fn = journal_fn

    def run(
        self,
        *,
        epoch_id:       str,
        fitness_scores: Dict[str, float],
        market_scalar:  float = 1.0,
    ) -> SelectionSummary:
        """Execute one full Darwinian selection cycle. Never raises."""
        try:
            result = self._arb.arbitrate(
                self._pool,
                fitness_scores,
                epoch_id=epoch_id,
                market_scalar=market_scalar,
            )
            self._ledger.record_arbitration(epoch_id=epoch_id, result=result)

            for agent in result.starved_agents:
                self._ledger.record_starvation(
                    agent_id=agent, epoch_id=epoch_id,
                    starvation_count=self._arb._starv_count.get(agent, 0))
            for agent in result.evicted_agents:
                self._ledger.record_eviction(
                    agent_id=agent, epoch_id=epoch_id, freed_share=0.0)

            winner, winner_share = self._find_winner(result.new_shares)
            summary = SelectionSummary(
                epoch_id=epoch_id,
                agent_count=len(fitness_scores),
                evicted=result.evicted_agents,
                starved=result.starved_agents,
                winner=winner,
                winner_share=winner_share,
                market_scalar=result.market_scalar,
                completed_at=time.time(),
            )
            self._emit_journal(summary)
            log.info(
                "DarwinianSelection: epoch=%s agents=%d winner=%s share=%.3f evicted=%s",
                epoch_id, len(fitness_scores), winner, winner_share, result.evicted_agents,
            )
            return summary

        except Exception as exc:
            log.error("DarwinianSelectionPipeline.run failed: %s", exc)
            return SelectionSummary(
                epoch_id=epoch_id, agent_count=0, evicted=[], starved=[],
                winner=None, winner_share=0.0, market_scalar=market_scalar,
                completed_at=time.time(),
            )

    @staticmethod
    def _find_winner(shares: Dict[str, float]):
        if not shares:
            return None, 0.0
        winner = max(shares, key=lambda a: shares[a])
        return winner, shares[winner]

    def _emit_journal(self, summary: SelectionSummary) -> None:
        if self._journal_fn is None:
            try:
                from security.ledger.journal import log as _jlog
                self._journal_fn = _jlog
            except Exception:
                return
        try:
            self._journal_fn(tx_type=_EVENT_TYPE, payload={
                "event_type":   _EVENT_TYPE,
                "epoch_id":     summary.epoch_id,
                "agent_count":  summary.agent_count,
                "winner":       summary.winner,
                "winner_share": summary.winner_share,
                "evicted":      summary.evicted,
                "starved":      summary.starved,
                "market_scalar": summary.market_scalar,
            })
        except Exception as exc:
            log.warning("DarwinianSelectionPipeline: journal failed — %s", exc)


__all__ = ["DarwinianSelectionPipeline", "SelectionSummary"]
