# Whale.Dic Secrets Setup (Mobile + Rotation)

## Security posture

Whale.Dic secrets for dork/ledger integrations are **fail-closed** and do **not** allow plaintext fallback env vars.

Forbidden plaintext env vars:

- `ADAAD_WHALEDIC_ANTHROPIC_API_KEY`
- `ADAAD_WHALEDIC_LEDGER_API_TOKEN`

If either is set, startup aborts with `plaintext_secret_env_forbidden:*`.

## Supported secret sources

Whale.Dic supports two secret backends:

1. **Encrypted environment payload** (`fernet:` token)
2. **OS keyring reference** (`service:user`)

### Encrypted environment loading

1. Generate a Fernet key (store outside repo):

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

2. Encrypt each secret:

```bash
python - <<'PY'
from cryptography.fernet import Fernet
key = b"<ADAAD_SECRETS_FERNET_KEY>"
print(Fernet(key).encrypt(b"<ANTHROPIC_API_KEY>").decode())
print(Fernet(key).encrypt(b"<LEDGER_API_TOKEN>").decode())
PY
```

3. Export runtime env (example mobile shell profile, not committed to git):

```bash
export ADAAD_SECRETS_FERNET_KEY='<key>'
export ADAAD_WHALEDIC_DORK_ENABLED=1
export ADAAD_WHALEDIC_ANTHROPIC_API_KEY_ENC='fernet:<encrypted_token>'
export ADAAD_WHALEDIC_LEDGER_AUTH_ENABLED=1
export ADAAD_WHALEDIC_LEDGER_API_TOKEN_ENC='fernet:<encrypted_token>'
```

### OS keystore-backed retrieval

Use keyring references when your mobile OS (or Termux plugin) exposes keyring APIs:

```bash
export ADAAD_WHALEDIC_DORK_ENABLED=1
export ADAAD_WHALEDIC_ANTHROPIC_API_KEY_KEYRING='adaad.whaledic:anthropic'
export ADAAD_WHALEDIC_LEDGER_AUTH_ENABLED=1
export ADAAD_WHALEDIC_LEDGER_API_TOKEN_KEYRING='adaad.whaledic:ledger_api'
```

The runtime reads secret material via keyring and only retains in process memory.

## Mobile operator procedure (Termux/Android)

1. Keep encrypted env exports in shell memory for the active session only.
2. Never commit secret values or encrypted blobs into repository files.
3. Start server/orchestrator; startup will fail if required secrets are missing or invalid.
4. Confirm Whale.Dic UI loads with key-availability flag (without exposing secret values).

## Rotation procedure

1. Generate new Fernet key (or write new keyring value).
2. Re-encrypt Anthropic + ledger API secrets using the new key.
3. Update runtime environment variables atomically in one maintenance window.
4. Restart service and verify startup gate passes.
5. Revoke old key/keyring material.
6. Record rotation event in your operator runbook / evidence ledger.

For repository plaintext-leak incidents, follow `docs/security/SECRET_ROTATION_RUNBOOK.md` in addition to this Whale.Dic-specific procedure.

## Failure codes

- `whaledic_secret_missing_required:*` — required secret not provided for enabled feature.
- `whaledic_secret_invalid_encrypted_payload` — encrypted env token cannot be decrypted.
- `whaledic_secret_backend_unavailable:keyring` — keyring backend unavailable.
- `whaledic_secret_multiple_sources:*` — both encrypted env and keyring ref set for same secret.
