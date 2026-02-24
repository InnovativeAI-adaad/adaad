# SPDX-License-Identifier: Apache-2.0
"""Isolation backend abstractions for hardened sandbox execution."""

from __future__ import annotations

from dataclasses import dataclass
import os
import sys
from typing import Protocol, Sequence

from runtime.sandbox.manifest import SandboxManifest
from runtime.sandbox.policy import SandboxPolicy
from runtime.sandbox.resources import build_rlimit_preexec_hook, rlimit_enforcement_supported
from runtime.test_sandbox import TestSandbox, TestSandboxResult


@dataclass(frozen=True)
class EnforcedControl:
    """Single isolation control enforcement record."""

    control: str
    profile: str
    mechanism: str
    enforced: bool
    simulated: bool = False


@dataclass(frozen=True)
class IsolationPreparation:
    """Backend pre-execution isolation state."""

    mode: str
    controls: tuple[EnforcedControl, ...]


def capability_drop_supported() -> tuple[bool, str]:
    if "android" in sys.platform:
        return False, "capability_drop_android_platform"
    uname = getattr(os, "uname", None)
    if callable(uname):
        try:
            machine = str(uname()).lower()
        except Exception:
            machine = ""
        if "android" in machine:
            return False, "capability_drop_android_platform"
    return True, "ok"


class IsolationBackend(Protocol):
    """Execution backend that can enforce sandbox policy controls."""

    def prepare(self, *, manifest: SandboxManifest, policy: SandboxPolicy) -> IsolationPreparation: ...

    def run(
        self,
        *,
        test_sandbox: TestSandbox,
        manifest: SandboxManifest,
        args: Sequence[str] | None,
        retries: int,
    ) -> TestSandboxResult: ...


@dataclass(frozen=True)
class ProcessIsolationBackend:
    """Ephemeral process backend with explicit policy-control profiles."""

    seccomp_profile_id: str = "seccomp.default.v1"
    capability_profile_id: str = "caps.drop.default.v1"
    resource_profile_id: str = "rlimit.default.v1"
    supports_resource_quotas: bool = True

    def prepare(self, *, manifest: SandboxManifest, policy: SandboxPolicy) -> IsolationPreparation:
        controls: list[EnforcedControl] = []
        if not policy.syscall_allowlist or not self.seccomp_profile_id:
            raise RuntimeError("sandbox_policy_unenforceable:syscall_allowlist")
        controls.append(
            EnforcedControl(
                control="syscall_allowlist",
                profile=self.seccomp_profile_id,
                mechanism="seccomp",
                enforced=True,
            )
        )

        if not policy.capability_drop or not self.capability_profile_id:
            raise RuntimeError("sandbox_policy_unenforceable:capability_drop")
        capability_supported, capability_reason = capability_drop_supported()
        if not capability_supported:
            raise RuntimeError(f"sandbox_policy_unenforceable:{capability_reason}")
        controls.append(
            EnforcedControl(
                control="capability_drop",
                profile=self.capability_profile_id,
                mechanism="process_capability_drop",
                enforced=True,
            )
        )

        if not self.supports_resource_quotas:
            raise RuntimeError("sandbox_policy_unenforceable:resource_quotas")
        if manifest.cpu_seconds <= 0 or manifest.memory_mb <= 0 or manifest.disk_mb <= 0 or manifest.timeout_s <= 0:
            raise RuntimeError("sandbox_policy_unenforceable:resource_quotas")
        supported, reason = rlimit_enforcement_supported()
        if not supported:
            raise RuntimeError(f"sandbox_policy_unenforceable:{reason}")
        controls.append(
            EnforcedControl(
                control="resource_quotas",
                profile=self.resource_profile_id,
                mechanism="process_rlimit",
                enforced=True,
            )
        )
        return IsolationPreparation(mode="process", controls=tuple(controls))

    def run(
        self,
        *,
        test_sandbox: TestSandbox,
        manifest: SandboxManifest,
        args: Sequence[str] | None,
        retries: int,
    ) -> TestSandboxResult:
        preexec_hook = build_rlimit_preexec_hook(
            cpu_limit_s=manifest.cpu_seconds,
            memory_limit_mb=manifest.memory_mb,
            disk_limit_mb=manifest.disk_mb,
        )
        return test_sandbox.run_tests_with_retry(args=args, retries=retries, preexec_fn=preexec_hook)


@dataclass(frozen=True)
class ContainerIsolationBackend:
    """Container isolation backend placeholder used for fail-closed gating."""

    runtime_profile_id: str = ""

    def prepare(self, *, manifest: SandboxManifest, policy: SandboxPolicy) -> IsolationPreparation:
        del manifest, policy
        if not self.runtime_profile_id:
            raise RuntimeError("sandbox_policy_unenforceable:container_runtime")
        return IsolationPreparation(mode="container", controls=())

    def run(
        self,
        *,
        test_sandbox: TestSandbox,
        manifest: SandboxManifest,
        args: Sequence[str] | None,
        retries: int,
    ) -> TestSandboxResult:
        del manifest
        del test_sandbox
        raise RuntimeError("sandbox_backend_unavailable:container")


__all__ = [
    "capability_drop_supported",
    "ContainerIsolationBackend",
    "EnforcedControl",
    "IsolationBackend",
    "IsolationPreparation",
    "ProcessIsolationBackend",
]
