# SPDX-License-Identifier: Apache-2.0
"""Deterministic governance policy lifecycle transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.governance.canon_law import CanonLawError, emit_violation_event, load_canon_law, one_way_escalation
from runtime.governance.foundation import sha256_prefixed_digest
from security.ledger.journal import append_tx

POLICY_STATES: tuple[str, ...] = ("authoring", "review-approved", "signed", "deployed")

_ALLOWED_TRANSITIONS: dict[str, str] = {
    "authoring": "review-approved",
    "review-approved": "signed",
    "signed": "deployed",
}


class PolicyLifecycleError(ValueError):
    """Raised when a policy lifecycle transition is malformed or disallowed."""


@dataclass(frozen=True)
class PolicyTransitionProof:
    artifact_digest: str
    previous_transition_hash: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class PolicyLifecycleTransition:
    artifact_digest: str
    from_state: str
    to_state: str
    proof: PolicyTransitionProof
    transition_hash: str


def _require_state(value: Any, field: str) -> str:
    if not isinstance(value, str) or value not in POLICY_STATES:
        raise PolicyLifecycleError(f"{field} must be one of {POLICY_STATES}")
    return value


def _require_prefixed_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != len("sha256:") + 64:
        raise PolicyLifecycleError(f"{field} must be a sha256-prefixed digest")
    return value


def _require_proof(value: Any) -> PolicyTransitionProof:
    if not isinstance(value, dict):
        raise PolicyLifecycleError("proof must be an object")
    artifact_digest = _require_prefixed_hash(value.get("artifact_digest"), "proof.artifact_digest")
    previous_transition_hash = _require_prefixed_hash(value.get("previous_transition_hash"), "proof.previous_transition_hash")
    evidence = value.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        raise PolicyLifecycleError("proof.evidence must be a non-empty object")
    return PolicyTransitionProof(
        artifact_digest=artifact_digest,
        previous_transition_hash=previous_transition_hash,
        evidence=evidence,
    )


def transition_digest(*, artifact_digest: str, from_state: str, to_state: str, proof: PolicyTransitionProof) -> str:
    payload = {
        "artifact_digest": artifact_digest,
        "from_state": from_state,
        "to_state": to_state,
        "proof": {
            "artifact_digest": proof.artifact_digest,
            "previous_transition_hash": proof.previous_transition_hash,
            "evidence": proof.evidence,
        },
    }
    return sha256_prefixed_digest(payload)


def apply_transition(*, artifact_digest: str, from_state: str, to_state: str, proof: dict[str, Any]) -> PolicyLifecycleTransition:
    clauses = load_canon_law()
    escalation = "advisory"

    def _record(clause_id: str, reason: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal escalation
        clause = clauses[clause_id]
        entry = emit_violation_event(component="policy_lifecycle", clause=clause, reason=reason, context=context)
        escalation = one_way_escalation(escalation, clause.escalation)
        return {"clause_id": clause_id, "escalation": escalation, "mutation_blocked": clause.mutation_block, "fail_closed": clause.fail_closed, "ledger_hash": entry.get("hash", "")}

    try:
        normalized_from = _require_state(from_state, "from_state")
        normalized_to = _require_state(to_state, "to_state")
    except PolicyLifecycleError as exc:
        event = _record("VIII.undefined_state_fail_closed", "undefined_state", context={"from_state": from_state, "to_state": to_state, "error": str(exc)})
        raise PolicyLifecycleError(
            f"{exc}; escalation={event['escalation']}; mutation_blocked={event['mutation_blocked']}; fail_closed={event['fail_closed']}; ledger_hash={event['ledger_hash']}"
        ) from exc
    except CanonLawError as exc:
        raise PolicyLifecycleError(f"canon_law_error:{exc}; fail_closed=true") from exc
    expected_next = _ALLOWED_TRANSITIONS.get(normalized_from)
    if expected_next != normalized_to:
        event = _record("VI.lifecycle_transition_must_be_declared", "invalid_transition", context={"from_state": normalized_from, "to_state": normalized_to, "expected_next": expected_next})
        raise PolicyLifecycleError(
            f"invalid transition {normalized_from!r} -> {normalized_to!r}; expected {expected_next!r}; escalation={event['escalation']}; ledger_hash={event['ledger_hash']}"
        )

    normalized_digest = _require_prefixed_hash(artifact_digest, "artifact_digest")
    normalized_proof = _require_proof(proof)
    if normalized_proof.artifact_digest != normalized_digest:
        event = _record("VII.lifecycle_proof_must_match_artifact", "proof_digest_mismatch", context={"artifact_digest": normalized_digest, "proof_digest": normalized_proof.artifact_digest})
        raise PolicyLifecycleError(
            f"proof.artifact_digest must match artifact_digest; escalation={event['escalation']}; mutation_blocked={event['mutation_blocked']}; fail_closed={event['fail_closed']}; ledger_hash={event['ledger_hash']}"
        )

    tx_hash = transition_digest(
        artifact_digest=normalized_digest,
        from_state=normalized_from,
        to_state=normalized_to,
        proof=normalized_proof,
    )
    transition = PolicyLifecycleTransition(
        artifact_digest=normalized_digest,
        from_state=normalized_from,
        to_state=normalized_to,
        proof=normalized_proof,
        transition_hash=tx_hash,
    )
    append_tx(
        tx_type="policy_lifecycle_transition",
        payload={
            "artifact_digest": transition.artifact_digest,
            "from_state": transition.from_state,
            "to_state": transition.to_state,
            "proof": {
                "artifact_digest": transition.proof.artifact_digest,
                "previous_transition_hash": transition.proof.previous_transition_hash,
                "evidence": transition.proof.evidence,
            },
            "transition_hash": transition.transition_hash,
        },
        tx_id=f"POLICY-{transition.to_state.upper()}",
    )
    return transition


__all__ = [
    "POLICY_STATES",
    "PolicyLifecycleError",
    "PolicyLifecycleTransition",
    "PolicyTransitionProof",
    "apply_transition",
    "transition_digest",
]
