# SPDX-License-Identifier: Apache-2.0

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.foundation.determinism import SeededDeterminismProvider
from runtime.sandbox.executor import HardenedSandboxExecutor
from runtime.sandbox.isolation import EnforcedControl, IsolationPreparation
from runtime.test_sandbox import TestSandboxResult, TestSandboxStatus


class _FakeSandbox:
    def run_tests_with_retry(self, args=None, retries=1, preexec_fn=None):
        return TestSandboxResult(
            ok=True,
            output="ok",
            returncode=0,
            duration_s=0.1,
            timeout_s=60,
            sandbox_dir="/tmp/x",
            stdout="ok",
            stderr="",
            status=TestSandboxStatus.OK,
            retries=retries,
            memory_mb=12.5,
            observed_syscalls=("open", "read"),
            attempted_write_paths=("reports",),
            attempted_network_hosts=(),
        )


class _ViolationSandbox:
    def __init__(self, *, syscalls=("open",), write_paths=(), hosts=()):
        self.syscalls = tuple(syscalls)
        self.write_paths = tuple(write_paths)
        self.hosts = tuple(hosts)

    def run_tests_with_retry(self, args=None, retries=1, preexec_fn=None):
        return TestSandboxResult(
            ok=True,
            output="ok",
            returncode=0,
            duration_s=0.1,
            timeout_s=60,
            sandbox_dir="/tmp/x",
            stdout="ok",
            stderr="",
            status=TestSandboxStatus.OK,
            retries=retries,
            memory_mb=12.5,
            observed_syscalls=self.syscalls,
            attempted_write_paths=self.write_paths,
            attempted_network_hosts=self.hosts,
        )


def test_hardened_executor_records_evidence():
    executor = HardenedSandboxExecutor(_FakeSandbox(), provider=SeededDeterminismProvider("seed"))
    result = executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")
    assert result.ok
    assert executor.last_evidence_hash.startswith("sha256:")
    assert executor.last_evidence_payload["resource_usage_hash"].startswith("sha256:")
    assert executor.last_evidence_payload["isolation_mode"] == "process"
    assert executor.last_evidence_payload["enforced_controls"]
    resource_controls = [c for c in executor.last_evidence_payload["enforced_controls"] if c["control"] == "resource_quotas"]
    assert resource_controls
    assert resource_controls[0]["mechanism"] == "process_rlimit"


