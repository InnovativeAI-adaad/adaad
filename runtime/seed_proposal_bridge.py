# SPDX-License-Identifier: Apache-2.0
"""Phase 74 — Seed-to-Proposal Bridge.

Converts an approved ``CapabilitySeed`` promotion entry into a
``ProposalRequest`` for the ``ProposalEngine`` pipeline.  This module is
the final link connecting the governed seed evolution lifecycle
(Phases 71–73) to the existing mutation proposal infrastructure.

Constitutional invariants
=========================
SEED-PROP-0         Only seeds with status == ``"approved"`` in the promotion
                    queue may be converted.  Any other status raises
                    ``SeedNotApprovedError``.
SEED-PROP-HUMAN-0   The generated ``ProposalRequest`` is advisory: it enters the
                    ProposalEngine for evaluation only.  No mutation is applied
                    without passing GovernanceGate + HUMAN-0.  This bridge never
                    bypasses any governance gate.
SEED-PROP-DETERM-0  ``build_proposal_request()`` is deterministic: equal inputs
                    (seed_id, promotion entry, epoch_id) produce an identical
                    ``ProposalRequest`` including ``cycle_id``.
SEED-PROP-LEDGER-0  Every successful bridge call appends a ``SeedProposalEvent``
                    to the lineage ledger before the ``ProposalRequest`` is
                    returned.  Ledger failure raises ``RuntimeError`` and the
                    request is not returned.
SEED-PROP-BUS-0     A ``seed_proposal_generated`` bus frame is emitted after the
                    ledger write (IBUS-FAILSAFE-0 — bus failure is non-fatal).

Lane → strategy_id mapping
============================
The ``strategy_id`` passed to ``ProposalEngine`` is derived deterministically
from the seed's lane, ensuring the appropriate mutation strategy is selected:

  governance    → "governance_improvement"
  performance   → "performance_optimisation"
  correctness   → "correctness_hardening"
  security      → "security_hardening"
  <any other>   → "general_improvement"
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Mapping, Optional

from runtime.evolution.proposal_engine import ProposalRequest
from runtime.seed_promotion import SeedPromotionQueue, get_promotion_queue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lane → strategy_id routing table
# ---------------------------------------------------------------------------

_LANE_STRATEGY: Dict[str, str] = {
    "governance":   "governance_improvement",
    "performance":  "performance_optimisation",
    "correctness":  "correctness_hardening",
    "security":     "security_hardening",
}
_DEFAULT_STRATEGY = "general_improvement"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SeedNotApprovedError(ValueError):
    """Raised when the seed's promotion status is not 'approved' (SEED-PROP-0)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lane_to_strategy(lane: str) -> str:
    """Deterministically map a seed lane to a ProposalEngine strategy_id."""
    return _LANE_STRATEGY.get(lane.lower().strip(), _DEFAULT_STRATEGY)


