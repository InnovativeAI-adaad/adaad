# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.orchestration.adaad_trigger import AdaadTriggerOrchestrator, LedgerSchemaError, VirtualLedgerWriter, parse_trigger

pytestmark = pytest.mark.regression_standard


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
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)

    envelope = orchestrator.run("DEVADAAD simulate", scenario="merge_ready")

    assert envelope["status"] == "ready"
    assert envelope["replay_gate_pass"] is True
    assert envelope["replay_verification"]["verified_sha"] == "sha-verified-0001"
    assert envelope["merge_target_sha"] == "sha-verified-0001"
    assert envelope["merge_target_matches_verified_sha"] is True
    assert "replay_verified_sha_context: PASS" in envelope["output"]
    assert "merge_target_matches_verified_sha: PASS" in envelope["output"]


def test_devadaad_executes_real_merge_pinned_to_verified_sha(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=tmp_path, check=True)
    (tmp_path / "demo.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "demo.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("feature\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "feature"], cwd=tmp_path, check=True, capture_output=True, text=True)
    verified_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, check=True, capture_output=True, text=True)

    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)
    envelope = orchestrator.run(
        "DEVADAAD",
        scenario="merge_ready",
        replay_verification={
            "manifest_path": "security/replay_manifests/verified-sha.replay_manifest.v1.json",
            "bundle_digest": "sha256:" + ("d" * 64),
            "verification_result": "pass",
            "verified_sha": verified_sha,
            "merge_target_sha": verified_sha,
            "schema_valid": True,
            "signature_valid": True,
            "divergence": False,
        },
    )

    merge_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    merge_parents = subprocess.run(
        ["git", "show", "--format=%P", "--no-patch", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().split()

    assert envelope["status"] == "merged"
    assert envelope["merge_result"]["status"] == "executed"
    assert envelope["verified_sha"] == verified_sha
    assert envelope["merge_target_sha"] == verified_sha
    assert envelope["merge_result"]["verified_sha"] == verified_sha
    assert envelope["merge_result"]["merge_target_sha"] == verified_sha
    assert envelope["merge_result"]["merge_commit_sha"] == merge_head
    assert verified_sha in merge_parents
    assert "merge_commit_sha:" in envelope["output"]


def test_devadaad_blocks_when_merge_sha_verification_is_missing(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)

    envelope = orchestrator.run("DEVADAAD", scenario="merge_verification_missing")

    assert envelope["status"] == "blocked"
    assert envelope["replay_gate_pass"] is False
    assert envelope["blocked_reason"] == "missing_merge_sha_verification"
    assert envelope["merge_result"]["status"] == "blocked"
    assert envelope["merge_result"]["reason"] == "missing_merge_sha_verification"
    assert "merge_target_matches_verified_sha: FAIL" in envelope["output"]


def test_devadaad_replay_divergence_blocks_merge(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "demo.txt").write_text("data\n", encoding="utf-8")
    orchestrator = AdaadTriggerOrchestrator(repo_root=tmp_path)

    envelope = orchestrator.run("DEVADAAD", scenario="replay_diverged")

    assert envelope["status"] == "blocked"
    assert envelope["replay_gate_pass"] is False
    assert envelope["blocked_reason"] == "replay_divergence_detected"
    assert "replay_verified_sha_context: FAIL" in envelope["output"]
