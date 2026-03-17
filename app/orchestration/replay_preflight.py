# SPDX-License-Identifier: Apache-2.0
"""Replay preflight orchestration extracted from app.main."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict

from app import APP_ROOT
from runtime.api.runtime_services import dump, metrics, now_iso
from runtime.evolution.replay_divergence_artifacts import build_replay_divergence_artifacts
from security.ledger import journal


def aggregate_replay_score(results: list[Dict[str, Any]]) -> float:
    if not results:
        return 1.0
    scores = [float(result.get("replay_score", 0.0)) for result in results]
    return round(sum(scores) / len(scores), 4)


def write_replay_manifest(outcome: Dict[str, Any]) -> str:
    manifests_dir = APP_ROOT.parent / "security" / "replay_manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_component(value: Any) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "unknown")).strip("-._")
        return normalized or "unknown"

    mode_component = _sanitize_component(outcome.get("mode"))
    target_component = _sanitize_component(outcome.get("target"))
    timestamp_component = _sanitize_component(outcome.get("ts"))
    manifest_path = manifests_dir / f"{mode_component}__{target_component}__{timestamp_component}.json"
    manifest_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(manifest_path)


def execute_replay_preflight(
    orchestrator: Any,
    dump_func: Any,
    *,
    verify_only: bool = False,
    replay_env_flags: Callable[[], Dict[str, str]],
) -> Dict[str, Any]:
    mode = orchestrator.replay_mode
    preflight = orchestrator.evolution_runtime.replay_preflight(mode, epoch_id=orchestrator.replay_epoch or None)
    has_divergence = bool(preflight.get("has_divergence"))
    orchestrator.state["replay_mode"] = mode.value
    orchestrator.state["replay_target"] = preflight.get("verify_target")
    orchestrator.state["replay_decision"] = preflight.get("decision")
    orchestrator.state["replay_results"] = preflight.get("results", [])
    orchestrator.state["replay_divergence"] = has_divergence
    orchestrator.state["status"] = "replay_warning" if has_divergence else "replay_verified"
    replay_score = aggregate_replay_score(preflight.get("results", []))
    orchestrator.state["replay_score"] = replay_score
    outcome = {
        "mode": mode.value,
        "verify_only": verify_only,
        "ok": not has_divergence,
        "decision": preflight.get("decision"),
        "target": preflight.get("verify_target"),
        "divergence": has_divergence,
        "results": preflight.get("results", []),
        "replay_score": replay_score,
        "ts": now_iso(),
    }
    journal.write_entry(agent_id="system", action="replay_verified", payload=outcome)
    try:
        manifest_path = write_replay_manifest(outcome)
        orchestrator._v(f"Replay manifest written: {manifest_path}")
    except Exception as exc:
        metrics.log(
            event_type="replay_manifest_write_failed",
            payload={"error": str(exc), "mode": outcome["mode"], "target": outcome.get("target")},
            level="WARN",
        )
    if has_divergence:
        replay_command = f"python -m app.main --verify-replay --replay {mode.value}"
        if orchestrator.replay_epoch:
            replay_command += f" --replay-epoch {orchestrator.replay_epoch}"
        try:
            bundle = build_replay_divergence_artifacts(
                preflight=preflight,
                replay_command=replay_command,
                replay_env_flags=replay_env_flags(),
                ledger=orchestrator.evolution_runtime.ledger,
                artifacts_root=APP_ROOT.parent / "security" / "replay_artifacts",
            )
            outcome["divergence_artifacts"] = {
                "artifact_dir": bundle.artifact_dir,
                "machine_report": bundle.machine_report_path,
                "human_report": bundle.human_report_path,
            }
            orchestrator._v("Replay divergence artifacts:")
            orchestrator._v(f"  Dir: {bundle.artifact_dir}")
            orchestrator._v(f"  JSON: {bundle.machine_report_path}")
            orchestrator._v(f"  MD: {bundle.human_report_path}")
        except Exception as exc:
            metrics.log(
                event_type="replay_divergence_artifact_failed",
                payload={"error": str(exc), "mode": outcome["mode"], "target": outcome.get("target")},
                level="WARN",
            )
    if has_divergence and mode.fail_closed:
        orchestrator._fail("replay_divergence", payload={"artifacts": outcome.get("divergence_artifacts") or {}})
    orchestrator._v("Replay Summary:")
    orchestrator._v(f"  Mode: {mode.value}")
    orchestrator._v(f"  Target: {preflight.get('verify_target')}")
    orchestrator._v(f"  Divergence: {has_divergence}")
    orchestrator._v(f"  Score: {replay_score}")
    if verify_only:
        dump_func()
        return {"verify_only": True, **outcome}
    return {"verify_only": False, **outcome}
