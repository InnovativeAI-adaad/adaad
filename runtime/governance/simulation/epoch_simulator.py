# SPDX-License-Identifier: Apache-2.0
"""Epoch Replay Simulator — ADAAD-8 / Policy Simulation Mode

Replays historical epochs under a SimulationPolicy and returns per-epoch
simulation results. Operates as a read-only substrate over the existing
ReplayEngine — no ledger writes, no constitution state transitions, no
mutation executor calls occur during any simulation run.

Isolation invariant: SimulationPolicy.simulation must be True at the point of
simulator construction. The simulator checks this before any epoch evaluation.
No simulated constraint can reach a live governance surface.

Scoring version binding: simulation binds to the scoring_algorithm_version
recorded in each replayed epoch when evaluating risk/fitness-dependent
constraints.

Determinism guarantee: identical ledger slice + identical SimulationPolicy +
identical epoch-scoped scoring versions → identical EpochSimulationResult
objects.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Mapping, Optional, Sequence

from runtime.governance.simulation.constraint_interpreter import (
    SimulationPolicy,
    SimulationPolicyError,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EpochSimulationResult:
    """Per-epoch simulation result.

    All fields are deterministic given the same ledger slice, SimulationPolicy,
    and epoch-scoped scoring versions.
    """
    epoch_id: str
    actual_mutations_advanced: int       # mutations advanced in live history
    simulated_mutations_advanced: int    # mutations that would pass under SimulationPolicy
    blocked_by_simulation: List[str]     # mutation IDs gated under hypothetical policy
    velocity_delta_pct: float            # (simulated − actual) / actual × 100; 0.0 if actual=0
    drift_risk_delta: float              # drift risk delta under simulation (heuristic)
    governance_health_score: float       # composite [0.0, 1.0] for this epoch under simulation
    scoring_algorithm_version: str       # version bound from epoch record

    def to_dict(self) -> Dict[str, Any]:
        d = dict(asdict(self))
        d["blocked_by_simulation"] = list(self.blocked_by_simulation)
        return d


@dataclass(frozen=True)
class SimulationRunResult:
    """Aggregate result for a complete simulation run across all evaluated epochs."""
    simulation: bool              # always True
    epoch_count: int
    total_mutations_actual: int
    total_mutations_simulated: int
    total_mutations_blocked: int
    velocity_impact_pct: float    # mean velocity delta across epochs
    drift_risk_delta_mean: float  # mean drift risk delta across epochs
    governance_health_score_mean: float
    epoch_results: List[EpochSimulationResult]
    policy_digest: str            # SHA-256 of serialised policy — for determinism checks
    run_digest: str               # SHA-256 of serialised results — for determinism checks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation": self.simulation,
            "epoch_count": self.epoch_count,
            "total_mutations_actual": self.total_mutations_actual,
            "total_mutations_simulated": self.total_mutations_simulated,
            "total_mutations_blocked": self.total_mutations_blocked,
            "velocity_impact_pct": self.velocity_impact_pct,
            "drift_risk_delta_mean": self.drift_risk_delta_mean,
            "governance_health_score_mean": self.governance_health_score_mean,
            "policy_digest": self.policy_digest,
            "run_digest": self.run_digest,
            "epoch_results": [r.to_dict() for r in self.epoch_results],
        }


# ---------------------------------------------------------------------------
# Isolation-checked base
# ---------------------------------------------------------------------------

class SimulationIsolationError(Exception):
    """Raised when a simulation operation would reach a live governance surface."""


def _assert_simulation_flag(policy: SimulationPolicy) -> None:
    """Raise SimulationIsolationError if policy.simulation is not True.

    This check is the GovernanceGate boundary equivalent for the simulator.
    It enforces that SimulationPolicy objects can never reach live governance
    state by verifying the structural flag before any evaluation begins.
    """
    if not policy.simulation:
        raise SimulationIsolationError(
            "SimulationPolicy.simulation must be True. "
            "Simulation must not reach live governance surfaces."
        )


# ---------------------------------------------------------------------------
# Constraint evaluation helpers
# ---------------------------------------------------------------------------

def _evaluate_mutation_under_policy(
    mutation: Dict[str, Any],
    policy: SimulationPolicy,
) -> tuple[bool, str]:
    """Return (passes, reason) for a single mutation under a SimulationPolicy.

    This is a pure function — no side effects, no ledger writes.
    Constraints are checked in deterministic order.
    """
    mutation_id = str(mutation.get("mutation_id", mutation.get("id", "unknown")))
    risk_score = float(mutation.get("risk_score", 0.0))
    complexity_delta = float(mutation.get("complexity_delta", 0.0))
    lineage_depth = int(mutation.get("lineage_depth", 0))
    test_coverage = float(mutation.get("test_coverage", 1.0))
    tier = str(mutation.get("tier", ""))
    entropy = float(mutation.get("entropy", 0.0))

    # 1. Max risk score
    if policy.max_risk_score is not None and risk_score > policy.max_risk_score:
        return False, f"risk_score={risk_score:.3f} exceeds max_risk_score={policy.max_risk_score:.3f}"

    # 2. Max complexity delta
    if policy.max_complexity_delta is not None and complexity_delta > policy.max_complexity_delta:
        return False, f"complexity_delta={complexity_delta:.3f} exceeds max_complexity_delta={policy.max_complexity_delta:.3f}"

    # 3. Min test coverage
    if policy.min_test_coverage is not None and test_coverage < policy.min_test_coverage:
        return False, f"test_coverage={test_coverage:.3f} below min_test_coverage={policy.min_test_coverage:.3f}"

    # 4. Freeze tier
    if tier and policy.is_tier_frozen(tier):
        return False, f"tier={tier!r} is frozen under simulation policy"

    # 5. Require lineage depth
    if policy.require_lineage_depth is not None and lineage_depth < policy.require_lineage_depth:
        return False, f"lineage_depth={lineage_depth} below require_lineage_depth={policy.require_lineage_depth}"

    # 6. Escalate reviewers on risk (this constraint doesn't block — it flags; treated as pass)
    # Reviewer escalation is calibration telemetry, not a gate.

    return True, "pass"


def _evaluate_epoch_under_policy(
    epoch_data: Dict[str, Any],
    policy: SimulationPolicy,
    actual_mutations_advanced: int,
) -> EpochSimulationResult:
    """Evaluate a single epoch's mutation records under a SimulationPolicy.

    Pure function — no side effects.
    """
    epoch_id = str(epoch_data.get("epoch_id", "unknown"))
    scoring_version = str(epoch_data.get("scoring_algorithm_version", "unknown"))
    mutations = list(epoch_data.get("mutations", []))

    # Apply epoch-level ceiling first
    candidate_mutations = mutations
    if policy.max_mutations_per_epoch is not None:
        candidate_mutations = mutations[: policy.max_mutations_per_epoch]

    blocked: List[str] = []
    simulated_advanced = 0

    for mutation in candidate_mutations:
        passes, _reason = _evaluate_mutation_under_policy(mutation, policy)
        if passes:
            simulated_advanced += 1
        else:
            blocked.append(str(mutation.get("mutation_id", mutation.get("id", "unknown"))))

    # Entropy constraint — epoch-level
    epoch_entropy = float(epoch_data.get("entropy", 0.0))
    if policy.max_entropy_per_epoch is not None and epoch_entropy > policy.max_entropy_per_epoch:
        # Block all remaining un-blocked mutations in this epoch
        additional_blocked = [
            str(m.get("mutation_id", m.get("id", "unknown")))
            for m in candidate_mutations
            if str(m.get("mutation_id", m.get("id", "unknown"))) not in blocked
        ]
        blocked.extend(additional_blocked)
        simulated_advanced = max(0, simulated_advanced - len(additional_blocked))

    # Velocity delta
    if actual_mutations_advanced > 0:
        velocity_delta_pct = ((simulated_advanced - actual_mutations_advanced) / actual_mutations_advanced) * 100.0
    else:
        velocity_delta_pct = 0.0

    # Drift risk delta (heuristic: proportion of mutations blocked)
    total_evaluated = len(candidate_mutations)
    blocked_pct = len(blocked) / total_evaluated if total_evaluated > 0 else 0.0
    drift_risk_delta = round(blocked_pct * 0.5, 4)  # bounded heuristic

    # Governance health score (heuristic: inverse of block rate, clamped to [0, 1])
    governance_health_score = round(max(0.0, 1.0 - blocked_pct), 4)

    return EpochSimulationResult(
        epoch_id=epoch_id,
        actual_mutations_advanced=actual_mutations_advanced,
        simulated_mutations_advanced=simulated_advanced,
        blocked_by_simulation=list(blocked),
        velocity_delta_pct=round(velocity_delta_pct, 4),
        drift_risk_delta=drift_risk_delta,
        governance_health_score=governance_health_score,
        scoring_algorithm_version=scoring_version,
    )


# ---------------------------------------------------------------------------
# Policy digest
# ---------------------------------------------------------------------------

def _compute_policy_digest(policy: SimulationPolicy) -> str:
    serialised = json.dumps(policy.to_dict(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialised.encode()).hexdigest()


def _compute_run_digest(epoch_results: List[EpochSimulationResult]) -> str:
    payload = json.dumps(
        [r.to_dict() for r in epoch_results],
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# EpochReplaySimulator
# ---------------------------------------------------------------------------

class EpochReplaySimulator:
    """Read-only epoch replay simulator.

    Integrates with the existing ReplayEngine as a read-only substrate.
    Applies a SimulationPolicy to historical epoch data and returns
    structured simulation results per epoch.

    Isolation invariant: SimulationPolicy.simulation must be True at
    construction. If a live (simulation=False) policy is passed, construction
    raises SimulationIsolationError.

    No ledger writes, constitution state transitions, or mutation executor
    calls occur during any simulation run.
    """

    def __init__(
        self,
        policy: SimulationPolicy,
        replay_engine: Any = None,   # ReplayEngine | None — optional for unit tests
    ) -> None:
        _assert_simulation_flag(policy)
        self._policy = policy
        self._replay_engine = replay_engine

    @property
    def policy(self) -> SimulationPolicy:
        return self._policy

    def simulate_epoch(
        self,
        epoch_id: str,
        epoch_data: Optional[Dict[str, Any]] = None,
    ) -> EpochSimulationResult:
        """Simulate a single epoch under the policy.

        Args:
            epoch_id: The epoch identifier.
            epoch_data: Pre-fetched epoch data dict (for testing / offline use).
                If None and a replay_engine was provided, the engine is used to
                reconstruct the epoch. If both are absent, returns a zero-state result.

        Returns:
            EpochSimulationResult — deterministic given the same inputs.
        """
        _assert_simulation_flag(self._policy)

        if epoch_data is None and self._replay_engine is not None:
            try:
                epoch_data = self._replay_engine.reconstruct_epoch(epoch_id)
            except Exception:
                epoch_data = {}

        if epoch_data is None:
            epoch_data = {}

        epoch_data.setdefault("epoch_id", epoch_id)
        actual_advanced = int(epoch_data.get("actual_mutations_advanced", len(epoch_data.get("mutations", []))))

        return _evaluate_epoch_under_policy(epoch_data, self._policy, actual_advanced)

    def simulate_epoch_range(
        self,
        epoch_ids: Sequence[str],
        epoch_data_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> SimulationRunResult:
        """Simulate a range of epochs under the policy.

        Args:
            epoch_ids: Ordered sequence of epoch identifiers to simulate.
            epoch_data_map: Optional pre-fetched {epoch_id: epoch_data} dict.
                Epochs not in the map are reconstructed via replay_engine if present,
                otherwise treated as empty epochs.

        Returns:
            SimulationRunResult — deterministic given the same inputs.
        """
        _assert_simulation_flag(self._policy)

        results: List[EpochSimulationResult] = []

        for epoch_id in epoch_ids:
            ep_data = (epoch_data_map or {}).get(epoch_id)
            result = self.simulate_epoch(epoch_id, epoch_data=ep_data)
            results.append(result)

        total_actual = sum(r.actual_mutations_advanced for r in results)
        total_simulated = sum(r.simulated_mutations_advanced for r in results)
        total_blocked = sum(len(r.blocked_by_simulation) for r in results)

        n = len(results)
        velocity_impact_pct = sum(r.velocity_delta_pct for r in results) / n if n > 0 else 0.0
        drift_mean = sum(r.drift_risk_delta for r in results) / n if n > 0 else 0.0
        health_mean = sum(r.governance_health_score for r in results) / n if n > 0 else 1.0

        policy_digest = _compute_policy_digest(self._policy)
        run_digest = _compute_run_digest(results)

        return SimulationRunResult(
            simulation=True,
            epoch_count=n,
            total_mutations_actual=total_actual,
            total_mutations_simulated=total_simulated,
            total_mutations_blocked=total_blocked,
            velocity_impact_pct=round(velocity_impact_pct, 4),
            drift_risk_delta_mean=round(drift_mean, 4),
            governance_health_score_mean=round(health_mean, 4),
            epoch_results=list(results),
            policy_digest=policy_digest,
            run_digest=run_digest,
        )


__all__ = [
    "EpochSimulationResult",
    "SimulationRunResult",
    "SimulationIsolationError",
    "EpochReplaySimulator",
    "build_innovation_forecast",
]


def build_innovation_forecast(
    events: Sequence[Mapping[str, Any]],
    horizon_epochs: int,
    seed_input: str = "vision-default",
) -> Dict[str, Any]:
    """Build deterministic innovation forecast envelopes over a bounded horizon.

    This helper is intentionally pure and replayable so Vision Mode can consume
    scenario trajectories without touching live governance state.
    """
    horizon = max(50, min(int(horizon_epochs), 200))
    ordered_events = sorted(
        [dict(e) for e in events],
        key=lambda row: (
            str(row.get("epoch_id", "")),
            str(row.get("path", "")),
            str(row.get("capability", "")),
            str(row.get("agent_id", "")),
        ),
    )
    capability_deltas: Dict[str, float] = {}
    dead_end_causes: Dict[str, str] = {}
    total_delta = 0.0
    for row in ordered_events:
        capability = str(row.get("capability", "")).strip()
        delta = float(row.get("fitness_delta", 0.0))
        if capability:
            capability_deltas[capability] = round(capability_deltas.get(capability, 0.0) + delta, 6)
        total_delta += delta
        if bool(row.get("dead_end", False)):
            path_id = str(row.get("path", "unknown"))
            dead_end_causes[path_id] = str(row.get("blocking_cause", row.get("status_reason", "unknown_cause")))

    base_score = total_delta / max(1, len(ordered_events))
    bands = {
        "best": round(base_score * 1.2, 6),
        "base": round(base_score, 6),
        "worst": round(base_score * 0.8, 6),
    }
    digest_payload = json.dumps(
        {
            "seed_input": seed_input,
            "horizon_epochs": horizon,
            "ordered_events": ordered_events,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    input_digest = "sha256:" + hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
    coverage = round(min(1.0, len(ordered_events) / max(1, horizon)), 6)
    confidence = round(min(1.0, 0.35 + (coverage * 0.65)), 6)
    return {
        "horizon_epochs": horizon,
        "capability_graph_deltas": [
            {"capability": key, "fitness_delta_sum": capability_deltas[key]}
            for key in sorted(capability_deltas)
        ],
        "trajectory_bands": bands,
        "dead_end_paths": [
            {"path_id": key, "blocking_cause": dead_end_causes[key]}
            for key in sorted(dead_end_causes)
        ],
        "confidence_metadata": {
            "input_digest": input_digest,
            "event_window": len(ordered_events),
            "seed_input": seed_input,
            "coverage_ratio": coverage,
            "confidence_score": confidence,
            "replayable": True,
        },
    }
