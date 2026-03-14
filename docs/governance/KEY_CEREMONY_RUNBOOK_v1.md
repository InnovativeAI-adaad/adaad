# Governance Key Ceremony Runbook v1

**Version:** 1.0.0
**Status:** Ready for Execution
**Effective:** 2026-03-14
**Authority:** `CONSTITUTION.md → SECURITY_INVARIANTS_MATRIX.md`
**Owner:** ArchitectAgent (`architect@adaad.ai`)
**Implements:** FINDING-66-004 (Phase 66 / WORK-66-D)
**Classification:** Governance-Critical — Handle with care

---

## Purpose

This runbook specifies the Ed25519 governance key ceremony for ADAAD. Executing
this ceremony upgrades the system from single-key governance to a 2-of-3
threshold model, eliminating the single point of failure on the constitutional
lineage chain.

Until this ceremony is executed, governance signatures rely on a single key.
The ceremony is a one-time event. Once executed, the threshold model is permanent
and cannot be downgraded without a constitutional amendment.

**Constitutional constraint:** This ceremony MUST be executed by humans.
No agent may execute, simulate, or partially execute this ceremony.
ArchitectAgent's role is specification only.

---

## Key Holder Roles

| Role | Holder | Responsibility |
|------|--------|----------------|
| PRIMARY | Dustin L. Reid (Innovadaad) | Day-to-day governance signing; quorum anchor |
| SECONDARY | To be designated by Innovadaad | Second signer for amendments; backup PRIMARY |
| WITNESS | To be designated by Innovadaad | Third signer; emergency quorum completion |

**Designation action required:** Before executing this ceremony, Innovadaad must
designate SECONDARY and WITNESS key holders and record their names in this document.

```
SECONDARY key holder: _____________________________ (Innovadaad to complete)
WITNESS key holder:   _____________________________ (Innovadaad to complete)
```

SECONDARY and WITNESS may be individuals, hardware security modules (HSMs), or
held in reserve by Innovadaad pending future team growth. A single person MAY
hold SECONDARY or WITNESS roles initially, but PRIMARY+SECONDARY must be held
by different individuals for meaningful threshold protection.

---

## Threshold Signing Rule

Any of the following governance actions requires **signatures from at least 2 of 3
key holders** (2-of-3 threshold):

- Constitutional rule addition, modification, or removal
- SECURITY_INVARIANTS_MATRIX.md changes
- ARCHITECTURE_CONTRACT.md layer boundary changes
- Federation trusted key roster changes
- Governance ledger genesis event issuance
- This runbook's own amendment

Single-key signatures remain valid for all other governance actions (standard
PR merge, phase plans, documentation updates).

---

## Pre-Ceremony Requirements

Complete all of the following before scheduling the ceremony:

- [ ] SECONDARY key holder designated and named above
- [ ] WITNESS key holder designated and named above
- [ ] Air-gapped machine (or dedicated offline device) available for each key holder
- [ ] Python 3.8+ with `cryptography` library available on ceremony machine
- [ ] Secure storage for private keys decided (encrypted USB, hardware key, HSM, etc.)
- [ ] Date and attendance confirmed for all key holders (or async ceremony coordinated)

---

## Part 1 — Key Generation

Each key holder executes the following independently on their own machine.
**Private keys MUST NOT be shared, transmitted, or stored on networked systems.**

### Step 1.1 — Generate Ed25519 Key Pair

Run on an air-gapped or trusted machine:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

# Generate key
private_key = Ed25519PrivateKey.generate()
public_key  = private_key.public_key()

# Export public key (safe to share)
public_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
print("PUBLIC KEY (commit this to repo):")
print(public_pem.decode())

# Export private key (NEVER share or commit)
private_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
print("PRIVATE KEY (store securely, never commit):")
print(private_pem.decode())
```

### Step 1.2 — Assign Key IDs

Key IDs follow the pattern `governance-<role>-1`:

| Role | Key ID |
|------|--------|
| PRIMARY | `governance-primary-1` |
| SECONDARY | `governance-secondary-1` |
| WITNESS | `governance-witness-1` |

### Step 1.3 — Record Public Keys

Each key holder transmits ONLY their public key PEM to the ceremony coordinator
(Innovadaad). Private keys remain with each holder permanently.

---

## Part 2 — Registry Commit

The ceremony coordinator (Innovadaad) commits all three public keys to the repo.

### Step 2.1 — Update governance/federation_trusted_keys.json

Add all three governance keys to the trusted key registry:

```json
{
  "trusted_keys": [
    {
      "key_id": "governance-primary-1",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n<PRIMARY PUBLIC KEY>\n-----END PUBLIC KEY-----",
      "role": "governance",
      "holder": "Dustin L. Reid",
      "created": "YYYY-MM-DD"
    },
    {
      "key_id": "governance-secondary-1",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n<SECONDARY PUBLIC KEY>\n-----END PUBLIC KEY-----",
      "role": "governance",
      "holder": "<SECONDARY HOLDER NAME>",
      "created": "YYYY-MM-DD"
    },
    {
      "key_id": "governance-witness-1",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n<WITNESS PUBLIC KEY>\n-----END PUBLIC KEY-----",
      "role": "governance",
      "holder": "<WITNESS HOLDER NAME>",
      "created": "YYYY-MM-DD"
    }
  ]
}
```

### Step 2.2 — Emit Genesis Ledger Event

After the registry commit merges, emit a genesis event to the governance ledger:

```python
from runtime.evolution.lineage_v2 import LineageLedgerV2

