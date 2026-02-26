# SPDX-License-Identifier: Apache-2.0
"""Canonical AGM event envelope model and validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4


_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class AGMEventValidationError(ValueError):
    """Raised when event envelope validation fails."""


@dataclass(frozen=True)
class AGMEventEnvelope:
    schema_version: str
    event_id: str
    event_type: str
    emitted_at: str
    payload: dict[str, Any]
    signature: str
    signing_key_id: str
    signature_algorithm: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "emitted_at": self.emitted_at,
            "payload": dict(self.payload),
            "signature": self.signature,
            "signing_key_id": self.signing_key_id,
            "signature_algorithm": self.signature_algorithm,
        }


@dataclass(frozen=True)
class ScoringEvent:
    mutation_id: str
    score: float
    metrics: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"mutation_id": self.mutation_id, "score": float(self.score)}
        if self.metrics:
            payload["metrics"] = dict(self.metrics)
        return payload


@dataclass(frozen=True)
class DeploymentGatingEvent:
    environment: str
    gate_decision: str
    step_11_commit_sha: str
    step_11_contract_passed: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "gate_decision": self.gate_decision,
            "step_11_commit_sha": self.step_11_commit_sha,
            "step_11_contract_passed": self.step_11_contract_passed,
        }


TypedLedgerEvent = ScoringEvent | DeploymentGatingEvent


def create_event_envelope(event: TypedLedgerEvent) -> AGMEventEnvelope:
    event_type = "scoring_event" if isinstance(event, ScoringEvent) else "deployment_gating_event"
    envelope = AGMEventEnvelope(
        schema_version="1.0",
        event_id=str(uuid4()),
        event_type=event_type,
        emitted_at=datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        payload=event.to_payload(),
        signature="",
        signing_key_id="",
        signature_algorithm="",
    )
    validate_event_envelope(envelope, require_signature=False)
    return envelope


def validate_event_envelope(envelope: AGMEventEnvelope, *, require_signature: bool = True) -> None:
    if envelope.schema_version != "1.0":
        raise AGMEventValidationError("invalid:schema_version")
    if not envelope.event_id.strip():
        raise AGMEventValidationError("missing:event_id")
    if envelope.event_type not in {"scoring_event", "deployment_gating_event"}:
        raise AGMEventValidationError("invalid:event_type")
    if not envelope.emitted_at.endswith("Z"):
        raise AGMEventValidationError("invalid:emitted_at")
    if not isinstance(envelope.payload, dict):
        raise AGMEventValidationError("invalid:payload")
    if require_signature:
        if not envelope.signature.strip():
            raise AGMEventValidationError("missing:signature")
        if not envelope.signing_key_id.strip():
            raise AGMEventValidationError("missing:signing_key_id")
        if not envelope.signature_algorithm.strip():
            raise AGMEventValidationError("missing:signature_algorithm")
    if envelope.event_type == "deployment_gating_event":
        _validate_step_11_commit_contract(envelope.payload)


def _validate_step_11_commit_contract(payload: dict[str, Any]) -> None:
    commit_sha = payload.get("step_11_commit_sha")
    contract_passed = payload.get("step_11_contract_passed")
    if not isinstance(commit_sha, str) or not _COMMIT_SHA_RE.fullmatch(commit_sha):
        raise AGMEventValidationError("invalid:step_11_commit_sha")
    if contract_passed is not True:
        raise AGMEventValidationError("invalid:step_11_contract")
