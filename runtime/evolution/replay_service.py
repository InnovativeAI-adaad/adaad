# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runtime.api.orchestration import StatusEnvelope
from runtime.timeutils import now_iso
from security.ledger import journal


class ReplayVerificationService:
    def __init__(self, *, manifests_dir: Path) -> None:
        self.manifests_dir = manifests_dir

    def run_preflight(
        self,
        *,
        evolution_runtime: Any,
        replay_mode: Any,
        replay_epoch: str,
        verify_only: bool = False,
    ) -> tuple[StatusEnvelope, dict[str, Any]]:
        preflight = evolution_runtime.replay_preflight(replay_mode, epoch_id=replay_epoch or None)
        has_divergence = bool(preflight.get("has_divergence"))
        replay_score = self._aggregate_replay_score(preflight.get("results", []))
        outcome = {
            "mode": replay_mode.value,
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
        manifest_path = self.write_replay_manifest(outcome)
        evidence_refs = (manifest_path.as_posix(),)
        status = "error" if has_divergence and replay_mode.fail_closed else ("warn" if has_divergence else "ok")
        reason = "replay_divergence" if has_divergence else "replay_verified"
        envelope = StatusEnvelope(status=status, reason=reason, evidence_refs=evidence_refs, payload=outcome)
        return envelope, preflight

    @staticmethod
    def _aggregate_replay_score(results: list[dict[str, Any]]) -> float:
        if not results:
            return 1.0
        scores = [float(result.get("replay_score", 0.0)) for result in results]
        return round(sum(scores) / len(scores), 4)

    def write_replay_manifest(self, outcome: dict[str, Any]) -> Path:
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

        def _sanitize_component(value: Any) -> str:
            normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "unknown")).strip("-._")
            return normalized or "unknown"

        mode_component = _sanitize_component(outcome.get("mode"))
        target_component = _sanitize_component(outcome.get("target"))
        timestamp_component = _sanitize_component(outcome.get("ts"))
        manifest_path = self.manifests_dir / f"{mode_component}__{target_component}__{timestamp_component}.json"
        manifest_path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest_path
