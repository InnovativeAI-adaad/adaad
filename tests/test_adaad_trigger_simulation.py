# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.orchestration.adaad_trigger import AdaadTriggerOrchestrator, LedgerSchemaError, VirtualLedgerWriter, parse_trigger

pytestmark = pytest.mark.regression_standard


class RecordingGitAdapter:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def stage(self, *, simulation: bool) -> dict[str, object]:
        self.operations.append("stage")
        return {"status": "executed", "simulation": simulation, "operation": "git_add"}

    def merge(self, *, simulation: bool) -> dict[str, object]:
        self.operations.append("merge")
        return {"status": "executed", "simulation": simulation, "operation": "git_merge"}


class FailingAttestationLedger(VirtualLedgerWriter):
    def write_event(self, event):  # type: ignore[override]
        if event.get("event_type") == "merge_attestation.v1":
            raise RuntimeError("ledger_append_failed")
        return super().write_event(event)


def test_parse_trigger_supports_simulation_action() -> None:
    request = parse_trigger("ADAAD simulate")

    assert request.principal == "ADAAD"
    assert request.action == "simulate"
    assert request.simulation is True
    assert request.merge_authority is False


def test_virtual_ledger_writer_validates_required_schema_keys() -> None:
    ledger = VirtualLedgerWriter()

    with pytest.raises(LedgerSchemaError, match="ledger_schema_missing"):
        ledger.write_event({"event_type": "x"})


def test_simulation_mode_preserves_formatting_and_disables_mutations(tmp_path: Path) -> None:
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)

    envelope = orchestrator.run("ADAAD simulate", scenario="dependency_blocked")

    assert envelope["simulation"] is True
    assert envelope["stage_result"]["status"] == "skipped"
    assert envelope["merge_result"]["status"] == "skipped"
    assert "simulation=true" in envelope["output"]
    assert "tier_0:" in envelope["output"]


def test_non_simulation_mode_can_execute_stage_operation(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")

    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)
    envelope = orchestrator.run("ADAAD", scenario="merge_ready")

    assert envelope["simulation"] is False
    assert envelope["stage_result"]["status"] == "executed"


def test_end_to_end_simulation_never_mutates_git_state(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=tmp_path, check=True, capture_output=True, text=True)

    pre_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    pre_status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout

    script = Path(__file__).resolve().parents[1] / "scripts" / "run_adaad_trigger.py"
    subprocess.run(
        ["python", str(script), "ADAAD simulate", "--scenario", "tier1_failure"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    post_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    post_status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout

    assert pre_head == post_head
    assert pre_status == post_status == ""


def test_devadaad_merge_ready_requires_verified_sha_replay_context(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")
    ledger = VirtualLedgerWriter()
    git_adapter = RecordingGitAdapter()
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path, ledger_writer=ledger, git_mutation_adapter=git_adapter)

    envelope = orchestrator.run("DEVADAAD", scenario="merge_ready")

    assert envelope["status"] == "ready"
    assert envelope["replay_gate_pass"] is True
    assert envelope["replay_verification"]["verified_sha"] == "c" * 40
    assert envelope["merge_attestation"]["event"]["event_type"] == "merge_attestation.v1"
    assert envelope["merge_attestation"]["event"]["payload"]["pr_id"] == "PR-PHASE65-01"
    assert ledger.events[-1]["event_type"] == "merge_attestation.v1"
    assert git_adapter.operations == ["stage", "merge"]
    assert "replay_verified_sha_context: PASS" in envelope["output"]
    assert "merge_attestation: PASS" in envelope["output"]


def test_devadaad_replay_divergence_blocks_merge(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)

    envelope = orchestrator.run("DEVADAAD", scenario="replay_diverged")

    assert envelope["status"] == "blocked"
    assert envelope["replay_gate_pass"] is False
    assert envelope["blocked_reason"] == "replay_divergence_detected"
    assert "replay_verified_sha_context: FAIL" in envelope["output"]


def test_devadaad_merge_is_blocked_when_attestation_write_fails(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")
    git_adapter = RecordingGitAdapter()
    orchestrator = AdaadTriggerOrchestrator(
        repo_root=tmp_path,
        ledger_writer=FailingAttestationLedger(),
        git_mutation_adapter=git_adapter,
    )

    envelope = orchestrator.run("DEVADAAD", scenario="merge_ready")

    assert envelope["status"] == "blocked"
    assert envelope["blocked_reason"] == "attestation_write_failed"
    assert envelope["merge_attestation"] is None
    assert envelope["merge_result"]["status"] == "blocked"
    assert git_adapter.operations == ["stage"]
    assert "merge_attestation: FAIL" in envelope["output"]
