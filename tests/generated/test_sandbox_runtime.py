from __future__ import annotations

from runtime.sandbox.executor import HardenedSandboxExecutor
from runtime.sandbox.policy import default_sandbox_policy
from runtime.test_sandbox import TestSandbox


def test_runtime_sandbox_executor_uses_default_policy() -> None:
    sandbox = TestSandbox(timeout_s=10)
    executor = HardenedSandboxExecutor(test_sandbox=sandbox, policy=default_sandbox_policy())
    assert executor.policy.profile_id == "default-v1"
