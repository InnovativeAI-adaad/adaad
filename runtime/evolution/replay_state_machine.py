# SPDX-License-Identifier: Apache-2.0
"""Pure replay preflight state-machine primitives.

This module is intentionally side-effect free. It computes replay traversal
outcomes and fail-closed invariants from canonical event inputs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


CANONICAL_SCHEMA_VERSION = "replay_state_machine.v1"


@dataclass(frozen=True)
class ReplayDecision:
    mode: str
    verify_target: str
    decision: str
    has_divergence: bool
    federation_drift_detected: bool
    halt_reason: str | None
    divergence_class: str | None


class ReplayStateMachine:
    """Deterministic replay-preflight transition function."""

    @staticmethod
    def transition(
        *,
        mode: str,
        fail_closed: bool,
        verify_target: str,
        events: Sequence[Mapping[str, Any]],
        prior_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        prior = dict(prior_state or {})
        canonical_events = [dict(event) for event in events]

        has_divergence = any(not bool(event.get("passed", False)) for event in canonical_events)
        federation_drift_detected = any(bool(event.get("federation_drift_detected", False)) for event in canonical_events)

        divergence_class: str | None = None
        if federation_drift_detected:
            divergence_class = "federation_drift_detected"
        elif has_divergence:
            divergence_class = "replay_divergence"

        halt_reason = divergence_class if (fail_closed and divergence_class is not None) else None
        decision = "fail_closed" if halt_reason is not None else "continue"

        invariant_decision = ReplayDecision(
            mode=mode,
            verify_target=verify_target,
            decision=decision,
            has_divergence=has_divergence,
            federation_drift_detected=federation_drift_detected,
            halt_reason=halt_reason,
            divergence_class=divergence_class,
        )

        manifest_payload = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "mode": invariant_decision.mode,
            "target": invariant_decision.verify_target,
            "decision": invariant_decision.decision,
            "divergence": invariant_decision.has_divergence,
            "federation_drift_detected": invariant_decision.federation_drift_detected,
            "halt_reason": invariant_decision.halt_reason,
            "divergence_class": invariant_decision.divergence_class,
            "results": canonical_events,
        }

        next_state = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "mode": invariant_decision.mode,
            "verify_target": invariant_decision.verify_target,
            "decision": invariant_decision.decision,
            "has_divergence": invariant_decision.has_divergence,
            "federation_drift_detected": invariant_decision.federation_drift_detected,
            "halt_reason": invariant_decision.halt_reason,
            "divergence_class": invariant_decision.divergence_class,
            "results": canonical_events,
            "prior_state_hash": str(prior.get("state_hash") or ""),
        }

        state_hash = ReplayStateMachine._canonical_hash(next_state)
        next_state["state_hash"] = state_hash

        return {
            "next_state": next_state,
            "manifest_payload": manifest_payload,
            "invariant_checks": {
                "decision": invariant_decision.decision,
                "halt_reason": invariant_decision.halt_reason,
                "divergence_class": invariant_decision.divergence_class,
                "has_divergence": invariant_decision.has_divergence,
                "federation_drift_detected": invariant_decision.federation_drift_detected,
            },
        }

    @staticmethod
    def _canonical_hash(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


__all__ = ["CANONICAL_SCHEMA_VERSION", "ReplayDecision", "ReplayStateMachine"]
