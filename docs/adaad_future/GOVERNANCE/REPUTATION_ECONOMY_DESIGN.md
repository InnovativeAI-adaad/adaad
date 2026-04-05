# Reputation Economy Design

**Innovation:** INNOV-15 (Agent Reputation Staking) + INNOV-16 (Emergent Role Specialization)  
**Status:** Pre-implementation design — target Phase 100–101  
**Authority:** HUMAN-0 — Dustin L. Reid

---

## Economic Model

The reputation economy solves the cheap-talk problem in autonomous proposal systems: when proposals are free, quality is unenforceable. When proposals cost stake, quality becomes self-selecting.

### Wallet Architecture

Each agent maintains a wallet tracked in `data/agent_wallets.json`:
```json
{
  "agent-structural-architect-001": 142.5,
  "agent-safety-hardener-002": 87.3,
  "agent-adaptive-explorer-003": 23.1
}
```

Initial balance: 100.0 credits. No inflation mechanism. Supply is capped. Credits are earned by passing governance and lost by failing.

### Stake Mechanics

```
On Proposal:
  deduct = max(MIN_STAKE, min(balance × 0.05, balance × MAX_STAKE_FRACTION))
  wallet[agent] -= deduct
  ledger.append(StakeRecord(pending))

On PASSED verdict:
  returned = deduct × GOVERNANCE_PASS_MULTIPLIER  # 1.5x
  wallet[agent] += returned
  ledger.update(StakeRecord(passed, final_balance=wallet[agent]))

On FAILED verdict:
  # Stake already deducted. No return.
  ledger.update(StakeRecord(failed, final_balance=wallet[agent]))
```

### Long-Term Balance Dynamics

An agent with 100% pass rate compounds:
- Epoch 1: 100.0 → stake 5.0 → return 7.5 → balance 102.5
- Epoch 10: ~125.0
- Epoch 50: ~310.0

An agent with 50% pass rate (alternating):
- Pass: +2.5 (7.5 returned - 5.0 staked)
- Fail: -5.0
- Net per 2 epochs: -2.5
- Epoch 50: ~38.0 (bankruptcy territory)

An agent that reaches near-zero balance is effectively silenced — it can only propose with MIN_STAKE until it earns back through successful proposals.

---

## Role-Weighted Routing

After Phase 101 ships, routing uses role assignments:

### Routing Priority Matrix

| Mutation Type | Preferred Role | Secondary | Tertiary |
|---|---|---|---|
| Structural refactor | structural_architect | adaptive_explorer | undifferentiated |
| Safety hardening | safety_hardener | structural_architect | undifferentiated |
| Performance opt | performance_optimizer | adaptive_explorer | undifferentiated |
| Test coverage | test_coverage_guardian | structural_architect | undifferentiated |
| Exploratory | adaptive_explorer | performance_optimizer | undifferentiated |

### Routing Algorithm

```python
def route_proposal(mutation_type: str, agents: list[Agent]) -> Agent:
    preferred_role = ROUTING_MATRIX[mutation_type]["preferred"]
    
    # Filter to agents with preferred role and positive balance
    candidates = [
        a for a in agents
        if (a.role == preferred_role or a.role == "secondary_role")
        and a.balance >= MIN_STAKE
    ]
    
    if not candidates:
        # Fall back to any solvent agent
        candidates = [a for a in agents if a.balance >= MIN_STAKE]
    
    # Weight by cumulative stake gains (reward quality track record)
    weights = [max(0.1, a.cumulative_gains / a.total_staked) for a in candidates]
    
    return random.choices(candidates, weights=weights)[0]
```

---

## Reputation Score vs Balance

Balance is a point-in-time metric. Reputation is cumulative:

```
reputation_score = (
    (cumulative_passed / total_proposals) × 0.60 +    # pass rate
    (cumulative_stake_gains / initial_balance) × 0.25 + # ROI proxy
    (epochs_active / MAX_EPOCHS) × 0.15               # tenure
)
```

Reputation score used for:
- Routing priority boost (high reputation → more proposals assigned)
- Jury selection weighting (INNOV-14: CJS prefers high-reputation jurors)
- Post-mortem interview prioritization (INNOV-17)

---

## Anti-Gaming Measures

### MIN_STAKE Floor
Prevents agents from proposing with near-zero stake when bankrupt. Forces retirement or recharge through approved proposals.

### MAX_STAKE_FRACTION Cap
Prevents agents from going all-in on a single proposal. Enforces diversification.

### STAKE-0 Invariant
Ledger-first ordering means stake records are immutable before the governance gate runs. No retroactive stake adjustment.

### STAKE-HUMAN-0 Ceiling Advisory
At 10x initial balance, a HUMAN-0 advisory fires. Prevents runaway accumulation by a single agent without oversight.

---

## Bankruptcy and Recovery

An agent with balance < MIN_STAKE is in **stake bankruptcy**:
- Cannot propose new mutations
- Still receives behavioral observation for role discovery
- Can be rehabilitated by governance-approved credit grant (HUMAN-0 required)
- Rehabilitation grant is ledgered as a distinct event type

Governance-level bankruptcy (INNOV-21) is separate: it is triggered by governance debt score, not individual agent balance.

---

## Open Design Questions (Pre-Phase 100)

1. **Should stake compound interest between epochs?** Currently: no. Credits sit idle between proposals.

2. **Should high-stake proposals get higher jury attention?** Currently: CJS triggers on HIGH_STAKES_PATHS (file paths), not stake amount. Future: stake amount could influence jury size.

3. **Should role assignments affect initial balance?** Currently: uniform 100.0. Future: specialized roles could start with lower balance but higher routing priority.

4. **Should failed agents' stakes be redistributed?** Currently: burned (removed from supply). Future: partial redistribution to agents who flagged the mutation as risky.

These are HUMAN-0 decisions for Phase 100 plan ratification.
