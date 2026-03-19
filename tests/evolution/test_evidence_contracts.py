# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
from runtime.evolution.evidence_contracts import (
    EvidenceCollector,
    NormalizedEvidenceItem,
    validate_normalized_item,
    validate_normalized_payload,
)
from runtime.evolution.lineage_v2 import LineageLedgerV2

pytestmark = pytest.mark.regression_standard


class _StaticCollector(EvidenceCollector):
    def __init__(self, items: list[NormalizedEvidenceItem]) -> None:
        self._items = items

    def collect(self, *args: object, **kwargs: object) -> list[NormalizedEvidenceItem]:
        return list(self._items)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def test_normalized_item_validation_fails_closed_on_extra_metadata() -> None:
    item = NormalizedEvidenceItem(
        source_id="source",
        epoch_id="epoch-1",
        canonical_digest="sha256:" + ("a" * 64),
        schema_version="normalized_evidence_item.v1",
        deterministic_flags=("canonical_json",),
        payload={"value": 1},
    )

    baseline = item.as_dict()
    baseline["nondeterministic_timestamp"] = "2026-03-19T00:00:00Z"
    errors = validate_normalized_payload(baseline)
    assert "$.nondeterministic_timestamp:additional_property" in errors
    assert "$.nondeterministic_timestamp:unexpected_metadata" in errors
    assert validate_normalized_item(item) == []
    collector = _StaticCollector([item])
    collected = collector.collect()
    assert len(collected) == 1
    assert collected[0] == item


def test_evidence_bundle_collectors_emit_normalized_items_and_are_deterministic(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {"config": 1}})
    ledger.append_bundle_with_digest(
        "epoch-1",
        {
            "bundle_id": "bundle-1",
            "impact": 0.2,
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-1"},
            "strategy_set": ["safe"],
        },
    )
    ledger.append_event("federated_evidence_verified", {"proposal_id": "p-1", "passed": True, "axes": [], "failure_codes": []})

    sandbox_path = tmp_path / "sandbox_evidence.jsonl"
    _write_jsonl(
        sandbox_path,
        [
            {
                "payload": {
                    "evidence_hash": "sha256:evidence1",
                    "manifest_hash": "sha256:manifest1",
                    "policy_hash": "sha256:policy1",
                    "manifest": {"epoch_id": "epoch-1", "bundle_id": "bundle-1"},
                },
                "prev_hash": "sha256:0",
                "hash": "sha256:entry1",
            }
        ],
    )

    builder = EvidenceBundleBuilder(ledger=ledger, sandbox_evidence_path=sandbox_path)
    epoch_ids = ["epoch-1"]

    first = builder._collect_bundle_events(epoch_ids)
    second = builder._collect_bundle_events(epoch_ids)

    assert all(isinstance(item, NormalizedEvidenceItem) for item in first)
    assert [item.as_dict() for item in first] == [item.as_dict() for item in second]
    assert all(validate_normalized_item(item) == [] for item in first)
