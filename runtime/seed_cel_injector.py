# SPDX-License-Identifier: Apache-2.0
"""Phase 75 — Seed Proposal CEL Injector.

Wires an approved seed's ``ProposalRequest`` (from Phase 74
``build_proposal_request()``) into a CEL epoch's ``context`` dict so that
Step 4 (PROPOSAL-GENERATE) uses the seed-derived request instead of the
default auto-generated one.

The injector is the final link in the seed evolution pipeline:

    CapabilitySeed → evolve_seed → graduation → promotion queue
    → human review (approved) → build_proposal_request()
    → inject_seed_proposal_into_context()    ← Phase 75
    → LiveWiredCEL.run_epoch(context=ctx)   ← existing CEL pipeline
    → GovernanceGate + HUMAN-0              ← existing gates unchanged

Constitutional invariants
=========================
SEED-CEL-0          ``inject_seed_proposal_into_context()`` is the only
                    supported mechanism to route a seed-derived
                    ``ProposalRequest`` into a CEL epoch.  Direct mutation of
                    CEL-internal state is prohibited.
SEED-CEL-HUMAN-0    The injector sets ``context["seed_proposal_request"]``
                    as an advisory signal only.  Step 4 reads it if present
                    but falls back to the default request if absent — no
                    invariant of CEL-ORDER-0 is altered.
SEED-CEL-DETERM-0   Equal (ProposalRequest, epoch_context) inputs produce an
                    identical injected context dict (deterministic merge).
SEED-CEL-AUDIT-0    Every injection call appends a ``SeedCELInjectionEvent``
                    to the lineage ledger before returning the context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from runtime.evolution.proposal_engine import ProposalRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Injection API
# ---------------------------------------------------------------------------


def inject_seed_proposal_into_context(
    request: ProposalRequest,
    *,
    base_context: Optional[Dict[str, Any]] = None,
    ledger: Optional[Any] = None,
) -> Dict[str, Any]:
    """Merge a seed-derived ``ProposalRequest`` into a CEL epoch context dict.

    The returned dict is suitable for passing directly to
    ``LiveWiredCEL.run_epoch(context=ctx)``.

    Parameters
    ----------
    request:       Seed-derived ``ProposalRequest`` from ``build_proposal_request()``.
    base_context:  Existing epoch context to merge into (copied, never mutated).
    ledger:        ``LineageLedgerV2`` for ``SeedCELInjectionEvent`` (SEED-CEL-AUDIT-0).

    Returns
    -------
    New context dict with ``seed_proposal_request`` key set.

    Raises
    ------
    RuntimeError   if the lineage ledger write fails (SEED-CEL-AUDIT-0).
    """
    ctx: Dict[str, Any] = dict(base_context or {})

    # SEED-CEL-0 — canonical injection key
    ctx["seed_proposal_request"] = {
        "cycle_id":    request.cycle_id,
        "strategy_id": request.strategy_id,
        "context":     dict(request.context),
    }

    # Promote seed fields into top-level context so CEL Step 4 can read them
    seed_ctx = dict(request.context)
    for key in (
        "seed_id", "seed_lane", "seed_intent", "seed_author",
        "seed_expansion_score", "seed_lineage_digest", "seed_epoch_id",
        "review_operator_id",
    ):
        if key in seed_ctx:
            ctx.setdefault(key, seed_ctx[key])

    # Carry forward strategy_id so Step 4 picks it up directly
    ctx["strategy_id"] = request.strategy_id

    # SEED-CEL-AUDIT-0 — ledger write before return
    if ledger is None:
        try:
            from runtime.evolution.lineage_v2 import LineageLedgerV2  # noqa: PLC0415
            ledger = LineageLedgerV2()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"seed_cel_injector: LineageLedgerV2 unavailable — "
                f"cannot satisfy SEED-CEL-AUDIT-0: {exc}"
            ) from exc

    try:
        ledger.append_event("SeedCELInjectionEvent", {
            "cycle_id":    request.cycle_id,
            "strategy_id": request.strategy_id,
            "seed_id":     seed_ctx.get("seed_id", ""),
            "seed_lane":   seed_ctx.get("seed_lane", ""),
            "ritual":      "seed_cel_injection",
        })
    except Exception as exc:
        raise RuntimeError(
            f"seed_cel_injector: ledger write failed — "
            f"context NOT returned (SEED-CEL-AUDIT-0): {exc}"
        ) from exc

    logger.info(
        "seed_cel_injector: injected seed=%s strategy=%s cycle=%s",
        seed_ctx.get("seed_id", "?"),
        request.strategy_id,
        request.cycle_id,
    )

    return ctx


# ---------------------------------------------------------------------------
# CEL Step 4 hook — reads injected request if present
# ---------------------------------------------------------------------------


def resolve_step4_request(
    state: Dict[str, Any],
    default_cycle_id: str,
    default_strategy_id: str,
) -> ProposalRequest:
    """Return the seed-derived or default ``ProposalRequest`` for CEL Step 4.

    SEED-CEL-HUMAN-0: if ``state["context"]["seed_proposal_request"]`` is
    present, construct a ``ProposalRequest`` from it; otherwise fall back to
    the default auto-generated request built from epoch context.

    This function is pure (no side effects) and deterministic (SEED-CEL-DETERM-0).
    """
    context: Dict[str, Any] = dict(state.get("context", {}))
    seed_req_dict = context.get("seed_proposal_request")

    if seed_req_dict and isinstance(seed_req_dict, dict):
        logger.debug(
            "seed_cel_injector: step4 using seed-derived request cycle=%s strategy=%s",
            seed_req_dict.get("cycle_id"), seed_req_dict.get("strategy_id"),
        )
        return ProposalRequest(
            cycle_id=str(seed_req_dict.get("cycle_id", default_cycle_id)),
            strategy_id=str(seed_req_dict.get("strategy_id", default_strategy_id)),
            context=dict(seed_req_dict.get("context", {})),
        )

    return ProposalRequest(
        cycle_id=default_cycle_id,
        strategy_id=default_strategy_id,
        context=context,
    )


__all__ = [
    "inject_seed_proposal_into_context",
    "resolve_step4_request",
]
