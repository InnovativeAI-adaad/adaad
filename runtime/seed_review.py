# SPDX-License-Identifier: Apache-2.0
"""Phase 73 — Seed Review Decision.

Provides the governed human-approval workflow for seeds in the promotion
queue (Phase 72).  A human governor calls ``record_review()`` to approve
or reject a seed; the decision is hash-chained into the lineage ledger,
emitted to the innovations bus, and reflected in the promotion queue entry.

Constitutional invariants
=========================
SEED-REVIEW-0       Every review decision writes exactly one
                    ``SeedReviewDecisionEvent`` to the lineage ledger before
                    any status transition occurs.  Write failures abort the
                    decision; queue entry status is not mutated on failure.
SEED-REVIEW-HUMAN-0 Only a decision with ``operator_id`` set may be recorded.
                    Empty or whitespace-only operator_id raises
                    ``ReviewAuthorityError``.  This invariant enforces that no
                    system process can self-approve a seed (HUMAN-0 extension).
SEED-REVIEW-IDEM-0  Reviewing a seed whose status is already terminal
                    (``approved`` or ``rejected``) is a no-op; the existing
                    decision is returned unchanged.
SEED-REVIEW-AUDIT-0 Every decision carries a ``decision_digest`` (SHA-256 of
                    seed_id + status + operator_id + decided_at) for replay
                    verification.
SEED-REVIEW-BUS-0   ``seed_promotion_approved`` or ``seed_promotion_rejected``
                    bus frame is emitted after ledger write (IBUS-FAILSAFE-0 —
                    bus failure never reverts the ledger write).

Review decision schema
======================
{
  "seed_id":        str,
  "status":         "approved" | "rejected",
  "operator_id":    str,
  "decided_at":     ISO-8601 UTC,
  "notes":          str,
  "decision_digest": sha256 hex,
}
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from runtime.seed_promotion import SeedPromotionQueue, get_promotion_queue

logger = logging.getLogger(__name__)

# Terminal statuses — idempotency guard (SEED-REVIEW-IDEM-0)
_TERMINAL_STATUSES = frozenset({"approved", "rejected"})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReviewAuthorityError(ValueError):
    """Raised when operator_id is absent or whitespace (SEED-REVIEW-HUMAN-0)."""


class SeedNotFoundError(KeyError):
    """Raised when the seed_id is not in the promotion queue."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_digest(
    seed_id: str, status: str, operator_id: str, decided_at: str
) -> str:
    """Deterministic SHA-256 digest for a review decision (SEED-REVIEW-AUDIT-0)."""
    payload = json.dumps(
        {
            "decided_at": decided_at,
            "operator_id": operator_id,
            "seed_id": seed_id,
            "status": status,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _emit_review_frame(seed_id: str, status: str, operator_id: str, epoch_id: str) -> None:
    """Emit bus frame for approved or rejected seed review (SEED-REVIEW-BUS-0)."""
    frame_type = (
        "seed_promotion_approved" if status == "approved" else "seed_promotion_rejected"
    )
    try:
        from runtime.innovations_bus import get_bus  # noqa: PLC0415

        get_bus().emit_sync(
            {
                "type": frame_type,
                "seed_id": seed_id,
                "status": status,
                "operator_id": operator_id,
                "epoch_id": epoch_id,
                "ritual": "seed_review_decision",
            }
        )
    except Exception as exc:  # noqa: BLE001  IBUS-FAILSAFE-0
        logger.warning("seed_review: bus emit failed (non-fatal) — %s", exc)


def _append_review_event(ledger: Any, decision: Dict[str, Any]) -> None:
    """Write SeedReviewDecisionEvent to lineage ledger (SEED-REVIEW-0)."""
    ledger.append_event("SeedReviewDecisionEvent", decision)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def record_review(
    seed_id: str,
    *,
    status: str,
    operator_id: str,
    notes: str = "",
    ledger: Optional[Any] = None,
    queue: Optional[SeedPromotionQueue] = None,
) -> Dict[str, Any]:
    """Record a human review decision for a promoted seed.

    Parameters
    ----------
    seed_id:      Seed to review (must be in promotion queue).
    status:       ``"approved"`` or ``"rejected"`` — no other values accepted.
    operator_id:  Human governor ID (SEED-REVIEW-HUMAN-0 — must be non-empty).
    notes:        Optional free-text notes for the audit record.
    ledger:       ``LineageLedgerV2`` instance (created if not supplied).
    queue:        ``SeedPromotionQueue`` (process singleton used if not supplied).

    Returns
    -------
    Decision dict (also mutated into the promotion queue entry).

    Raises
    ------
    ReviewAuthorityError   if operator_id is blank (SEED-REVIEW-HUMAN-0).
    SeedNotFoundError      if seed_id is absent from the promotion queue.
    ValueError             if status is not 'approved' or 'rejected'.
    RuntimeError           if the lineage ledger write fails (SEED-REVIEW-0).
    """
    # SEED-REVIEW-HUMAN-0 — operator required
    if not operator_id or not operator_id.strip():
        raise ReviewAuthorityError(
            "operator_id must be non-empty (SEED-REVIEW-HUMAN-0): "
            "no system process may self-approve a seed."
        )

    if status not in ("approved", "rejected"):
        raise ValueError(f"status must be 'approved' or 'rejected'; got {status!r}")

    _queue = queue or get_promotion_queue()
    entry = _queue.get(seed_id)
    if entry is None:
        raise SeedNotFoundError(
            f"seed_id {seed_id!r} not found in promotion queue"
        )

    # SEED-REVIEW-IDEM-0 — terminal status is a no-op
    if entry.get("status") in _TERMINAL_STATUSES:
        logger.debug(
            "seed_review: idempotent review seed=%s existing_status=%s",
            seed_id, entry["status"],
        )
        return entry

    decided_at = _now_iso()
    digest = _decision_digest(seed_id, status, operator_id, decided_at)

    decision: Dict[str, Any] = {
        "seed_id": seed_id,
        "lane": entry.get("lane", ""),
        "status": status,
        "operator_id": operator_id.strip(),
        "decided_at": decided_at,
        "notes": notes,
        "decision_digest": digest,
        "expansion_score": entry.get("expansion_score"),
        "lineage_digest": entry.get("lineage_digest", ""),
        "epoch_id": entry.get("epoch_id", ""),
    }

    # SEED-REVIEW-0 — ledger write before any status mutation
    if ledger is None:
        try:
            from runtime.evolution.lineage_v2 import LineageLedgerV2  # noqa: PLC0415
            ledger = LineageLedgerV2()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"seed_review: LineageLedgerV2 unavailable — cannot satisfy "
                f"SEED-REVIEW-0 (ledger write before status transition): {exc}"
            ) from exc

    try:
        _append_review_event(ledger, decision)
    except Exception as exc:
        raise RuntimeError(
            f"seed_review: ledger write failed — status NOT mutated (SEED-REVIEW-0): {exc}"
        ) from exc

    # Mutate queue entry status only after successful ledger write
    entry["status"] = status
    entry["review_decision"] = decision

    logger.info(
        "seed_review: seed=%s status=%s operator=%s digest=%s",
        seed_id, status, operator_id, digest[:12],
    )

    # SEED-REVIEW-BUS-0 — emit bus frame (failure non-fatal)
    _emit_review_frame(seed_id, status, operator_id, entry.get("epoch_id", ""))

    return decision


__all__ = [
    "ReviewAuthorityError",
    "SeedNotFoundError",
    "record_review",
]
