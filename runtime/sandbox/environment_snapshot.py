# SPDX-License-Identifier: Apache-2.0
"""Deterministic environment fingerprint collection for replay evidence."""

from __future__ import annotations

from pathlib import Path
import os
import platform
from typing import Any, Dict, Mapping

from runtime import ROOT_DIR
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.foundation import canonical_json, sha256_digest, sha256_prefixed_digest


_DEPENDENCY_LOCK_CANDIDATES = (
    "requirements.lock",
    "requirements.txt",
    "poetry.lock",
    "Pipfile.lock",
    "pyproject.toml",
)

_ENV_WHITELIST_KEYS = (
    "ADAAD_ENV",
    "ADAAD_FORCE_DETERMINISTIC_PROVIDER",
    "ADAAD_DETERMINISTIC_SEED",
    "ADAAD_REPLAY_MODE",
    "CRYOVANT_DEV_MODE",
    "PYTHONHASHSEED",
)


def _digest_file(path: Path) -> str:
    return "sha256:" + sha256_digest(read_file_deterministic(path))


def _dependency_lock_digest() -> str:
    digests: Dict[str, str] = {}
    for relative in _DEPENDENCY_LOCK_CANDIDATES:
        target = ROOT_DIR / relative
        if target.exists() and target.is_file():
            digests[relative] = _digest_file(target)
    return sha256_prefixed_digest(digests)


def _container_profile_digest() -> str:
    profile_dir = ROOT_DIR / "runtime" / "sandbox" / "container_profiles"
    fingerprints: Dict[str, str] = {}
    if profile_dir.exists():
        for profile in sorted(profile_dir.glob("*.json")):
            fingerprints[profile.name] = _digest_file(profile)
    return sha256_prefixed_digest(fingerprints)


def _runtime_toolchain_fingerprint() -> str:
    toolchain = {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "python_build": list(platform.python_build()),
        "python_compiler": platform.python_compiler(),
        "platform": platform.platform(),
    }
    return sha256_prefixed_digest(toolchain)


def _env_whitelist_digest() -> str:
    env_subset = {key: str(os.getenv(key) or "") for key in _ENV_WHITELIST_KEYS}
    return sha256_prefixed_digest(env_subset)


def _collect_filesystem_state(paths: tuple[str, ...]) -> Dict[str, str]:
    state: Dict[str, str] = {}
    for relative in paths:
        target = ROOT_DIR / relative
        if target.is_file():
            state[relative] = _digest_file(target)
    return state


def collect_pre_execution_snapshot(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    replay_seed = str(manifest.get("replay_seed") or "")
    parent_seed = str(manifest.get("parent_replay_seed") or "")
    tracked_files = tuple(sorted(set(_DEPENDENCY_LOCK_CANDIDATES)))
    filesystem_state = _collect_filesystem_state(tracked_files)
    filesystem_baseline_digest = sha256_prefixed_digest(filesystem_state)
    return {
        "runtime_version": platform.python_version(),
        "runtime_toolchain_fingerprint": _runtime_toolchain_fingerprint(),
        "dependency_lock_digest": _dependency_lock_digest(),
        "env_whitelist_digest": _env_whitelist_digest(),
        "container_profile_digest": _container_profile_digest(),
        "filesystem_snapshot_digest": filesystem_baseline_digest,
        "filesystem_baseline_digest": filesystem_baseline_digest,
        "seed_lineage": {
            "root_seed": parent_seed or replay_seed,
            "parent_seed": parent_seed,
            "current_seed": replay_seed,
        },
        "_tracked_files": list(tracked_files),
        "_filesystem_state": filesystem_state,
    }


def capture_post_execution_delta(pre_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    tracked_files = tuple(str(item) for item in (pre_snapshot.get("_tracked_files") or []))
    before = {
        str(key): str(value)
        for key, value in dict(pre_snapshot.get("_filesystem_state") or {}).items()
        if isinstance(key, str)
    }
    after = _collect_filesystem_state(tracked_files)

    added = sorted(path for path in after.keys() if path not in before)
    removed = sorted(path for path in before.keys() if path not in after)
    modified = sorted(path for path in after.keys() if before.get(path) != after.get(path))

    delta = {
        "added": added,
        "removed": removed,
        "modified": modified,
        "post_filesystem_snapshot_digest": sha256_prefixed_digest(after),
    }
    return json.loads(canonical_json(delta))


__all__ = ["collect_pre_execution_snapshot", "capture_post_execution_delta"]
