# Phase 92 — INNOV-08: Adversarial Fitness Red Team
## ArchitectAgent Proposal | Governor Ratification Package (Closed)

**Prepared by:** Claude (ArchitectAgent role, DUSTADAAD environment)
**Prepared:** 2026-03-27
**Last reviewed:** 2026-03-28
**Governor:** Dustin L. Reid — HUMAN-0
**Base version:** v9.24.1 (Phase 91 complete — Audit Hardening + LSME INNOV-07)
**Target release:** v9.25.0 (shipped)
**Current canonical state:** Phase 93 complete — v9.26.0 (INNOV-09 AFIT shipped)
**Current/Next pointer:** Current = Phase 93 (v9.26.0), Next = Phase 94 (INNOV-10 roadmap)
**Phase 92 closure artifact:** `artifacts/governance/phase92/phase92_sign_off.json`
**Authority:** `CONSTITUTION.md v0.9.0` → `ARCHITECTURE_CONTRACT.md`
**HUMAN-0 gate:** This plan requires governor ratification before PR-92-01 may open.
**Source specification:** `ADAAD_30_INNOVATIONS.md §8 — Adversarial Fitness Red Team`

---

## Executive Summary

Phase 91 completed the Post-GA Governance Hardening Sprint and shipped Live Shadow Mutation Execution (LSME / INNOV-07) — ADAAD now runs every mutation proposal through a zero-write shadow execution harness before live promotion, with full divergence and latency gating.

Phase 92 ships **INNOV-08: Adversarial Fitness Red Team (AFRT)** — a dedicated red-team agent whose sole mandate is to falsify mutation proposals before the `GovernanceGate` accepts them. Where `LSME` validates *behavior under execution*, `AFRT` generates *targeted adversarial test cases* against proposals, specifically probing paths the proposing agent didn't cover. A mutation that survives the Red Team has been stress-tested beyond its own suite.

This is the first dedicated adversarial reasoning layer in the CEL — moving ADAAD from self-evaluation to **adversarial peer-review as a constitutional gate**.

---

## Phase 91 Baseline — What Was Shipped

| Artifact | Version | Status |
|---|---|---|
| Live Shadow Mutation Execution (LSME) | v9.24.0 | ✅ shipped |
| `ShadowExecutionHarness` — zero-write invariant (LSME-0) | v9.24.0 | ✅ enforced |
| `ShadowFitnessReport` — LSME-GATE-1 divergence + latency gating | v9.24.0 | ✅ enforced |
| Phase 91 Senior Audit — 5-patch hardening | v9.24.1 | ✅ merged |
| LINEAGE-CACHE-01, CI-DUPE-01, PYPROJECT-VER-01, PHONE-LIBCST-01, AUDIT-TEL-01 | v9.24.1 | ✅ resolved |
| Tests: 341 test files, all gates tier_0–tier_3 passing | v9.24.1 | ✅ |
| HUMAN-0 attest: phase91-human0-attested | 2026-03-27 | ✅ |

---

## Constitutional Grounding

AFRT extends the Constitutional Evolution Loop at **Step 6 (Fitness Evaluation)** by inserting an adversarial falsification pass between proposal generation and scoring. The mutation proposal is handed to `AdversarialRedTeamAgent` before `GovernanceGate.evaluate()` runs. If the Red Team discovers uncovered failure paths, the mutation is returned to the proposer with a `RedTeamFindingsReport` rather than being scored as-is.

This is architecturally parallel to how `LSME` gates on *execution behavior* — AFRT gates on *reasoning coverage*. Both gates must pass for a mutation to advance to `GovernanceGate` evaluation.

```
Proposal → LSME gate → AFRT gate → GovernanceGate → Ledger append
              ↓ fail        ↓ fail
           ABORTED      RETURNED (with RedTeamFindingsReport)
```

HUMAN-0 invariant is preserved: the Red Team Agent may *reject* proposals, but may never *approve* a constitutionally gated mutation without the full gate stack.

---

## Scope

### Track A (P0) — Core AFRT Engine

