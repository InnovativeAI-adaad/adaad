# ADAAD-7 Execution Plan (Governance Closure → Federated Readiness)

This plan operationalizes the immediate governance and security closure work needed before `v1.1-GA`, then sequences ADAAD toward ADAAD-7 and beyond.

It integrates:
- March 3rd security/governance commits,
- the active audit-report priorities,
- and ADAAD's constitutional architecture goals.

---

## Phase 1 — Finalize v1.1-GA Compliance (Immediate)

Operational tracker: `docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md`.

> **Release gate:** All Phase 1 steps are required before tagging `v1.1-GA`.

| Step | Action | Owner | Outcome |
|---|---|---|---|
| 1.1 | Merge `feat/auth-contract-enforcement` and verify CI | Security Lead | `GateCertifier.passed` uses `token_ok`; CI green on exact SHA |
| 1.2 | Audit all `verify_session()` call sites | Security Lead | Only test-only usage remains; no runtime/app calls |
| 1.3 | Merge `feat/ci-hardening` PR | CI Maintainer | `secret_scan.yml` present; branch protection enforces secret scan |
| 1.4 | Align release evidence matrix with strict gate | Governance Lead | Matrix matches gate logic; all artifacts traceable |
| 1.5 | Refactor governance gate into deterministic module | Codex Lead | Gate decisions are pure functions; replay-safe |
| 1.6 | Expand mutation risk scorer test suite | Codex Lead | 25+ cases; stable scoring across environments |

---

## Phase 2 — Constitutional Surface Expansion (Short-Term)

| Step | Action | Owner | Outcome |
|---|---|---|---|
| 2.1 | Open PR-3H tracking issue with formal acceptance criteria | Governance Lead | Sandbox hardening scoped before reputation logic |
| 2.2 | Add key-rotation enforcement audit to evidence checklist | Security Lead | `README_IMPLEMENTATION_ALIGNMENT.md` item closed |
| 2.3 | Scope external trust-root hardening for replay bundles | Governance Lead | `ReplayProofBuilder` supports third-party verification |
| 2.4 | Add rate limiting to `/replay/diff` forensics endpoint | Runtime Lead | Red-team scenario hardened |
| 2.5 | Add runtime intake scaffolding, schemas, and tests | Codex Lead | Intake becomes a constitutional boundary |
| 2.6 | Refine sandbox timeout enforcement and backend coverage | Runtime Lead | All mutations fail-closed deterministically |

---

## Phase 3 — Governance Intelligence & Federated Readiness

| Step | Action | Owner | Outcome |
|---|---|---|---|
| 3.1 | Architect semantic scoring layer for mutation proposals | Codex Lead | Red-team harness evolves beyond keyword matching |
| 3.2 | Design federation wire protocol for Android swarm | Systems Architect | Multi-instance governance state sharing scoped |
| 3.3 | Harden MCP-only submission boundary for ADAAD-9 | Governance Lead | `proposal_validator.py` clamps `authority_level`; no shortcut paths |
| 3.4 | Normalize path lineage across all modules | Codex Lead | Replay lineage is stable across environments |
| 3.5 | Implement He65 Doctor gate validation | Governance Lead | Constitutional health check for mutation proposals |

---

## Phase 4 — Strategic Consolidation & Public Positioning

| Step | Action | Owner | Outcome |
|---|---|---|---|
| 4.1 | Publish constitutional replay digest | Governance Lead | Replay lineage and gate decisions are externally auditable |
| 4.2 | Finalize README and public positioning narrative | Founder | ADAAD identity is clear, authoritative, and investor-ready |
| 4.3 | Automate branding and registry workflows | Founder | Trademark, domain, and release automation complete |
| 4.4 | Launch pilot customer onboarding flow | Product Lead | 48-hour engagement pipeline is deterministic and modular |
| 4.5 | Open-source ADAAD core with governance guarantees | Founder | Public release includes replay, scoring, and gate proofs |

---

## Architectural Watch Items (Ongoing)

These surfaces remain high-risk and should stay under continuous constitutional monitoring:

1. **ADAAD-9 (Aponi-as-IDE)** — MCP-only submission boundary remains sole entry point.
2. **Red-team harness** — migrate from keyword matching to semantic proposal analysis.
3. **Android swarm coordination** — federation wire protocol must be scoped before ADAAD-7 execution begins.

---

## Governance Notes

- This document is execution guidance and does **not** alter constitutional authority boundaries by itself.
- Any policy/rule changes still require the normal constitutional amendment flow.
- `v1.1-GA` should only be tagged after complete evidence closure for all Phase 1 steps.


## Execution governance model

- **Decision cadence:** daily closure stand-up until all Phase 1 controls are complete.
- **Evidence authority:** each step owner submits immutable evidence links (SHA + CI run + artifact hash).
- **Tagging rule:** `v1.1-GA` is blocked unless every Phase 1 step has governance sign-off.
- **Replay safety rule:** no gate logic change is accepted without deterministic replay proof.

## Dependency ordering constraints

1. Complete auth/CI closure (1.1–1.3) before gate/matrix updates (1.4–1.5).
2. Complete deterministic gate refactor (1.5) before risk-suite expansion sign-off (1.6).
3. Promote Phase 2 sandbox/runtime intake work only after Phase 1 closure is attested.
