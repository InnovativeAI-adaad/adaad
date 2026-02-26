# SPDX-License-Identifier: Apache-2.0
"""Append-only deterministic scoring ledger helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.evolution.agm_event import AGMEventEnvelope, TypedLedgerEvent, create_event_envelope
from runtime.evolution.event_signing import DeterministicMockSigner, EventSigner, EventVerifier
from runtime.governance.policy_artifact import GovernancePolicyError, load_governance_policy
from runtime.state.ledger_store import ScoringLedgerStore


class ScoringLedger:
    def __init__(self, path: Path, *, signer: EventSigner | None = None, verifier: EventVerifier | None = None) -> None:
        backend = "json"
        try:
            backend = load_governance_policy().state_backend
        except GovernancePolicyError:
            backend = "json"
        self.store = ScoringLedgerStore(path=path, backend=backend)
        deterministic = DeterministicMockSigner()
        self.signer: EventSigner = signer or deterministic
        self.verifier: EventVerifier = verifier or deterministic

    def append(self, event: TypedLedgerEvent) -> dict[str, Any]:
        envelope = create_event_envelope(event)
        canonical = self.store.canonical_event_content(envelope)
        signed = self.signer.sign(canonical)
        signed_envelope = AGMEventEnvelope(
            schema_version=envelope.schema_version,
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            emitted_at=envelope.emitted_at,
            payload=envelope.payload,
            signature=signed.signature,
            signing_key_id=signed.signing_key_id,
            signature_algorithm=signed.algorithm,
        )
        return self.store.append_event(signed_envelope, verifier=self.verifier)

    def append_envelope(self, envelope: AGMEventEnvelope) -> dict[str, Any]:
        return self.store.append_event(envelope, verifier=self.verifier)

    def last_hash(self) -> str:
        return self.store.last_hash()


__all__ = ["ScoringLedger"]
