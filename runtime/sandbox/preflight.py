# SPDX-License-Identifier: Apache-2.0
"""Deterministic sandbox preflight checks executed before mutation tests."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from runtime.sandbox.manifest import SandboxManifest
from runtime.sandbox.policy import SandboxPolicy

_DISALLOWED_ENV_KEYS = frozenset({
    "LD_PRELOAD",
    "PYTHONINSPECT",
    "LD_LIBRARY_PATH",
    "PYTHONSTARTUP",
})
# C-02 hardening: extend beyond basic shell metacharacters to cover bash word-splitting
# bypasses, null-byte injection, and shell-builtin execution primitives.
_DISALLOWED_TOKEN_FRAGMENTS: tuple[str, ...] = (
    # Shell control operators
    "&&", "||", ";", "|", "`", "$(", "${",
    # Redirect operators
    ">", "<", "<<",
    # IFS word-splitting bypasses
    "$IFS", "${IFS}",
    # Null-byte injection
    "\x00", "%00",
    # Shell evaluation primitives
    "eval ", "eval\t", "exec ", "exec\t",
    "source ", "source\t",
    # Newline injection (literal and escaped)
    "\\n",
)
_MAX_TOKEN_LENGTH = 512
_MAX_TOKEN_PREVIEW_LENGTH = 80


def _token_preview(token: str) -> str:
    return token[:_MAX_TOKEN_PREVIEW_LENGTH]


def _validate_command_token(token: str) -> tuple[str, ...]:
    violations: list[str] = []
    if any(fragment in token for fragment in _DISALLOWED_TOKEN_FRAGMENTS):
        violations.append(f"disallowed_command_token:{_token_preview(token)}")
    if len(token) > _MAX_TOKEN_LENGTH:
        violations.append(f"oversized_command_token:{len(token)}")
    return tuple(violations)


def _validate_write_allowlist(write_path_allowlist: Any) -> tuple[str, ...]:
    """H-03: Validate write-path allowlist entries before mount processing.

    Rejects any entry containing ``..`` path traversal sequences.
    Fails closed so a malformed allowlist cannot silently open a
    path-bypass during mount validation.
    """
    violations: list[str] = []
    entries = list(write_path_allowlist) if write_path_allowlist is not None else []
    for entry in entries:
        entry_str = str(entry)
        if ".." in PurePosixPath(entry_str).parts:
            violations.append(f"write_allowlist_traversal:{entry_str}")
    return tuple(violations)


def analyze_execution_plan(*, manifest: SandboxManifest, policy: SandboxPolicy) -> dict[str, Any]:
    """Return deterministic preflight verdict for execution plan safety."""
    violations: list[str] = []
    command = tuple(str(item) for item in manifest.command)

    if not command:
        violations.append("missing_command")
    for token in command:
        violations.extend(_validate_command_token(token))
    for key, _ in manifest.env:
        if key in _DISALLOWED_ENV_KEYS:
            violations.append(f"disallowed_env:{key}")

    # H-03: validate write-path allowlist entries before processing mounts.
    violations.extend(_validate_write_allowlist(policy.write_path_allowlist))

    allowed_write_roots = tuple(PurePosixPath(root) for root in policy.write_path_allowlist)
    for mount in manifest.mounts:
        if isinstance(mount, (list, tuple)) and len(mount) == 2:
            target = str(mount[1])
        else:
            target = str(mount)
        normalized_target = PurePosixPath(target)
        if not any(normalized_target == root or root in normalized_target.parents for root in allowed_write_roots):
            violations.append(f"disallowed_mount_target:{target}")

    return {
        "ok": not violations,
        "reason": "ok" if not violations else violations[0],
        "violations": tuple(violations),
        "checks": {
            "command": command,
            "env_keys": tuple(key for key, _ in manifest.env),
            "mount_count": len(manifest.mounts),
        },
    }


__all__ = ["analyze_execution_plan"]
