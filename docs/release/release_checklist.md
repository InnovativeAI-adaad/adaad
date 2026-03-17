# Release Checklist

Use this checklist for any release candidate, with strict enforcement for governance and public-readiness milestones across current roadmap phases.

## Release types

| Release type | Typical scope | Governance evidence expectation |
| --- | --- | --- |
| Patch | Bug fixes, security fixes, low-risk maintenance | Update impacted evidence rows and validate completion before announcement. |
| Minor | Backward-compatible features and operational improvements | Refresh claims/evidence matrix for new scope and validate all required rows. |
| Major | Breaking changes, protocol shifts, or significant architecture updates | Full evidence review, versioned documentation updates, and release gate enforcement. |
| Governance milestone | Public-readiness/governance-tagged checkpoint | Strict announcement block until all governance evidence and gate workflows pass. |

## Required artifacts

| Artifact | Required path | Purpose |
| --- | --- | --- |
| Release notes | `docs/releases/<version>.md` | Canonical summary of scope, changes, and operator impact. |
| Claims/evidence matrix | `docs/comms/claims_evidence_matrix.md` | Tracks objective evidence for externally stated claims. |
| Evidence validator | `scripts/validate_release_evidence.py` | Enforces evidence completeness checks in CI and pre-release review. |
| Strict governance release gate workflow | `.github/workflows/governance_strict_release_gate.yml` | Hard gate for governance/public-readiness tagging controls and release block enforcement. |

## Build and quality gates

- [ ] CI required checks are green for the release commit.
- [ ] Determinism and governance test suites passed on the release commit.
- [ ] `CodeQL / Analyze (python)` is green for the release commit/PR (`.github/workflows/codeql.yml`).
- [ ] `python scripts/validate_no_build_lib_sources.py` passes (no git-tracked `build/lib/**/*.py` files).
- [ ] Python packaging artifacts (`build/`, `dist/`, `*.egg-info/`) are treated as ephemeral CI/release outputs, not versioned source-of-truth.

## Dependabot PR triage workflow

- [ ] Confirm Dependabot PR scope matches one configured ecosystem (`/` for `requirements.server.txt`, `/archives/backend` for archive mirror dependencies, or GitHub Actions).
- [ ] Verify CI is green and dependency diffs are limited to expected files for the ecosystem.
- [ ] For security updates, prioritize merge after checks pass.
- [ ] For patch/minor grouped updates, review upstream changelogs for regression or policy-impact risk.
- [ ] For any update that impacts auth, cryptography, policy, or sandbox-critical paths, request maintainer escalation before merge.
- [ ] Preserve dependency tracking labels (`dependencies`, `security`) and link the PR to release notes/evidence updates when applicable.

Reference: `docs/DEPENDABOT_REVIEW_POLICY.md`.

## Evidence completeness gate (announcement blocker)

- [ ] `docs/comms/claims_evidence_matrix.md` is updated for this release scope.
- [ ] All required claim rows are marked `Complete` with objective evidence links.
- [ ] `python scripts/validate_release_evidence.py --require-complete` passes.
- [ ] `python scripts/validate_release_hardening_claims.py` passes (release notes do not over-claim unavailable hardened sandbox modes).
- [ ] `python scripts/validate_architecture_snapshot.py` passes (architecture deep-dive metadata block is structurally valid and report version aligned).

> **Hard block:** Do not publish public release notes, governance milestone updates, roadmap posts, or social announcements until every evidence entry above is complete and validated.

## Versioned documentation and release notes

- [ ] Release notes file exists at `docs/releases/<version>.md` and reflects the current scope; include explicit roadmap/phase mapping for the release window.
- [ ] Governance/spec deltas are reflected in versioned docs.
- [ ] Any externally referenced docs/spec links are immutable/versioned.

## Phase 65 post-merge sync automation (v9.0.0)

