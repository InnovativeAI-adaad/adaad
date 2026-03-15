# SPDX-License-Identifier: Apache-2.0
"""Phase 76 — Seed CEL Outcome Recorder.

Closes the seed lifecycle feedback loop by recording the outcome of a CEL
epoch that ran with an injected seed proposal (Phase 75) back into the
lineage ledger as a ``SeedCELOutcomeEvent``.

Full seed lifecycle pipeline (Phases 71 → 76)
=============================================
    CapabilitySeed → evolve_seed() → graduation → SeedPromotionQueue
    → human review (approved) → build_proposal_request()         [Phase 74]
    → inject_seed_proposal_into_context()                         [Phase 75]
    → LiveWiredCEL.run_epoch(context=ctx)
    → GovernanceGate + HUMAN-0 gates unchanged
    → record_cel_outcome()                                        [Phase 76] ✓

Constitutional invariants
=========================
SEED-OUTCOME-0        ``record_cel_outcome()`` is the only supported mechanism
                      for writing a CEL epoch outcome back to the lineage ledger
                      for a seed-derived proposal.
SEED-OUTCOME-LINK-0   Every outcome record must carry ``seed_id``, ``cycle_id``,
                      and ``epoch_id`` to enable full lineage traceability.
SEED-OUTCOME-DETERM-0 Equal (seed_id, cycle_id, epoch_id, outcome_status) inputs
                      produce an identical ``outcome_digest``.
SEED-OUTCOME-AUDIT-0  ``SeedCELOutcomeEvent`` is written to the lineage ledger
                      before the bus frame is emitted; ledger failure aborts the
                      entire call and the bus frame is never emitted.
SEED-OUTCOME-IDEM-0   Submitting a duplicate outcome for the same (seed_id,
                      cycle_id) returns the existing record unchanged without
                      writing a second ledger entry.
CEL-OUTCOME-FAIL-0    Outcome wiring in the CEL post-epoch hook is wrapped in
                      try/except; epoch completion is never blocked by outcome
                      recording failure.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Outcome status vocabulary
OUTCOME_STATUSES = frozenset({"success", "partial", "failed", "skipped"})

# In-process idempotency store — keyed by (seed_id, cycle_id)
_outcome_registry: Dict[tuple[str, str], Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SeedOutcomeLinkError(ValueError):
    """Raised when required link fields are missing (SEED-OUTCOME-LINK-0)."""


class SeedOutcomeStatusError(ValueError):
    """Raised when outcome_status is not in OUTCOME_STATUSES."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _outcome_digest(
    seed_id: str,
    cycle_id: str,
    epoch_id: str,
    outcome_status: str,
) -> str:
    """Deterministic SHA-256 outcome digest (SEED-OUTCOME-DETERM-0)."""
    payload = json.dumps(
        {
            "seed_id":        seed_id,
            "cycle_id":       cycle_id,
            "epoch_id":       epoch_id,
            "outcome_status": outcome_status,
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_cel_outcome(
    seed_id: str,
    cycle_id: str,
    epoch_id: str,
    outcome_status: str,
    *,
    fitness_delta: float = 0.0,
    mutation_count: int = 0,
    notes: str = "",
    ledger: Optional[Any] = None,
    bus: Optional[Any] = None,
) -> Dict[str, Any]:
    """Record the outcome of a CEL epoch that used an injected seed proposal.

    Parameters
    ----------
    seed_id:        Originating Capability Seed identifier (SEED-OUTCOME-LINK-0).
    cycle_id:       ProposalRequest cycle_id from Phase 74/75 (SEED-OUTCOME-LINK-0).
    epoch_id:       CEL epoch identifier (SEED-OUTCOME-LINK-0).
    outcome_status: One of ``success``, ``partial``, ``failed``, ``skipped``.
    fitness_delta:  Change in fitness score observed after this epoch.
    mutation_count: Number of mutations generated in the epoch.
    notes:          Free-text operator notes.
    ledger:         ``LineageLedgerV2`` instance (injected for testing).
    bus:            ``InnovationsEventBus`` instance (injected for testing).

    Returns
    -------
    Outcome record dict.

    Raises
    ------
    SeedOutcomeLinkError    if seed_id, cycle_id, or epoch_id are empty.
    SeedOutcomeStatusError  if outcome_status is not a recognised value.
    RuntimeError            if the lineage ledger write fails (SEED-OUTCOME-AUDIT-0).
    """
    # SEED-OUTCOME-LINK-0
    for field_name, field_val in (
        ("seed_id",  seed_id),
        ("cycle_id", cycle_id),
        ("epoch_id", epoch_id),
    ):
        if not field_val or not field_val.strip():
            raise SeedOutcomeLinkError(
                f"record_cel_outcome: '{field_name}' is required "
                f"(SEED-OUTCOME-LINK-0)"
            )

    # Status validation
    if outcome_status not in OUTCOME_STATUSES:
        raise SeedOutcomeStatusError(
            f"record_cel_outcome: unknown outcome_status '{outcome_status}'; "
            f"must be one of {sorted(OUTCOME_STATUSES)}"
        )

    # SEED-OUTCOME-IDEM-0 — idempotency on (seed_id, cycle_id)
    idem_key = (seed_id, cycle_id)
    if idem_key in _outcome_registry:
        logger.debug(
            "seed_cel_outcome: idempotent return for seed=%s cycle=%s",
            seed_id, cycle_id,
        )
        return _outcome_registry[idem_key]

    digest = _outcome_digest(seed_id, cycle_id, epoch_id, outcome_status)
    recorded_at = _now_iso()

    outcome: Dict[str, Any] = {
        "seed_id":        seed_id,
        "cycle_id":       cycle_id,
        "epoch_id":       epoch_id,
        "outcome_status": outcome_status,
        "fitness_delta":  float(fitness_delta),
        "mutation_count": int(mutation_count),
        "notes":          notes,
        "recorded_at":    recorded_at,
        "outcome_digest": digest,
    }

    # SEED-OUTCOME-AUDIT-0 — ledger write BEFORE bus emit
    if ledger is None:
        try:
            from runtime.evolution.lineage_v2 import LineageLedgerV2  # noqa: PLC0415
            ledger = LineageLedgerV2()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"seed_cel_outcome: LineageLedgerV2 unavailable — "
                f"cannot satisfy SEED-OUTCOME-AUDIT-0: {exc}"
            ) from exc

    try:
        ledger.append_event("SeedCELOutcomeEvent", {
            "seed_id":        seed_id,
            "cycle_id":       cycle_id,
            "epoch_id":       epoch_id,
            "outcome_status": outcome_status,
            "fitness_delta":  float(fitness_delta),
            "mutation_count": int(mutation_count),
            "outcome_digest": digest,
            "ritual":         "seed_cel_outcome",
        })
    except Exception as exc:
        raise RuntimeError(
            f"seed_cel_outcome: ledger write failed — outcome NOT recorded "
            f"(SEED-OUTCOME-AUDIT-0): {exc}"
        ) from exc

    # Register in idempotency store
    _outcome_registry[idem_key] = outcome

    # Bus emit — fail-safe (IBUS-FAILSAFE-0 / SEED-OUTCOME-AUDIT-0 already satisfied)
    if bus is None:
        try:
            from runtime.innovations_bus import get_innovations_bus  # noqa: PLC0415
            bus = get_innovations_bus()
        except Exception:  # noqa: BLE001
            bus = None

    if bus is not None:
        try:
            bus.emit("seed_cel_outcome", {
                "seed_id":        seed_id,
                "cycle_id":       cycle_id,
                "epoch_id":       epoch_id,
                "outcome_status": outcome_status,
                "fitness_delta":  float(fitness_delta),
                "mutation_count": int(mutation_count),
                "outcome_digest": digest,
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "seed_cel_outcome: bus emit failed (non-fatal): %s", exc
            )

    logger.info(
        "seed_cel_outcome: recorded seed=%s cycle=%s epoch=%s status=%s Δfitness=%.4f",
        seed_id, cycle_id, epoch_id, outcome_status, fitness_delta,
    )

    return outcome


def get_cel_outcome(seed_id: str, cycle_id: str) -> Optional[Dict[str, Any]]:
    """Return the recorded outcome for (seed_id, cycle_id), or None."""
    return _outcome_registry.get((seed_id, cycle_id))


def clear_outcome_registry() -> None:
    """Clear the in-process registry (test utility only)."""
    _outcome_registry.clear()


__all__ = [
    "OUTCOME_STATUSES",
    "SeedOutcomeLinkError",
    "SeedOutcomeStatusError",
    "record_cel_outcome",
    "get_cel_outcome",
    "clear_outcome_registry",
]
