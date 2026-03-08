# SPDX-License-Identifier: Apache-2.0
"""Replay helpers for deterministic sandbox evidence verification."""

from __future__ import annotations

from typing import Any, Dict

from runtime.governance.foundation import sha256_prefixed_digest


REPLAY_HASH_FIELDS = (
    "manifest_hash",
    "stdout_hash",
    "stderr_hash",
    "syscall_trace_hash",
    "resource_usage_hash",
    "runtime_version_hash",
    "runtime_toolchain_fingerprint_hash",
    "dependency_lock_digest_hash",
    "env_whitelist_digest_hash",
    "container_profile_digest_hash",
    "filesystem_snapshot_digest_hash",
    "filesystem_baseline_digest_hash",
    "seed_lineage_hash",
)


def replay_sandbox_execution(manifest: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Verify persisted sandbox evidence hash invariants."""
    expected_manifest_hash = sha256_prefixed_digest(manifest)
    expected_stdout_hash = sha256_prefixed_digest(str(evidence.get("stdout") or ""))
    expected_stderr_hash = sha256_prefixed_digest(str(evidence.get("stderr") or ""))
    expected_syscall_trace_hash = sha256_prefixed_digest(list(evidence.get("syscall_trace") or ()))
    expected_resource_usage_hash = sha256_prefixed_digest(dict(evidence.get("resource_usage") or {}))

    replay_env = dict(evidence.get("replay_environment_fingerprint") or {})
    expected_runtime_version_hash = sha256_prefixed_digest(str(replay_env.get("runtime_version") or ""))
    expected_runtime_toolchain_fingerprint_hash = sha256_prefixed_digest(
        str(replay_env.get("runtime_toolchain_fingerprint") or "")
    )
    expected_dependency_lock_digest_hash = sha256_prefixed_digest(str(replay_env.get("dependency_lock_digest") or ""))
    expected_env_whitelist_digest_hash = sha256_prefixed_digest(str(replay_env.get("env_whitelist_digest") or ""))
    expected_container_profile_digest_hash = sha256_prefixed_digest(str(replay_env.get("container_profile_digest") or ""))
    expected_filesystem_snapshot_digest_hash = sha256_prefixed_digest(str(replay_env.get("filesystem_snapshot_digest") or ""))
    expected_filesystem_baseline_digest_hash = sha256_prefixed_digest(str(replay_env.get("filesystem_baseline_digest") or ""))
    expected_seed_lineage_hash = sha256_prefixed_digest(dict(replay_env.get("seed_lineage") or {}))

    observed_manifest_hash = str(evidence.get("manifest_hash") or "")
    observed_stdout_hash = str(evidence.get("stdout_hash") or "")
    observed_stderr_hash = str(evidence.get("stderr_hash") or "")
    observed_syscall_trace_hash = str(evidence.get("syscall_trace_hash") or "")
    observed_resource_usage_hash = str(evidence.get("resource_usage_hash") or "")
    observed_runtime_version_hash = str(evidence.get("runtime_version_hash") or "")
    observed_runtime_toolchain_fingerprint_hash = str(evidence.get("runtime_toolchain_fingerprint_hash") or "")
    observed_dependency_lock_digest_hash = str(evidence.get("dependency_lock_digest_hash") or "")
    observed_env_whitelist_digest_hash = str(evidence.get("env_whitelist_digest_hash") or "")
    observed_container_profile_digest_hash = str(evidence.get("container_profile_digest_hash") or "")
    observed_filesystem_snapshot_digest_hash = str(evidence.get("filesystem_snapshot_digest_hash") or "")
    observed_filesystem_baseline_digest_hash = str(evidence.get("filesystem_baseline_digest_hash") or "")
    observed_seed_lineage_hash = str(evidence.get("seed_lineage_hash") or "")

    checks = {
        "manifest_hash": expected_manifest_hash == observed_manifest_hash,
        "stdout_hash": expected_stdout_hash == observed_stdout_hash,
        "stderr_hash": expected_stderr_hash == observed_stderr_hash,
        "syscall_trace_hash": expected_syscall_trace_hash == observed_syscall_trace_hash,
        "resource_usage_hash": expected_resource_usage_hash == observed_resource_usage_hash,
        "runtime_version_hash": expected_runtime_version_hash == observed_runtime_version_hash,
        "runtime_toolchain_fingerprint_hash": expected_runtime_toolchain_fingerprint_hash
        == observed_runtime_toolchain_fingerprint_hash,
        "dependency_lock_digest_hash": expected_dependency_lock_digest_hash == observed_dependency_lock_digest_hash,
        "env_whitelist_digest_hash": expected_env_whitelist_digest_hash == observed_env_whitelist_digest_hash,
        "container_profile_digest_hash": expected_container_profile_digest_hash == observed_container_profile_digest_hash,
        "filesystem_snapshot_digest_hash": expected_filesystem_snapshot_digest_hash == observed_filesystem_snapshot_digest_hash,
        "filesystem_baseline_digest_hash": expected_filesystem_baseline_digest_hash == observed_filesystem_baseline_digest_hash,
        "seed_lineage_hash": expected_seed_lineage_hash == observed_seed_lineage_hash,
    }
    passed = all(checks.values())
    return {
        "passed": passed,
        "checks": checks,
        "expected_manifest_hash": expected_manifest_hash,
        "observed_manifest_hash": observed_manifest_hash,
        "expected_stdout_hash": expected_stdout_hash,
        "observed_stdout_hash": observed_stdout_hash,
        "expected_stderr_hash": expected_stderr_hash,
        "observed_stderr_hash": observed_stderr_hash,
        "expected_syscall_trace_hash": expected_syscall_trace_hash,
        "observed_syscall_trace_hash": observed_syscall_trace_hash,
        "expected_resource_usage_hash": expected_resource_usage_hash,
        "observed_resource_usage_hash": observed_resource_usage_hash,
        "expected_runtime_version_hash": expected_runtime_version_hash,
        "observed_runtime_version_hash": observed_runtime_version_hash,
        "expected_runtime_toolchain_fingerprint_hash": expected_runtime_toolchain_fingerprint_hash,
        "observed_runtime_toolchain_fingerprint_hash": observed_runtime_toolchain_fingerprint_hash,
        "expected_dependency_lock_digest_hash": expected_dependency_lock_digest_hash,
        "observed_dependency_lock_digest_hash": observed_dependency_lock_digest_hash,
        "expected_env_whitelist_digest_hash": expected_env_whitelist_digest_hash,
        "observed_env_whitelist_digest_hash": observed_env_whitelist_digest_hash,
        "expected_container_profile_digest_hash": expected_container_profile_digest_hash,
        "observed_container_profile_digest_hash": observed_container_profile_digest_hash,
        "expected_filesystem_snapshot_digest_hash": expected_filesystem_snapshot_digest_hash,
        "observed_filesystem_snapshot_digest_hash": observed_filesystem_snapshot_digest_hash,
        "expected_filesystem_baseline_digest_hash": expected_filesystem_baseline_digest_hash,
        "observed_filesystem_baseline_digest_hash": observed_filesystem_baseline_digest_hash,
        "expected_seed_lineage_hash": expected_seed_lineage_hash,
        "observed_seed_lineage_hash": observed_seed_lineage_hash,
    }


__all__ = ["REPLAY_HASH_FIELDS", "replay_sandbox_execution"]
