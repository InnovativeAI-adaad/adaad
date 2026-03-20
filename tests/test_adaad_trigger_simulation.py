# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.orchestration.adaad_trigger import AdaadTriggerOrchestrator, LedgerSchemaError, VirtualLedgerWriter, parse_trigger

pytestmark = pytest.mark.regression_standard


class RecordingGitAdapter:
    def __init__(self) -> None:
        self.stage_calls = 0
        self.merge_calls = 0

    def stage(self, *, simulation: bool) -> dict[str, object]:
        self.stage_calls += 1
        return {"status": "executed" if not simulation else "skipped", "simulation": simulation, "operation": "git_add"}

    def merge(self, *, simulation: bool) -> dict[str, object]:
        self.merge_calls += 1
        return {"status": "noop" if not simulation else "skipped", "simulation": simulation, "operation": "git_merge"}


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
    assert envelope["status"] == "blocked"
    assert envelope["decision"]["evaluated"] is True
    assert envelope["decision"]["allow_git_mutations"] is False
    assert envelope["decision"]["mutation_kind"] == "simulated"
    assert envelope["stage_result"] == {
        "status": "skipped",
        "reason": "blocked",
        "simulation": True,
        "operation": "git_add",
    }
    assert envelope["merge_result"] == {
        "status": "skipped",
        "reason": "blocked",
        "simulation": True,
        "operation": "git_merge",
    }
    assert "simulation=true" in envelope["output"]
    assert "Decision: deny" in envelope["output"]
    assert "Repository mutation: not_mutated" in envelope["output"]
    assert "tier_0:" in envelope["output"]


def test_non_simulation_mode_can_execute_stage_operation(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")

    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)
    envelope = orchestrator.run("ADAAD", scenario="merge_ready")

    assert envelope["simulation"] is False
    assert envelope["decision"]["allow_git_mutations"] is True
    assert envelope["decision"]["mutated_repository_state"] is True
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


def test_run_blocks_git_mutations_for_tier1_failure(tmp_path: Path) -> None:
    git_adapter = RecordingGitAdapter()
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path, git_mutation_adapter=git_adapter)

    envelope = orchestrator.run("ADAAD", scenario="tier1_failure")

    assert envelope["status"] == "blocked"
    assert envelope["blocked_reason"] == "tier_1_failed"
    assert envelope["decision"]["all_required_gates_passed"] is False
    assert envelope["decision"]["allow_git_mutations"] is False
    assert envelope["decision"]["evaluated_gates"]["tier_1"]["passed"] is False
    assert envelope["stage_result"] == {
        "status": "skipped",
        "reason": "blocked",
        "simulation": False,
        "operation": "git_add",
    }
    assert envelope["merge_result"] == {
        "status": "skipped",
        "reason": "blocked",
        "simulation": False,
        "operation": "git_merge",
    }
    assert git_adapter.stage_calls == 0
    assert git_adapter.merge_calls == 0
    assert "Decision: deny" in envelope["output"]
    assert "Repository mutation: not_mutated" in envelope["output"]


def test_devadaad_merge_ready_requires_verified_sha_replay_context(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)

    envelope = orchestrator.run("DEVADAAD", scenario="merge_ready")

    assert envelope["status"] == "ready"
    assert envelope["decision"]["allow_git_mutations"] is True
    assert envelope["decision"]["mutated_repository_state"] is True
    assert envelope["replay_gate_pass"] is True
    assert envelope["replay_verification"]["verified_sha"] == "sha-verified-0001"
    assert "replay_verified_sha_context: PASS" in envelope["output"]


def test_run_blocks_git_mutations_for_replay_divergence(tmp_path: Path) -> None:
    git_adapter = RecordingGitAdapter()
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path, git_mutation_adapter=git_adapter)

    envelope = orchestrator.run("DEVADAAD", scenario="replay_diverged")

    assert envelope["status"] == "blocked"
    assert envelope["replay_gate_pass"] is False
    assert envelope["blocked_reason"] == "replay_divergence_detected"
    assert envelope["decision"]["all_required_gates_passed"] is False
    assert envelope["decision"]["allow_git_mutations"] is False
    assert envelope["decision"]["evaluated_gates"]["tier_m"]["passed"] is False
    assert envelope["stage_result"] == {
        "status": "skipped",
        "reason": "blocked",
        "simulation": False,
        "operation": "git_add",
    }
    assert envelope["merge_result"] == {
        "status": "skipped",
        "reason": "blocked",
        "simulation": False,
        "operation": "git_merge",
    }
    assert git_adapter.stage_calls == 0
    assert git_adapter.merge_calls == 0
    assert "replay_verified_sha_context: FAIL" in envelope["output"]
    assert "Decision: deny" in envelope["output"]
    assert "Repository mutation: not_mutated" in envelope["output"]


def test_run_marks_successful_simulation_as_evaluated_without_repository_mutation(tmp_path: Path) -> None:
    git_adapter = RecordingGitAdapter()
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path, git_mutation_adapter=git_adapter)

    envelope = orchestrator.run("ADAAD simulate", scenario="merge_ready")

    assert envelope["status"] == "ready"
    assert envelope["simulation"] is True
    assert envelope["decision"] == {
        "status": "ready",
        "blocked_reason": None,
        "all_required_gates_passed": True,
        "allow_git_mutations": True,
        "evaluated": True,
        "evaluated_gates": {
            "tier_0": {"scenario_pass": True, "gate_pass": True, "passed": True},
            "tier_1": {"scenario_pass": True, "gate_pass": True, "passed": True},
            "tier_3": {"scenario_pass": True, "gate_pass": True, "passed": True},
        },
        "mutation_kind": "simulated",
        "mutated_repository_state": False,
    }
    assert envelope["stage_result"] == {"status": "skipped", "simulation": True, "operation": "git_add"}
    assert envelope["merge_result"] == {"status": "skipped", "simulation": True, "operation": "git_merge"}
    assert git_adapter.stage_calls == 1
    assert git_adapter.merge_calls == 1
    assert "Decision: allow" in envelope["output"]
    assert "Repository mutation: not_mutated" in envelope["output"]
