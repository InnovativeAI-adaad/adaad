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

## 8. Dependency-safe merge sequence

This section is the canonical workflow reference for selecting and staging the next PR when `ADAAD` is invoked without an explicit PR target.

### Ordered PR list

Process PRs in this exact order unless an explicit, documented governance exception is approved by lane ownership:

1. `PR-CI-01` — Unify Python version pin
2. `PR-CI-02` — SPDX header enforcement
3. `PR-LINT-01` — Determinism lint: `adaad/orchestrator/`
4. `PR-HARDEN-01` — Boot env validation + signing key assertion
5. `PR-SECURITY-01` — Federation key pinning registry
6. `PR-PERF-01` — Streaming lineage ledger
7. `PR-OPS-01` — Snapshot atomicity + sequence ordering
8. `PR-DOCS-01` — Federation key registry governance doc

### Dependency rules

- Never skip a PR in the ordered list above.
- A PR is eligible only when all listed prerequisites are merged.
- `PR-SECURITY-01` requires transport.py audit completion before implementation starts.
- `PR-DOCS-01` prerequisite: `PR-OPS-01` must be merged (strict serial dependency model).
- Sequence is flexible here only for docs lane: **disabled** under current policy; `PR-DOCS-01` does not run in parallel and remains gated behind the serial sequence.
- Out-of-sequence changes on security or determinism surfaces are rejected unless lane-owner sign-off is explicitly recorded in the PR description.
- Agent MUST emit `[ADAAD WAITING]` unless `PR-OPS-01` is merged and CI-green on merge SHA.

### Criteria for “next unmerged PR”

Select the next PR using all criteria below:

1. Start at the top of the ordered PR list and scan downward.
2. Ignore PRs already merged.
3. For the first unmerged PR encountered, verify each dependency is merged and any special prerequisite (for example transport audit completion) is satisfied.
4. If all prerequisites are satisfied, that PR is the **next unmerged PR** and becomes the active target.
5. If prerequisites are not satisfied, do not advance to lower PRs; treat as blocked.

### Handling blocked dependencies (`[ADAAD WAITING]`)

When the first unmerged PR has unmet prerequisites:

- Emit status prefix exactly as: `[ADAAD WAITING]`
- Report the blocked PR ID/title and enumerate each unmet dependency.
- Stop progression immediately (no repository source/docs/workflow writes, no PR staging, no next-PR advancement).
- Operational exception: `.adaad_agent_state.json` may be written only to persist agent runtime state (`blocked_reason`, `blocked_at_gate`, `blocked_at_tier` as applicable).
- `.adaad_agent_state.json` is a non-product artifact, is gitignored, and must never appear in PR diffs.
- Resume only after operator remediation confirms all prerequisite dependencies are merged/satisfied.
