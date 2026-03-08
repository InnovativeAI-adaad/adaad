# Cryovant Key Handling

- `security/keys/` is created automatically on first run by Cryovant; if you need to provision it manually, run `mkdir -p security/keys` before setting owner-only permissions (`chmod 700 security/keys`).
- Do not commit private keys to version control.
- Ledger writes are recorded in `security/ledger/lineage.jsonl` and mirrored to `reports/metrics.jsonl`.

## Mutation ledger signing and verification

- Mutation ledger records now include `prev_hash`, `canonical_payload_hash`, `signature_bundle`, and `key_metadata` to enforce append-only lineage and signer-policy traceability.
- Non-test runtime paths must provide production `EventSigner` and `EventVerifier` implementations; deterministic mock signing is reserved for test mode.

### Operational key-rotation workflow

1. Provision a new signing key in the production signer backend (KMS/HSM) and mark it as pending active.
2. Update the governance policy artifact signer metadata (`signer.key_id`, `signer.trusted_key_ids`, and algorithm) so the new key is trusted before cutover.
3. Deploy signer/verifier configuration so runtime writes use the new active key while verifier trusts overlap keys during the rotation window.
4. Run full verification against existing and newly-written ledgers using:
   - `python scripts/verify_mutation_ledger.py --ledger <path-to-ledger.jsonl>`
5. Remove retired keys from trusted sets only after verification confirms no active records require them.

### Verification workflow

1. Export verifier key material for validation runs:
   - `export ADAAD_LEDGER_SIGNING_KEYS='{"<key-id>":"<shared-secret-or-test-key>"}'`
2. Execute the ledger verifier script against each ledger artifact.
3. Treat any chain mismatch, signature failure, or key-policy violation as fail-closed and block release progression.
