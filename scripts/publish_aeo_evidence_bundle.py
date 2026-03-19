# SPDX-License-Identifier: Apache-2.0
"""Build, validate, and publish a deterministic evidence bundle to configured AEO destination."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from runtime.evolution.evidence_bundle import EvidenceBundleBuilder, EvidenceBundleError
from runtime.evolution.lineage_v2 import LineageLedgerV2


def _bootstrap_ci_epoch(ledger: LineageLedgerV2, epoch_id: str) -> None:
    if epoch_id in ledger.list_epoch_ids():
        return
    ledger.append_event("EpochStartEvent", {"epoch_id": epoch_id, "ts": "2026-03-19T00:00:00Z", "metadata": {"source": "ci"}})
    ledger.append_event(
        "MutationBundleEvent",
        {
            "epoch_id": epoch_id,
            "bundle_id": f"bundle-{epoch_id}",
            "impact": 0.0,
            "strategy_set": ["ci-evidence"],
            "certificate": {"bundle_id": f"bundle-{epoch_id}", "strategy_set": ["ci-evidence"]},
        },
    )
    ledger.append_event(
        "MutationEvidenceEvent",
        {
            "epoch_id": epoch_id,
            "mutation_id": f"bundle-{epoch_id}",
            "evidence_id": f"evidence-bundle-{epoch_id}",
            "evidence_scope_required": True,
            "evidence_bundle_id": f"bundle-{epoch_id}",
            "evidence_bundle_present": True,
            "evidence_bundle_valid": True,
            "evidence_status": "valid",
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": epoch_id, "ts": "2026-03-19T00:00:01Z", "metadata": {"source": "ci"}})


def _publish(destination: str, payload: dict) -> None:
    req = urllib.request.Request(
        destination,
        data=json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:  # noqa: S310
        if not (200 <= int(response.status) < 300):
            raise RuntimeError(f"aeo_publish_failed:http_status={response.status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish deterministic evidence bundle to AEO endpoint.")
    parser.add_argument("--destination", required=True, help="AEO destination URL.")
    parser.add_argument("--epoch-id", default="ci-evidence-epoch", help="Epoch id used for deterministic CI evidence bundle.")
    parser.add_argument("--ledger-path", default="artifacts/ci/lineage_evidence.jsonl")
    parser.add_argument("--export-dir", default="artifacts/ci/evidence")
    args = parser.parse_args()

    destination = args.destination.strip()
    if not destination:
        raise SystemExit("aeo_destination_unconfigured")

    ledger = LineageLedgerV2(Path(args.ledger_path))
    _bootstrap_ci_epoch(ledger, args.epoch_id)
    builder = EvidenceBundleBuilder(ledger=ledger, export_dir=Path(args.export_dir))
    try:
        bundle = builder.build_bundle(epoch_start=args.epoch_id, persist=True)
    except EvidenceBundleError as exc:
        raise SystemExit(f"evidence_bundle_build_failed:{exc}") from exc

    validation_errors = builder.validate_bundle(bundle)
    if validation_errors:
        raise SystemExit("evidence_bundle_validation_failed:" + "|".join(validation_errors))

    publish_payload = {
        "schema_version": "aeo_evidence_publish.v1",
        "bundle_id": bundle.get("bundle_id", ""),
        "bundle_digest": str((bundle.get("export_metadata") or {}).get("digest") or ""),
        "bundle": bundle,
    }
    try:
        _publish(destination, publish_payload)
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        raise SystemExit(f"aeo_publish_failed:{exc}") from exc
    print(json.dumps({"ok": True, "destination": destination, "bundle_id": bundle.get("bundle_id", "")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
