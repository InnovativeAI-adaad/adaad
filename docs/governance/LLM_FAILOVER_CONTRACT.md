# LLM Failover Governance Contract

**Version:** 1.0.0
**Status:** Active
**Effective:** 2026-03-14
**Authority:** `CONSTITUTION.md → ARCHITECTURE_CONTRACT.md`
**Owner:** ArchitectAgent (`architect@adaad.ai`)
**Implements:** FINDING-66-001 (Phase 66 / WORK-66-C)
**Enforcement module:** `runtime/autonomy/ai_mutation_proposer.py`

---

## Purpose

This contract defines the deterministic, auditable behavior of all LLM API calls
made by the ADAAD mutation proposer. It specifies timeout policy, failure
classification, retry budget, and the evidence obligation that ensures every
LLM call outcome is recorded in the governance ledger.

Silent LLM failures are a constitutional violation. Every outcome — success,
retry, failover, or exhaustion — must produce a ledger event.

---

## 1. Provider Sequence

```
PROVIDER_SEQUENCE: [primary]

primary:   Anthropic Claude API (https://api.anthropic.com/v1/messages)
           Model: claude-sonnet-4-20250514
```

The sequence is extensible. A secondary provider may be added in a future
constitutional amendment. Until then, primary exhaustion → epoch skipped.

---

## 2. Timeout Policy

All values are per-call unless otherwise noted.

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| `per_call_timeout_s` | 30 | seconds | urllib timeout per HTTP request |
| `max_retries_per_agent` | 1 | count | Total attempts = 2 (initial + 1 retry) |
| `global_timeout_budget_s` | 90 | seconds | Wall-clock budget for all 3 agents combined |

**Derivation:** `global_timeout_budget_s = per_call_timeout_s × 3 agents = 90s`.
Agents run concurrently; budget is a wall-clock deadline, not a sum of serial timeouts.

These values are encoded as defaults in `propose_from_all_agents()` and must not
be reduced below these floors without a constitutional amendment.

---

## 3. Failure Classification

Every failure is classified into one of three categories. Classification is
deterministic given the exception type.

### 3.1 Transient — `agent_timeout`

**Trigger:** `TimeoutError` raised during HTTP call.
**Action:** Retry within `max_retries_per_agent` budget.
**Outcome after retries exhausted:** Agent contributes zero proposals; failure
payload recorded with `code: "agent_timeout"`.
**Ledger event severity:** WARNING.

### 3.2 Persistent — `agent_error`

**Trigger:** Any non-timeout exception (`urllib.error.HTTPError`, `json.JSONDecodeError`,
`Exception`) after all retries exhausted.
**Action:** Agent contributes zero proposals; failure payload recorded with
`code: "agent_error"`.
**Ledger event severity:** WARNING.

### 3.3 Total Exhaustion — `zero_proposal_epoch`

**Trigger:** All agents in `CANONICAL_AGENT_ORDER` return zero proposals.
**Action:** Epoch is SKIPPED. No mutation proceeds. Ledger event emitted with
`code: "zero_proposal_epoch"` and `severity: BLOCKING`.
**Constitutional constraint:** A zero-proposal epoch is NOT a governance gate
failure. The epoch is skipped with evidence. The EvolutionLoop MAY retry on
the next scheduled cycle.

### 3.4 Malformed Response

**Trigger:** LLM response is non-empty but `json.JSONDecodeError` is raised
during proposal parsing.
**Action:** Treated as `agent_error`. Zero proposals from that agent.
**Ledger event severity:** WARNING.

---

## 4. Evidence Obligation

### 4.1 Constitutional Requirement

Every LLM call outcome MUST produce a governance evidence event. This is a
BLOCKING constitutional constraint — silent failure is forbidden.

### 4.2 Event Schema

Event type: `llm_call_outcome`

```json
{
  "event_type": "llm_call_outcome",
  "payload": {
    "agent":          "<architect|dream|beast>",
    "provider":       "anthropic",
    "model":          "claude-sonnet-4-20250514",
    "outcome":        "<success|timeout|error|zero_proposal_epoch>",
    "attempt_count":  <int>,
    "latency_ms":     <float>,
    "epoch_id":       "<epoch identifier or null>",
    "failure_code":   "<agent_timeout|agent_error|null>",
    "failure_detail": "<string or null>"
  }
}
```

### 4.3 Publication Responsibility

The EvolutionLoop (caller of `propose_from_all_agents()`) is responsible for
publishing `llm_call_outcome` events to the governance ledger after receiving
the `AgentProposalBatch`. The proposer returns structured failure payloads in
`AgentProposalBatch.failures` to enable this.

**Note on current state:** As of v9.1.0, the failure payload structure exists
in `AgentProposalBatch.failures`. Full ledger publication from EvolutionLoop
is the next enforcement step and is tracked in the hardening backlog.

### 4.4 Minimum Current Enforcement

As of v9.1.0, the following is enforced and test-gated:

- `AgentProposalBatch.failures` contains a structured payload for every failed agent
- Failure payload includes `code`, `attempts`, `timeout_seconds`, and `detail`
- A zero-proposal epoch (all agents failed) is detectable from `AgentProposalBatch`
  without inspecting logs

Full ledger publication enforcement is Phase 67+ scope.

---

## 5. Zero-Proposal Epoch Rule

```
IF len(all_proposals_across_all_agents) == 0:
  - epoch_outcome = SKIPPED
  - NO mutation is applied
  - Evidence event emitted: type="llm_call_outcome", outcome="zero_proposal_epoch"
  - EvolutionLoop records epoch as skipped, not failed
  - No governance gate evaluation occurs (nothing to evaluate)
  - Next epoch cycle proceeds normally
```

This rule is UNCONDITIONAL. It cannot be overridden by configuration, feature
flag, or runtime parameter.

---

## 6. Forbidden Behaviors

| Behavior | Classification |
|----------|---------------|
| Applying a mutation when all agents returned zero proposals | BLOCKING violation |
| Silently swallowing an LLM exception without a failure payload | BLOCKING violation |
| Reducing `per_call_timeout_s` below 30s without amendment | BLOCKING violation |
| Treating a zero-proposal epoch as a governance gate failure | INCORRECT behavior |
| Retrying beyond `max_retries_per_agent` without amendment | BLOCKING violation |

---

## 7. Amendment Procedure

Changes to `PROVIDER_SEQUENCE`, timeout floor values, or retry counts require:

1. A constitutional amendment PR approved by Innovadaad
2. Update to this document (`LLM_FAILOVER_CONTRACT.md`) with new version
3. Update to `propose_from_all_agents()` defaults to match
4. Test gate update confirming new floor values are enforced

---

## 8. References

- Implementation: `runtime/autonomy/ai_mutation_proposer.py`
- Failure payload schema: `_failure_payload()` in same module
- Caller: `runtime/evolution/evolution_loop.py :: run_epoch()`
- Constitutional basis: `CONSTITUTION.md` §Fail-Closed Governance
- Architecture basis: `ARCHITECTURE_CONTRACT.md` §Layer ownership
