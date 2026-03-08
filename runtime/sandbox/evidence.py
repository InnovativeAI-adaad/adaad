# SPDX-License-Identifier: Apache-2.0
"""Sandbox evidence generation and append-only ledger."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping

from runtime import ROOT_DIR
from runtime.governance.foundation import ZERO_HASH, canonical_json, sha256_prefixed_digest
from runtime.governance.resource_accounting import coalesce_resource_usage_snapshot
from runtime.sandbox.syscall_filter import syscall_trace_fingerprint

SANDBOX_EVIDENCE_PATH = ROOT_DIR / "security" / "ledger" / "sandbox_evidence.jsonl"
_DEFAULT_DEV_SIGNING_KEY = "adaad-dev-evidence-signing-key"


def _control_capability_flags(control: Mapping[str, Any]) -> Dict[str, bool | str]:
    mechanism = str(control.get("mechanism") or "")
    simulated = bool(control.get("simulated"))
    enforced = bool(control.get("enforced"))

    enforced_in_kernel = mechanism in {
        "docker_seccomp",
        "docker_cgroup_limits",
        "docker_network",
        "docker_readonly_mounts",
    }
    observed_only = simulated or mechanism == "seccomp"
    best_effort = enforced and not enforced_in_kernel and not observed_only

    mode = "simulated/observed-only" if observed_only else ("enforced_in-kernel" if enforced_in_kernel else "best-effort")
    return {
        "enforced_in_kernel": enforced_in_kernel,
        "best_effort": best_effort,
        "simulated_or_observed_only": observed_only,
        "mode": mode,
    }


def _augment_controls_with_capabilities(enforced_controls: tuple[Dict[str, Any], ...]) -> list[Dict[str, Any]]:
    controls: list[Dict[str, Any]] = []
    for raw in enforced_controls:
        item = dict(raw)
        item["capability_flags"] = _control_capability_flags(item)
        controls.append(item)
    return controls


def _signing_key_bytes() -> bytes:
    return str(os.getenv("ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY") or _DEFAULT_DEV_SIGNING_KEY).encode("utf-8")


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return canonical_json(dict(payload)).encode("utf-8")


def sign_bundle(payload: Mapping[str, Any], *, metadata: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Return a deterministically signed evidence payload.

    Invariants:
    - signature excludes the `signed_digest` field itself.
    - canonical JSON ordering is preserved by `canonical_json`.
    """

    bundle = dict(payload)
    bundle.pop("signed_digest", None)
    if metadata is not None:
        bundle["signature_metadata"] = dict(metadata)
    digest = hmac.new(_signing_key_bytes(), _canonical_bytes(bundle), hashlib.sha256).hexdigest()
    bundle["signed_digest"] = f"sha256:{digest}"
    return bundle


def verify_bundle_signature(payload: Mapping[str, Any]) -> bool:
    observed = str(payload.get("signed_digest") or "")
    if not observed.startswith("sha256:"):
        return False
    expected = sign_bundle(payload).get("signed_digest")
    return hmac.compare_digest(observed, str(expected))


