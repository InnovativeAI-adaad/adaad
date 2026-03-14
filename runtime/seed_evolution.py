# SPDX-License-Identifier: Apache-2.0
"""Phase 71 — Capability Seed Evolution Epoch Hook.

Wires ``ADAADInnovationEngine.evolve_seed()`` into the governed epoch
lifecycle.  On every cadence tick, each registered seed advances its
expansion score and the result is written to the lineage ledger.

When ``expansion_score >= GRADUATION_THRESHOLD`` the seed enters the
**Graduation Ceremony**: a ``seed_graduated`` frame is emitted to the
innovations bus and a ``capability_graduation`` ritual event is written
to the lineage ledger.

Constitutional invariants
=========================
SEED-EVOL-0    evolve_seed is called for every active seed at each epoch
               cadence tick; results are written to the lineage ledger
               before any graduation check.
SEED-GRAD-0    Graduation fires when and only when expansion_score >= 0.85.
               A seed may graduate exactly once per epoch; re-graduation on
               the same epoch_id is idempotent (guarded by seen-set).
SEED-EVOL-FAIL-0  Any failure in seed evolution is caught and logged as
               WARNING; the epoch continues uninterrupted (CEL-WIRE-FAIL-0).

Graduation ceremony sequence
=============================
1. Emit ``seed_graduated`` bus frame (IBUS-FAILSAFE-0).
2. Append ``SeedGraduationEvent`` to lineage ledger.
3. Write ``capability_graduation`` ritual record to state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set

from runtime.innovations import ADAADInnovationEngine, CapabilitySeed

logger = logging.getLogger(__name__)

# Graduation threshold (SEED-GRAD-0).
GRADUATION_THRESHOLD: float = 0.85

# Default cadence: run seed evolution every N epochs.
SEED_EVOLUTION_CADENCE: int = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _emit_seed_graduated(
    seed_id: str,
    lane: str,
    expansion_score: float,
    epoch_id: str,
) -> None:
    """Emit seed_graduated bus frame (IBUS-FAILSAFE-0 — never raises)."""
    try:
        from runtime.innovations_bus import emit_seed_graduated  # noqa: PLC0415
        emit_seed_graduated(seed_id, lane, expansion_score, epoch_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("seed_evolution: emit_seed_graduated failed — %s", exc)


def _append_graduation_event(
    ledger: Any,
    seed: CapabilitySeed,
    evolution_result: Dict[str, Any],
    epoch_id: str,
) -> None:
    """Write SeedGraduationEvent + capability_graduation ritual to lineage ledger."""
    payload = {
        "seed_id": seed.seed_id,
        "lane": seed.lane,
        "intent": seed.intent,
        "author": seed.author,
        "lineage_digest": evolution_result["lineage_digest"],
        "expansion_score": evolution_result["expansion_score"],
        "epochs": evolution_result["epochs"],
        "epoch_id": epoch_id,
        "ritual": "capability_graduation",
    }
    try:
        ledger.append_event("SeedGraduationEvent", payload)
        logger.info(
            "seed_evolution: graduation committed seed=%s score=%.4f epoch=%s",
            seed.seed_id,
            evolution_result["expansion_score"],
            epoch_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("seed_evolution: lineage graduation write failed — %s", exc)


def _append_evolution_event(
    ledger: Any,
    seed: CapabilitySeed,
    evolution_result: Dict[str, Any],
    epoch_id: str,
) -> None:
    """Write SeedEvolutionEvent to lineage ledger (SEED-EVOL-0)."""
    payload = {
        "seed_id": seed.seed_id,
        "lane": seed.lane,
        "lineage_digest": evolution_result["lineage_digest"],
        "expansion_score": evolution_result["expansion_score"],
        "epochs": evolution_result["epochs"],
        "status": evolution_result["status"],
        "epoch_id": epoch_id,
    }
    try:
        ledger.append_event("SeedEvolutionEvent", payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("seed_evolution: lineage evolution write failed — %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_seed_evolution(
    engine: ADAADInnovationEngine,
    seeds: Sequence[CapabilitySeed],
    epoch_id: str,
    epoch_seq: int,
    state: Dict[str, Any],
    *,
    ledger: Any = None,
    cadence: int = SEED_EVOLUTION_CADENCE,
    graduation_threshold: float = GRADUATION_THRESHOLD,
    _graduated_this_epoch: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Evolve all registered seeds on the epoch cadence tick.

    Parameters
    ----------
    engine:               ADAADInnovationEngine instance.
    seeds:                Active CapabilitySeed objects to evolve.
    epoch_id:             Current epoch identifier (deterministic string).
    epoch_seq:            Sequential epoch counter (0-based).
    state:                CEL epoch state dict (mutated in-place with results).
    ledger:               LineageLedgerV2 instance (optional; new instance
                          created if not supplied).
    cadence:              Evolve every N epochs.  0 → every epoch.
    graduation_threshold: expansion_score floor for graduation ceremony.
    _graduated_this_epoch: Internal dedup set (test injection point).

    Returns
    -------
    List of evolution result dicts (one per seed processed this tick).
    SEED-EVOL-FAIL-0: individual seed failures are caught and logged;
    other seeds continue processing.
    """
    if cadence > 0 and epoch_seq % cadence != 0:
        return []

    if not seeds:
        return []

    # Lazy-import lineage ledger to avoid circular deps at module load.
    if ledger is None:
        try:
            from runtime.evolution.lineage_v2 import LineageLedgerV2  # noqa: PLC0415
            ledger = LineageLedgerV2()
        except Exception as exc:  # noqa: BLE001
            logger.warning("seed_evolution: LineageLedgerV2 unavailable — %s", exc)
            ledger = None

    graduated_set: Set[str] = _graduated_this_epoch if _graduated_this_epoch is not None else set()
    results: List[Dict[str, Any]] = []

    for seed in seeds:
        try:
            evolution_result = engine.evolve_seed(seed, epochs=epoch_seq + 1)

            # SEED-EVOL-0: write evolution record to lineage ledger.
            if ledger is not None:
                _append_evolution_event(ledger, seed, evolution_result, epoch_id)

            evolution_result["epoch_id"] = epoch_id
            results.append(evolution_result)

            logger.debug(
                "seed_evolution: seed=%s score=%.4f status=%s",
                seed.seed_id,
                evolution_result["expansion_score"],
                evolution_result["status"],
            )

            # SEED-GRAD-0: graduation ceremony when threshold reached.
            score = evolution_result["expansion_score"]
            if score >= graduation_threshold and seed.seed_id not in graduated_set:
                graduated_set.add(seed.seed_id)
                # 1. Emit bus frame.
                _emit_seed_graduated(seed.seed_id, seed.lane, score, epoch_id)
                # 2. Write graduation event to lineage ledger.
                if ledger is not None:
                    _append_graduation_event(ledger, seed, evolution_result, epoch_id)
                # 3. Record ritual in state.
                graduations = state.setdefault("capability_graduations", [])
                graduations.append(
                    {
                        "seed_id": seed.seed_id,
                        "lane": seed.lane,
                        "expansion_score": score,
                        "epoch_id": epoch_id,
                        "ritual": "capability_graduation",
                    }
                )

        except Exception as exc:  # noqa: BLE001  SEED-EVOL-FAIL-0
            logger.warning(
                "seed_evolution: seed=%s failed — %s", seed.seed_id, exc
            )

    state["seed_evolution_results"] = results
    return results


__all__ = [
    "GRADUATION_THRESHOLD",
    "SEED_EVOLUTION_CADENCE",
    "run_seed_evolution",
]
