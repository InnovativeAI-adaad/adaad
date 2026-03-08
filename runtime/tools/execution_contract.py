# SPDX-License-Identifier: Apache-2.0
"""Unified tool execution contract for deterministic governance gating."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


PASSING_STATUSES = frozenset({"passed"})
TERMINAL_FAILURE_STATUSES = frozenset({"failed", "timeout", "missing_dependency"})


@dataclass(frozen=True)
class ToolExecutionRequest:
    tool_id: str
    check_kind: str
    command: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 300.0
    working_directory: str | None = None
    artifact_pointers: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        return {
            "tool_id": self.tool_id,
            "check_kind": self.check_kind,
            "command": list(self.command),
            "environment": dict(sorted(self.environment.items())),
            "timeout_seconds": self.timeout_seconds,
            "working_directory": self.working_directory,
            "artifact_pointers": dict(sorted(self.artifact_pointers.items())),
        }


@dataclass(frozen=True)
class ToolExecutionResult:
    request: ToolExecutionRequest
    status: str
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: int
    failure_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status in PASSING_STATUSES

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["request"] = self.request.to_payload()
        payload["ok"] = self.ok
        return payload


@dataclass(frozen=True)
class GovernanceToolFinding:
    tool_id: str
    check_kind: str
    status: str
    tier: str
    should_block: bool
    reason_code: str

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


def normalize_tool_output(raw: str, *, max_chars: int = 8000) -> str:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = normalized.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars]


def _resolve_workdir(working_directory: str | None) -> str:
    if working_directory:
        return str(Path(working_directory).resolve())
    return str(Path.cwd())


def execute_tool_request(request: ToolExecutionRequest) -> ToolExecutionResult:
    if not request.command:
        return ToolExecutionResult(
            request=request,
            status="failed",
            returncode=None,
            stdout="",
            stderr="",
            duration_ms=0,
            failure_reason="empty_command",
        )

    command_head = request.command[0]
    if os.sep not in command_head and (os.altsep is None or os.altsep not in command_head):
        if shutil.which(command_head) is None:
            return ToolExecutionResult(
                request=request,
                status="missing_dependency",
                returncode=None,
                stdout="",
                stderr="",
                duration_ms=0,
                failure_reason=f"missing_executable:{command_head}",
            )

    started = time.monotonic()
    env = os.environ.copy()
    env.update(request.environment)

    try:
        completed = subprocess.run(
            list(request.command),
            cwd=_resolve_workdir(request.working_directory),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=request.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return ToolExecutionResult(
            request=request,
            status="timeout",
            returncode=None,
            stdout=normalize_tool_output(exc.stdout or ""),
            stderr=normalize_tool_output(exc.stderr or ""),
            duration_ms=duration_ms,
            failure_reason="timeout",
        )

    duration_ms = int((time.monotonic() - started) * 1000)
    return ToolExecutionResult(
        request=request,
        status="passed" if completed.returncode == 0 else "failed",
        returncode=completed.returncode,
        stdout=normalize_tool_output(completed.stdout),
        stderr=normalize_tool_output(completed.stderr),
        duration_ms=duration_ms,
        failure_reason="" if completed.returncode == 0 else "non_zero_exit",
    )


def _build_request(
    *,
    tool_id: str,
    check_kind: str,
    command: Sequence[str],
    timeout_seconds: float,
    environment: Mapping[str, str] | None = None,
    working_directory: str | None = None,
    artifact_pointers: Mapping[str, str] | None = None,
) -> ToolExecutionRequest:
    return ToolExecutionRequest(
        tool_id=tool_id,
        check_kind=check_kind,
        command=tuple(command),
        timeout_seconds=timeout_seconds,
        environment=dict(environment or {}),
        working_directory=working_directory,
        artifact_pointers=dict(artifact_pointers or {}),
    )


def test_check_request(*, tool_id: str, command: Sequence[str], timeout_seconds: float = 900.0, environment: Mapping[str, str] | None = None, working_directory: str | None = None, artifact_pointers: Mapping[str, str] | None = None) -> ToolExecutionRequest:
    return _build_request(
        tool_id=tool_id,
        check_kind="test",
        command=command,
        timeout_seconds=timeout_seconds,
        environment=environment,
        working_directory=working_directory,
        artifact_pointers=artifact_pointers,
    )


def lint_check_request(*, tool_id: str, command: Sequence[str], timeout_seconds: float = 300.0, environment: Mapping[str, str] | None = None, working_directory: str | None = None, artifact_pointers: Mapping[str, str] | None = None) -> ToolExecutionRequest:
    return _build_request(
        tool_id=tool_id,
        check_kind="lint",
        command=command,
        timeout_seconds=timeout_seconds,
        environment=environment,
        working_directory=working_directory,
        artifact_pointers=artifact_pointers,
    )


def build_check_request(*, tool_id: str, command: Sequence[str], timeout_seconds: float = 1800.0, environment: Mapping[str, str] | None = None, working_directory: str | None = None, artifact_pointers: Mapping[str, str] | None = None) -> ToolExecutionRequest:
    return _build_request(
        tool_id=tool_id,
        check_kind="build",
        command=command,
        timeout_seconds=timeout_seconds,
        environment=environment,
        working_directory=working_directory,
        artifact_pointers=artifact_pointers,
    )


def dependency_check_request(*, tool_id: str, command: Sequence[str], timeout_seconds: float = 300.0, environment: Mapping[str, str] | None = None, working_directory: str | None = None, artifact_pointers: Mapping[str, str] | None = None) -> ToolExecutionRequest:
    return _build_request(
        tool_id=tool_id,
        check_kind="dependency",
        command=command,
        timeout_seconds=timeout_seconds,
        environment=environment,
        working_directory=working_directory,
        artifact_pointers=artifact_pointers,
    )


def classify_tool_result_for_governance(result: ToolExecutionResult) -> GovernanceToolFinding:
    if result.ok:
        return GovernanceToolFinding(
            tool_id=result.request.tool_id,
            check_kind=result.request.check_kind,
            status=result.status,
            tier="advisory",
            should_block=False,
            reason_code="tool_pass",
        )

    block_on_failure_kinds = {"test", "lint", "build"}
    if result.request.check_kind in block_on_failure_kinds:
        return GovernanceToolFinding(
            tool_id=result.request.tool_id,
            check_kind=result.request.check_kind,
            status=result.status,
            tier="block",
            should_block=True,
            reason_code=f"{result.request.check_kind}_{result.status}",
        )

    tier = "warn"
    return GovernanceToolFinding(
        tool_id=result.request.tool_id,
        check_kind=result.request.check_kind,
        status=result.status,
        tier=tier,
        should_block=False,
        reason_code=f"{result.request.check_kind}_{result.status}",
    )


def evaluate_governance_tool_findings(results: Sequence[ToolExecutionResult]) -> dict[str, object]:
    findings = [classify_tool_result_for_governance(result) for result in results]
    block_count = sum(1 for item in findings if item.tier == "block")
    warn_count = sum(1 for item in findings if item.tier == "warn")
    advisory_count = sum(1 for item in findings if item.tier == "advisory")
    return {
        "ok": block_count == 0,
        "highest_tier": "block" if block_count else ("warn" if warn_count else "advisory"),
        "counts": {"block": block_count, "warn": warn_count, "advisory": advisory_count},
        "findings": [item.to_payload() for item in findings],
        "tool_results": [result.to_payload() for result in results],
    }


__all__ = [
    "GovernanceToolFinding",
    "ToolExecutionRequest",
    "ToolExecutionResult",
    "build_check_request",
    "classify_tool_result_for_governance",
    "dependency_check_request",
    "evaluate_governance_tool_findings",
    "execute_tool_request",
    "lint_check_request",
    "normalize_tool_output",
    "test_check_request",
]
