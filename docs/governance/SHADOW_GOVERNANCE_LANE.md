# Shadow Governance Lane Specification

## Purpose

The shadow-governance lane is a replay-only promotion control that evaluates candidate governance policy artifacts against fixed historical ledger datasets before a policy can be promoted.

This lane is **non-production and non-authoritative**: it does not mutate runtime state, write governance ledgers, or alter active decision outcomes.

## Admissible policy experiment types

Only the following policy experiments are admissible in this lane:

1. **Threshold tuning**
   - Updates to warning/blocking thresholds under existing policy schema keys.
2. **Weight rebalance**
   - Numeric reweighting of existing risk factor weights without introducing new factors.
3. **Deterministic classifier shape-preserving updates**
   - Candidate logic that keeps the same deterministic input/output contract (`allow` or `block`) and avoids external/non-deterministic data sources.
4. **Replay guardrail refinements**
   - Changes that adjust replay-related gating sensitivity while preserving fail-closed semantics.

Not admissible:

- schema-version jumps for the evaluator input contract,
- introduction of network/clock/random dependencies,
- mutation of production ledgers/state from replay execution,
- experiments that bypass evidence capture.

## Required replay datasets

Every policy-touching PR must evaluate against all required datasets:

- `tests/fixtures/governance/shadow_replay_ledger.json`

Dataset contract (per record):

- `entry_id` (string)
- `features` (object with deterministic numeric inputs)
- `expected_decision` (`allow` or `block`)
- `historical_decision` (`allow` or `block`)

## Pass/fail thresholds

The shadow-governance replay gate is fail-closed and passes only when all thresholds are satisfied:

- `false_allow_rate <= 0.05`
- `false_block_rate <= 0.20`
- `divergence_count <= 3`

Definitions:

- **false allow rate** = count(candidate=`allow` and expected=`block`) / total records
- **false block rate** = count(candidate=`block` and expected=`allow`) / total records
- **divergence count** = count(candidate decision differs from `historical_decision`)

## Explicit non-production constraints

1. Replay-only execution: evaluator may read artifacts and datasets but must not write runtime state.
2. No signing/promotion side effects: passing shadow lane does not activate candidate policy.
3. Deterministic outputs: same inputs must produce byte-stable metrics output.
4. CI mandatory for policy-touching PRs: gate cannot be skipped or downgraded to advisory.
5. Evidence required: promotion remains blocked until claims-evidence row `shadow-governance-validation-complete` is marked complete.
