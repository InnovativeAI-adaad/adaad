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

from runtime.evolution.event_signing import (
    DeterministicMockSigner,
    EventSigner,
    EventVerifier,
    SignatureBundle,
    load_hmac_keyring_from_env,
    HMACKeyringVerifier,
)
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


def _production_verifier_from_env() -> EventVerifier:
    return HMACKeyringVerifier(load_hmac_keyring_from_env())

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
            if signer is None:
                raise ValueError("MutationLedger requires production signer when test_mode is disabled")
            resolved_verifier = verifier or _production_verifier_from_env()
            if isinstance(signer, DeterministicMockSigner) or isinstance(resolved_verifier, DeterministicMockSigner):
                raise ValueError("DeterministicMockSigner is restricted to test_mode only")
            self.signer = signer
            self.verifier = resolved_verifier
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

    def _validate_existing_chain(self) -> None:
        rows = self.entries()
        expected_prev = GENESIS_PREV_HASH
        for index, row in enumerate(rows, start=1):
            entry_obj = row.get("entry")
            if not isinstance(entry_obj, dict):
                raise ValueError(f"row {index}: entry must be an object")
            ledger_entry = LedgerEntry(
                variant_id=str(entry_obj.get("variant_id", "")),
                seed=int(entry_obj.get("seed")),
                metrics={str(k): float(v) for k, v in dict(entry_obj.get("metrics", {})).items()},
                promoted=bool(entry_obj.get("promoted")),
            )
            prev_hash = str(row.get("prev_hash", ""))
            if prev_hash != expected_prev:
                raise ValueError(f"row {index}: prev_hash mismatch expected {expected_prev} got {prev_hash}")

            payload_hash = str(row.get("canonical_payload_hash", ""))
            expected_payload_hash = canonical_payload_hash(ledger_entry)
            if payload_hash != expected_payload_hash:
                raise ValueError(f"row {index}: canonical_payload_hash mismatch")

            signature_obj = row.get("signature_bundle")
            if not isinstance(signature_obj, dict):
                raise ValueError(f"row {index}: signature_bundle must be an object")
            signature = SignatureBundle(
                signature=str(signature_obj.get("signature", "")),
                signing_key_id=str(signature_obj.get("signing_key_id", "")),
                algorithm=str(signature_obj.get("algorithm", "")),
            )
            top_level_key_id = str(row.get("signing_key_id", ""))
            top_level_algorithm = str(row.get("signature_algorithm", ""))
            if top_level_key_id and top_level_key_id != signature.signing_key_id:
                raise ValueError(f"row {index}: signing_key_id metadata mismatch")
            if top_level_algorithm and top_level_algorithm != signature.algorithm:
                raise ValueError(f"row {index}: signature_algorithm metadata mismatch")

            key_meta_obj = row.get("key_metadata")
            if not isinstance(key_meta_obj, dict):
                raise ValueError(f"row {index}: key_metadata must be an object")
            key_metadata = LedgerKeyMetadata(
                active_key_id=str(key_meta_obj.get("active_key_id", "")),
                trusted_key_ids=tuple(str(x) for x in key_meta_obj.get("trusted_key_ids", [])),
                allowed_algorithms=tuple(str(x) for x in key_meta_obj.get("allowed_algorithms", [])),
            )

            if signature.signing_key_id not in set(key_metadata.trusted_key_ids):
                raise ValueError(f"row {index}: signing key is not trusted by key_metadata")
            if signature.algorithm not in set(key_metadata.allowed_algorithms):
                raise ValueError(f"row {index}: signature algorithm is not allowed by key_metadata")

            canonical = canonical_record_payload(
                entry=ledger_entry,
                prev_hash=prev_hash,
                payload_hash=payload_hash,
                key_metadata=key_metadata,
            )
            if not self.verifier.verify(message=canonical, signature=signature):
                raise ValueError(f"row {index}: signature verification failed")

            expected_hash = record_hash(canonical_payload=canonical, signature_bundle=signature)
            actual_hash = str(row.get("hash", ""))
            if actual_hash != expected_hash:
                raise ValueError(f"row {index}: hash mismatch")
            expected_prev = actual_hash

    def append(self, entry: LedgerEntry) -> str:
        if not self.test_mode:
            self._validate_existing_chain()
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
            "signing_key_id": signature_bundle.signing_key_id,
            "signature_algorithm": signature_bundle.algorithm,
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
