import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.sandbox.evidence import build_sandbox_evidence
from runtime.sandbox.replay import replay_sandbox_execution


def _build_valid_replay_inputs():
    manifest = {"mutation_id": "m1", "epoch_id": "e1", "replay_seed": "0000000000000001"}
    evidence = build_sandbox_evidence(
        manifest=manifest,
        result={"stdout": "hello", "stderr": "", "duration_s": 0.1, "memory_mb": 10, "disk_mb": 0, "returncode": 0},
        policy_hash="sha256:" + ("1" * 64),
        syscall_trace=("open", "read"),
        provider_ts="2026-02-14T00:00:00Z",
        replay_environment_fingerprint={
            "runtime_version": "3.11.9",
            "runtime_toolchain_fingerprint": "sha256:" + ("7" * 64),
            "dependency_lock_digest": "sha256:" + ("2" * 64),
            "env_whitelist_digest": "sha256:" + ("8" * 64),
            "container_profile_digest": "sha256:" + ("3" * 64),
            "filesystem_snapshot_digest": "sha256:" + ("4" * 64),
            "filesystem_baseline_digest": "sha256:" + ("5" * 64),
            "seed_lineage": {
                "root_seed": "0000000000000001",
                "parent_seed": "",
                "current_seed": "0000000000000001",
            },
        },
    )
    return manifest, evidence


def test_replay_sandbox_execution_passes_for_valid_evidence():
    manifest, evidence = _build_valid_replay_inputs()
    replay = replay_sandbox_execution(manifest, evidence)
    assert replay["passed"] is True


def test_replay_sandbox_execution_detects_environment_drift_even_when_output_hashes_match():
    manifest, evidence = _build_valid_replay_inputs()
    tampered_evidence = dict(evidence)
    tampered_evidence["replay_environment_fingerprint"] = dict(evidence["replay_environment_fingerprint"])
    tampered_evidence["replay_environment_fingerprint"]["runtime_version"] = "3.12.1"
    replay = replay_sandbox_execution(manifest, tampered_evidence)
    assert replay["passed"] is False
    assert replay["checks"]["runtime_version_hash"] is False
    assert replay["checks"]["stdout_hash"] is True


def test_replay_sandbox_execution_detects_dependency_drift_even_when_output_hashes_match():
    manifest, evidence = _build_valid_replay_inputs()
    tampered_evidence = dict(evidence)
    tampered_evidence["replay_environment_fingerprint"] = dict(evidence["replay_environment_fingerprint"])
    tampered_evidence["replay_environment_fingerprint"]["dependency_lock_digest"] = "sha256:" + ("9" * 64)
    replay = replay_sandbox_execution(manifest, tampered_evidence)
    assert replay["passed"] is False
    assert replay["checks"]["dependency_lock_digest_hash"] is False
    assert replay["checks"]["stdout_hash"] is True


def test_replay_sandbox_execution_detects_toolchain_drift_even_when_output_hashes_match():
    manifest, evidence = _build_valid_replay_inputs()
    tampered_evidence = dict(evidence)
    tampered_evidence["replay_environment_fingerprint"] = dict(evidence["replay_environment_fingerprint"])
    tampered_evidence["replay_environment_fingerprint"]["runtime_toolchain_fingerprint"] = "sha256:" + ("6" * 64)
    replay = replay_sandbox_execution(manifest, tampered_evidence)
    assert replay["passed"] is False
    assert replay["checks"]["runtime_toolchain_fingerprint_hash"] is False
    assert replay["checks"]["stdout_hash"] is True


def test_replay_sandbox_execution_detects_env_whitelist_drift_even_when_output_hashes_match():
    manifest, evidence = _build_valid_replay_inputs()
    tampered_evidence = dict(evidence)
    tampered_evidence["replay_environment_fingerprint"] = dict(evidence["replay_environment_fingerprint"])
    tampered_evidence["replay_environment_fingerprint"]["env_whitelist_digest"] = "sha256:" + ("5" * 64)
    replay = replay_sandbox_execution(manifest, tampered_evidence)
    assert replay["passed"] is False
    assert replay["checks"]["env_whitelist_digest_hash"] is False
    assert replay["checks"]["stdout_hash"] is True


def test_replay_sandbox_execution_detects_filesystem_baseline_drift_even_when_output_hashes_match():
    manifest, evidence = _build_valid_replay_inputs()
    tampered_evidence = dict(evidence)
    tampered_evidence["replay_environment_fingerprint"] = dict(evidence["replay_environment_fingerprint"])
    tampered_evidence["replay_environment_fingerprint"]["filesystem_baseline_digest"] = "sha256:" + ("6" * 64)
    replay = replay_sandbox_execution(manifest, tampered_evidence)
    assert replay["passed"] is False
    assert replay["checks"]["filesystem_baseline_digest_hash"] is False
    assert replay["checks"]["stdout_hash"] is True
