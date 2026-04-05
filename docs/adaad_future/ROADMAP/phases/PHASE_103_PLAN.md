# Phase 103 Plan — INNOV-18: Temporal Governance Windows

**Authority:** HUMAN-0 — Dustin L. Reid  
**Target version:** v9.36.0  
**Predecessor:** Phase 102 must be shipped  
**Tests:** T103-TGW-01 through T103-TGW-30 (30 required)

## Objective
Constitutional rules with health-state-dependent severity. When health > 0.85 rules are relaxed. When health < 0.60 rules tighten. Tamper-evident SHA-256 log of every evaluation.

## Scaffold Status
Module already scaffolded in `runtime/innovations30/`. This phase promotes it from scaffold to full constitutional implementation with Hard-class invariants.

## Gate Stack
- Tier 0: Preflight (version hygiene, import contracts)
- Tier 1: Full suite (all existing + 30 new T103 tests)
- Tier 2: Governance artifact validation, evidence matrix row
- Tier 3: CHANGELOG, ROADMAP, agent state update

## pytest.ini Mark
```
"phase103: Phase 103 INNOV-18 [Temporal Governance Windows] (TGW) tests"
```

## Evidence Artifacts
```
artifacts/governance/phase103/phase103_sign_off.json
artifacts/governance/phase103/replay_digest.txt
artifacts/governance/phase103/tier_summary.json
artifacts/governance/phase103/identity_ledger_attestation.json
```

## HUMAN-0 Checkpoints
1. Plan ratification — before branch opens
2. Pre-merge — all 30 tests green, gate stack clean
3. Release — signed ILA for v9.36.0

## Commit Format
`feat(phase103): INNOV-18 Temporal Governance Windows (TGW) v9.36.0`
