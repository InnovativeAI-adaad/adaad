# Phase 66 Plan — Hardening Tier Alpha

**Version:** 1.0.0
**Status:** APPROVED
**Approved by:** Dustin L. Reid (Innovadaad / Founder, InnovativeAI LLC)
**Approval date:** 2026-03-14
**Authority:** Constitutional governance chain — `CONSTITUTION.md → ARCHITECTURE_CONTRACT.md → SECURITY_INVARIANTS_MATRIX.md → AGENTS.md`
**Base version:** v9.0.0
**Target release:** v9.1.0

---

## Purpose

Phase 66 is exclusively a hardening phase. No new architecture. No new subsystems.
All five deliverables close open findings from the Phase 65 deep dive.

Scope constraint: every work item must reduce risk or close an audit gap.
Any proposal that expands scope requires a new PLAN and human approval.

---

## Open Findings Closed by This Phase

| ID | Title | Severity | Work Item |
|----|-------|----------|-----------|
| FINDING-66-001 | LLM failover strategy undocumented | P2 | WORK-66-C |
| FINDING-66-002 | WeightAdaptor `prediction_accuracy` not in telemetry | P1 | WORK-66-A |
| FINDING-66-003 | Patent filing: constitutional mutation governance | P1 | WORK-66-E |
| FINDING-66-004 | 2-of-3 Ed25519 key ceremony not executed | P2 | WORK-66-D |
| FINDING-66-005 | `LineageLedgerV2` O(n) streaming invariants unspecified | P1 | WORK-66-B |

---

## Work Items

### WORK-66-A — WeightAdaptor Telemetry Completeness

**Finding:** FINDING-66-002 (P1)
**Branch:** `fix/66-weight-adaptor-telemetry`
**Scope:** `runtime/autonomy/epoch_telemetry.py` + tests only

**Problem:** `EpochRecord` omits `prediction_accuracy`. The adaptive learning
signal that governs mutation scoring weight evolution is absent from the
append-only governance telemetry. This breaks deterministic replay of
adaptive weight state at any historical epoch.

**Required changes:**

1. `EpochRecord` — add field `prediction_accuracy: Optional[float]`
2. `EpochTelemetry.append_from_result()` — capture `adaptor.prediction_accuracy`
   **after** `adapt()` has been called (post-adapt value)
3. `EpochRecord.to_dict()` — emit `"prediction_accuracy": self.prediction_accuracy`

**Gate conditions (all must pass):**
- `EpochRecord.to_dict()` contains key `"prediction_accuracy"`
- Value matches `WeightAdaptor.prediction_accuracy` at time of capture
- `None` accepted for records constructed without an adaptor (backward compat)
- No existing test regressions

**Invariants preserved:**
- `recorded_at` is wall-clock only; `prediction_accuracy` is the EMA value
- Append-only contract unchanged
- No changes to `WeightAdaptor` internals

---

### WORK-66-B — LineageLedgerV2 Streaming Verification Invariants

**Finding:** FINDING-66-005 (P1)
**Branch:** `fix/66-lineage-stream-invariants`
**Scope:** `runtime/evolution/lineage_v2.py` (minimal behavioral fix if needed) + tests

**Problem:** `_verified_tail_hash` caching exists (C-04 partial) but three invariants
are unspecified and untested: (1) partial scans must not poison the cache,
(2) external reload must clear the cache, (3) warm-cache appends must not re-scan.

**Required invariants:**

```
INV-LINEAGE-STREAM-1:
  _verified_tail_hash MUST be None after any reload from disk.
  Cache must not survive a new LineageLedgerV2() instantiation.

INV-LINEAGE-STREAM-2:
  verify_integrity(max_lines=k) where k < total_entries MUST NOT set
  _verified_tail_hash. Partial verification is not a complete integrity proof.

INV-LINEAGE-STREAM-3:
  append_event() on a warm cache (non-None _verified_tail_hash) MUST NOT
  re-scan the full ledger. One full scan per cold-start only.
```

**Gate conditions (all must pass):**
- Test: full `verify_integrity()` sets `_verified_tail_hash`
- Test: `verify_integrity(max_lines=k)` for `k < total` does NOT set `_verified_tail_hash`
- Test: successive appends on warm cache do not trigger re-scan
- Test: new `LineageLedgerV2()` from same path initializes `_verified_tail_hash = None`

**Failure modes:**
- FM-1: partial verify poisons cache → false integrity claim → constitutional violation
- FM-2: stale cache on reload → accepted without proof → audit gap
- FM-3: every append re-scans → O(n²) regression → performance invariant violated

---

### WORK-66-C — LLM Failover Governance Contract

**Finding:** FINDING-66-001 (P2)
**Branch:** `docs/66-llm-failover-contract`
**Scope:** New doc `docs/governance/LLM_FAILOVER_CONTRACT.md` + docstring update + one test

