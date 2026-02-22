# SPDX-License-Identifier: Apache-2.0
"""
Gatekeeper protocol stub for Phase-2 drift detection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

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


def _should_exclude(path: Path) -> bool:
    # Exclude dotfiles and .gitkeep placeholders to avoid false positives from
    # local/editor metadata and empty-directory sentinels.
    if path.name.startswith(".") or path.name.endswith(".gitkeep"):
        return True
    # Exclude the digest persistence artifact from the security tree to avoid
    # self-referential hash churn across runs.
    return path.as_posix() == "security/ledger/gate_hash.txt"


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
    ledger_hash_file = Path("security/ledger/gate_hash.txt")
    prev = ledger_hash_file.read_text(encoding="utf-8").strip() if ledger_hash_file.exists() else None
    drift = prev is not None and prev != digest

    persistence_error = None
    try:
        ledger_hash_file.parent.mkdir(parents=True, exist_ok=True)
        ledger_hash_file.write_text(digest, encoding="utf-8")
    except Exception as exc:
        persistence_error = f"{type(exc).__name__}: {exc}"

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
        "reasons": reasons,
    }
    if drift:
        payload["drift"] = True
    return payload


__all__ = ["run_gatekeeper"]
