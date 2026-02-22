# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from unittest import mock

from app.orchestration import MutationOrchestrationService
from runtime.boot.preflight import BootPreflightService
from runtime.evolution.replay_mode import ReplayMode
from runtime.evolution.replay_service import ReplayVerificationService


def test_boot_preflight_returns_typed_envelope() -> None:
    service = BootPreflightService()
    with mock.patch("runtime.boot.preflight.run_gatekeeper", return_value={"ok": False, "missing": ["ledger"]}):
        envelope = service.validate_gatekeeper()
    assert envelope.status == "error"
    assert envelope.reason == "gatekeeper_failed:ledger"
    assert envelope.evidence_refs


def test_replay_service_contract_envelope_and_manifest(tmp_path: Path) -> None:
    runtime = mock.Mock()
    runtime.replay_preflight.return_value = {
        "verify_target": "epoch-1",
        "decision": "continue",
        "has_divergence": False,
        "results": [{"replay_score": 1.0}],
    }
    service = ReplayVerificationService(manifests_dir=tmp_path / "replay_manifests")
    with mock.patch("runtime.evolution.replay_service.journal.write_entry"):
        envelope, preflight = service.run_preflight(
            evolution_runtime=runtime,
            replay_mode=ReplayMode.AUDIT,
            replay_epoch="epoch-1",
        )
    assert envelope.status == "ok"
    assert envelope.reason == "replay_verified"
    assert Path(envelope.evidence_refs[0]).exists()
    assert preflight["verify_target"] == "epoch-1"


def test_mutation_orchestration_transition_contract() -> None:
    service = MutationOrchestrationService()
    blocked = service.choose_transition(
        mutation_enabled=True,
        fail_closed=True,
        governance_gate_passed=True,
        exit_after_boot=False,
    )
    assert blocked.reason == "mutation_blocked_fail_closed"
    assert blocked.payload["run_cycle"] is False
