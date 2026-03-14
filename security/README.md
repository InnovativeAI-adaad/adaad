# Water (security)

Cryovant enforces environment validation, agent certification, and lineage ancestry checks. Ledger data is stored under `security/ledger/` and must be writable; keys live in `security/keys/` with owner-only permissions. Any failed validation blocks Dream/Beast execution.

Signature verification expects `sha256:<hex>` digests computed from `HMAC-SHA-256(key_bytes, b"cryovant")` and evaluates key files in `security/keys/` using deterministic filename ordering to support key rotation.

## Key rotation attestation

- `security/key_rotation_attestation.py` validates `security/keys/rotation.json` with deterministic reason codes.
- Validation supports both:
  - full attestation records (`rotation_date`, `previous_rotation_date`, `next_rotation_due`, `policy_days`, `attestation_hash`), and
  - legacy Cryovant metadata (`interval_seconds`, `last_rotation_ts`, `last_rotation_iso`) for migration compatibility.
- Full attestation hashing excludes ephemeral fields (`nonce`, `generated_at`, `host_info`, `attestation_hash`) before canonicalization so replay digests remain stable.
- `KEY_ROTATION_VERIFIED` can be emitted to metrics, lineage, and journal with a frozen payload to avoid post-construction mutation.


## Identity ring verification

- Cryovant now supports per-operation ring context verification for `device`, `agent`, `human`, and `federation` identity rings.
- Canonical schema enforcement lives in `security/ring_claims.py` and requires deterministic JSON canonicalization (`sort_keys=True`, compact separators) before hashing.
- `security/identity_rings.py::build_ring_token` now derives ring digests from the canonical claims payload and is consumed by `security/cryovant.py::verify_identity_rings` and `verify_governance_token(..., ring_claims=...)`.
- Ring verification outcomes are emitted fail-closed to ledger + runtime audit surfaces with explicit per-ring reasons:
  - ledger actions: `identity_ring_verified` / `identity_ring_verification_failed`
  - metrics event: `cryovant_ring_verification_result`
- Federation requests can enforce origin with `expected_federation_origin`; source mismatch fails closed with `federation_origin_mismatch`.