def test_hardened_executor_rejects_observed_syscall_violation():
    executor = HardenedSandboxExecutor(_ViolationSandbox(syscalls=("socket",)), provider=SeededDeterminismProvider("seed"))
    with pytest.raises(RuntimeError, match="sandbox_syscall_violation"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")


def test_hardened_executor_rejects_observed_write_path_violation():
    executor = HardenedSandboxExecutor(_ViolationSandbox(write_paths=("tmp/bad.txt",)), provider=SeededDeterminismProvider("seed"))
    with pytest.raises(RuntimeError, match="sandbox_write_path_violation"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")


def test_hardened_executor_rejects_observed_network_violation():
    executor = HardenedSandboxExecutor(_ViolationSandbox(hosts=("api.example",)), provider=SeededDeterminismProvider("seed"))
    with pytest.raises(RuntimeError, match="sandbox_network_violation"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")


def test_hardened_executor_rejects_missing_syscall_telemetry():
    executor = HardenedSandboxExecutor(_ViolationSandbox(syscalls=()), provider=SeededDeterminismProvider("seed"))
    with pytest.raises(RuntimeError, match="sandbox_missing_syscall_telemetry"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")


class _TelemetryBackend:
    def __init__(self):
        self.last_runtime_telemetry = {
            "backend": "docker",
            "denied_syscalls": ["clone"],
            "network_attempts": ["api.example"],
            "write_attempts": ["/workspace/tmp"],
            "resource_usage": {"memory_mb": 20.0},
        }

    def prepare(self, *, manifest, policy):
        return IsolationPreparation(
            mode="container",
            controls=(EnforcedControl("syscall_allowlist", "seccomp.profile", "docker_seccomp", True),),
        )

    def run(self, *, test_sandbox, manifest, args, retries):
        del test_sandbox, manifest, args, retries
        return TestSandboxResult(
            ok=True,
            output="ok",
            returncode=0,
            duration_s=0.1,
            timeout_s=60,
            sandbox_dir="/tmp/x",
            stdout="ok",
            stderr="",
            status=TestSandboxStatus.OK,
            retries=1,
            memory_mb=12.5,
            observed_syscalls=("open", "read"),
            attempted_write_paths=("reports",),
            attempted_network_hosts=(),
        )


def test_hardened_executor_records_container_runtime_telemetry():
    executor = HardenedSandboxExecutor(
        _FakeSandbox(),
        provider=SeededDeterminismProvider("seed"),
        isolation_backend=_TelemetryBackend(),
    )
    result = executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")
    assert result.ok
    assert executor.last_evidence_payload["isolation_mode"] == "container"
    assert executor.last_evidence_payload["runtime_telemetry"]["backend"] == "docker"
    assert executor.last_evidence_payload["runtime_telemetry"]["denied_syscalls"] == ["clone"]




def test_hardened_executor_reports_process_control_capability_flags_truthfully():
    executor = HardenedSandboxExecutor(_FakeSandbox(), provider=SeededDeterminismProvider("seed"))
    executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")

    controls = {item["control"]: item for item in executor.last_evidence_payload["enforced_controls"]}
    syscall = controls["syscall_allowlist"]["capability_flags"]
    assert syscall["simulated_or_observed_only"] is True
    assert syscall["enforced_in_kernel"] is False
    assert syscall["mode"] == "simulated/observed-only"

    quota = controls["resource_quotas"]["capability_flags"]
    assert quota["best_effort"] is True
    assert quota["enforced_in_kernel"] is False


def test_hardened_executor_reports_container_control_capability_flags_truthfully():
    executor = HardenedSandboxExecutor(
        _FakeSandbox(),
        provider=SeededDeterminismProvider("seed"),
        isolation_backend=_TelemetryBackend(),
    )
    executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")

    controls = {item["control"]: item for item in executor.last_evidence_payload["enforced_controls"]}
    syscall = controls["syscall_allowlist"]["capability_flags"]
    assert syscall["enforced_in_kernel"] is True
    assert syscall["simulated_or_observed_only"] is False
    assert syscall["mode"] == "enforced_in-kernel"

    telemetry = executor.last_evidence_payload["runtime_telemetry"]
    assert telemetry["syscall_validation"] == "telemetry_allowlist"
    assert telemetry["syscall_validation_enforced_in_kernel"] is False
    assert telemetry["hard_isolation"] is True

def test_container_rollout_fail_closed_without_profiles(monkeypatch):
    monkeypatch.setenv("ADAAD_FORCE_TIER", "SANDBOX")
    monkeypatch.setenv("ADAAD_SANDBOX_CONTAINER_ROLLOUT", "1")
    monkeypatch.delenv("ADAAD_SANDBOX_CONTAINER_RUNTIME_PROFILE", raising=False)
    executor = HardenedSandboxExecutor(_FakeSandbox(), provider=SeededDeterminismProvider("seed"))
    with pytest.raises(RuntimeError, match="sandbox_policy_unenforceable:container_runtime"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")


def test_sandbox_executor_respects_deprecated_resource_memory_alias(monkeypatch):
    monkeypatch.delenv("ADAAD_RESOURCE_MEMORY_MB", raising=False)
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "8")

    executor = HardenedSandboxExecutor(_FakeSandbox(), provider=SeededDeterminismProvider("seed"))
    with pytest.raises(RuntimeError, match="resource_bounds_exceeded:memory"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")


def test_sandbox_executor_prefers_canonical_resource_memory_env(monkeypatch):
    monkeypatch.setenv("ADAAD_RESOURCE_MEMORY_MB", "32")
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "8")

    executor = HardenedSandboxExecutor(_FakeSandbox(), provider=SeededDeterminismProvider("seed"))
    result = executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")
    assert result.ok