- [ ] `.github/workflows/phase65_post_merge_sync.yml` executed for merged `PR-PHASE65-01` (title or label match) and completed successfully.
- [ ] `python scripts/sync_phase_status_on_merge.py` passed with evidence gate (`scripts/validate_release_evidence.py --require-complete`) before any docs mutation.
- [ ] `ROADMAP.md` updated: Phase 65 tracker row is `shipped` + `complete`, and `Next` pointer moved to post-v9.0.0 item.
- [ ] `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` updated: Phase 65 status is `shipped`, and `active_phase`/`milestone` moved to post-65 state.
- [ ] If the workflow produced no diff, treat as idempotent no-op (do not force a commit).

### Rollback (fail-closed)

- [ ] If sync script fails due to missing anchors or unmet dependency checks, do **not** hand-edit docs in the same merge path; open remediation PR to restore canonical anchors/state first.
- [ ] If workflow commit is incorrect, revert only the bot-generated sync commit and rerun the workflow after fixing source anchors.
- [ ] Re-run `python scripts/validate_release_evidence.py --require-complete` and `python scripts/sync_phase_status_on_merge.py --dry-run` before reattempting.

## Tagging controls for governance/public-readiness releases

- [ ] For milestone tags (for example `vX.Y.Z-governance-*` or `vX.Y.Z-public-readiness-*`), confirm `.github/workflows/governance_strict_release_gate.yml` passed (including terminal `release-gate`).
- [ ] For legacy `v1.1-GA` references, preserve historical verification evidence that `GateCertifier.passed` requires `token_ok` in `runtime/governance/gate_certifier.py` and no production caller depends on deprecated `verify_session(...)` in `security/cryovant.py`.
- [ ] For current governance/public-readiness tags, confirm release notes include explicit links to active phase scope in `ROADMAP.md` and `docs/governance/ADAAD_PR_PROCESSION_2026-03.md`.
- [ ] Patent filing readiness artifact reviewed by IP counsel before creating governance/public-readiness tags, when applicable.
- [ ] `docs/governance/LANE_OWNERSHIP.md` exists and all lanes have identified owners.
- [ ] All pending claims-evidence rows from `ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md §Evidence Lane Output Contract` are `Complete` in `docs/comms/claims_evidence_matrix.md`.
- [ ] Federation HMAC key rotation runbook exists for `ADAAD_FEDERATION_MANIFEST_HMAC_KEY`, validated by security owner, before creating governance/public-readiness tags.
- [ ] If `ADAAD_KEY_ROTATION_MAX_AGE_DAYS` is overridden for release validation, ensure it is an integer string; malformed values fail-closed through governance gate reason `invalid_key_rotation_max_age_days`.
- [ ] Attach CI green status evidence (run URL or artifact) for the exact release commit before creating governance/public-readiness tags.
- [ ] Only create/publish the tag after evidence gate checks pass.

## Go/No-Go criteria

Proceed with release only when all conditions below are true:

- [ ] All checklist sections above are complete with no unresolved blockers.
- [ ] Required artifact paths exist and point to release-accurate content.
- [ ] Evidence validator and CI gates pass on the exact release commit/tag target.
- [ ] Rollback and communication owners are identified for release day.
- [ ] No 🔴 critical or 🟠 high audit findings remain open without accepted risk-acceptance record.
- [ ] Dependency-safe merge sequence was followed for all security/determinism-surface PRs in this release window.

If any criterion fails, the decision is **No-Go** until remediated.

---

Related docs: [Repository README](../../README.md) · [Documentation index](../README.md) · [Strategic build suggestions](../ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md) · [Program PR procession](../governance/ADAAD_PR_PROCESSION_2026-03.md) · [Roadmap](../../ROADMAP.md) · [v1.1-GA historical closure tracker](../governance/ADAAD_7_GA_CLOSURE_TRACKER.md) · [Release audit evidence verification checklist](../releases/RELEASE_AUDIT_CHECKLIST.md)
