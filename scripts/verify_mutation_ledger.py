# SPDX-License-Identifier: Apache-2.0
"""Validate mutation ledger chain integrity, signatures, and key policy compliance."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from runtime.evolution.event_signing import HMACKeyringVerifier, SignatureBundle, load_hmac_keyring_from_env
from runtime.governance.mutation_ledger import (
    GENESIS_PREV_HASH,
    LedgerEntry,
    LedgerKeyMetadata,
    canonical_payload_hash,
    canonical_record_payload,
    record_hash,
)
from runtime.governance.policy_artifact import GovernancePolicyError, load_governance_policy


def _load_policy_constraints() -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    if os.getenv("ADAAD_ENV") == "test":
        return None
    try:
        policy = load_governance_policy()
    except GovernancePolicyError:
        return None
    trusted = tuple(sorted(set(policy.signer.trusted_key_ids + (policy.signer.key_id,))))
    return policy.signer.key_id, trusted, (policy.signer.algorithm,)


def verify_mutation_ledger(ledger_path: Path) -> None:
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return
    verifier = HMACKeyringVerifier(load_hmac_keyring_from_env())
    policy_constraints = _load_policy_constraints()

    expected_prev = GENESIS_PREV_HASH
    for index, row in enumerate(rows, start=1):
        entry_obj = row.get("entry")
        if not isinstance(entry_obj, dict):
            raise ValueError(f"row {index}: entry must be an object")
        entry = LedgerEntry(
            variant_id=str(entry_obj.get("variant_id", "")),
            seed=int(entry_obj.get("seed")),
            metrics={str(k): float(v) for k, v in dict(entry_obj.get("metrics", {})).items()},
            promoted=bool(entry_obj.get("promoted")),
        )
        prev_hash = str(row.get("prev_hash", ""))
        if prev_hash != expected_prev:
            raise ValueError(f"row {index}: prev_hash mismatch expected {expected_prev} got {prev_hash}")

        payload_hash = str(row.get("canonical_payload_hash", ""))
        expected_payload_hash = canonical_payload_hash(entry)
        if payload_hash != expected_payload_hash:
            raise ValueError(f"row {index}: canonical_payload_hash mismatch")

        key_meta_obj = row.get("key_metadata")
        if not isinstance(key_meta_obj, dict):
            raise ValueError(f"row {index}: key_metadata must be an object")
        key_metadata = LedgerKeyMetadata(
            active_key_id=str(key_meta_obj.get("active_key_id", "")),
            trusted_key_ids=tuple(str(x) for x in key_meta_obj.get("trusted_key_ids", [])),
            allowed_algorithms=tuple(str(x) for x in key_meta_obj.get("allowed_algorithms", [])),
        )

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

        if signature.signing_key_id not in set(key_metadata.trusted_key_ids):
            raise ValueError(f"row {index}: signing key is not trusted by key_metadata")
        if signature.algorithm not in set(key_metadata.allowed_algorithms):
            raise ValueError(f"row {index}: signature algorithm is not allowed by key_metadata")

        if policy_constraints is not None:
            active_key, trusted_keys, allowed_algorithms = policy_constraints
            if signature.signing_key_id not in set(trusted_keys):
                raise ValueError(f"row {index}: signing key is not trusted by governance policy")
            if signature.algorithm not in set(allowed_algorithms):
                raise ValueError(f"row {index}: signature algorithm is not allowed by governance policy")
            if key_metadata.active_key_id != active_key:
                raise ValueError(f"row {index}: key_metadata.active_key_id does not match governance policy")

        canonical = canonical_record_payload(
            entry=entry,
            prev_hash=prev_hash,
            payload_hash=payload_hash,
            key_metadata=key_metadata,
        )
        if not verifier.verify(message=canonical, signature=signature):
            raise ValueError(f"row {index}: signature verification failed")

        expected_hash = record_hash(canonical_payload=canonical, signature_bundle=signature)
        actual_hash = str(row.get("hash", ""))
        if actual_hash != expected_hash:
            raise ValueError(f"row {index}: hash mismatch")
        expected_prev = actual_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True, help="Path to mutation ledger JSONL file")
    args = parser.parse_args()
    verify_mutation_ledger(args.ledger)
    print(f"OK: verified mutation ledger {args.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