| Work Item | Module | Invariant |
|---|---|---|
| `AdversarialRedTeamAgent` — adversarial test case generator | `runtime/evolution/afrt_engine.py` | AFRT-0 |
| `RedTeamFindingsReport` — structured falsification result | `runtime/evolution/afrt_engine.py` | AFRT-0 |
| CEL Step 6 wiring — inject AFRT before `GovernanceGate` | `runtime/evolution/constitutional_loop.py` | AFRT-GATE-0 |
| `CodeIntelModel` integration — find uncovered path surfaces | `runtime/code_intel.py` (existing) | AFRT-INTEL-0 |
| `RedTeamLedgerEvent` — ledger-first AFRT result record | `runtime/lineage/lineage_ledger_v2.py` | AFRT-LEDGER-0 |
| `AdversarialCaseGenerator` — up to 5 targeted test cases per proposal | `runtime/evolution/afrt_engine.py` | AFRT-CASES-0 |

### Track B (P1) — Aponi AFRT Dashboard Panel

| Work Item | Module | Detail |
|---|---|---|
| `afrt_panel.js` — real-time Red Team findings display | `ui/aponi/afrt_panel.js` | Live adversarial case stream |
| `AFRT_VERDICT` WebSocket event | `app/api/websocket.py` | Bus emission on Red Team verdict |
| `AFRT_FINDINGS` endpoint | `app/api/governance.py` | `GET /governance/afrt/findings` |

---

## Key Invariants

### AFRT-0 — Red Team zero-promotion invariant
The `AdversarialRedTeamAgent` must never autonomously promote or approve a mutation. Its only output is a `RedTeamFindingsReport` with verdict `PASS` or `RETURNED`. Any code path that allows AFRT to directly append a `MutationApprovalEvent` to the ledger violates AFRT-0 and must halt.

```python
# Enforced in AdversarialRedTeamAgent.evaluate()
assert report.verdict in (RedTeamVerdict.PASS, RedTeamVerdict.RETURNED)
assert not report.approval_emitted  # AFRT-0
```

### AFRT-GATE-0 — Gate ordering invariant
AFRT evaluation must occur *after* LSME (LSME-GATE-1) and *before* `GovernanceGate.evaluate()` in the CEL step sequence. Any CEL run where step ordering differs from `[LSME → AFRT → GovernanceGate]` must raise `CELStepOrderViolation`.

### AFRT-INTEL-0 — CodeIntel coupling invariant
Adversarial case generation must use `CodeIntelModel.get_uncovered_paths(proposal)` as the primary path surface. Cases generated without CodeIntel coverage data are inadmissible and must be discarded. This ensures Red Team cases target real coverage gaps, not arbitrary inputs.

### AFRT-LEDGER-0 — Ledger-first invariant
`RedTeamLedgerEvent` must be appended to `LineageLedgerV2` *before* the AFRT result is returned to the CEL orchestrator — consistent with the ledger-first principle established in Phase 73 (`phase73-seed-review-0-ledger-first`).

### AFRT-CASES-0 — Case count bound
`AdversarialCaseGenerator` must generate between 1 and 5 adversarial test cases per proposal. Zero cases is a malformed result (treat as AFRT engine failure, abort epoch). More than 5 cases exceeds the constitutional budget for adversarial overhead.

### AFRT-DETERM-0 — Deterministic reproducibility
Given identical proposal input and `CodeIntelModel` coverage snapshot, `AdversarialCaseGenerator` must produce identical adversarial test cases across runs. No `datetime.now()`, `random.random()`, or `uuid4()` calls within the case generation path.

---

## Acceptance Criteria

| Criterion | Verification |
|---|---|
| `AdversarialRedTeamAgent` generates 1–5 adversarial cases per proposal | `test_phase92_afrt.py` T92-AFRT-01..05 |
| AFRT-0: Red Team cannot emit approval events | T92-AFRT-06..08 |
| AFRT-GATE-0: CEL step order enforced | T92-AFRT-09..11 |
| AFRT-INTEL-0: cases sourced from CodeIntel uncovered paths | T92-AFRT-12..14 |
| AFRT-LEDGER-0: ledger event written before result returned | T92-AFRT-15..17 |
| AFRT-CASES-0: zero-case result treated as engine failure | T92-AFRT-18 |
| AFRT-DETERM-0: identical inputs → identical case set | T92-AFRT-19..20 |
| `RedTeamFindingsReport` correctly returned to proposer on failure | T92-AFRT-21..23 |
| Aponi panel displays live AFRT verdict stream (Track B) | T92-AFRT-24..25 |

