# Phase 113 Plan — INNOV-29: Curiosity-Driven Exploration with Hard Stops

## Objective
Deliver **INNOV-29 (Curiosity-Driven Exploration with Hard Stops)** as a governed phase increment with deterministic implementation sequencing, constitutional gate coverage, and release evidence alignment.

## Dependency Chain
- Immediate predecessor: **Phase 112** (must be merged before any Phase 113 source writes).
- Innovation lineage: `INNOV-28` → `INNOV-29` within `ADAAD_30_INNOVATIONS.md` phase roadmap (INNOV-10..30 mapped to Phases 94..114).
- Release dependency: target version **v9.46.0** follows predecessor semantic progression.
- Deterministic next-PR linkage: `state_alignment.expected_next_pr` resolves to `Phase 113` only when Phase 112 status is `shipped`.

## Invariants
- **HUMAN-0**: non-delegable governor sign-off required for phase ratification and release promotion.
- **REPLAY-0**: identical inputs produce identical governance and replay outputs.
- **GATE-0**: governance gate remains sole promotion authority.
- **PHASE-113-SEQ-0**: predecessor linkage is explicit and linear (`Phase 112` → `Phase 113`).
- **EVIDENCE-113-0**: no closure without complete claims-evidence row and resolvable artifacts.

## Tier Classification (Gate Applicability)
- **Tier 0 (always-on baseline):** required preflight and per-file verification.
- **Tier 1 (standard gate stack):** full test suite, governance tests, artifact verification, evidence validation.
- **Tier 2 (escalated):** required (critical governance/runtime innovation surface).
- **Tier 3 (PR completeness):** required (evidence row, docs/runbook alignment, CI tier declaration, lane declaration).
- **Tier M (merge-specific):** required only under `DEVADAAD` trigger.

## Acceptance Tests
- Phase-specific pytest module(s) covering innovation behavior and failure-mode assertions.
- Determinism and replay verification for all new ledger/reasoning paths.
- Governance invariant tests proving HUMAN-0 and gate ordering are preserved.
- Regression check: no pre-existing failures introduced versus base SHA.

## Evidence Artifacts Required
- `artifacts/governance/phase113/track_a_sign_off.json`
- `artifacts/governance/phase113/replay_digest.txt`
- `artifacts/governance/phase113/tier_summary.json`
- `docs/comms/claims_evidence_matrix.md` row updated to `Complete` for Phase 113 / INNOV-29.

## HUMAN-0 Checkpoints
1. **Plan ratification checkpoint:** governor approves this plan before PR open.
2. **Pre-merge checkpoint:** governor validates gate stack summary and evidence completeness.
3. **Release checkpoint:** governor records signed ledger attestation for `v9.46.0`.
