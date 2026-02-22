# SPDX-License-Identifier: Apache-2.0
"""Linux-first sandbox hardening policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from runtime.sandbox.syscall_filter import DEFAULT_SYSCALL_ALLOWLIST


@dataclass(frozen=True)
class SandboxHardeningPolicy:
    syscall_allowlist: Tuple[str, ...]
    workspace_prefixes: Tuple[str, ...]
    seccomp_available: bool


def default_hardening_policy() -> SandboxHardeningPolicy:
    return SandboxHardeningPolicy(
        syscall_allowlist=DEFAULT_SYSCALL_ALLOWLIST,
        workspace_prefixes=(".", "/workspace"),
        seccomp_available=True,
    )


__all__ = ["SandboxHardeningPolicy", "default_hardening_policy"]
