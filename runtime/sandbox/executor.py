# SPDX-License-Identifier: Apache-2.0
"""Hardened sandbox execution wrapper for test runs."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
import subprocess
from typing import Any, Sequence

from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider
from runtime.governance.resource_accounting import coalesce_resource_usage_snapshot
from runtime.governance.validators.resource_bounds import (
    ResourceBoundsExceeded,
    ResourceLimitEvent,
    _read_limit_with_deprecated_alias,
)
from runtime.sandbox.environment_snapshot import capture_post_execution_delta, collect_pre_execution_snapshot
from runtime.sandbox.evidence import SandboxEvidenceLedger, build_sandbox_evidence, sign_bundle
from runtime.sandbox.fs_rules import enforce_write_path_allowlist
from runtime.sandbox.isolation import ContainerIsolationBackend, IsolationBackend, ProcessIsolationBackend
from runtime.sandbox.manifest import SandboxManifest, validate_manifest
from runtime.sandbox.network_rules import enforce_network_egress_allowlist
from runtime.sandbox.policy import SandboxPolicy, default_sandbox_policy, validate_policy
from runtime.sandbox.preflight import analyze_execution_plan
from runtime.sandbox.resources import enforce_resource_quotas
from runtime.sandbox.syscall_filter import enforce_syscall_allowlist_with_fingerprint
from runtime.test_sandbox import TestSandbox, TestSandboxResult
from security.ledger import journal


class SandboxTimeoutError(RuntimeError):
    """Raised when sandbox execution exceeds configured timeout limits."""


def _is_sandbox_tier() -> bool:
    tier = str(os.getenv("ADAAD_FORCE_TIER") or "SANDBOX").strip().upper()
    return tier == "SANDBOX"


def _container_rollout_enabled() -> bool:
    raw = str(os.getenv("ADAAD_SANDBOX_CONTAINER_ROLLOUT") or "").strip().lower()
    return raw in {"1", "true", "on", "docker"}


def _default_isolation_backend() -> IsolationBackend:
    if _is_sandbox_tier() and _container_rollout_enabled():
        return ContainerIsolationBackend(
            runtime_profile_id=str(os.getenv("ADAAD_SANDBOX_CONTAINER_RUNTIME_PROFILE") or ""),
            seccomp_profile_id=str(os.getenv("ADAAD_SANDBOX_CONTAINER_SECCOMP_PROFILE") or ""),
            network_profile_id=str(os.getenv("ADAAD_SANDBOX_CONTAINER_NETWORK_PROFILE") or ""),
            write_path_profile_id=str(os.getenv("ADAAD_SANDBOX_CONTAINER_WRITE_PROFILE") or ""),
            resource_profile_id=str(os.getenv("ADAAD_SANDBOX_CONTAINER_RESOURCE_PROFILE") or ""),
            container_image=str(os.getenv("ADAAD_SANDBOX_CONTAINER_IMAGE") or "python:3.11-slim"),
        )
    return ProcessIsolationBackend()


def _configured_sandbox_timeout_seconds(default: int = 30) -> int:
    raw = str(os.getenv("ADAAD_SANDBOX_TIMEOUT_SECONDS", str(default))).strip()
    try:
        timeout_s = int(float(raw))
    except (TypeError, ValueError):
        return default
    return timeout_s if timeout_s > 0 else default


def _compute_code_hash(manifest: SandboxManifest) -> str:
    code_bytes = "\x00".join(manifest.command).encode("utf-8")
    return hashlib.sha256(code_bytes).hexdigest()


class HardenedSandboxExecutor:
    def __init__(
        self,
        test_sandbox: TestSandbox,
        *,
        policy: SandboxPolicy | None = None,
        provider: RuntimeDeterminismProvider | None = None,
        isolation_backend: IsolationBackend | None = None,
    ) -> None:
        self.test_sandbox = test_sandbox
        self.policy = policy or default_sandbox_policy()
        self.provider = provider or default_provider()
        self.isolation_backend = isolation_backend or _default_isolation_backend()
        self.evidence_ledger = SandboxEvidenceLedger()
        self.last_evidence_hash = ""
        self.last_evidence_payload: dict[str, object] = {}

    def _build_end_payload(
        self,
        *,
        manifest: SandboxManifest,
        mutation_id: str,
        epoch_id: str,
        replay_seed: str,
        duration_s: float,
        peak_memory_mb: float,
        status: str,
    ) -> dict[str, object]:
        return {
            "mutation_id": mutation_id,
            "epoch_id": epoch_id,
            "replay_seed": replay_seed,
            "status": status,
            "timeout_s": manifest.timeout_s,
            "duration_s": float(duration_s),
            "peak_memory_mb": float(peak_memory_mb),
            "code_hash": _compute_code_hash(manifest),
            "completed_at": self.provider.iso_now(),
        }

    def _emit_end_event(self, *, payload: dict[str, object]) -> None:
        journal.append_tx(tx_type="sandbox_execution_end.v1", payload=payload)

    def _record_evidence(
        self,
        *,
        manifest: SandboxManifest,
        result_payload: dict[str, Any],
        syscall_fingerprint: str,
        syscall_trace: tuple[str, ...],
        isolation_mode: str,
        enforced_controls: tuple[dict[str, Any], ...],
        preflight: dict[str, Any],
        events: tuple[dict[str, Any], ...],
        runtime_telemetry: dict[str, Any],
        replay_environment_fingerprint: dict[str, Any],
        replay_diagnostics: dict[str, Any],
    ) -> None:
        evidence_payload = build_sandbox_evidence(
            manifest=manifest.to_dict(),
            result=result_payload,
            policy_hash=self.policy.policy_hash,
            sandbox_policy_hash=self.policy.policy_hash,
            syscall_trace=syscall_trace,
            syscall_fingerprint=syscall_fingerprint,
            provider_ts=self.provider.iso_now(),
            isolation_mode=isolation_mode,
            enforced_controls=enforced_controls,
            preflight=preflight,
            events=events,
            runtime_telemetry=runtime_telemetry,
            replay_environment_fingerprint=replay_environment_fingerprint,
            replay_diagnostics=capture_post_execution_delta(replay_environment_fingerprint),
        )
        signed_payload = sign_bundle(
            evidence_payload,
            metadata={"policy_hash": self.policy.policy_hash, "provider_ts": evidence_payload["timestamp"]},
        )
        entry = self.evidence_ledger.append(signed_payload)
        self.last_evidence_payload = dict(signed_payload)
        self.last_evidence_hash = str((entry.get("payload") or {}).get("evidence_hash") or "")

    def run_tests_with_retry(
        self,
        *,
        mutation_id: str,
        epoch_id: str,
        replay_seed: str,
        args: Sequence[str] | None = None,
        retries: int = 1,
    ) -> TestSandboxResult:
        manifest = SandboxManifest(
            mutation_id=mutation_id,
            epoch_id=epoch_id,
            replay_seed=replay_seed,
            command=tuple(str(arg) for arg in (args or ["-x", "--tb=short"])),
            env=(("PYTHONDONTWRITEBYTECODE", "1"),),
            mounts=(),
            allowed_write_paths=self.policy.write_path_allowlist,
            allowed_network_hosts=self.policy.network_egress_allowlist,
            cpu_seconds=self.policy.cpu_seconds,
            memory_mb=self.policy.memory_mb,
            disk_mb=self.policy.disk_mb,
            timeout_s=_configured_sandbox_timeout_seconds(self.policy.timeout_s),
            deterministic_clock=True,
            deterministic_random=True,
        )
        validate_manifest(manifest)
        validate_policy(self.policy)

        pre_execution_snapshot = collect_pre_execution_snapshot(manifest.to_dict())

        preflight = analyze_execution_plan(manifest=manifest, policy=self.policy)
        if not preflight.get("ok"):
            raise RuntimeError(f"sandbox_preflight_violation:{preflight.get('reason', 'unknown')}")

        isolation_preparation = self.isolation_backend.prepare(manifest=manifest, policy=self.policy)
        if any(not control.enforced for control in isolation_preparation.controls):
            raise RuntimeError("sandbox_policy_unenforceable:control_not_enforced")

        execution_started_at = self.provider.iso_now()
        journal.append_tx(
            tx_type="sandbox_execution_start.v1",
            payload={
                "mutation_id": mutation_id,
                "epoch_id": epoch_id,
                "replay_seed": replay_seed,
                "timeout_s": manifest.timeout_s,
                "started_at": execution_started_at,
            },
        )

        try:
            result = self.isolation_backend.run(test_sandbox=self.test_sandbox, manifest=manifest, args=args, retries=retries)
        except subprocess.TimeoutExpired as exc:
            timeout_payload = self._build_end_payload(
                manifest=manifest,
                mutation_id=mutation_id,
                epoch_id=epoch_id,
                replay_seed=replay_seed,
                duration_s=float(manifest.timeout_s),
                peak_memory_mb=0.0,
                status="timeout",
            )
            journal.append_tx(tx_type="sandbox_timeout.v1", payload=timeout_payload)
            self._emit_end_event(payload=timeout_payload)
            raise SandboxTimeoutError(f"sandbox_timeout:{manifest.timeout_s}s") from exc

        result_payload = asdict(result)
        runtime_telemetry = dict(getattr(self.isolation_backend, "last_runtime_telemetry", {}) or {})
        runtime_telemetry.setdefault("syscall_validation", "telemetry_allowlist")
        runtime_telemetry.setdefault("syscall_validation_enforced_in_kernel", False)
        runtime_telemetry.setdefault("hard_isolation", isolation_preparation.mode == "container")
        runtime_telemetry.setdefault("hard_isolation_namespaces", isolation_preparation.mode == "container")
        runtime_telemetry.setdefault("hard_isolation_cgroups", isolation_preparation.mode == "container")

        max_wall = float(manifest.timeout_s)
        max_memory = float(
            _read_limit_with_deprecated_alias(
                canonical_env="ADAAD_RESOURCE_MEMORY_MB",
                deprecated_alias_env="ADAAD_MAX_MEMORY_MB",
                default=str(manifest.memory_mb),
                caster=float,
            )
        )
        if result.status.value == "timeout" or float(result.duration_s) > max_wall:
            timeout_payload = self._build_end_payload(
                manifest=manifest,
                mutation_id=mutation_id,
                epoch_id=epoch_id,
                replay_seed=replay_seed,
                duration_s=float(result.duration_s),
                peak_memory_mb=float(result.memory_mb or 0.0),
                status="timeout",
            )
            journal.append_tx(tx_type="sandbox_timeout.v1", payload=timeout_payload)
            self._emit_end_event(payload=timeout_payload)
            raise SandboxTimeoutError("sandbox_timeout_exceeded")
        if float(result.memory_mb or 0.0) > max_memory:
            self._emit_end_event(
                payload=self._build_end_payload(
                    manifest=manifest,
                    mutation_id=mutation_id,
                    epoch_id=epoch_id,
                    replay_seed=replay_seed,
                    duration_s=float(result.duration_s),
                    peak_memory_mb=float(result.memory_mb or 0.0),
                    status="resource_bounds_exceeded",
                )
            )
            raise ResourceBoundsExceeded(
                "resource_bounds_exceeded:memory",
                event=ResourceLimitEvent(
                    event="resource_bounds_exceeded",
                    resource="memory_mb",
                    limit=max_memory,
                    observed=float(result.memory_mb or 0.0),
                ),
            )
        result_payload["disk_mb"] = 0.0
        result_payload["resource_bounds_snapshot"] = coalesce_resource_usage_snapshot(
            observed=result_payload, telemetry=result_payload
        )

        if not result.observed_syscalls:
            self._record_evidence(
                manifest=manifest,
                result_payload=result_payload,
                syscall_fingerprint="",
                syscall_trace=(),
                isolation_mode=isolation_preparation.mode,
                enforced_controls=tuple(asdict(control) for control in isolation_preparation.controls),
                preflight=preflight,
                events=(
                    {
                        "event": "sandbox_integrity_violation",
                        "violation_type": "missing_syscall_telemetry",
                        "fail_closed": True,
                    },
                ),
                runtime_telemetry=runtime_telemetry,
                replay_environment_fingerprint=pre_execution_snapshot,
                replay_diagnostics=capture_post_execution_delta(pre_execution_snapshot),
            )
            self._emit_end_event(
                payload=self._build_end_payload(
                    manifest=manifest,
                    mutation_id=mutation_id,
                    epoch_id=epoch_id,
                    replay_seed=replay_seed,
                    duration_s=float(result.duration_s),
                    peak_memory_mb=float(result.memory_mb or 0.0),
                    status="missing_syscall_telemetry",
                )
            )
            raise RuntimeError("sandbox_missing_syscall_telemetry")

        syscall_ok, denied_syscalls, syscall_fingerprint = enforce_syscall_allowlist_with_fingerprint(
            result.observed_syscalls, self.policy.syscall_allowlist
        )
        if not syscall_ok:
            self._record_evidence(
                manifest=manifest,
                result_payload=result_payload,
                syscall_fingerprint=syscall_fingerprint,
                syscall_trace=result.observed_syscalls,
                isolation_mode=isolation_preparation.mode,
                enforced_controls=tuple(asdict(control) for control in isolation_preparation.controls),
                preflight=preflight,
                events=(
                    {
                        "event": "sandbox_integrity_violation",
                        "violation_type": "syscall_allowlist",
                        "details": list(denied_syscalls),
                        "fail_closed": True,
                    },
                ),
                runtime_telemetry=runtime_telemetry,
                replay_environment_fingerprint=pre_execution_snapshot,
                replay_diagnostics=capture_post_execution_delta(pre_execution_snapshot),
            )
            self._emit_end_event(
                payload=self._build_end_payload(
                    manifest=manifest,
                    mutation_id=mutation_id,
                    epoch_id=epoch_id,
                    replay_seed=replay_seed,
                    duration_s=float(result.duration_s),
                    peak_memory_mb=float(result.memory_mb or 0.0),
                    status="syscall_violation",
                )
            )
            raise RuntimeError(f"sandbox_syscall_violation:{','.join(denied_syscalls)}")

        write_ok, write_violations = enforce_write_path_allowlist(result.attempted_write_paths, manifest.allowed_write_paths)
        if not write_ok:
            self._record_evidence(
                manifest=manifest,
                result_payload=result_payload,
                syscall_fingerprint=syscall_fingerprint,
                syscall_trace=result.observed_syscalls,
                isolation_mode=isolation_preparation.mode,
                enforced_controls=tuple(asdict(control) for control in isolation_preparation.controls),
                preflight=preflight,
                events=(
                    {
                        "event": "sandbox_integrity_violation",
                        "violation_type": "write_path_allowlist",
                        "details": list(write_violations),
                        "fail_closed": True,
                    },
                ),
                runtime_telemetry=runtime_telemetry,
                replay_environment_fingerprint=pre_execution_snapshot,
                replay_diagnostics=capture_post_execution_delta(pre_execution_snapshot),
            )
            self._emit_end_event(
                payload=self._build_end_payload(
                    manifest=manifest,
                    mutation_id=mutation_id,
                    epoch_id=epoch_id,
                    replay_seed=replay_seed,
                    duration_s=float(result.duration_s),
                    peak_memory_mb=float(result.memory_mb or 0.0),
                    status="write_path_violation",
                )
            )
            raise RuntimeError(f"sandbox_write_path_violation:{','.join(write_violations)}")

        network_ok, network_violations = enforce_network_egress_allowlist(
            result.attempted_network_hosts,
            manifest.allowed_network_hosts,
            dns_resolution_allowed=self.policy.dns_resolution_allowed,
        )
        if not network_ok:
            self._record_evidence(
                manifest=manifest,
                result_payload=result_payload,
                syscall_fingerprint=syscall_fingerprint,
                syscall_trace=result.observed_syscalls,
                isolation_mode=isolation_preparation.mode,
                enforced_controls=tuple(asdict(control) for control in isolation_preparation.controls),
                preflight=preflight,
                events=(
                    {
                        "event": "sandbox_integrity_violation",
                        "violation_type": "network_egress_allowlist",
                        "details": list(network_violations),
                        "fail_closed": True,
                    },
                ),
                runtime_telemetry=runtime_telemetry,
                replay_environment_fingerprint=pre_execution_snapshot,
                replay_diagnostics=capture_post_execution_delta(pre_execution_snapshot),
            )
            self._emit_end_event(
                payload=self._build_end_payload(
                    manifest=manifest,
                    mutation_id=mutation_id,
                    epoch_id=epoch_id,
                    replay_seed=replay_seed,
                    duration_s=float(result.duration_s),
                    peak_memory_mb=float(result.memory_mb or 0.0),
                    status="network_violation",
                )
            )
            raise RuntimeError(f"sandbox_network_violation:{','.join(network_violations)}")

        resource_verdict = enforce_resource_quotas(
            observed_cpu_s=result.duration_s,
            observed_memory_mb=float(result.memory_mb or 0.0),
            observed_disk_mb=0.0,
            observed_duration_s=result.duration_s,
            cpu_limit_s=manifest.cpu_seconds,
            memory_limit_mb=manifest.memory_mb,
            disk_limit_mb=manifest.disk_mb,
            timeout_s=manifest.timeout_s,
        )
        if not resource_verdict["passed"]:
            self._record_evidence(
                manifest=manifest,
                result_payload=result_payload,
                syscall_fingerprint=syscall_fingerprint,
                syscall_trace=result.observed_syscalls,
                isolation_mode=isolation_preparation.mode,
                enforced_controls=tuple(asdict(control) for control in isolation_preparation.controls),
                preflight=preflight,
                events=(
                    {
                        "event": "sandbox_integrity_violation",
                        "violation_type": "resource_quota",
                        "details": dict(resource_verdict),
                        "fail_closed": True,
                    },
                ),
                runtime_telemetry=runtime_telemetry,
                replay_environment_fingerprint=pre_execution_snapshot,
                replay_diagnostics=capture_post_execution_delta(pre_execution_snapshot),
            )
            self._emit_end_event(
                payload=self._build_end_payload(
                    manifest=manifest,
                    mutation_id=mutation_id,
                    epoch_id=epoch_id,
                    replay_seed=replay_seed,
                    duration_s=float(result.duration_s),
                    peak_memory_mb=float(result.memory_mb or 0.0),
                    status="resource_quota_violation",
                )
            )
            raise RuntimeError("sandbox_resource_quota_violation")

        self._record_evidence(
            manifest=manifest,
            result_payload=result_payload,
            syscall_fingerprint=syscall_fingerprint,
            syscall_trace=result.observed_syscalls,
            isolation_mode=isolation_preparation.mode,
            enforced_controls=tuple(asdict(control) for control in isolation_preparation.controls),
            preflight=preflight,
            events=(
                {
                    "event": "sandbox_integrity_verified",
                    "status": "ok",
                },
            ),
            runtime_telemetry=runtime_telemetry,
            replay_environment_fingerprint=pre_execution_snapshot,
            replay_diagnostics=capture_post_execution_delta(pre_execution_snapshot),
        )

        peak_memory_mb = max(
            float(result.memory_mb or 0.0),
            float(((runtime_telemetry.get("resource_usage") or {}).get("memory_mb") or 0.0)),
        )
        self._emit_end_event(
            payload=self._build_end_payload(
                manifest=manifest,
                mutation_id=mutation_id,
                epoch_id=epoch_id,
                replay_seed=replay_seed,
                duration_s=float(result.duration_s),
                peak_memory_mb=peak_memory_mb,
                status="ok",
            )
        )
        return result


__all__ = ["HardenedSandboxExecutor", "SandboxTimeoutError"]
