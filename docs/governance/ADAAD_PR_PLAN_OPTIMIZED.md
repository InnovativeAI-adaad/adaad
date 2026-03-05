# ADAAD PR Plan (Optimized)

## Scope

This plan captures normalized CI-tier assignments for ADAAD PR execution. Tier authority is `docs/governance/ci-gating.md`.

## Phase 0 Track A — Hardening PRs

| PR | Title | Audit finding | CI tier | Dependencies |
|---|---|---|---|---|
| PR-CI-01 | Unify Python version pin | H-01 | standard | none |
| PR-CI-02 | SPDX header enforcement | H-08 | standard | none |
| PR-LINT-01 | Determinism lint: `adaad/orchestrator/` | H-05 | critical | none |
| PR-HARDEN-01 | Boot env validation + signing key assertion | C-01, H-02 | critical | none |
| PR-SECURITY-01 | Federation key pinning registry | C-03 | critical | transport.py audit |
| PR-PERF-01 | Streaming lineage ledger | C-04 | standard | none |
| PR-OPS-01 | Snapshot atomicity + sequence ordering | H-07, M-02 | standard | none |
| PR-DOCS-01 | Federation key registry governance doc | C-03 | docs | PR-SECURITY-01 |

## PR-LINT-01 specification

- **PR ID:** PR-LINT-01
- **Lane:** Determinism
- **Change surfaces:**
  - `tools/lint_determinism.py`
  - `adaad/orchestrator/**`
  - workflow trigger edits tied to CI gate logic
- **Authoritative CI tier:** **critical**

### Tier rationale (locked)

`ci-gating.md` classifies default non-governance code changes as `standard`, but explicitly requires CI workflow edits that change gate logic to be treated as governance-impact changes. For PR-LINT-01, workflow trigger/gating edits are in-scope; therefore governance-impact flags must be checked and escalation behavior is required. This locks PR-LINT-01 to `critical` to prevent ambiguous reinterpretation in future planning passes.

## Gate mapping by CI tier

| Tier | Required escalations |
|---|---|
| docs | Tier 0 + Tier 1 baseline only (no escalated suites unless flags force escalation) |
| low | Tier 0 + Tier 1 baseline only |
| standard | Tier 0 + Tier 1 baseline; Tier 2 only when replay/ledger flag or governance/runtime/security path trigger applies |
| critical | Tier 0 + Tier 1 + Tier 2 escalated suites (strict replay/evidence/promotion as triggered by policy) |

## Milestone mapping

| Milestone | PRs | CI tier note |
|---|---|---|
| Phase 0 Track A | PR-CI-01, PR-CI-02, PR-LINT-01, PR-HARDEN-01, PR-SECURITY-01, PR-PERF-01, PR-OPS-01, PR-DOCS-01 | PR-LINT-01 is fixed at `critical`; all references must match this value |