def _cycle_id(seed_id: str, epoch_id: str, lineage_digest: str) -> str:
    """Deterministic cycle_id for the ProposalRequest (SEED-PROP-DETERM-0)."""
    canonical = json.dumps(
        {"epoch_id": epoch_id, "lineage_digest": lineage_digest, "seed_id": seed_id},
        sort_keys=True, separators=(",", ":"),
    )
    return "seed-cycle-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _emit_proposal_frame(seed_id: str, cycle_id: str, strategy_id: str, epoch_id: str) -> None:
    """Emit seed_proposal_generated bus frame (SEED-PROP-BUS-0, IBUS-FAILSAFE-0)."""
    try:
        from runtime.innovations_bus import get_bus  # noqa: PLC0415
        get_bus().emit_sync({
            "type": "seed_proposal_generated",
            "seed_id": seed_id,
            "cycle_id": cycle_id,
            "strategy_id": strategy_id,
            "epoch_id": epoch_id,
            "ritual": "seed_to_proposal",
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("seed_proposal_bridge: bus emit failed (non-fatal) — %s", exc)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def build_proposal_request(
    seed_id: str,
    *,
    epoch_id: str = "",
    queue: Optional[SeedPromotionQueue] = None,
    ledger: Optional[Any] = None,
) -> ProposalRequest:
    """Build a ``ProposalRequest`` from an approved promotion queue entry.

    Parameters
    ----------
    seed_id:   Seed to bridge (must be in the promotion queue with status='approved').
    epoch_id:  Current epoch identifier — used for deterministic cycle_id.
    queue:     Promotion queue (process singleton used if not supplied).
    ledger:    ``LineageLedgerV2`` (created if not supplied).

    Returns
    -------
    A ``ProposalRequest`` ready for ``ProposalEngine.generate()``.

    Raises
    ------
    KeyError         if seed_id is absent from the promotion queue.
    SeedNotApprovedError  if seed status != 'approved' (SEED-PROP-0).
    RuntimeError     if the lineage ledger write fails (SEED-PROP-LEDGER-0).
    """
    _queue = queue or get_promotion_queue()
    entry = _queue.get(seed_id)
    if entry is None:
        raise KeyError(f"seed_id {seed_id!r} not found in promotion queue")

    # SEED-PROP-0 — only approved seeds
    if entry.get("status") != "approved":
        raise SeedNotApprovedError(
            f"seed {seed_id!r} has status={entry.get('status')!r}; "
            "only 'approved' seeds may enter the proposal pipeline (SEED-PROP-0)"
        )

    lane = entry.get("lane", "")
    strategy_id = _lane_to_strategy(lane)
    lineage_digest = entry.get("lineage_digest", "")
    cid = _cycle_id(seed_id, epoch_id, lineage_digest)

    context: Dict[str, Any] = {
        # ProposalEngine StrategyInput fields
        "mutation_score":        entry.get("expansion_score", 0.5),
        "governance_debt_score": 0.0,
        "horizon_cycles":        1,
        "resource_budget":       1.0,
        "lineage_health":        1.0,
        # Seed-specific signals (passed through to proposal adapter)
        "seed_id":               seed_id,
        "seed_lane":             lane,
        "seed_intent":           entry.get("intent", ""),
        "seed_author":           entry.get("author", ""),
        "seed_lineage_digest":   lineage_digest,
        "seed_expansion_score":  entry.get("expansion_score", 0.0),
        "seed_epoch_id":         entry.get("epoch_id", ""),
        "review_operator_id":    entry.get("review_decision", {}).get("operator_id", ""),
        "epoch_id":              epoch_id,
    }

    request = ProposalRequest(
        cycle_id=cid,
        strategy_id=strategy_id,
        context=context,
    )

    # SEED-PROP-LEDGER-0 — write before returning request
    if ledger is None:
        try:
            from runtime.evolution.lineage_v2 import LineageLedgerV2  # noqa: PLC0415
            ledger = LineageLedgerV2()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"seed_proposal_bridge: LineageLedgerV2 unavailable — "
                f"cannot satisfy SEED-PROP-LEDGER-0: {exc}"
            ) from exc

    try:
        ledger.append_event("SeedProposalEvent", {
            "seed_id":     seed_id,
            "cycle_id":    cid,
            "strategy_id": strategy_id,
            "lane":        lane,
            "epoch_id":    epoch_id,
            "lineage_digest": lineage_digest,
            "context_keys": sorted(context.keys()),
            "ritual":      "seed_to_proposal",
        })
    except Exception as exc:
        raise RuntimeError(
            f"seed_proposal_bridge: ledger write failed — "
            f"ProposalRequest NOT returned (SEED-PROP-LEDGER-0): {exc}"
        ) from exc

    logger.info(
        "seed_proposal_bridge: seed=%s strategy=%s cycle=%s",
        seed_id, strategy_id, cid,
    )

    # SEED-PROP-BUS-0 (non-fatal)
    _emit_proposal_frame(seed_id, cid, strategy_id, epoch_id)

    return request


__all__ = [
    "SeedNotApprovedError",
    "build_proposal_request",
    "LANE_STRATEGY",
]

# Export mapping for tests
LANE_STRATEGY = dict(_LANE_STRATEGY)
