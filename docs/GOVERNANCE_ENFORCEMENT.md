# Governance Enforcement

## Governance flow (evidence path)

<p align="center">
  <img src="assets/adaad-governance-flow.svg" width="900" alt="Governance enforcement flow illustrating proposal intake, policy gates, replay checks, and evidence logging stages">
</p>

*Evidence path: proposal intent and context enter policy evaluation, replay and determinism controls gate execution, and resulting decisions are anchored in governance/ledger artifacts for auditability.*

Required branch protections for `main`:

- Required status checks must pass before merge.
- Required pull request approvals: minimum 2 reviewers for governance/security scope.
- Force pushes are disabled.
- Linear commit history is required.

Required CI checks (branch protection required-check table):

| Required check | Trigger condition | Enforcement |
|---|---|---|
| `full-test-suite` (`PYTHONPATH=. pytest tests/ -q`) | Always-on in `.github/workflows/ci.yml` | Blocks merge on any test failure |
| `governance-tests` (`PYTHONPATH=. pytest tests/ -k governance -q`) | Always-on in `.github/workflows/ci.yml` | Blocks governance regressions |
| `determinism-lint` (`python tools/lint_determinism.py ...`) | Always-on in `.github/workflows/ci.yml` | Blocks nondeterministic governance/runtime/security changes |
| `spdx-header-lint` (`python scripts/check_spdx_headers.py`) | Always-on in `.github/workflows/ci.yml` | Blocks SPDX header drift |
| `phase7-reputation-gate` | Conditional required check when governance/server/relevant UI paths change (`governance/**`, `server.py`, `ui/**`) | Runs Phase 7 selector set: reputation, ledger, review pressure, constitutional-floor, reviewer panel endpoint/UI coverage |
| `Secret Scan / secret-scan` | Always-on via `.github/workflows/secret_scan.yml` | Required branch-protection secret scanning gate |
| `Doc Sync Preview (PR Gate) / doc-sync-preview` | Always-on via `.github/workflows/doc_sync_preview.yml` for PRs to `main` | Fail-closed pre-merge documentation drift gate (`sync_docs_on_merge.py --dry-run --format json`) |
| `CodeQL / Analyze (python)` | Always-on via `.github/workflows/codeql.yml` (`push`, `pull_request`, weekly `schedule`) | Required branch-protection CodeQL security analysis gate |
| `Branch Protection Check` | Repository branch-protection validation workflow | Fails closed on branch-protection drift |

`Branch Protection Check` workflow validates required branch settings via GitHub API (conflict-resolved policy source).

- Branch protection check requires `GITHUB_TOKEN` permission `administration: read` (granted by org admin).
- Branch protection check enforces `required_pull_request_reviews.required_approving_review_count >= 2`.
- Branch protection check enforces required contexts for `Secret Scan / secret-scan`, `CI / docs-validation`, `Doc Sync Preview (PR Gate) / doc-sync-preview`, and `CodeQL / Analyze (python)`.
- Governance strict release gate (`.github/workflows/governance_strict_release_gate.yml`) executes determinism lint, entropy discipline checks, governance strict-mode validation, strict replay verification, constitution fingerprint stability, and reviewer calibration validation on Python 3.11.9.

Release required-check table (`governance_strict_release_gate.yml`):

| Required check | Trigger condition | Enforcement |
|---|---|---|
| `determinism-lint` | Governance/public-readiness release tag or manual dispatch | Fail-closed release prerequisite |
| `entropy-discipline-checks` | Governance/public-readiness release tag or manual dispatch | Fail-closed release prerequisite |
| `governance-strict-mode-validation` | Governance/public-readiness release tag or manual dispatch | Fail-closed release prerequisite |
| `replay-strict-validation` | Governance/public-readiness release tag or manual dispatch | Fail-closed release prerequisite |
| `constitution-fingerprint-stability` | Governance/public-readiness release tag or manual dispatch | Fail-closed release prerequisite |
| `reviewer-calibration-validation` | Governance/public-readiness release tag or manual dispatch | Phase 7 fail-closed reviewer calibration invariant gate |
| `release-gate` | Always (aggregates all upstream strict release jobs) | Fails closed unless every required release job result is `success` |


## Implementation status alignment (v0.70.0)

- CI enforces full suite, governance suite, and required determinism lint checks.
- Determinism lint required-scope enforcement includes federation transport/coordination/protocol/manifest modules and fails closed when any required governance file is missing.
- Branch protection verification checks `required_status_checks`, `enforce_admins`, and a minimum of 2 required approvals.
- Governance strict release gate runs fail-closed release protection via the terminal `release-gate` job, which blocks when any required upstream governance check fails, is cancelled, or is skipped.
- Lineage continuity helper is wired conservatively: enforced when lineage_v2 chain resolves for the request agent; genesis/journal invariants remain authoritative fallback.



## CI/CD posture (audit mirror)

The repository no longer fits a "No CI" classification. Active workflows cover core CI, CodeQL, release gating, red-team, determinism lint, entropy health, and branch-protection validation.

### Current-state matrix

| Workflow file | Triggers | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | `push`/`pull_request` on `main` | Primary CI, governance and replay/evidence gates |
| `.github/workflows/codeql.yml` | `push`/`pull_request` on `main`, weekly cron | CodeQL security analysis |
| `.github/workflows/governance_strict_release_gate.yml` | Governance/public-readiness tag pushes, manual dispatch | Strict governance release gate |
| `.github/workflows/redteam_nightly.yml` | Nightly cron, manual dispatch | Deterministic red-team corpus run |
| `.github/workflows/determinism_lint.yml` | `pull_request` (critical paths) | Determinism lint lane |
| `.github/workflows/entropy_health.yml` | Daily cron, manual dispatch | Entropy health monitoring |
| `.github/workflows/secret_scan.yml` | `push`/`pull_request` on `main` | Secret scanning over repository contents and commit history |

### Remaining automation gaps

- `.github/dependabot.yml` is configured for root Python dependencies, archive backend dependencies, and GitHub Actions; maintain grouped patch/minor update posture and review discipline.

### Audit freshness

- Baseline commit: `0df3d3f7a3befe91faf6b327505a8f3e9ae31d49`
- Baseline date: `2026-03-02T07:34:19-06:00`
- PR-CI-01 enforcement confirmation: `2026-03-06` — Python version unified to `3.11.9` across all CI workflows; `scripts/check_workflow_python_version.py` guard passes; H-01 closed.
- PR-CI-02 enforcement confirmation: `2026-03-06` — `spdx-header-lint` job wired always-on
  in `ci.yml`; `scripts/check_spdx_headers.py` passes on all Python source files; H-08 closed.

## Canonical Governance Law (v1)

Runtime governance validators are now bound to `runtime/governance/canon_law_v1.yaml`, which defines machine-enforceable Articles I–VIII and escalation tiers (`advisory`, `conservative`, `governance`, `critical`).

Violation handling is deterministic:
- validators emit `governance_canon_violation` ledger transactions with hash-stable payloads
- escalation is one-way only (no automatic de-escalation)
- undefined escalation/state is fail-closed (`critical`, mutation blocked)