def build_sandbox_evidence(
    *,
    manifest: Dict[str, Any],
    result: Dict[str, Any],
    policy_hash: str,
    sandbox_policy_hash: str | None = None,
    syscall_trace: tuple[str, ...] = (),
    syscall_fingerprint: str | None = None,
    provider_ts: str,
    isolation_mode: str = "process",
    enforced_controls: tuple[Dict[str, Any], ...] = (),
    preflight: Dict[str, Any] | None = None,
    events: tuple[Dict[str, Any], ...] = (),
    runtime_telemetry: Mapping[str, Any] | None = None,
    replay_environment_fingerprint: Mapping[str, Any] | None = None,
    replay_diagnostics: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a canonical sandbox evidence payload for ledger persistence.

    Replay invariants:
    - `manifest_hash == sha256(manifest)`
    - `stdout_hash == sha256(stdout)`
    - `stderr_hash == sha256(stderr)`
    - `syscall_trace_hash == sha256(syscall_trace)`
    - `resource_usage_hash == sha256(resource_usage)`
    """
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    trace = tuple(str(item) for item in syscall_trace)
    resource_usage = coalesce_resource_usage_snapshot(observed=result, telemetry=result)
    deterministic_runtime_telemetry = json.loads(canonical_json(dict(runtime_telemetry or {})))
    deterministic_replay_environment = json.loads(canonical_json(dict(replay_environment_fingerprint or {})))
    deterministic_replay_diagnostics = json.loads(canonical_json(dict(replay_diagnostics or {})))
    payload = {
        "manifest_hash": sha256_prefixed_digest(manifest),
        "policy_hash": policy_hash,
        "sandbox_policy_hash": sandbox_policy_hash or policy_hash,
        "stdout": stdout,
        "stdout_hash": sha256_prefixed_digest(stdout),
        "stderr": stderr,
        "stderr_hash": sha256_prefixed_digest(stderr),
        "syscall_trace": list(trace),
        "syscall_trace_hash": sha256_prefixed_digest(list(trace)),
        "syscall_fingerprint": syscall_fingerprint or syscall_trace_fingerprint(trace),
        "resource_usage": resource_usage,
        "resource_usage_hash": sha256_prefixed_digest(resource_usage),
        "exit_code": result.get("returncode"),
        "replay_seed": str(manifest.get("replay_seed") or ""),
        "timestamp": provider_ts,
        "manifest": dict(manifest),
        "isolation_mode": isolation_mode,
        "enforced_controls": _augment_controls_with_capabilities(enforced_controls),
        "preflight": dict(preflight or {"ok": True, "reason": "not_provided"}),
        "events": [dict(item) for item in events],
        "runtime_telemetry": deterministic_runtime_telemetry,
        "runtime_telemetry_hash": sha256_prefixed_digest(deterministic_runtime_telemetry),
        "replay_environment_fingerprint": deterministic_replay_environment,
        "replay_environment_fingerprint_hash": sha256_prefixed_digest(deterministic_replay_environment),
        "runtime_version_hash": sha256_prefixed_digest(str(deterministic_replay_environment.get("runtime_version") or "")),
        "runtime_toolchain_fingerprint_hash": sha256_prefixed_digest(
            str(deterministic_replay_environment.get("runtime_toolchain_fingerprint") or "")
        ),
        "dependency_lock_digest_hash": sha256_prefixed_digest(
            str(deterministic_replay_environment.get("dependency_lock_digest") or "")
        ),
        "env_whitelist_digest_hash": sha256_prefixed_digest(
            str(deterministic_replay_environment.get("env_whitelist_digest") or "")
        ),
        "container_profile_digest_hash": sha256_prefixed_digest(
            str(deterministic_replay_environment.get("container_profile_digest") or "")
        ),
        "filesystem_snapshot_digest_hash": sha256_prefixed_digest(
            str(deterministic_replay_environment.get("filesystem_snapshot_digest") or "")
        ),
        "filesystem_baseline_digest_hash": sha256_prefixed_digest(
            str(deterministic_replay_environment.get("filesystem_baseline_digest") or "")
        ),
        "seed_lineage_hash": sha256_prefixed_digest(dict(deterministic_replay_environment.get("seed_lineage") or {})),
        "replay_diagnostics": deterministic_replay_diagnostics,
        "replay_diagnostics_hash": sha256_prefixed_digest(deterministic_replay_diagnostics),
    }
    payload["evidence_hash"] = sha256_prefixed_digest(payload)
    return payload


class SandboxEvidenceLedger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or SANDBOX_EVIDENCE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def _last_hash(self) -> str:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return ZERO_HASH
        last = json.loads(lines[-1])
        return str(last.get("hash") or ZERO_HASH)

    def append(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prev_hash = self._last_hash()
        entry = {"payload": dict(payload), "prev_hash": prev_hash}
        entry["hash"] = sha256_prefixed_digest(entry)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(entry) + "\n")
        return entry


__all__ = [
    "SANDBOX_EVIDENCE_PATH",
    "SandboxEvidenceLedger",
    "build_sandbox_evidence",
    "sign_bundle",
    "verify_bundle_signature",
]
