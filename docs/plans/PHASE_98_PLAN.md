# Phase 98 Plan — INNOV-13: Institutional Memory Transfer

## Objective
Deliver **INNOV-13 (Institutional Memory Transfer)** as a governed phase increment with
deterministic implementation sequencing, constitutional gate coverage, and release evidence
alignment.

## Dependency Chain
- Immediate predecessor: **Phase 97** — INNOV-12 MGV — v9.30.0 (must be merged before any Phase 98 source writes)
- Innovation lineage: `INNOV-12` → `INNOV-13` within `ADAAD_30_INNOVATIONS.md`
- Release dependency: target version **v9.31.0**
- Deterministic next-PR linkage: `state_alignment.expected_next_pr` resolves to Phase 98 only when Phase 97 status is `shipped`

## Innovation Summary
A cryptographically verified protocol for transferring `CodebaseKnowledgeGraph` and
`SoulboundLedger` state from one ADAAD instance to a newly bootstrapped instance on different
hardware. The exporting instance signs a knowledge bundle; the importing instance verifies the
signature and imports under chain-of-custody governance events. Accumulated engineering wisdom
outlives any particular hardware deployment.

## Invariants (to be introduced)
- **IMT-0**: transfer bundle MUST be cryptographically signed by the exporting instance before transmission
- **IMT-VERIFY-0**: importing instance MUST verify signature before any knowledge state write
- **IMT-CHAIN-0**: every import event MUST be recorded in `governance_events.jsonl` with full provenance
- **IMT-DETERM-0**: bundle serialization is deterministic (canonical JSON, sorted keys, no datetime/random)
- **HUMAN-0**: non-delegable governor sign-off for phase ratification and release promotion
- **REPLAY-0**: identical inputs produce identical governance and replay outputs
- **GATE-0**: governance gate remains sole promotion authority
- **PHASE-98-SEQ-0**: predecessor linkage explicit and linear (Phase 97 → Phase 98)
- **EVIDENCE-98-0**: no closure without complete claims-evidence row and resolvable artifacts

## Tier Classification (Gate Applicability)
- **Tier 0 (always-on baseline):** required preflight and per-file verification
- **Tier 1 (standard gate stack):** full test suite, governance tests, artifact verification, evidence validation
- **Tier 2 (escalated):** required (critical governance/runtime innovation surface — knowledge transfer touches SoulboundLedger and KnowledgeGraph)
- **Tier 3 (PR completeness):** required (evidence row, docs/runbook alignment, CI tier declaration, lane declaration)
- **Tier M (merge-specific):** required under DEVADAAD trigger

## Acceptance Tests
- Phase-specific pytest module `tests/innovations/test_phase98_imt.py` — T98-IMT-01..30 minimum
- Signature verification roundtrip (sign → verify → import)
- Determinism: identical source state produces identical bundle digest
- Governance invariant tests proving HUMAN-0 and gate ordering preserved
- Chain-of-custody: governance_events.jsonl records import event with full provenance
- Regression: no pre-existing failures introduced versus base SHA

## Evidence Artifacts Required
- `artifacts/governance/phase98/phase98_sign_off.json`
- `artifacts/governance/phase98/track_a_sign_off.json`
- `artifacts/governance/phase98/replay_digest.txt`
- `artifacts/governance/phase98/tier_summary.json`
- `docs/comms/claims_evidence_matrix.md` row updated to `Complete` for Phase 98 / INNOV-13

## HUMAN-0 Checkpoints
1. **Plan ratification checkpoint:** governor approves this plan before PR open
2. **Pre-merge checkpoint:** governor validates gate stack summary and evidence completeness
3. **Release checkpoint:** governor records signed ledger attestation for `v9.31.0`

## Next
**Phase 99 — INNOV-14 Constitutional Jury System → v9.32.0**
