# Governance Risk Sign-off Memo — ADAAD-7 to ADAAD-9 Documentation Amendments

## Scope of Sign-off
This memo signs off the structural governance risks raised in review for:
- `EPIC_1_Reviewer_Reputation.md`
- `EPIC_2_Policy_Simulation_DSL.md`

## Review Objective
Validate invariant compliance (He65), scope isolation, governance drift risk, version-chain coherence (6 → 9), and hidden coupling controls.

## Required Amendments Status

### 1) Epic 1 — Epoch-Scoped Weight Snapshot
**Status:** Resolved.

**Added invariant language:**
- Reputation weight vector is snapshotted and journaled per epoch before scorer execution.
- Replay uses epoch-scoped weights, never current runtime/config values.
- Mid-epoch weight changes are deferred until next epoch boundary.

**Risk impact:**
- Eliminates replay drift from retroactive or mid-epoch tuning.
- Preserves deterministic recomputation under strict replay.

### 2) Epic 2 — Ephemeral Simulation Context Isolation
**Status:** Resolved.

**Added invariant language:**
- Simulation must instantiate ephemeral lineage ledger.
- Simulation must instantiate ephemeral entropy ledger.
- Simulation must use isolated policy evaluation context.
- No shared mutable runtime state with live execution (caches/counters/singletons).
- Simulation state is discarded after completion; only explicit simulation artifacts/events persist.

**Risk impact:**
- Eliminates state bleed into live governance path.
- Prevents phantom mutation-rate/resource/entropy effects.
- Protects replay coherence and fail-closed governance behavior.

### 3) Cross-Epic Scoring-Version Binding (Recommended Hardening)
**Status:** Resolved in documentation.

**Added invariant language:**
- Reputation scoring records and replays `scoring_algorithm_version` per epoch.
- Simulation replay binds risk/fitness-dependent evaluation to epoch-scoped scoring versions.
- Simulation artifacts (`SimulationResult` / `GovernanceProfile`) include scoring-version metadata.
- Evidence acceptance criteria require `scoring_algorithm_version` and `constitution_version` provenance fields.

**Risk impact:**
- Eliminates replay drift from scoring-logic refactors across minor versions.
- Closes hidden coupling between Epic 1 reputation, Epic 2 simulation risk constraints, and Epic 3 evidence interpretation.

## Residual Risk Assessment (Post-Amendment)

| Risk | Epic | Severity | Status | Control |
|---|---:|---:|---|---|
| Replay drift via weight tuning | 7 | HIGH | Mitigated | Epoch-scoped weight snapshots, replay-bound lookup |
| Replay drift via scoring logic refactor | 7/8 | HIGH | Mitigated | Epoch-scoped `scoring_algorithm_version` binding |
| Simulation state bleed | 8 | HIGH | Mitigated | Ephemeral isolated contexts; no shared mutable structures |
| IDE bypass path | 9 | MEDIUM | Unchanged/controlled | MCP-only submission boundary remains explicit |
| Quorum below constitutional floor | 7 | HIGH | Controlled | Constitutional floor checks remain mandatory |

## Governance Conclusion
With the required invariants now explicitly documented — including scoring-version binding — the ADAAD-7/8 epic surfaces are structurally aligned with deterministic replay, governance isolation, and constitutional floor protections. Governance drift risk is reduced from **MEDIUM** to **LOW-MEDIUM** across the 6 → 9 chain, with no new hidden coupling introduced by these documentation updates.

**Sign-off recommendation:** ✅ Approved for merge as documentation hardening.
