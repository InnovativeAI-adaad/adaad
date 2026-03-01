# SPDX-License-Identifier: MIT

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


def test_mutation_orchestration_normalizes_empty_and_duplicate_tasks() -> None:
    service = MutationOrchestrationService()
    envelope = service.evaluate_dream_tasks(["", "  ", "task-a", "task-a", " task-b "])

    assert envelope.status == "ok"
    assert envelope.payload["safe_boot"] is False
    assert envelope.payload["task_count"] == 2


def test_mutation_orchestration_warns_when_tasks_collapse_to_empty() -> None:
    service = MutationOrchestrationService()
    envelope = service.evaluate_dream_tasks(["  ", "", "\n"])

    assert envelope.status == "warn"
    assert envelope.reason == "no_tasks"
    assert envelope.payload == {"safe_boot": True}



def test_mutation_orchestration_ignores_non_string_tasks_deterministically() -> None:
    service = MutationOrchestrationService()
    envelope = service.evaluate_dream_tasks(["task-a", 7, None, " task-b "])  # type: ignore[list-item]

    assert envelope.status == "ok"
    assert envelope.payload["safe_boot"] is False
    assert envelope.payload["task_count"] == 2



def test_mutation_orchestration_preserves_first_seen_order_for_large_input() -> None:
    service = MutationOrchestrationService()
    tasks = [f"task-{idx % 10}" for idx in range(200)]

    envelope = service.evaluate_dream_tasks(tasks)

    assert envelope.status == "ok"
    assert envelope.payload["task_count"] == 10


def test_mutation_orchestration_supports_unicode_labels_deterministically() -> None:
    service = MutationOrchestrationService()
    envelope = service.evaluate_dream_tasks([" α ", "β", "α", "β", "γ"])

    assert envelope.status == "ok"
    assert envelope.payload["safe_boot"] is False
    assert envelope.payload["task_count"] == 3



def test_mutation_orchestration_blocked_payload_isolation() -> None:
    service = MutationOrchestrationService()

    first = service.choose_transition(
        mutation_enabled=False,
        fail_closed=False,
        governance_gate_passed=True,
        exit_after_boot=False,
    )
    first.payload["run_cycle"] = True

    second = service.choose_transition(
        mutation_enabled=False,
        fail_closed=False,
        governance_gate_passed=True,
        exit_after_boot=False,
    )
    assert second.payload == {"run_cycle": False}
