# SPDX-License-Identifier: Apache-2.0

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.foundation.determinism import SeededDeterminismProvider
from runtime.sandbox.executor import HardenedSandboxExecutor
from runtime.sandbox.isolation import ProcessIsolationBackend
from runtime.sandbox.manifest import SandboxManifest
from runtime.sandbox.policy import default_sandbox_policy
from runtime.sandbox.preflight import analyze_execution_plan
from runtime.test_sandbox import TestSandboxResult, TestSandboxStatus


class _TrackingSandbox:
    def __init__(self) -> None:
        self.calls = 0

    def run_tests_with_retry(self, args=None, retries=1, preexec_fn=None):
        self.calls += 1
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
            memory_mb=16.0,
            observed_syscalls=("open", "read"),
            attempted_write_paths=("reports/safe.txt",),
            attempted_network_hosts=(),
        )


class _HookTrackingSandbox(_TrackingSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.preexec_fn = None

    def run_tests_with_retry(self, args=None, retries=1, preexec_fn=None):
        self.preexec_fn = preexec_fn
        return super().run_tests_with_retry(args=args, retries=retries)


def test_backend_failure_blocks_mutation_execution_before_tests_run():
    sandbox = _TrackingSandbox()
    backend = ProcessIsolationBackend(seccomp_profile_id="")
    executor = HardenedSandboxExecutor(
        sandbox,
        provider=SeededDeterminismProvider("seed"),
        isolation_backend=backend,
    )

    with pytest.raises(RuntimeError, match="sandbox_policy_unenforceable:syscall_allowlist"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")

    assert sandbox.calls == 0


def test_preflight_blocks_disallowed_command_before_tests_run():
    sandbox = _TrackingSandbox()
    executor = HardenedSandboxExecutor(sandbox, provider=SeededDeterminismProvider("seed"))

    with pytest.raises(RuntimeError, match="sandbox_preflight_violation"):
        executor.run_tests_with_retry(
            mutation_id="m1",
            epoch_id="e1",
            replay_seed="0000000000000001",
            args=("-x", "--tb=short", "&&"),
        )

    assert sandbox.calls == 0


def test_preflight_rejects_disallowed_mount_targets():
    policy = default_sandbox_policy()
    manifest = SandboxManifest(
        mutation_id="m1",
        epoch_id="e1",
        replay_seed="0000000000000001",
        command=("-x",),
        env=(("PYTHONDONTWRITEBYTECODE", "1"),),
        mounts=("tmp",),
        allowed_write_paths=policy.write_path_allowlist,
        allowed_network_hosts=policy.network_egress_allowlist,
        cpu_seconds=policy.cpu_seconds,
        memory_mb=policy.memory_mb,
        disk_mb=policy.disk_mb,
        timeout_s=policy.timeout_s,
        deterministic_clock=True,
        deterministic_random=True,
    )

    preflight = analyze_execution_plan(manifest=manifest, policy=policy)
    assert preflight["ok"] is False
    assert preflight["reason"].startswith("disallowed_mount_target")


def test_resource_rlimit_hook_is_passed_into_execution_path():
    sandbox = _HookTrackingSandbox()
    executor = HardenedSandboxExecutor(sandbox, provider=SeededDeterminismProvider("seed"))
    result = executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")

    assert result.ok
    assert sandbox.preexec_fn is not None


def test_backend_fails_closed_when_rlimit_enforcement_unavailable(monkeypatch):
    sandbox = _TrackingSandbox()
    backend = ProcessIsolationBackend()
    executor = HardenedSandboxExecutor(
        sandbox,
        provider=SeededDeterminismProvider("seed"),
        isolation_backend=backend,
    )
    monkeypatch.setattr("runtime.sandbox.isolation.rlimit_enforcement_supported", lambda: (False, "resource_quotas_platform"))

    with pytest.raises(RuntimeError, match="sandbox_policy_unenforceable:resource_quotas_platform"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")

    assert sandbox.calls == 0


def test_backend_fails_closed_for_android_capability_drop_degradation(monkeypatch):
    sandbox = _TrackingSandbox()
    backend = ProcessIsolationBackend()
    executor = HardenedSandboxExecutor(
        sandbox,
        provider=SeededDeterminismProvider("seed"),
        isolation_backend=backend,
    )
    monkeypatch.setattr("runtime.sandbox.isolation.capability_drop_supported", lambda: (False, "capability_drop_android_platform"))

    with pytest.raises(RuntimeError, match="sandbox_policy_unenforceable:capability_drop_android_platform"):
        executor.run_tests_with_retry(mutation_id="m1", epoch_id="e1", replay_seed="0000000000000001")

    assert sandbox.calls == 0
