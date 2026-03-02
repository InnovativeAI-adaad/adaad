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

## CI/CD Coverage Finding (Reclassified)

Previous wording that described ADAAD as having "missing CI/CD" is no longer accurate. The repository has multiple active GitHub Actions workflows, so the finding is reclassified from **No CI** to **targeted automation gaps**.

### Current-State Workflow Matrix

| Workflow file | Triggers | Primary purpose | Finding status |
|---|---|---|---|
| `.github/workflows/ci.yml` | `push`/`pull_request` on `main` | Primary CI pipeline (tests, governance checks, strict replay, evidence and promotion lanes) | Present |
| `.github/workflows/ci-generated.yml` | `pull_request`, `push` on `main`, `workflow_dispatch` | Generated-artifact CI validation for deterministic fixtures | Present |
| `.github/workflows/codeql.yml` | `push`/`pull_request` on `main`, weekly cron | CodeQL static analysis security lane | Present |
| `.github/workflows/governance_strict_release_gate.yml` | Release/governance tag pushes, `workflow_dispatch` | Strict release gate for governance/public-readiness tags | Present |
| `.github/workflows/release_evidence_gate.yml` | `push` for `v0.70.0` tag | Legacy tag-specific release evidence gate | Present (narrow scope) |
| `.github/workflows/redteam_nightly.yml` | Nightly cron, `workflow_dispatch` | Red-team nightly harness execution | Present |
| `.github/workflows/determinism_lint.yml` | `pull_request` on determinism-critical paths | Determinism lint lane for governance/evolution/security surfaces | Present |
| `.github/workflows/entropy_health.yml` | Daily cron, `workflow_dispatch` | Entropy health profile checks | Present |
| `.github/workflows/entropy_baseline.yml` | `push` on `main` | Entropy baseline generation/comparison baseline updates | Present |
| `.github/workflows/branch_protection_check.yml` | `pull_request` on `main`, `workflow_dispatch` | Branch protection policy verification gate | Present |

### Remaining Gaps (Specific, Not "No CI")

- **Secret-scanning CI lane gap:** no dedicated secret scanning workflow (for example, gitleaks/trufflehog) is defined under `.github/workflows/`.
- **Dependabot automation gap:** `.github/dependabot.yml` is absent, so dependency update PR automation is not currently configured.
- **Release gate consolidation gap:** both a strict governance release gate and a legacy fixed-tag release evidence gate exist; scope rationalization is still advisable.

## Audit Freshness

- **Assessment baseline commit SHA:** `0df3d3f7a3befe91faf6b327505a8f3e9ae31d49`
- **Baseline commit date:** `2026-03-02T07:34:19-06:00`
- **Workflow inventory source:** `.github/workflows/*.yml` at the baseline commit above.
