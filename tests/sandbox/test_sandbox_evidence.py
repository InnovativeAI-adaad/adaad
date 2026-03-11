import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.sandbox.evidence import SandboxEvidenceLedger, build_sandbox_evidence


def test_sandbox_evidence_ledger_hash_chain(tmp_path):
    ledger = SandboxEvidenceLedger(tmp_path / "sandbox_evidence.jsonl")
    payload = build_sandbox_evidence(
        manifest={"mutation_id": "m1", "epoch_id": "e1", "replay_seed": "0000000000000001"},
        result={"stdout": "ok", "stderr": "", "duration_s": 0.1, "memory_mb": 10, "disk_mb": 0, "returncode": 0},
        policy_hash="sha256:" + ("1" * 64),
        syscall_trace=("open", "read"),
        provider_ts="2026-02-14T00:00:00Z",
        replay_environment_fingerprint={
            "runtime_version": "3.11.9",
            "dependency_lock_digest": "sha256:" + ("2" * 64),
            "container_profile_digest": "sha256:" + ("3" * 64),
            "filesystem_snapshot_digest": "sha256:" + ("4" * 64),
            "seed_lineage": {"root_seed": "0001", "parent_seed": "", "current_seed": "0001"},
        },
        replay_diagnostics={"added": [], "removed": [], "modified": [], "post_filesystem_snapshot_digest": "sha256:" + ("5" * 64)},
    )
    first = ledger.append(payload)
    second = ledger.append(payload)
    assert first["prev_hash"].startswith("sha256:")
    assert second["prev_hash"] == first["hash"]
    assert payload["evidence_hash"].startswith("sha256:")
    assert payload["resource_usage_hash"].startswith("sha256:")
    assert payload["sandbox_policy_hash"] == payload["policy_hash"]
    assert payload["syscall_fingerprint"].startswith("sha256:")
    assert payload["events"] == []

    assert payload["isolation_mode"] == "process"
    assert payload["preflight"]["ok"] is True
    assert payload["runtime_telemetry"] == {}
    assert payload["runtime_telemetry_hash"].startswith("sha256:")
    assert payload["replay_environment_fingerprint_hash"].startswith("sha256:")
    assert payload["runtime_version_hash"].startswith("sha256:")
    assert payload["dependency_lock_digest_hash"].startswith("sha256:")
    assert payload["container_profile_digest_hash"].startswith("sha256:")
    assert payload["filesystem_snapshot_digest_hash"].startswith("sha256:")
    assert payload["seed_lineage_hash"].startswith("sha256:")
    assert payload["replay_diagnostics_hash"].startswith("sha256:")


def test_sandbox_evidence_resource_accounting_is_deterministic():
    manifest = {"mutation_id": "m1", "epoch_id": "e1", "replay_seed": "0000000000000001"}
    result = {"stdout": "ok", "stderr": "", "duration_s": 0.1, "memory_mb": 10, "disk_mb": 0, "returncode": 0}
    first = build_sandbox_evidence(
        manifest=manifest,
        result=result,
        policy_hash="sha256:" + ("1" * 64),
        syscall_trace=("open", "read"),
        provider_ts="2026-02-14T00:00:00Z",
    )
    second = build_sandbox_evidence(
        manifest=manifest,
        result=result,
        policy_hash="sha256:" + ("1" * 64),
        syscall_trace=("open", "read"),
        provider_ts="2026-02-14T00:00:00Z",
    )

    assert first["resource_usage"] == second["resource_usage"]
    assert first["resource_usage"]["duration_s"] == 0.1
    assert first["resource_usage_hash"] == second["resource_usage_hash"]


def test_sandbox_evidence_runtime_telemetry_is_canonical():
    payload = build_sandbox_evidence(
        manifest={"mutation_id": "m1", "epoch_id": "e1", "replay_seed": "0000000000000001"},
        result={"stdout": "ok", "stderr": "", "duration_s": 0.1, "memory_mb": 10, "disk_mb": 0, "returncode": 0},
        policy_hash="sha256:" + ("1" * 64),
        syscall_trace=("open", "read"),
        provider_ts="2026-02-14T00:00:00Z",
        runtime_telemetry={"b": 2, "a": 1},
        replay_environment_fingerprint={
            "runtime_version": "3.11.9",
            "dependency_lock_digest": "sha256:" + ("2" * 64),
            "container_profile_digest": "sha256:" + ("3" * 64),
            "filesystem_snapshot_digest": "sha256:" + ("4" * 64),
            "seed_lineage": {"root_seed": "0001", "parent_seed": "", "current_seed": "0001"},
        },
        replay_diagnostics={"added": [], "removed": [], "modified": [], "post_filesystem_snapshot_digest": "sha256:" + ("5" * 64)},
    )
    assert list(payload["runtime_telemetry"].keys()) == ["a", "b"]
    assert payload["runtime_telemetry_hash"].startswith("sha256:")
    assert payload["replay_environment_fingerprint"]["runtime_version"] == "3.11.9"
