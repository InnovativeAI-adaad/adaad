# SPDX-License-Identifier: Apache-2.0

import hashlib
import subprocess

import pytest

from runtime.governance.foundation.determinism import SeededDeterminismProvider
from runtime.sandbox.executor import HardenedSandboxExecutor, SandboxTimeoutError
from runtime.sandbox.policy import SandboxPolicy
from runtime.test_sandbox import TestSandboxResult, TestSandboxStatus


class _ResultSandbox:
    def __init__(self, *, status: TestSandboxStatus, duration_s: float = 0.1, memory_mb: float = 16.0):
        self.status = status
        self.duration_s = duration_s
        self.memory_mb = memory_mb

    def run_tests_with_retry(self, args=None, retries=1, preexec_fn=None):
        del args, retries, preexec_fn
        return TestSandboxResult(
            ok=self.status != TestSandboxStatus.TIMEOUT,
            output="ok",
            returncode=0,
            duration_s=self.duration_s,
            timeout_s=30,
            sandbox_dir="/tmp/x",
            stdout="ok",
            stderr="",
            status=self.status,
            retries=1,
            memory_mb=self.memory_mb,
            observed_syscalls=("open", "read"),
            attempted_write_paths=("reports",),
            attempted_network_hosts=(),
        )


def _test_policy(timeout_s: int = 30) -> SandboxPolicy:
    return SandboxPolicy(
        profile_id="default-v1",
        syscall_allowlist=("close", "fstat", "mmap", "open", "read", "stat", "write"),
        write_path_allowlist=("reports",),
        network_egress_allowlist=(),
        dns_resolution_allowed=False,
        capability_drop=("net_admin",),
        cpu_seconds=60,
        memory_mb=1024,
        disk_mb=2048,
        timeout_s=timeout_s,
    )


def test_hardening_emits_start_and_end_events(monkeypatch):
    txs = []
    monkeypatch.setattr("runtime.sandbox.executor.journal.append_tx", lambda tx_type, payload, tx_id=None: txs.append((tx_type, payload)))

    executor = HardenedSandboxExecutor(
        _ResultSandbox(status=TestSandboxStatus.OK, duration_s=0.42, memory_mb=32.5),
        policy=_test_policy(),
        provider=SeededDeterminismProvider("seed"),
    )

    result = executor.run_tests_with_retry(
        mutation_id="m-1",
        epoch_id="e-1",
        replay_seed="0000000000000001",
        args=("-q",),
    )

    assert result.ok
    assert txs[0][0] == "sandbox_execution_start.v1"
    assert txs[-1][0] == "sandbox_execution_end.v1"
    end_payload = txs[-1][1]
    assert end_payload["duration_s"] == pytest.approx(0.42)
    assert end_payload["peak_memory_mb"] == pytest.approx(32.5)
    assert end_payload["status"] == "ok"
    assert end_payload["code_hash"] == hashlib.sha256("-q".encode("utf-8")).hexdigest()


def test_hardening_raises_timeout_and_emits_timeout_events(monkeypatch):
    txs = []
    monkeypatch.setattr("runtime.sandbox.executor.journal.append_tx", lambda tx_type, payload, tx_id=None: txs.append((tx_type, payload)))

    executor = HardenedSandboxExecutor(
        _ResultSandbox(status=TestSandboxStatus.TIMEOUT, duration_s=31.0, memory_mb=8.0),
        policy=_test_policy(timeout_s=30),
        provider=SeededDeterminismProvider("seed"),
    )

    with pytest.raises(SandboxTimeoutError):
        executor.run_tests_with_retry(
            mutation_id="m-2",
            epoch_id="e-2",
            replay_seed="0000000000000001",
            args=("-x", "--tb=short"),
        )

    tx_types = [tx_type for tx_type, _ in txs]
    assert tx_types[0] == "sandbox_execution_start.v1"
    assert "sandbox_timeout.v1" in tx_types
    assert tx_types[-1] == "sandbox_execution_end.v1"

    timeout_payload = next(payload for tx_type, payload in txs if tx_type == "sandbox_timeout.v1")
    assert timeout_payload["duration_s"] == pytest.approx(31.0)
    assert timeout_payload["peak_memory_mb"] == pytest.approx(8.0)
    assert timeout_payload["status"] == "timeout"


def test_hardening_handles_backend_timeout_expired(monkeypatch):
    txs = []
    monkeypatch.setattr("runtime.sandbox.executor.journal.append_tx", lambda tx_type, payload, tx_id=None: txs.append((tx_type, payload)))

    class _TimeoutBackend:
        last_runtime_telemetry = {}

        def prepare(self, *, manifest, policy):
            from runtime.sandbox.isolation import EnforcedControl, IsolationPreparation

            del policy
            return IsolationPreparation(
                mode="process",
                controls=(EnforcedControl("resource_quotas", "rlimit", "process_rlimit", True),),
            )

        def run(self, *, test_sandbox, manifest, args, retries):
            del test_sandbox, manifest, args, retries
            raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=30)

    executor = HardenedSandboxExecutor(
        _ResultSandbox(status=TestSandboxStatus.OK),
        policy=_test_policy(timeout_s=30),
        provider=SeededDeterminismProvider("seed"),
        isolation_backend=_TimeoutBackend(),
    )

    with pytest.raises(SandboxTimeoutError):
        executor.run_tests_with_retry(
            mutation_id="m-3",
            epoch_id="e-3",
            replay_seed="0000000000000001",
            args=("-q",),
        )

    tx_types = [tx_type for tx_type, _ in txs]
    assert tx_types == ["sandbox_execution_start.v1", "sandbox_timeout.v1", "sandbox_execution_end.v1"]
    timeout_payload = txs[1][1]
    end_payload = txs[2][1]
    assert timeout_payload["status"] == "timeout"
    assert timeout_payload["peak_memory_mb"] == pytest.approx(0.0)
    assert end_payload == timeout_payload
