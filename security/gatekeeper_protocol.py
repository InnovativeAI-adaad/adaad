# SPDX-License-Identifier: Apache-2.0
"""
Gatekeeper protocol stub for Phase-2 drift detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List

LOG = logging.getLogger(__name__)

REQUIRED_DIRS = [
    Path("app"),
    Path("runtime"),
    Path("security"),
    Path("security/ledger"),
    Path("security/keys"),
]

MANIFEST_TREES = [
    Path("app"),
    Path("runtime"),
    Path("security"),
]

SCHEMA_VERSION = 2
MANIFEST_VERSION = "gatekeeper_manifest_v2"
MAX_REPORTED_PATHS = 50

LEDGER_HASH_PATH = Path("security/ledger/gate_hash.txt")
LEDGER_SNAPSHOT_PATH = Path("security/ledger/gate_manifest_snapshot.json")
LEDGER_EVENT_PATH = Path("security/ledger/gatekeeper_events.jsonl")

_EXCLUDED_LEDGER_FILES = {
    LEDGER_HASH_PATH.as_posix(),
    LEDGER_SNAPSHOT_PATH.as_posix(),
    LEDGER_EVENT_PATH.as_posix(),
}


def _should_exclude(path: Path) -> bool:
    # Exclude dotfiles and .gitkeep placeholders to avoid false positives from
    # local/editor metadata and empty-directory sentinels.
    if path.name.startswith(".") or path.name.endswith(".gitkeep"):
        return True
    # Exclude the digest persistence artifact from the security tree to avoid
    # self-referential hash churn across runs.
    return path.as_posix() in _EXCLUDED_LEDGER_FILES


def _tree_manifest(tree_root: Path) -> List[Dict[str, str]]:
    manifest: List[Dict[str, str]] = []
    for p in sorted(tree_root.rglob("*")):
        if p.is_dir() or _should_exclude(p):
            continue
        rel_path = p.relative_to(tree_root.parent).as_posix()
        file_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest.append({"path": rel_path, "sha256": file_hash})
    return sorted(manifest, key=lambda item: item["path"])


def _tree_subhash(tree_root: Path) -> str:
    manifest_payload = json.dumps(_tree_manifest(tree_root), sort_keys=True)
    return hashlib.sha256(manifest_payload.encode("utf-8")).hexdigest()


def _build_manifest_snapshot() -> Dict[str, str]:
    snapshot: Dict[str, str] = {}
    for tree_root in MANIFEST_TREES:
        for item in _tree_manifest(tree_root):
            snapshot[item["path"]] = item["sha256"]
    return dict(sorted(snapshot.items()))


def _compute_drift(prev_snapshot: Dict[str, str], curr_snapshot: Dict[str, str]) -> Dict[str, object]:
    prev_paths = set(prev_snapshot)
    curr_paths = set(curr_snapshot)
    added_paths = sorted(curr_paths - prev_paths)
    removed_paths = sorted(prev_paths - curr_paths)
    changed_paths = sorted(path for path in (curr_paths & prev_paths) if prev_snapshot[path] != curr_snapshot[path])

    return {
        "added_count": len(added_paths),
        "removed_count": len(removed_paths),
        "changed_count": len(changed_paths),
        "added_paths": added_paths[:MAX_REPORTED_PATHS],
        "removed_paths": removed_paths[:MAX_REPORTED_PATHS],
        "changed_paths": changed_paths[:MAX_REPORTED_PATHS],
    }


def _write_ledger_event(event_payload: Dict[str, object]) -> None:
    entry = json.dumps(event_payload, sort_keys=True)
    with LEDGER_EVENT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{entry}\n")


def run_gatekeeper() -> Dict[str, object]:
    missing: List[str] = []
    for path in REQUIRED_DIRS:
        if not path.exists():
            missing.append(str(path))

    sub_hashes = {
        tree_root.as_posix(): _tree_subhash(tree_root)
        for tree_root in MANIFEST_TREES
    }
    ordered_subhash_material = "\n".join(
        f"{tree_name}:{sub_hashes[tree_name]}" for tree_name in sorted(sub_hashes)
    )
    digest = hashlib.sha256(ordered_subhash_material.encode("utf-8")).hexdigest()
    manifest_snapshot = _build_manifest_snapshot()
    prev = LEDGER_HASH_PATH.read_text(encoding="utf-8").strip() if LEDGER_HASH_PATH.exists() else None

    prev_snapshot: Dict[str, str] = {}
    snapshot_load_error = None
    if LEDGER_SNAPSHOT_PATH.exists():
        try:
            loaded_snapshot = json.loads(LEDGER_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded_snapshot, dict):
                prev_snapshot = {str(path): str(file_hash) for path, file_hash in loaded_snapshot.items()}
        except (JSONDecodeError, OSError, ValueError) as exc:
            snapshot_load_error = f"{type(exc).__name__}: {exc}"
            LOG.warning(
                "gatekeeper snapshot load failed",
                extra={
                    "reason_code": "snapshot_load_failed",
                    "error_type": type(exc).__name__,
                    "path": str(LEDGER_SNAPSHOT_PATH),
                },
            )

    drift_report = _compute_drift(prev_snapshot, manifest_snapshot)
    has_snapshot_baseline = bool(prev_snapshot)
    drift = (
        (drift_report["added_count"] + drift_report["removed_count"] + drift_report["changed_count"]) > 0
        if has_snapshot_baseline
        else prev is not None and prev != digest
    )

    provenance = {
        "changed_count": drift_report["changed_count"],
        "sample_changed_paths": drift_report["changed_paths"][:10],
        "manifest_version": MANIFEST_VERSION,
    }

    persistence_error = snapshot_load_error
    persistence_reason_code = "snapshot_load_failed" if snapshot_load_error else None
    try:
        LEDGER_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_HASH_PATH.write_text(digest, encoding="utf-8")
        LEDGER_SNAPSHOT_PATH.write_text(
            json.dumps(manifest_snapshot, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _write_ledger_event(
            {
                "event": "gatekeeper_result",
                "schema_version": SCHEMA_VERSION,
                "drift": drift,
                "hash": digest,
                "manifest_version": MANIFEST_VERSION,
                "provenance": provenance,
                "drift_report": drift_report,
            }
        )
    except OSError as exc:
        persistence_error = f"{type(exc).__name__}: {exc}"
        persistence_reason_code = "hash_persist_failed"
        LOG.error(
            "gatekeeper persistence failed",
            extra={
                "reason_code": persistence_reason_code,
                "operation_class": "governance-critical",
                "path": str(LEDGER_HASH_PATH),
                "error_type": type(exc).__name__,
            },
        )

    reasons: List[str] = []
    if missing:
        reasons.append("missing_paths")
    if drift:
        reasons.append("drift_detected")
    if persistence_error:
        reasons.append("hash_persist_failed")

    ok = not reasons
    payload = {
        "ok": ok,
        "missing": missing,
        "hash": digest,
        "sub_hashes": sub_hashes,
        "persistence_error": persistence_error,
        "persistence_reason_code": persistence_reason_code,
        "reasons": reasons,
        "schema_version": SCHEMA_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "provenance": provenance,
    }
    if drift:
        payload["drift"] = True
        payload["drift_report"] = drift_report
    return payload


__all__ = ["run_gatekeeper"]
