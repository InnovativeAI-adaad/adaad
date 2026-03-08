# SPDX-License-Identifier: Apache-2.0
"""Immutable append-only mutation ledger — canonical runtime implementation.

This module is the authoritative implementation. The governance/ adapter layer
re-exports from here. Import from runtime.governance.mutation_ledger directly
or via the runtime.api.app_layer facade.
"""

from __future__ import annotations

import os
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from runtime.evolution.event_signing import DeterministicMockSigner, EventSigner, EventVerifier, SignatureBundle
from runtime.governance.policy_artifact import GovernancePolicyError, load_governance_policy

GENESIS_PREV_HASH = "sha256:" + ("0" * 64)


@dataclass(frozen=True)
class LedgerEntry:
    variant_id: str
    seed: int
    metrics: dict[str, float]
    promoted: bool

    def serialized(self) -> str:
        return json.dumps(
            {
                "variant_id": self.variant_id,
                "seed": self.seed,
                "metrics": self.metrics,
                "promoted": self.promoted,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def sha256(self) -> str:
        return hashlib.sha256(self.serialized().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LedgerKeyMetadata:
    active_key_id: str
    trusted_key_ids: tuple[str, ...]
    allowed_algorithms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "active_key_id": self.active_key_id,
            "trusted_key_ids": list(self.trusted_key_ids),
            "allowed_algorithms": list(self.allowed_algorithms),
        }


def canonical_payload_hash(entry: LedgerEntry) -> str:
    digest = hashlib.sha256(entry.serialized().encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def canonical_record_payload(
    *,
    entry: LedgerEntry,
    prev_hash: str,
    payload_hash: str,
    key_metadata: LedgerKeyMetadata,
) -> str:
    payload = {
        "entry": json.loads(entry.serialized()),
        "prev_hash": prev_hash,
        "canonical_payload_hash": payload_hash,
        "key_metadata": key_metadata.to_dict(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def record_hash(*, canonical_payload: str, signature_bundle: SignatureBundle) -> str:
    digest = hashlib.sha256(
        (
            canonical_payload
            + "|"
            + signature_bundle.signature
            + "|"
            + signature_bundle.signing_key_id
            + "|"
            + signature_bundle.algorithm
        ).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _infer_test_mode() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("ADAAD_ENV") == "test"


def _default_key_metadata() -> LedgerKeyMetadata:
    try:
        policy = load_governance_policy()
        trusted = tuple(sorted(set(policy.signer.trusted_key_ids + (policy.signer.key_id,))))
        return LedgerKeyMetadata(
            active_key_id=policy.signer.key_id,
            trusted_key_ids=trusted,
            allowed_algorithms=(policy.signer.algorithm,),
        )
    except GovernancePolicyError:
        return LedgerKeyMetadata(
            active_key_id="mock-kms-key",
            trusted_key_ids=("mock-kms-key",),
            allowed_algorithms=("hmac-sha256",),
        )


class MutationLedger:
    def __init__(
        self,
        path: Path,
        *,
        signer: EventSigner | None = None,
        verifier: EventVerifier | None = None,
        key_metadata: LedgerKeyMetadata | None = None,
        test_mode: bool | None = None,
    ) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self.test_mode = _infer_test_mode() if test_mode is None else test_mode
        if self.test_mode:
            deterministic = DeterministicMockSigner()
            self.signer: EventSigner = signer or deterministic
            self.verifier: EventVerifier = verifier or deterministic
        else:
            if signer is None or verifier is None:
                raise ValueError("MutationLedger requires production signer and verifier when test_mode is disabled")
            if isinstance(signer, DeterministicMockSigner) or isinstance(verifier, DeterministicMockSigner):
                raise ValueError("DeterministicMockSigner is restricted to test_mode only")
            self.signer = signer
            self.verifier = verifier
        if key_metadata is not None:
            self.key_metadata = key_metadata
        elif self.test_mode:
            self.key_metadata = LedgerKeyMetadata(
                active_key_id="mock-kms-key",
                trusted_key_ids=("mock-kms-key",),
                allowed_algorithms=("hmac-sha256",),
            )
        else:
            self.key_metadata = _default_key_metadata()

    def append(self, entry: LedgerEntry) -> str:
        prev_hash = self.last_hash()
        payload_hash = canonical_payload_hash(entry)
        canonical = canonical_record_payload(
            entry=entry,
            prev_hash=prev_hash,
            payload_hash=payload_hash,
            key_metadata=self.key_metadata,
        )
        signature_bundle = self.signer.sign(canonical)
        payload = {
            "entry": json.loads(entry.serialized()),
            "prev_hash": prev_hash,
            "canonical_payload_hash": payload_hash,
            "signature_bundle": {
                "signature": signature_bundle.signature,
                "signing_key_id": signature_bundle.signing_key_id,
                "algorithm": signature_bundle.algorithm,
            },
            "key_metadata": self.key_metadata.to_dict(),
            "hash": record_hash(canonical_payload=canonical, signature_bundle=signature_bundle),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return str(payload["hash"])

    def last_hash(self) -> str:
        for line in reversed(self.path.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                return str(json.loads(line).get("hash", GENESIS_PREV_HASH))
        return GENESIS_PREV_HASH

    def entries(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


__all__ = [
    "GENESIS_PREV_HASH",
    "LedgerEntry",
    "LedgerKeyMetadata",
    "MutationLedger",
    "canonical_payload_hash",
    "canonical_record_payload",
    "record_hash",
]