ledger = LineageLedgerV2()
ledger.append_event("GovernanceKeyCeremony", {
    "ceremony_version": "1.0.0",
    "threshold": "2-of-3",
    "algorithm": "Ed25519",
    "key_ids": [
        "governance-primary-1",
        "governance-secondary-1",
        "governance-witness-1"
    ],
    "executed_by": "Dustin L. Reid",
    "ceremony_date": "YYYY-MM-DD",
    "runbook_version": "KEY_CEREMONY_RUNBOOK_v1.md"
})
print("Genesis event committed to governance ledger.")
```

### Step 2.3 — Produce Ceremony Artifact

Create `governance/KEY_CEREMONY_RECORD_v1.json` in the repo:

```json
{
  "ceremony_version": "1.0.0",
  "executed_date": "YYYY-MM-DD",
  "threshold": "2-of-3",
  "algorithm": "Ed25519",
  "key_holders": {
    "primary":   { "key_id": "governance-primary-1",   "holder": "Dustin L. Reid" },
    "secondary": { "key_id": "governance-secondary-1", "holder": "<NAME>" },
    "witness":   { "key_id": "governance-witness-1",   "holder": "<NAME>" }
  },
  "ledger_genesis_hash": "<hash of GovernanceKeyCeremony ledger entry>",
  "runbook_ref": "docs/governance/KEY_CEREMONY_RUNBOOK_v1.md"
}
```

This file is evidence. It is committed to main via a PR signed by PRIMARY.

---

## Part 3 — Threshold Signing Procedure

For any action requiring 2-of-3 threshold:

### Step 3.1 — Proposer Signs

The proposer (typically PRIMARY) signs the governance artifact:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import hashlib, json

artifact = json.dumps(your_governance_artifact, sort_keys=True).encode()
artifact_hash = hashlib.sha256(artifact).hexdigest()

private_key = load_pem_private_key(open("primary_key.pem", "rb").read(), password=None)
signature = private_key.sign(artifact_hash.encode())
print("signature_hex:", signature.hex())
print("key_id: governance-primary-1")
```

### Step 3.2 — Second Signer Verifies and Countersigns

The second signer independently verifies the artifact content and signs:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# Verify proposer signature first
public_key = load_pem_public_key(open("primary_public.pem", "rb").read())
public_key.verify(bytes.fromhex(proposer_sig_hex), artifact_hash.encode())
print("Proposer signature verified.")

# Then countersign
my_private = load_pem_private_key(open("secondary_key.pem", "rb").read(), password=None)
my_sig = my_private.sign(artifact_hash.encode())
print("countersignature_hex:", my_sig.hex())
print("key_id: governance-secondary-1")
```

### Step 3.3 — Commit Both Signatures

The PR for any threshold-required action must include both signatures in a
`.signatures` sidecar file alongside the governed artifact.

---

## Part 4 — Key Revocation and Rotation

If a key is compromised or a key holder departs:

1. **Halt threshold-required actions** until rotation is complete
2. **Convene remaining 2 holders** — the 2 uncompromised holders issue a
   `GovernanceKeyRevocation` ledger event naming the revoked key ID
3. **Generate replacement key** following Part 1 above
4. **Remove revoked key** from `governance/federation_trusted_keys.json`
   (the old key_id must remain in the ledger history — only remove from
   the active registry)
5. **Add replacement key** to the registry via a threshold-signed PR
6. **Update KEY_CEREMONY_RECORD** with new key holder information
7. **Emit `GovernanceKeyRotation` ledger event** recording the event

**Invariant:** The hash chain is never broken during rotation. The revocation
and replacement are separate ledger events; the chain links through both.

---

## Part 5 — Ceremony Completion Checklist

Record completion of each step. All items must be checked before FINDING-66-004
can be closed.

- [ ] SECONDARY key holder designated and named
- [ ] WITNESS key holder designated and named
- [ ] PRIMARY Ed25519 key pair generated (air-gapped recommended)
- [ ] SECONDARY Ed25519 key pair generated
- [ ] WITNESS Ed25519 key pair generated
- [ ] All three public keys committed to `governance/federation_trusted_keys.json`
- [ ] `GovernanceKeyCeremony` ledger event emitted and hash recorded
- [ ] `governance/KEY_CEREMONY_RECORD_v1.json` committed to main
- [ ] PR signed by PRIMARY key
- [ ] `.adaad_agent_state.json` updated: FINDING-66-004 status → `"resolved"`

---

## Ceremony Execution Tracking

This runbook is published. The ceremony itself is a separate phase action.

| Item | Status |
|------|--------|
| Runbook published | ✅ 2026-03-14 |
| SECONDARY designated | ⏳ Pending Innovadaad |
| WITNESS designated | ⏳ Pending Innovadaad |
| Keys generated | ⏳ Pending ceremony execution |
| Registry committed | ⏳ Pending ceremony execution |
| Ledger genesis event | ⏳ Pending ceremony execution |
| FINDING-66-004 closed | ⏳ Pending full execution |

Ceremony execution may occur in Phase 66 (async) or is deferred to Phase 67
as a dedicated governance milestone, at Innovadaad's discretion.

---

## References

- Constitutional basis: `CONSTITUTION.md` §Fail-Closed Governance
- Federation key architecture: `docs/governance/FEDERATION_KEY_REGISTRY.md`
- Security invariants: `docs/governance/SECURITY_INVARIANTS_MATRIX.md`
- Active key registry: `governance/federation_trusted_keys.json`
- Ceremony record (post-execution): `governance/KEY_CEREMONY_RECORD_v1.json`
