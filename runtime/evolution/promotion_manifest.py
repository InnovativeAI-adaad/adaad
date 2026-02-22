# SPDX-License-Identifier: Apache-2.0
"""Promotion manifest writer for mutation promotion audit trails."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from runtime import ROOT_DIR
from runtime.evolution.lineage_v2 import LEDGER_V2_PATH, LineageLedgerV2
from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider, require_replay_safe_provider
from runtime.governance.foundation.hashing import ZERO_HASH, sha256_prefixed_digest
from runtime.governance.pr_lifecycle_event_contract import build_event_digest, derive_idempotency_key
from runtime.governance.validators.promotion_contract import validate_promotion_policy_event

PROMOTION_MANIFESTS_DIR = ROOT_DIR / "security" / "promotion_manifests"


def _to_datetime_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def emit_pr_lifecycle_event(
    *,
    policy_version: str,
    evaluation_result: str,
    decision_id: str,
    ledger_path: Path | None = None,
    provider: RuntimeDeterminismProvider | None = None,
    replay_mode: str = "off",
    recovery_tier: str | None = None,
) -> Dict[str, Any]:
    """Emit a promotion policy lifecycle event to the lineage ledger."""

    runtime_provider = provider or default_provider()
    require_replay_safe_provider(runtime_provider, replay_mode=replay_mode, recovery_tier=recovery_tier)

    ledger = LineageLedgerV2(ledger_path or LEDGER_V2_PATH)
    existing_entries = ledger.read_all()

    lifecycle_events: list[Dict[str, Any]] = []
    for entry in existing_entries:
        if entry.get("type") != "PRLifecycleEvent":
            continue
        payload = entry.get("payload")
        if isinstance(payload, dict):
            lifecycle_events.append(payload)

    previous_event_digest = ZERO_HASH
    sequence = 1
    attempt = 1
    if lifecycle_events:
        latest = max(
            lifecycle_events,
            key=lambda event: (_to_datetime_utc(str(event.get("emitted_at") or "1970-01-01T00:00:00Z")), int(event.get("sequence", 0))),
        )
        previous_event_digest = str(latest.get("event_digest") or ZERO_HASH)
        sequence = int(latest.get("sequence", 0)) + 1

        same_key_attempts = [
            int(event.get("attempt", 1))
            for event in lifecycle_events
            if isinstance(event.get("payload"), dict)
            and str(event.get("payload", {}).get("decision_id") or "") == decision_id
        ]
        if same_key_attempts:
            attempt = max(same_key_attempts) + 1

    commit_sha = hashlib.sha1(decision_id.encode("utf-8")).hexdigest()
    pr_number = 1
    idempotency_key = derive_idempotency_key(pr_number=pr_number, commit_sha=commit_sha, event_type="promotion_policy_evaluated")
    event_id = f"prl_{sha256_prefixed_digest(f'{decision_id}:{sequence}:{attempt}').split(':', 1)[1][:16]}"
    emitted_at = runtime_provider.iso_now()
    event: Dict[str, Any] = {
        "schema_version": "1.0",
        "event_id": event_id,
        "event_type": "promotion_policy_evaluated",
        "pr_number": pr_number,
        "commit_sha": commit_sha,
        "idempotency_key": idempotency_key,
        "attempt": attempt,
        "sequence": sequence,
        "emitted_at": emitted_at,
        "correlation_id": f"promotion:{decision_id}",
        "previous_event_digest": previous_event_digest,
        "event_digest": "",
        "payload": {
            "policy_version": str(policy_version),
            "evaluation_result": str(evaluation_result),
            "decision_id": str(decision_id),
        },
    }
    event["event_digest"] = build_event_digest(event)

    validate_promotion_policy_event(event=event, lineage_entries=existing_entries)
    ledger.append_event("PRLifecycleEvent", event)
    return event


class PromotionManifestWriter:
    """Write one JSON manifest per promoted mutation."""

    def __init__(
        self,
        output_dir: Path | None = None,
        provider: RuntimeDeterminismProvider | None = None,
        *,
        replay_mode: str = "off",
        recovery_tier: str | None = None,
    ) -> None:
        self.output_dir = output_dir or PROMOTION_MANIFESTS_DIR
        self.provider = provider or default_provider()
        self.replay_mode = replay_mode
        self.recovery_tier = recovery_tier

    @staticmethod
    def _canonical_hash(payload: Dict[str, Any]) -> str:
        material = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def write(self, payload: Dict[str, Any]) -> Dict[str, str]:
        require_replay_safe_provider(self.provider, replay_mode=self.replay_mode, recovery_tier=self.recovery_tier)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = self.provider.format_utc("%Y%m%d%H%M%S")
        parent_id = str(payload.get("parent_id") or "unknown")
        child_id = str(payload.get("child_id") or "unknown")
        label = f"{ts}_{parent_id.replace(':', '_').replace('/', '_')}__{child_id.replace(':', '_').replace('/', '_')}"
        manifest_path = self.output_dir / f"{label}.json"
        manifest_payload = dict(payload)
        manifest_payload["manifest_schema_version"] = "1.0"
        manifest_payload["written_at"] = self.provider.format_utc("%Y-%m-%dT%H:%M:%SZ")
        manifest_hash = self._canonical_hash(manifest_payload)
        manifest_payload["manifest_hash"] = f"sha256:{manifest_hash}"
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "manifest_path": str(manifest_path),
            "manifest_hash": manifest_payload["manifest_hash"],
        }


__all__ = ["PromotionManifestWriter", "PROMOTION_MANIFESTS_DIR", "emit_pr_lifecycle_event"]
