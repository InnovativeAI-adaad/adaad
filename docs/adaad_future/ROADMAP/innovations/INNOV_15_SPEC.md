# INNOV-15 Specification — Agent Reputation Staking (ARS)

**Phase:** 100  
**Version target:** v9.33.0  
**Module:** `runtime/innovations30/reputation_staking.py`  
**Scaffold:** Complete — promotion to full implementation required  
**Authority:** HUMAN-0 — Dustin L. Reid

---

## Purpose

Converts hollow proposals into costly commitments. When agents stake credits on proposals, they have economic skin in the game. Failed proposals burn stake. Successful proposals multiply it. This creates natural selection pressure for quality without adding bureaucracy.

---

## Economic Model

```
Initial balance: 100.0 credits (configurable per agent)

Stake on proposal:
  amount = max(MIN_STAKE, balance * 0.05)  # default 5%
  amount = min(amount, balance * MAX_STAKE_FRACTION)  # cap at 20%
  amount = max(MIN_STAKE, min(amount, balance))  # floor/ceiling
  
  pre_balance = balance
  balance = balance - amount

Outcome: PASSED
  returned = amount * GOVERNANCE_PASS_MULTIPLIER  # 1.5x
  balance = balance + returned
  net_gain = returned - amount  # = 0.5 * amount

Outcome: FAILED  
  burned = amount * GOVERNANCE_FAIL_BURN_RATE  # 1.0x (100%)
  balance = balance - 0  # already deducted on stake
  net_loss = amount  # full stake lost
```

**Constants:**
```python
MIN_STAKE: float = 1.0
MAX_STAKE_FRACTION: float = 0.20
GOVERNANCE_PASS_MULTIPLIER: float = 1.5
GOVERNANCE_FAIL_BURN_RATE: float = 1.0
```

---

## Hard-Class Invariants

### STAKE-0: Ledger Persists Before Balance Mutates
```
The stake record must be written to the append-only JSONL ledger
BEFORE any balance change is applied to the in-memory wallet.
Violation raises StakeInvariantViolation.
```

### STAKE-DETERM-0: Deterministic Stake Digest
```
stake_digest = "sha256:" + sha256(f"{agent_id}:{mutation_id}:{staked_amount}")[:16]
Same inputs always produce the same digest.
```

### STAKE-HUMAN-0: Balance Ceiling Advisory
```
When agent balance exceeds 10x initial_balance, HUMAN-0 advisory
is triggered before additional stake is accepted.
The system records the advisory event but does not block the stake.
```

### STAKE-BURN-0: No Partial Burns
```
GOVERNANCE_FAIL_BURN_RATE must be applied atomically.
No partial burns. Either the full burn applies or the stake is returned.
```

---

## Test Requirements (T100-ARS-01 through T100-ARS-30)

| Test ID | Scenario | Expected |
|---|---|---|
| T100-ARS-01 | Register agent with initial balance | Balance == 100.0 |
| T100-ARS-02 | Stake default amount (5% of balance) | Record created, balance decremented |
| T100-ARS-03 | Stake custom amount within bounds | Custom amount applied |
| T100-ARS-04 | MIN_STAKE floor enforcement | Amount never < MIN_STAKE |
| T100-ARS-05 | MAX_STAKE_FRACTION ceiling | Amount never > 0.20 * balance |
| T100-ARS-06 | Settle PASSED outcome | Balance += amount * 1.5 |
| T100-ARS-07 | Settle FAILED outcome | Balance unchanged (stake already deducted) |
| T100-ARS-08 | Stake digest determinism | Same inputs → same digest |
| T100-ARS-09 | Ledger-first ordering | JSONL record exists before balance change |
| T100-ARS-10 | Wallet persistence | Balance survives reload |
| T100-ARS-11 | Multiple agents independent | Agent A stake doesn't affect Agent B |
| T100-ARS-12 | Insufficient balance handling | stake <= balance enforced |
| T100-ARS-13 | STAKE-0 invariant assertion | Test that invariant is declared Hard-class |
| T100-ARS-14 | STAKE-DETERM-0 invariant | Determinism verified across 100 runs |
| T100-ARS-15 | STAKE-HUMAN-0 advisory trigger | Advisory event logged at 10x ceiling |
| T100-ARS-16 | Balance accumulation over epochs | Compound gains tracked correctly |
| T100-ARS-17 | Zero balance agent | Stake limited to actual balance |
| T100-ARS-18 | Fail-open ledger read | Corrupt JSONL gracefully skipped |
| T100-ARS-19 | Concurrent stake records | Multiple stakes on different mutations |
| T100-ARS-20 | Pre-stake balance recorded | pre_stake_balance stored correctly |
| T100-ARS-21 | outcome field transitions | pending → passed/failed |
| T100-ARS-22 | final_balance recorded | Correct final balance on settle |
| T100-ARS-23 | Replay from ledger | Ledger can reconstruct wallet state |
| T100-ARS-24 | __all__ export | Module exports in __all__ |
| T100-ARS-25 | Integration: CEL step wiring | ConstitutionalEvolutionLoop calls stake() |
| T100-ARS-26 | Integration: settle on gate verdict | GovernanceGate calls settle() |
| T100-ARS-27 | Multiple epochs same agent | Cumulative balance history tracked |
| T100-ARS-28 | StakeRecord dataclass immutability | Records are not mutated after creation |
| T100-ARS-29 | Wallet save/load roundtrip | JSON roundtrip preserves precision |
| T100-ARS-30 | STAKE-BURN-0 atomicity | No partial burns possible |

---

## Integration Points

### CEL Integration (Step N — Post-Proposal Receipt)
```python
# In ConstitutionalEvolutionLoop.run_epoch():
stake_record = self.reputation_staking.stake(
    agent_id=proposal.agent_id,
    mutation_id=proposal.mutation_id,
    epoch_id=epoch_id
)
```

### GovernanceGate Integration (Post-Decision)
```python
# After gate verdict:
self.reputation_staking.settle(
    stake_record=stake_record,
    outcome='passed' if verdict.approved else 'failed'
)
```

---

## Routing Impact (post-Phase 101)

After EmergentRoles ships (Phase 101), the routing layer will:
1. Identify the agent's emergent role
2. Boost routing priority for agents with high cumulative stake gains
3. Reduce routing priority for agents with consecutive stake losses

This creates a virtuous cycle: quality proposals → stake gains → routing priority → more proposals → more quality signal.

---

*Spec status: INNOV-15 scaffold exists at runtime/innovations30/reputation_staking.py*  
*Promotion to full implementation: Phase 100 · v9.33.0*
