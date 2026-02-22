# SPDX-License-Identifier: Apache-2.0
"""Deterministic replay proof bundle generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from runtime.constitution import CONSTITUTION_VERSION


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def generate_proof_bundle(epoch_id: str, *, ledger_path: Path | None = None) -> Dict[str, Any]:
    ledger = ledger_path or Path("security/ledger/lineage_v2.jsonl")
    lines = [line.strip() for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()] if ledger.exists() else []
    entries = [json.loads(line) for line in lines]
    baseline_digest = _digest({"epoch_id": epoch_id, "seed": "foundation"})
    ledger_state_hash = _digest(entries)
    mutation_graph_fingerprint = _digest([str((entry.get("payload") or {}).get("mutation_id") or "") for entry in entries])
    bundle = {
        "epoch_id": epoch_id,
        "baseline_digest": baseline_digest,
        "ledger_state_hash": ledger_state_hash,
        "mutation_graph_fingerprint": mutation_graph_fingerprint,
        "constitution_version": CONSTITUTION_VERSION,
    }
    bundle["bundle_hash"] = _digest(bundle)
    return bundle


__all__ = ["generate_proof_bundle"]
