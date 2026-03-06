# SPDX-License-Identifier: Apache-2.0
# Federation Key Registry

**Status:** Active — Governed by `governance/federation_trusted_keys.json`
**Last reviewed:** 2026-03-05
**Governance impact:** Critical — changes require PR review + CI gate pass

---

## Purpose

The federation key registry prevents caller-supplied public key substitution attacks in the
federation transport layer. Prior to PR-SECURITY-01, `verify_message_signature()` accepted
any public key embedded in the message payload, allowing an attacker to substitute their
own key+signature pair. This document governs the registry lifecycle.

---

## Architecture

```
governance/federation_trusted_keys.json   ← source of truth (in-repo, governance-signed)
       │
       ▼
runtime/governance/federation/key_registry.py   ← loader with in-process cache
       │
       ▼
runtime/governance/federation/transport.py      ← verify_message_signature()
       │                                            calls get_trusted_public_key(key_id)
       ▼
FederationTransportContractError raised if key_id not in registry
```

---

## Registry Format

`governance/federation_trusted_keys.json`:

```json
{
  "trusted_keys": [
    {
      "key_id": "federation-root-1",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `key_id` | string | ✅ | Unique identifier. Referenced in federation message `$.signature.key_id`. |
| `public_key_pem` | string | ✅ | Ed25519 public key in PEM format. |

---

## Adding a Key

1. Generate an Ed25519 key pair:
   ```bash
   python3 -c "
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
   key = Ed25519PrivateKey.generate()
   pub = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
   print(pub.decode())
   "
   ```
2. Add a new entry to `governance/federation_trusted_keys.json` with a unique `key_id`.
3. Open a PR targeting `main` with label `governance-impact`.
4. Obtain ≥ 2 reviewer approvals.
5. Verify CI green — the registry is validated at boot by `key_registry.py`.

---

## Revoking a Key

1. Remove the entry for the `key_id` from `governance/federation_trusted_keys.json`.
2. Open a PR with label `governance-impact` and `security`.
3. After merge, any federation message signed by the revoked key will be rejected
   with `federation_key_id_untrusted:<key_id>`.

---

## Key Rotation Runbook

| Step | Action |
|---|---|
| 1 | Generate replacement key pair (see "Adding a Key" above). |
| 2 | Add new key entry with a new `key_id` (e.g. `federation-root-2`). |
| 3 | Merge PR, deploy. Both old and new keys now accepted. |
| 4 | Update all federation peers to sign with new key_id. |
| 5 | After all peers migrated, remove old key entry in a follow-up PR. |
| 6 | Emit `FEDERATION_KEY_ROTATED` ledger event manually or via rotation script. |

---

## Error Codes

| Code | Meaning |
|---|---|
| `key_registry:unreadable` | Registry file missing or malformed JSON. Boot fails. |
| `federation_key_registry_invalid` | Registry has no `trusted_keys` list or list is empty. |
| `federation_key_registry_malformed` | Individual key entry missing required fields. |
| `federation_key_id_untrusted:<key_id>` | Message presents a key_id not in registry. |

---

## Tests

- `tests/governance/federation/test_federation_key_registry.py` — registry loader unit tests
- `tests/governance/federation/test_federation_transport_trusted_keys.py` — transport integration tests

---

## Related Governance Documents

- [Security Invariants Matrix](SECURITY_INVARIANTS_MATRIX.md)
- [Federation Conflict Runbook](FEDERATION_CONFLICT_RUNBOOK.md)
- [Replay Proof of Legitimacy Exchange](REPLAY_PROOF_OF_LEGITIMACY_EXCHANGE.md)

---

## Phase 5: HMAC Federation Key Rotation Runbook

Phase 5 adds HMAC signing to all federated mutation proposals via
`FederationManifest`.  The HMAC key is separate from the transport signing key
and governs proposal envelope integrity.

### HMAC Key Requirements

| Attribute | Requirement |
|---|---|
| Minimum length | 32 bytes (256 bits) |
| Environment variable | `ADAAD_FEDERATION_HMAC_KEY` |
| Mode enforcement | `federation_mode_enabled=True` → fail-closed (raises `FederationHMACKeyError`) |
| Mode tolerance | `federation_mode_enabled=False` → WARNING only (dev/test) |
| Rotation cadence | Every 90 days or immediately on suspected compromise |

### HMAC Key Rotation Procedure

| Step | Action | Governance Gate |
|---|---|---|
| 1 | Generate 32-byte cryptographically random key: `python3 -c "import secrets; print(secrets.token_hex(32))"` | — |
| 2 | Store new key in KMS/HSM with label `adaad-federation-hmac-v{N+1}` | KMS operator sign-off |
| 3 | Update `ADAAD_FEDERATION_HMAC_KEY` env var in deployment config | PR review + CI gate |
| 4 | Deploy to staging; run federation determinism CI job | CI green required |
| 5 | Verify `validate_hmac_key()` passes in staging logs | Ops verification |
| 6 | Deploy to production with rolling restart | Change management |
| 7 | Emit `FEDERATION_HMAC_KEY_ROTATED` ledger event | Automated (deployment hook) |
| 8 | Archive old key in KMS with `retired` label; do NOT delete for 30 days | KMS audit trail |
| 9 | Update this document with new key version and rotation date | Documentation PR |

### Emergency Rotation (Suspected Compromise)

1. Immediately set `federation_mode_enabled=False` to halt federation gate enforcement while rotating.
2. Generate and deploy new HMAC key (Steps 1–6 above, expedited).
3. Invalidate all proposals signed with the compromised key — set status `quarantined:hmac_key_compromised`.
4. Re-enable `federation_mode_enabled=True`.
5. File a `security` incident in the governance ledger with full timeline.

### HMAC Key Error Codes

| Code | Meaning |
|---|---|
| `federation_hmac_key_weak` | Key is present but shorter than 32 bytes. Raises in federation mode. |
| `federation_hmac_key_missing` | `ADAAD_FEDERATION_HMAC_KEY` env var is unset or empty. |
| `FederationHMACKeyError` | Python exception raised on contract violation in federation mode. |

### Tests

- `runtime/governance/federation/tests/test_federation_hmac_key_validation.py` — 21 tests covering key validation, mode enforcement, boundary cases.

---

## Phase 5: Federated Evidence Matrix Key Anchors

Every federated epoch produces a `chain_digest` that is registered in the
`FederatedEvidenceMatrix`.  These digests are anchors for cross-repo
determinism verification.

### Anchor Registration

Anchors are registered automatically by `EvolutionFederationBridge.on_epoch_rotation()`.

Manual registration (emergency recovery):

```bash
python3 -c "
from runtime.governance.federation.federated_evidence_matrix import FederatedEvidenceMatrix
m = FederatedEvidenceMatrix(audit_writer=None)
m.record_local_epoch('epoch-id', 'sha256:<digest>')
print('Registered')
"
```

### Anchor Conflict Resolution

If `record_local_epoch` raises `FederatedEvidenceMatrixError` with `local_epoch_digest_conflict`:
1. Do NOT overwrite — a conflict indicates replay divergence or tampering.
2. Open a `security` incident immediately.
3. Halt federated mutation propagation (`federation_mode_enabled=False`).
4. Run full replay verification across the conflicted epoch.
5. Resolve via governance sign-off before re-enabling federation.

---
