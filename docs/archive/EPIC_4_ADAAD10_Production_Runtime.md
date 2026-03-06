# Epic: ADAAD-10 — Production Runtime Hardening

> **Labels:** `market` `darwinian` `container` `federation` `v1.4`
> **Milestone:** ADAAD-10 Production Runtime
> **Complexity:** Major (4 parallel tracks)
> **Governance impact:** Critical — execution authority surfaces expanded

## Problem Statement

ADAAD-9 delivered a governance-first authoring experience. ADAAD-10 closes the gap
between the governance substrate and production-grade runtime: live economic signals
replace simulated market scores, agents compete for real resource budgets under
evolutionary pressure, mutations execute inside real container isolation, and
federation operates autonomously across nodes without human coordination.

## Tracks

| Track | ID | Title | Files |
|---|---|---|---|
| A | PR-10-01..02 | Live Market Signal Adapters | `runtime/market/` |
| B | PR-10-03..04 | True Darwinian Agent Budget Competition | `runtime/evolution/budget/` |
| C | PR-10-05..06 | Real Container-Level Isolation Backend | `runtime/sandbox/container_orchestrator.py` |
| D | PR-10-07..08 | Fully Autonomous Multi-Node Federation | `runtime/governance/federation/peer_discovery.py`, `consensus.py` |

## Track A — Live Market Signal Adapters

Replace `simulated_market_score` with a real-time adapter pipeline.

- `runtime/market/__init__.py` — market package
- `runtime/market/signal_adapter.py` — `MarketSignalAdapter` protocol + `MarketSignalReading` dataclass
- `runtime/market/feed_registry.py` — `FeedRegistry` with deterministic adapter ordering, TTL caching, fail-closed stale guard
- `runtime/market/adapters/` — concrete adapters: `VolatilityIndexAdapter`, `ResourcePriceAdapter`, `DemandSignalAdapter`
- `runtime/market/market_fitness_integrator.py` — bridges live readings into `EconomicFitnessEvaluator.live_market_score`
- Schema: `schemas/market_signal_reading.v1.json`

## Track B — True Darwinian Agent Budget Competition

Agents compete for a finite shared budget pool. Budget is redistributed based on
fitness scores — high-fitness agents gain allocation, low-fitness agents starve.

- `runtime/evolution/budget/__init__.py`
- `runtime/evolution/budget/pool.py` — `AgentBudgetPool` (frozen total, per-agent shares, append-only allocation ledger)
- `runtime/evolution/budget/arbitrator.py` — `BudgetArbitrator` (Darwinian reallocation: fitness-weighted Softmax, starvation threshold, eviction policy)
- `runtime/evolution/budget/competition_ledger.py` — append-only competition event ledger
- Integration into `runtime/evolution/fitness_orchestrator.py` — post-fitness hook calls arbitrator

## Track C — Real Container-Level Isolation Backend

`ContainerIsolationBackend` exists. This track delivers the orchestration layer:
container pool management, health probes, lifecycle state machine, and makes
`ADAAD_SANDBOX_CONTAINER_ROLLOUT=true` the recommended default.

- `runtime/sandbox/container_orchestrator.py` — `ContainerOrchestrator` (pool, lifecycle, health)
- `runtime/sandbox/container_health.py` — `ContainerHealthProbe` + liveness/readiness checks
- `runtime/sandbox/container_profiles/` — default seccomp, network, write, resource profiles
- Integration: `executor.py` wires orchestrator into `HardenedSandboxExecutor`

## Track D — Fully Autonomous Multi-Node Federation

Current federation is file-based, local-only. This track delivers real peer
discovery, gossip propagation, autonomous Raft-inspired consensus, and
cross-node constitutional enforcement.

- `runtime/governance/federation/peer_discovery.py` — `PeerRegistry` + `GossipProtocol`
- `runtime/governance/federation/consensus.py` — `FederationConsensusEngine` (Raft-inspired: leader election, log replication, constitutional quorum enforcement)
- `runtime/governance/federation/node_supervisor.py` — `FederationNodeSupervisor` (heartbeat, partition detection, autonomous rejoin)
- Integration: `coordination.py` delegates to `ConsensusEngine` for cross-node decisions

## Authority Invariants

- Market adapters are read-only; they influence fitness scoring but cannot approve mutations.
- Budget arbitration is a governance surface; eviction events are journaled and subject to lineage continuity rules.
- Container backend does not expand mutation authority; it hardens the execution surface.
- Federation consensus gates cross-node policy changes through the same constitutional evaluation that governs single-node mutations.
