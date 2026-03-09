# SPDX-License-Identifier: Apache-2.0
"""RoutedDecisionTelemetry — append-only journal events for IntelligenceRouter outcomes.

Phase 17: Every call to IntelligenceRouter.route() now emits a
`routed_intelligence_decision.v1` journal entry capturing: cycle_id, strategy_id,
outcome, composite critique score, dimension verdicts, and review_digest.

Design principles:
- Append-only: the emitter never mutates pipeline state.
- Fail-isolated: emission failure is caught and logged; router outcome is never degraded.
- Deterministic payload: same RoutedIntelligenceDecision always produces identical payload.
- No external I/O required: default sink is an in-memory append-only log (replay-safe).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event type constant — registered in CANONICAL_EVENT_TYPES (Phase 17)
# ---------------------------------------------------------------------------

EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION = "routed_intelligence_decision.v1"

ROUTED_DECISION_TELEMETRY_VERSION = "17.0"


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def build_routed_decision_payload(
    *,
    cycle_id: str,
    strategy_id: str,
    outcome: str,
    composite: float,
    dimension_verdicts: Mapping[str, str],
    review_digest: str,
    confidence: float,
    risk_flags: list[str],
) -> dict[str, Any]:
    """Build the deterministic payload for a routed_intelligence_decision.v1 event.

    Same inputs always produce identical output — replay-safe.
    """
    return {
        "event_type": EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION,
        "telemetry_version": ROUTED_DECISION_TELEMETRY_VERSION,
        "cycle_id": cycle_id,
        "strategy_id": strategy_id,
        "outcome": outcome,
        "composite_score": round(float(composite), 6),
        "confidence": round(float(confidence), 6),
        "dimension_verdicts": dict(sorted(dimension_verdicts.items())),
        "review_digest": review_digest,
        "risk_flags": sorted(risk_flags),
        "payload_digest": _payload_digest(
            cycle_id=cycle_id,
            strategy_id=strategy_id,
            outcome=outcome,
            composite=composite,
            review_digest=review_digest,
        ),
    }


def _payload_digest(
    *,
    cycle_id: str,
    strategy_id: str,
    outcome: str,
    composite: float,
    review_digest: str,
) -> str:
    raw = json.dumps(
        {
            "cycle_id": cycle_id,
            "strategy_id": strategy_id,
            "outcome": outcome,
            "composite": round(float(composite), 6),
            "review_digest": review_digest,
        },
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# In-memory append-only sink (default)
# ---------------------------------------------------------------------------


@dataclass
class InMemoryTelemetrySink:
    """Thread-unsafe in-memory journal — for testing and single-process use."""

    _entries: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, payload: dict[str, Any]) -> None:
        self._entries.append(dict(payload))

    def entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# RoutedDecisionTelemetry — Phase 17
# ---------------------------------------------------------------------------


class RoutedDecisionTelemetry:
    """Emits append-only telemetry events from IntelligenceRouter.route().

    Accepts any callable sink(payload: dict) — defaults to InMemoryTelemetrySink.
    Emission failures are caught, logged, and never propagated to the caller.
    """

    def __init__(self, sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        if sink is None:
            self._default_sink = InMemoryTelemetrySink()
            self._sink: Callable[[dict[str, Any]], None] = self._default_sink.emit
        else:
            self._default_sink = None
            self._sink = sink

    def emit_routed_decision(self, decision: Any) -> None:
        """Emit a routed_intelligence_decision.v1 event from a RoutedIntelligenceDecision.

        Fail-isolated: any exception is caught and logged.
        """
        try:
            payload = build_routed_decision_payload(
                cycle_id=str(decision.proposal.proposal_id).split(":")[0],
                strategy_id=decision.strategy.strategy_id,
                outcome=decision.outcome,
                composite=decision.critique.weighted_aggregate,
                dimension_verdicts=dict(decision.critique.dimension_verdicts),
                review_digest=decision.critique.review_digest,
                confidence=decision.strategy.confidence,
                risk_flags=list(decision.critique.risk_flags),
            )
            self._sink(payload)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "RoutedDecisionTelemetry.emit_routed_decision failed: %s — telemetry suppressed",
                exc,
            )

    @property
    def default_sink(self) -> InMemoryTelemetrySink | None:
        """Returns the default in-memory sink if no external sink was provided."""
        return self._default_sink
