# Phase 107 Plan — INNOV-22: Market-Conditioned Fitness

**Authority:** HUMAN-0 — Dustin L. Reid  
**Target version:** v9.40.0  
**Predecessor:** Phase 106 must be shipped  
**Tests:** T107-MCF-01 through T107-MCF-30 (30 required)

## Objective
Real external signals (github_stars, benchmark_rank, api_latency) injected into fitness scoring. No fitness evaluation is purely synthetic. Signal staleness gate at 3 epochs.

## Scaffold Status
Module already scaffolded in `runtime/innovations30/`. This phase promotes it from scaffold to full constitutional implementation with Hard-class invariants.

## Gate Stack
- Tier 0: Preflight (version hygiene, import contracts)
- Tier 1: Full suite (all existing + 30 new T107 tests)
- Tier 2: Governance artifact validation, evidence matrix row
- Tier 3: CHANGELOG, ROADMAP, agent state update

## pytest.ini Mark
```
"phase107: Phase 107 INNOV-22 [Market-Conditioned Fitness] (MCF) tests"
```

## Evidence Artifacts
```
artifacts/governance/phase107/phase107_sign_off.json
artifacts/governance/phase107/replay_digest.txt
artifacts/governance/phase107/tier_summary.json
artifacts/governance/phase107/identity_ledger_attestation.json
```

## HUMAN-0 Checkpoints
1. Plan ratification — before branch opens
2. Pre-merge — all 30 tests green, gate stack clean
3. Release — signed ILA for v9.40.0

## Commit Format
`feat(phase107): INNOV-22 Market-Conditioned Fitness (MCF) v9.40.0`