**Minimum gate:** 25/25 tests passing before PR-92-01 may merge.

---

## Implementation Notes

### `AdversarialRedTeamAgent` — core interface

```python
@dataclass
class RedTeamFindingsReport:
    proposal_id: str
    verdict: RedTeamVerdict           # PASS | RETURNED
    adversarial_cases: list[AdversarialCase]  # 1-5 items
    uncovered_paths: list[str]        # from CodeIntelModel
    failure_cases: list[AdversarialCase]      # subset that failed
    report_hash: str                  # SHA-256 of deterministic repr
    trace_committed: bool             # ledger-first flag (AFRT-LEDGER-0)
    approval_emitted: bool = False    # always False — AFRT-0

class AdversarialRedTeamAgent:
    def evaluate(self, proposal: MutationRequest) -> RedTeamFindingsReport:
        """
        1. Query CodeIntelModel for uncovered paths (AFRT-INTEL-0)
        2. Generate up to 5 adversarial cases targeting those paths (AFRT-CASES-0)
        3. Execute each case in sandbox (read-only, no filesystem writes)
        4. Append RedTeamLedgerEvent to LineageLedgerV2 (AFRT-LEDGER-0)
        5. Return RedTeamFindingsReport with PASS or RETURNED verdict (AFRT-0)
        """
```

### CEL Step injection point

```python
# runtime/evolution/constitutional_loop.py — Step 6 (Fitness Evaluation)
# Existing order: [..., step5_sandbox_preflight, step6_fitness_eval, ...]
# Phase 92 order: [..., step5_sandbox_preflight, step6a_lsme, step6b_afrt, step6c_fitness_eval, ...]
```

### `RedTeamLedgerEvent` schema

```json
{
  "event_type": "RED_TEAM_EVALUATION",
  "proposal_id": "<proposal_id>",
  "verdict": "PASS | RETURNED",
  "adversarial_cases_count": 3,
  "failure_cases_count": 1,
  "uncovered_paths_sampled": ["runtime/foo.py:L42", "runtime/bar.py:L88"],
  "report_hash": "<sha256>",
  "timestamp_utc": "<iso8601>",
  "epoch_id": "<epoch_id>"
}
```

---

## Release Target

| Milestone | Target |
|---|---|
| Branch open | `feat/phase92-innov08-afrt` |
| PR-92-01 | Track A — AFRT core engine |
| PR-92-02 | Track B — Aponi AFRT panel |
| Version | v9.25.0 |
| HUMAN-0 gate | Governor ratification required before PR-92-01 opens |

---

## Non-Delegable Actions (Governor-Only)

| Action | Trigger |
|---|---|
| Ratify this plan | HUMAN-0 sign-off to open PR-92-01 |
| Tag `v9.25.0` with GPG signature | After PR-92-01 merges to main |
| Review `RedTeamFindingsReport` first live run | Advisory — not gate-blocking |

---

## Dependency Chain

```
Phase 91 (LSME INNOV-07) ✅
  └─ Phase 92 (AFRT INNOV-08) ← this plan
       └─ Phase 93 (INNOV-09 AFIT) ✅ shipped v9.26.0 — see `docs/plans/PHASE_93_CLOSURE.md`
```

AFRT depends on:
- `ShadowExecutionHarness` (Phase 91 LSME) — already shipped ✅
- `CodeIntelModel` (Phase 58) — already shipped ✅
- `LineageLedgerV2` (Phase 61+) — already shipped ✅
- `GovernanceGate` v2 (Phase 63) — already shipped ✅
- CEL 14-step loop (Phase 64) — already shipped ✅

All dependencies satisfied. Phase 92 may begin on HUMAN-0 ratification.
