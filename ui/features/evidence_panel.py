# SPDX-License-Identifier: Apache-2.0
"""Evidence panel feature helpers."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from runtime.evolution import EvidenceBundleError


def state_fingerprint(value: Any, json_module: Any) -> str:
    canonical = json_module.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def replay_diff_export(*, epoch_id: str, replay_diff: Any, bundle_builder: Any) -> dict[str, Any]:
    """Compute replay diff and attach evidence bundle export metadata.

    Failure contract (fail-closed):
      - If replay_diff returns ok=False  → propagate as-is (caller's error).
      - If build_bundle raises EvidenceBundleError  → structured error envelope,
        error_class="bundle_export_failed", detail=str(exc).
      - If build_bundle raises any unexpected exception  → re-raise; do not
        silently absorb unknown failures.

    All error envelopes include epoch_id for deterministic audit tracing.
    """
    diff = replay_diff(epoch_id)
    if not diff.get("ok"):
        return diff
    try:
        bundle = bundle_builder.build_bundle(epoch_start=epoch_id, persist=True)
    except EvidenceBundleError as exc:
        # Known, governed failure — return structured error without raising.
        return {
            "ok": False,
            "error": "bundle_export_failed",
            "error_class": "EvidenceBundleError",
            "epoch_id": epoch_id,
            "detail": str(exc),
        }
    # Unknown exceptions propagate — fail-closed, no silent swallowing.
    diff_payload = dict(diff)
    diff_payload["bundle_id"] = bundle.get("bundle_id", "")
    diff_payload["export_metadata"] = bundle.get("export_metadata", {})
    return diff_payload