**Problem:** `ai_mutation_proposer.py` calls the LLM with no documented failover policy,
timeout contract, or evidence obligation. A silent LLM failure produces a zero-candidate
epoch with no governance ledger entry.

**Decisions (ArchitectAgent judgment, Innovadaad-delegated):**
- `per_call_timeout_s: 30`
- `max_retries_per_provider: 2`
- `total_failover_budget_s: 90`
- `provider_sequence: [primary]` (single-provider baseline; extensible)

**Document must specify:**
1. Provider sequence and timeout policy (values above)
2. Failure classification: transient / persistent / malformed
3. Evidence obligation: every call outcome → ledger event `llm_call_outcome`
4. Zero-proposal epoch rule: epoch SKIPPED (not a gate failure); no mutation proceeds
5. Constitutional constraint: silent failure is forbidden; all outcomes are evidence

**Gate conditions:**
- `docs/governance/LLM_FAILOVER_CONTRACT.md` committed
- `ai_mutation_proposer.py` module docstring references the contract
- At minimum one test asserts exhaustion path emits a governance event type

---

### WORK-66-D — Governance Key Ceremony Runbook

**Finding:** FINDING-66-004 (P2)
**Branch:** `docs/66-key-ceremony-runbook`
**Scope:** New doc `docs/governance/KEY_CEREMONY_RUNBOOK_v1.md` only; no code

**Problem:** 2-of-3 Ed25519 threshold signing is specified but the key generation
ceremony has not been executed. Single-key governance is a single point of failure
for the constitutional lineage chain.

**ArchitectAgent judgment (delegated):**
- PRIMARY key holder: Innovadaad (Dustin L. Reid)
- SECONDARY key holder: designation deferred to Innovadaad post-runbook publication
- WITNESS key holder: designation deferred; may be held in reserve

**Runbook must specify:**
1. Three key-holder roles and responsibilities
2. Ed25519 key generation procedure (air-gapped recommended)
3. Public key registration as genesis ledger event
4. Threshold signing procedure for governance amendments
5. Revocation and rotation procedure without breaking hash chain
6. Ceremony artifact: signed commitment committed to repo as evidence

**Human gate:** Runbook publication is an ArchitectAgent deliverable.
Ceremony execution requires Innovadaad action (designate secondary/witness, execute).
Execution tracking deferred to Phase 67 or async.

---

### WORK-66-E — Patent Filing Execution

**Finding:** FINDING-66-003 (P1)
**Branch:** N/A — human action only
**Scope:** `docs/IP_PATENT_FILING_ARTIFACT.md` (already complete) → IP counsel

**Action required from Innovadaad:**
1. Transmit `docs/IP_PATENT_FILING_ARTIFACT.md` to IP counsel
2. Receive provisional application number
3. Record in `.adaad_agent_state.json`:
   ```json
   "patent_provisional_number": "US[XXXXX]/[YYYY]",
   "patent_filing_date": "YYYY-MM-DD"
   ```
4. FINDING-66-003 status updated to `"resolved"` in agent state

**Urgency:** Time-sensitive. The v1.1-GA deadline creates a public-disclosure bar
risk if filing is delayed past first public use of the patented method.

---

## Execution Sequence

```
Step 1  docs/phase66-plan        → This document. Human-approved. ✅
Step 2  fix/66-weight-adaptor-telemetry   → WORK-66-A (P1, code + tests)
Step 3  fix/66-lineage-stream-invariants  → WORK-66-B (P1, code + tests)
Step 4  docs/66-llm-failover-contract     → WORK-66-C (P2, doc + docstring + test)
Step 5  docs/66-key-ceremony-runbook      → WORK-66-D (P2, doc only)
Step 6  [Human] Patent filing             → WORK-66-E (P1, Innovadaad action)
Step 7  release/v9.1.0                    → Phase close, v9.1.0 tag
```

Each step is its own branch and PR. Steps 2–5 are sequential (fail-closed).
Step 6 is async (human-gated). Step 7 requires Steps 2–5 merged and Step 6 resolved.

---

## Invariants This Phase Must Not Violate

| Invariant | Source | Enforcement |
|-----------|--------|-------------|
| Append-only telemetry | ARCHITECTURE_CONTRACT | No delete/overwrite in EpochTelemetry |
| Deterministic replay | CONSTITUTION §replay | No `datetime.now()` in EpochRecord |
| Fail-closed governance | CONSTITUTION §gate | No silent errors in lineage verification |
| Human-gate Tier-0 | CONSTITUTION §tier-0 | Key ceremony and patent are human-only |
| One root cause per PR | AGENTS.md | Each work item is one branch and one PR |
| Never weaken tests | AGENTS.md | No test skips, no test deletions |

---

## Approval Record

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Founder / Innovadaad | Dustin L. Reid | 2026-03-14 | Signed |
| ArchitectAgent | architect@adaad.ai | 2026-03-14 | Committed |
