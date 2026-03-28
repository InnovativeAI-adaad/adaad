# Phase 97 Plan — INNOV-13: Institutional Memory Transfer

## Objective
Deliver **INNOV-13 (Institutional Memory Transfer)** as a governed phase increment with deterministic implementation sequencing, constitutional gate coverage, and release evidence alignment.

## Dependency Chain
- Immediate predecessor: **Phase 96** (must be merged before any Phase 97 source writes).
- Innovation lineage: `INNOV-12` → `INNOV-13` within `ADAAD_30_INNOVATIONS.md` phase roadmap (INNOV-10..30 mapped to Phases 94..114).
- Release dependency: target version **v9.30.0** follows predecessor semantic progression.
- Deterministic next-PR linkage: `state_alignment.expected_next_pr` resolves to `Phase 97` only when Phase 96 status is `shipped`.

## Invariants
- **HUMAN-0**: non-delegable governor sign-off required for phase ratification and release promotion.
- **REPLAY-0**: identical inputs produce identical governance and replay outputs.
- **GATE-0**: governance gate remains sole promotion authority.
- **PHASE-97-SEQ-0**: predecessor linkage is explicit and linear (`Phase 96` → `Phase 97`).
- **EVIDENCE-97-0**: no closure without complete claims-evidence row and resolvable artifacts.

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
- `artifacts/governance/phase97/track_a_sign_off.json`
- `artifacts/governance/phase97/replay_digest.txt`
- `artifacts/governance/phase97/tier_summary.json`
- `docs/comms/claims_evidence_matrix.md` row updated to `Complete` for Phase 97 / INNOV-13.

## HUMAN-0 Checkpoints
1. **Plan ratification checkpoint:** governor approves this plan before PR open.
2. **Pre-merge checkpoint:** governor validates gate stack summary and evidence completeness.
3. **Release checkpoint:** governor records signed ledger attestation for `v9.30.0`.
