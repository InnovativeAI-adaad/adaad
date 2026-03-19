# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.api.orchestration import StatusEnvelope
from runtime.evolution.replay_manifest import build_replay_manifest_v1, write_replay_manifest_v1
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
        replay_started_at = now_iso()
        preflight = evolution_runtime.replay_preflight(replay_mode, epoch_id=replay_epoch or None)
        replay_finished_at = now_iso()
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
            "divergence_details": preflight.get("divergence_details", []),
            "diagnostics": preflight.get("fail_closed_payload", {}),
            "replay_score": replay_score,
            "ts": replay_finished_at,
        }
        journal.write_entry(agent_id="system", action="replay_verified", payload=outcome)
        manifest = build_replay_manifest_v1(
            replay_started_at=replay_started_at,
            replay_finished_at=replay_finished_at,
            preflight=preflight,
            halted=has_divergence and replay_mode.fail_closed,
        )
        manifest_path = self.write_replay_manifest(manifest)
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

    def write_replay_manifest(self, manifest: dict[str, Any]) -> Path:
        return write_replay_manifest_v1(manifest, manifests_dir=self.manifests_dir)
