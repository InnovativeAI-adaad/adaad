# SPDX-License-Identifier: Apache-2.0
"""Mutation cycle orchestration extracted from app.main."""

from __future__ import annotations

import time
from typing import Any

from runtime.api.runtime_services import (
    determine_tier,
    evaluate_mutation,
    get_forced_tier,
    metrics,
    now_iso,
)
from security.ledger import journal


def run_mutation_cycle(orchestrator: Any) -> None:
    """
    Execute one architect → mutation engine → executor cycle.
    """
    if orchestrator.evolution_runtime.fail_closed:
        metrics.log(event_type="mutation_cycle_blocked", payload={"reason": "replay_fail_closed", "epoch_id": orchestrator.evolution_runtime.current_epoch_id}, level="ERROR")
        return
    hook_before = orchestrator.evolution_runtime.before_mutation_cycle()
    active_epoch_id = hook_before.get("epoch_id")
    epoch_meta = {"epoch_id": active_epoch_id, "epoch_start_ts": orchestrator.evolution_runtime.epoch_start_ts, "epoch_mutation_count": orchestrator.evolution_runtime.epoch_mutation_count}
    proposals = orchestrator.architect.propose_mutations()
    for proposal in proposals:
        proposal.epoch_id = active_epoch_id
    if not proposals:
        metrics.log(event_type="mutation_cycle_skipped", payload={"reason": "no proposals", "epoch_id": active_epoch_id}, level="INFO")
        return
    orchestrator.mutation_engine.refresh_state_from_metrics()
    selected, scores = orchestrator.mutation_engine.select(proposals)
    metrics.log(event_type="mutation_strategy_scores", payload={"scores": scores, **epoch_meta}, level="INFO")
    if not selected:
        metrics.log(event_type="mutation_cycle_skipped", payload={"reason": "no selection", "epoch_id": active_epoch_id}, level="INFO")
        return
    forced_tier = get_forced_tier()
    tier = forced_tier or determine_tier(selected.agent_id)
    if forced_tier is not None:
        metrics.log(
            event_type="mutation_tier_override",
            payload={"agent_id": selected.agent_id, "tier": tier.name},
            level="INFO",
        )
    platform_snapshot = orchestrator.resource_monitor.snapshot()
    eval_wall_start = time.monotonic()
    eval_cpu_start = time.process_time()
    envelope_state = {
        "epoch_id": active_epoch_id,
        "epoch_entropy_bits": int(getattr(orchestrator.evolution_runtime, "epoch_cumulative_entropy_bits", 0) or 0),
        "observed_entropy_bits": 0,
        "platform_telemetry": {
            "battery_percent": round(platform_snapshot.battery_percent, 4),
            "memory_mb": round(platform_snapshot.memory_mb, 4),
            "storage_mb": round(platform_snapshot.storage_mb, 4),
            "cpu_percent": round(platform_snapshot.cpu_percent, 4),
        },
        # Pre-evaluation snapshot for headroom checks: resource_bounds validates
        # platform capacity here, while post-evaluation timing is logged separately.
        "resource_measurements": {
            "wall_seconds": 0.0,
            "cpu_seconds": 0.0,
            "peak_rss_mb": round(platform_snapshot.memory_mb, 4),
        },
    }
    constitutional_verdict = evaluate_mutation(selected, tier, envelope_state=envelope_state)
    eval_wall_elapsed = max(0.0, time.monotonic() - eval_wall_start)
    eval_cpu_elapsed = max(0.0, time.process_time() - eval_cpu_start)
    metrics.log(
        event_type="constitutional_evaluation_resource_measurements",
        payload={
            "epoch_id": active_epoch_id,
            "agent_id": selected.agent_id,
            "wall_seconds": round(eval_wall_elapsed, 6),
            "cpu_seconds": round(eval_cpu_elapsed, 6),
            "peak_rss_mb": round(platform_snapshot.memory_mb, 4),
        },
        level="INFO",
    )
    if not constitutional_verdict.get("passed"):
        entropy_budget_verdict = next(
            (
                item
                for item in constitutional_verdict.get("verdicts", [])
                if isinstance(item, dict) and item.get("rule") == "entropy_budget_limit"
            ),
            {},
        )
        entropy_details = entropy_budget_verdict.get("details") if isinstance(entropy_budget_verdict, dict) else {}
        entropy_details = entropy_details if isinstance(entropy_details, dict) else {}
        if isinstance(entropy_details.get("details"), dict):
            entropy_details = dict(entropy_details["details"])
        if "entropy_budget_limit" in constitutional_verdict.get("blocking_failures", []):
            metrics.log(
                event_type="mutation_rejected_entropy",
                payload={
                    "agent_id": selected.agent_id,
                    "epoch_id": active_epoch_id,
                    "rule": "entropy_budget_limit",
                    "reason": entropy_details.get("reason") or entropy_budget_verdict.get("reason", "entropy_budget_limit"),
                    "max_mutation_entropy_bits": entropy_details.get("max_mutation_entropy_bits"),
                    "epoch_entropy_bits": entropy_details.get("epoch_entropy_bits"),
                    "constitutional_verdict": constitutional_verdict,
                    "evidence": {
                        "rule": "entropy_budget_limit",
                        "details": entropy_details,
                        "blocking_failures": constitutional_verdict.get("blocking_failures", []),
                    },
                },
                level="ERROR",
            )
        metrics.log(
            event_type="mutation_rejected_constitutional",
            payload={**constitutional_verdict, "epoch_id": active_epoch_id, "decision": "rejected", "evidence": constitutional_verdict},
            level="ERROR",
        )
        journal.write_entry(
            agent_id=selected.agent_id,
            action="mutation_rejected_constitutional",
            payload={**constitutional_verdict, "epoch_id": active_epoch_id, "decision": "rejected", "evidence": constitutional_verdict},
        )
        if orchestrator.dry_run:
            bias = orchestrator.mutation_engine.bias_details(selected)
            metrics.log(
                event_type="mutation_dry_run",
                payload={
                    "agent_id": selected.agent_id,
                    "strategy_id": selected.intent or "default",
                    "tier": tier.name,
                    "constitution_version": constitutional_verdict.get("constitution_version"),
                    "constitutional_verdict": constitutional_verdict,
                    "bias": bias,
                    "fitness_score": None,
                    "status": "rejected",
                },
                level="WARN",
            )
            journal.write_entry(
                agent_id=selected.agent_id,
                action="mutation_dry_run",
                payload={
                    "epoch_id": active_epoch_id,
                    "strategy_id": selected.intent or "default",
                    "tier": tier.name,
                    "constitutional_verdict": constitutional_verdict,
                    "bias": bias,
                    "fitness_score": None,
                    "status": "rejected",
                    "ts": now_iso(),
                },
            )
        return
    metrics.log(
        event_type="mutation_approved_constitutional",
        payload={
            "agent_id": selected.agent_id,
            **epoch_meta,
            "tier": tier.name,
            "constitution_version": constitutional_verdict.get("constitution_version"),
            "warnings": constitutional_verdict.get("warnings", []),
        },
        level="INFO",
    )
    if orchestrator.dry_run:
        try:
            fitness_score = orchestrator._simulate_fitness_score(selected)
        except ValueError as exc:
            metrics.log(
                event_type="mutation_dry_run_simulation_rejected",
                payload={
                    "agent_id": selected.agent_id,
                    "epoch_id": active_epoch_id,
                    "strategy_id": selected.intent or "default",
                    "tier": tier.name,
                    "constitution_version": constitutional_verdict.get("constitution_version"),
                    "constitutional_verdict": constitutional_verdict,
                    "reason": str(exc),
                    "decision": "rejected",
                    "evidence": {
                        "rule": "simulation_clone_type_safety",
                        "error": str(exc),
                    },
                },
                level="ERROR",
            )
            journal.write_entry(
                agent_id=selected.agent_id,
                action="mutation_dry_run",
                payload={
                    "epoch_id": active_epoch_id,
                    "strategy_id": selected.intent or "default",
                    "tier": tier.name,
                    "constitutional_verdict": constitutional_verdict,
                    "fitness_score": None,
                    "status": "rejected",
                    "reason": str(exc),
                    "ts": now_iso(),
                },
            )
            return
        bias = orchestrator.mutation_engine.bias_details(selected)
        metrics.log(
            event_type="mutation_dry_run",
            payload={
                "agent_id": selected.agent_id,
                "epoch_id": active_epoch_id,
                "strategy_id": selected.intent or "default",
                "tier": tier.name,
                "constitution_version": constitutional_verdict.get("constitution_version"),
                "constitutional_verdict": constitutional_verdict,
                "bias": bias,
                "fitness_score": fitness_score,
                "status": "approved",
            },
            level="INFO",
        )
        journal.write_entry(
            agent_id=selected.agent_id,
            action="mutation_dry_run",
            payload={
                "epoch_id": active_epoch_id,
                "strategy_id": selected.intent or "default",
                "tier": tier.name,
                "constitutional_verdict": constitutional_verdict,
                "bias": bias,
                "fitness_score": fitness_score,
                "status": "approved",
                "ts": now_iso(),
            },
        )
        return

    result = orchestrator.executor.execute(selected)
    journal.write_entry(
        agent_id=selected.agent_id,
        action="mutation_cycle",
        payload={
            "result": result,
            "constitutional_verdict": constitutional_verdict,
            "epoch_id": active_epoch_id,
            "epoch_start_ts": orchestrator.evolution_runtime.epoch_start_ts,
            "epoch_mutation_count": orchestrator.evolution_runtime.epoch_mutation_count,
            "replay": result.get("evolution", {}).get("replay", {}),
            "ts": now_iso(),
        },
    )
