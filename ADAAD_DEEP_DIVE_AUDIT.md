# ADAAD Deep Dive Audit — Auth Hardening Path Realignment

Audit-ID: AUTH-PATH-REALIGN-2026-03

## Objective
Realign all auth-hardening documentation and PR draft references so session/governance token validation points to the active implementation in `security/cryovant.py`, not `runtime/governance/auth/`.

## Authoritative Source of Truth
Verified canonical anchors in `security/cryovant.py`:

- `def verify_session(token: str) -> bool`
- `def verify_governance_token(`
- `fallback_namespace: str = "adaad-governance-session-dev-secret"`

## Audit Corrections

## Non-Canonical Path Notice

The path `runtime/governance/auth/` is not the active token validation surface.
Any PR or hardening change targeting that path for session/governance token
verification is considered misapplied and must be rejected in review.


### Severity Table Path Corrections
| Severity | Finding | Correct file path |
|---|---|---|
| High | Session validation hardening target misalignment | `security/cryovant.py` |
| High | Governance token validation hardening target misalignment | `security/cryovant.py` |
| Medium | Boot-entry auth validation reference alignment | `app/main.py` (when boot validation is part of scope) |

### Draft PR File List Realignment
For all auth-hardening PR specs, the canonical file targets are:

- `security/cryovant.py`
- `app/main.py` (only if boot validation wiring is in scope)
- Runtime boot entrypoints that invoke `verify_governance_token()` (if modified in that PR)

> `runtime/governance/auth/` must not be listed for token validation hardening.

### Implementation Snippet Realignment
All hardening snippets must patch real implementation surfaces:

```python
# security/cryovant.py

def verify_session(token: str) -> bool:
    ...


def verify_governance_token(...):
    ...
```

Boot validation examples (if included) must target:

```python
# app/main.py
# or the active runtime boot entrypoint
```

## Caller Verification Pass
Repository checks were run for:

- `verify_session(`
- `verify_governance_token(`
- `CRYOVANT_DEV_TOKEN`
- `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY`
- stale imports from `runtime.governance.auth`

Result: no `runtime/governance/auth` module references remain for token validation and no imports from `runtime.governance.auth` were found.

## Risk Classification
- **Operational risk:** Low (documentation/spec realignment only)
- **Governance correctness impact:** High (prevents hardening being applied to non-active paths)
