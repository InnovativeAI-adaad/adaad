# Production Auth Contract Design

## Token Format

## Canonical Implementation Location

Session and governance token validation logic is implemented in:

- `security/cryovant.py`

Do not target `runtime/governance/auth/` for auth hardening patches; that path is non-canonical for token validation.

`cryovant-gov-v1:<key_id>:<expires_at_unix>:<nonce>:sha256:<digest>`

Digest verification input:

`sha256:<key_id>:<expires_at_unix>:<nonce>`

Signature key resolution follows deterministic precedence:

1. `ADAAD_GOVERNANCE_SESSION_KEY_<KEY_ID>`
2. `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY`
3. fallback namespace secret (`adaad-governance-session-dev-secret:<key_id>`)
   (defined and resolved in `security/cryovant.py`)

## Security Properties

- expiry-bound token acceptance
- explicit key identity
- deterministic local verification
- no external network dependency

## Field constraints

- `key_id` and `nonce` must be trimmed, non-empty, and must not include `:` delimiters.
- Delimiter validation is enforced at both signing and verification time to prevent token-structure ambiguity.

## Dev Override Policy

`CRYOVANT_DEV_TOKEN` is accepted only when:

- `ADAAD_ENV=dev`
- `CRYOVANT_DEV_MODE` is truthy

## Migration Guidance

- Existing callers should migrate from `verify_session(...)` to `verify_governance_token(...)`.
- Keep `verify_session` for backward compatibility only; do not use for new governance paths.
- Boot-time validation examples must patch `app/main.py` (or the active runtime boot entrypoint), not a `runtime/governance/auth` module.
