# ADAAD Phase 6 — Test Acceptance Specification

> **Authority:** ArchitectAgent · `docs/governance/ARCHITECT_SPEC_v3.1.0.md` §2.7, §3.7
> **Status:** CANONICAL — required before PR-PHASE6-02 and PR-PHASE6-03 may merge
> **Version:** 1.0.0 · **Effective:** 2026-03-07

This document enumerates every acceptance test that must exist, pass, and be
replay-verifiable before each Phase 6 PR may merge. Test IDs are stable identifiers
for evidence matrix cross-referencing.

All tests must be deterministic: identical inputs → identical outcomes across
independent runs. Non-deterministic tests are a constitutional violation
(`lint_determinism.py` enforces this).

---

## PR-PHASE6-02 Tests (M6-03: EvolutionLoop × RoadmapAmendmentEngine)

**Target file:** `tests/autonomy/test_evolution_loop_amendment.py`
**Minimum count:** 10 tests (all IDs below are required)

| Test ID | Description | Gate Verified |
|---|---|---|
| `T6-03-01` | All 6 gates pass → proposal emitted; `EpochResult.amendment_proposed == True` | GATE-M603-01..06 |
| `T6-03-02` | `epoch_count % interval != 0` → no proposal; `EpochResult.amendment_proposed == False` | GATE-M603-01 |
| `T6-03-03` | `health_score < 0.80` → `PHASE6_HEALTH_GATE_FAIL` logged; epoch continues | GATE-M603-02 |
| `T6-03-04` | `divergence_count > 0` (federation enabled) → `PHASE6_FEDERATION_DIVERGENCE_BLOCKS_AMENDMENT` | GATE-M603-03 |
| `T6-03-05` | `prediction_accuracy <= 0.60` → `PHASE6_PREDICTION_ACCURACY_GATE_FAIL`; epoch continues | GATE-M603-04 |
| `T6-03-06` | Pending amendment exists → `PHASE6_AMENDMENT_STORM_BLOCKED`; no second proposal emitted | GATE-M603-05 (`INVARIANT PHASE6-STORM-0`) |
| `T6-03-07` | `amendment_trigger_interval < 1` → `GovernanceViolation`; epoch halts amendment eval | GATE-M603-06 |
| `T6-03-08` | Gate failure does NOT abort epoch; subsequent epoch processing completes normally | All gates — fail-open for epoch |
| `T6-03-09` | Identical epoch inputs → identical gate verdicts across two runs (determinism) | Determinism contract |
| `T6-03-10` | Gate verdicts written to evidence ledger for every trigger evaluation (pass and fail) | Ledger contract |
| `T6-03-11` | `EpochResult.amendment_id` matches `proposal.proposal_id` in ledger on successful proposal | Ledger cross-ref |
| `T6-03-12` | `authority_level != "governor-review"` → `GovernanceViolation` at proposal creation | `INVARIANT PHASE6-AUTH-0` |
| `T6-03-13` | No auto-approval path exists; `approve()` without `human_signoff_token` → `GovernanceViolation` | `FL-ROADMAP-SIGNOFF-V1` |

**Ledger event assertions (required in each relevant test):**
- `T6-03-01`: `roadmap_amendment_proposed` event present in ledger after proposal
- `T6-03-06`: `PHASE6_AMENDMENT_STORM_BLOCKED` event present in ledger
- `T6-03-07`: `GovernanceViolation` raised; `roadmap_amendment_rejected` in ledger

---

## PR-PHASE6-03 Tests (M6-04: Federated Roadmap Propagation)

**Target file:** `tests/governance/federation/test_federated_amendment.py`
**Minimum count:** 8 tests (all IDs below are required)

| Test ID | Description | Gate/Invariant Verified |
|---|---|---|
| `T6-04-01` | All propagation gates pass → proposal arrives at destination in `proposed` state | GATE-M604-01..06 |
| `T6-04-02` | Source approval does NOT set destination state; destination evaluates fresh | `INVARIANT PHASE6-FED-0` |
| `T6-04-03` | `divergence_count > 0` on any node → `PHASE6_FEDERATED_AMENDMENT_DIVERGENCE_BLOCKED`; all peers unchanged | GATE-M604-02 |
| `T6-04-04` | Partial peer failure → all-or-nothing rollback; all nodes revert to pre-propagation state | Rollback contract |
| `T6-04-05` | `federation_origin` field present in propagated proposal lineage chain | Lineage contract |
| `T6-04-06` | HMAC key absent → `FederationKeyError` at boot; propagation never reached | GATE-M604-01 (`federation_hmac_required`) |
| `T6-04-07` | `proposal.authority_level != "governor-review"` → `PHASE6_FEDERATED_AUTHORITY_VIOLATION`; rejected | GATE-M604-03 |
| `T6-04-08` | `verify_replay()` hash mismatch → `DeterminismViolation`; propagation halted; no peer receives proposal | GATE-M604-06 |
| `T6-04-09` | `federated_amendment_propagated` ledger event emitted on successful propagation to all peers | Ledger contract |
| `T6-04-10` | Pending amendment on any peer → `PHASE6_FEDERATED_AMENDMENT_STORM_BLOCKED`; propagation deferred | GATE-M604-05 (`INVARIANT PHASE6-STORM-0`) |

**Ledger event assertions (required in each relevant test):**
- `T6-04-01`: `federated_amendment_propagated` event in ledger of source and all peers
- `T6-04-04`: Rollback event in ledger; no `federated_amendment_propagated` emitted
- `T6-04-06`: `FederationKeyError` exception; no ledger entries from propagation path

---

## Shared Determinism Requirements

These properties apply to ALL Phase 6 tests and are verified by `lint_determinism.py`:

1. No `random`, `uuid4()`, `time.time()`, `datetime.now()` without seeded deterministic provider
2. No network calls from test bodies
3. All fixtures use frozen inputs (no live telemetry queries)
4. Ledger event payload fields are deterministic functions of inputs (no timestamps from wall clock)
   - Exception: `signoff_timestamp` in `roadmap_amendment_human_signoff` — must be injected as fixture parameter

---

## Evidence Matrix Cross-Reference

| Test ID | Evidence artifact path | PR |
|---|---|---|
| `T6-03-01..13` | `tests/autonomy/test_evolution_loop_amendment.py` | PR-PHASE6-02 |
| `T6-04-01..10` | `tests/governance/federation/test_federated_amendment.py` | PR-PHASE6-03 |

Both test files must be listed in `docs/comms/claims_evidence_matrix.md` Phase 6 rows
before the corresponding PR may merge. Evidence rows with empty `test_ref` block the
release gate (`phase6-evidence-matrix-complete` CI check).

---

*This specification is governed by `docs/CONSTITUTION.md`. Test IDs are stable identifiers
and must not be renamed without a corresponding evidence matrix update and ArchitectAgent
review. Authored by ArchitectAgent — no code generated.*
