# Release Checklist

Use this checklist for any release candidate, with strict enforcement for governance and public-readiness milestones.

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
| Release evidence gate workflow | `.github/workflows/release_evidence_gate.yml` | Hard gate for governance/public-readiness tagging controls. |

## Build and quality gates

- [ ] CI required checks are green for the release commit.
- [ ] Determinism and governance test suites passed on the release commit.
- [ ] CodeQL workflow is green for the release commit/PR.

## Evidence completeness gate (announcement blocker)

- [ ] `docs/comms/claims_evidence_matrix.md` is updated for this release scope.
- [ ] All required claim rows are marked `Complete` with objective evidence links.
- [ ] `python scripts/validate_release_evidence.py --require-complete` passes.

> **Hard block:** Do not publish public release notes, governance milestone updates, roadmap posts, or social announcements until every evidence entry above is complete and validated.

## Versioned documentation and release notes

- [ ] Release notes file exists at `docs/releases/<version>.md` (for this milestone: `docs/releases/1.0.0.md`) and reflects scope.
- [ ] Governance/spec deltas are reflected in versioned docs.
- [ ] Any externally referenced docs/spec links are immutable/versioned.

## Tagging controls for governance/public-readiness releases

- [ ] For milestone tags (for example `vX.Y.Z-governance-*` or `vX.Y.Z-public-readiness-*`), confirm `.github/workflows/release_evidence_gate.yml` passed.
- [ ] Only create/publish the tag after evidence gate checks pass.

## Go/No-Go criteria

Proceed with release only when all conditions below are true:

- [ ] All checklist sections above are complete with no unresolved blockers.
- [ ] Required artifact paths exist and point to release-accurate content.
- [ ] Evidence validator and CI gates pass on the exact release commit/tag target.
- [ ] Rollback and communication owners are identified for release day.

If any criterion fails, the decision is **No-Go** until remediated.

---

Related docs: [Repository README](../../README.md) · [Documentation index](../README.md)
