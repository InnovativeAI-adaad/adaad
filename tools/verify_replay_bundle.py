#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline verifier for replay proof bundles."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def verify(bundle_path: Path) -> int:
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    required = ["epoch_id", "baseline_digest", "ledger_state_hash", "mutation_graph_fingerprint", "constitution_version", "bundle_hash"]
    missing = [k for k in required if k not in payload]
    if missing:
        print(f"missing_keys:{','.join(missing)}")
        return 1
    recomputed = dict(payload)
    observed_hash = str(recomputed.pop("bundle_hash"))
    expected_hash = _digest(recomputed)
    if observed_hash != expected_hash:
        print("bundle_hash_mismatch")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_replay_bundle.py <bundle.json>")
    raise SystemExit(verify(Path(sys.argv[1])))
