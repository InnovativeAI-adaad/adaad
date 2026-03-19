# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from adaad.orchestrator.evidence_orchestrator import (
    DEFAULT_COLLECTOR_ORDER,
    EvidenceCollectorContext,
    MutationBundleCollector,
    SandboxEvidenceCollector,
    create_default_evidence_orchestrator,
)
from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
from runtime.evolution.lineage_v2 import LineageLedgerV2


class _StubReplayEngine:
    def replay_epoch(self, epoch_id: str) -> dict[str, object]:
        return {
            "digest": f"sha256:digest-{epoch_id}",
            "canonical_digest": f"sha256:canon-{epoch_id}",
            "events": 1,
            "sandbox_replay": [{"epoch_id": epoch_id}],
        }


def test_default_orchestrator_collector_order_is_explicit_and_stable() -> None:
    orchestrator = create_default_evidence_orchestrator()

    assert [type(collector) for collector in orchestrator.collectors] == list(DEFAULT_COLLECTOR_ORDER)


def test_collectors_sort_items_deterministically(tmp_path: Path) -> None:
    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {}})
    ledger.append_bundle_with_digest(
        "epoch-1",
        {
            "bundle_id": "bundle-z",
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-z"},
            "strategy_set": [],
        },
    )
    ledger.append_bundle_with_digest(
        "epoch-1",
        {
            "bundle_id": "bundle-a",
            "risk_tier": "low",
            "certificate": {"bundle_id": "bundle-a"},
            "strategy_set": [],
        },
    )

    sandbox_path = tmp_path / "sandbox_evidence.jsonl"
    sandbox_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "payload": {
                            "manifest": {"epoch_id": "epoch-1", "bundle_id": "bundle-z"},
                            "evidence_hash": "sha256:e2",
                        },
                        "hash": "sha256:entry-z",
                    }
                ),
                json.dumps(
                    {
                        "payload": {
                            "manifest": {"epoch_id": "epoch-1", "bundle_id": "bundle-a"},
                            "evidence_hash": "sha256:e1",
                        },
                        "hash": "sha256:entry-a",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    context = EvidenceCollectorContext(
        epoch_ids=["epoch-1"],
        ledger=ledger,
        replay_engine=_StubReplayEngine(),
        sandbox_evidence_path=sandbox_path,
    )

    bundles = MutationBundleCollector().collect(context)
    evidence = SandboxEvidenceCollector().collect(context)

    assert [item["bundle_id"] for item in bundles] == ["bundle-a", "bundle-z"]
    assert [item["bundle_id"] for item in evidence] == ["bundle-a", "bundle-z"]


def test_builder_uses_orchestrator_registered_collectors(tmp_path: Path) -> None:
    class _Collector:
        section = "bundle_index"

        def collect(self, context: EvidenceCollectorContext) -> list[dict[str, object]]:
            return [
                {
                    "epoch_id": context.epoch_ids[0],
                    "bundle_id": "bundle-from-orchestrator",
                    "bundle_digest": "sha256:bundle",
                    "epoch_digest": "sha256:epoch",
                    "risk_tier": "low",
                    "certificate": {"bundle_id": "bundle-from-orchestrator"},
                }
            ]

    class _NoopCollector:
        def __init__(self, section: str) -> None:
            self.section = section

        def collect(self, _context: EvidenceCollectorContext) -> list[dict[str, object]]:
            return []

    class _TestOrchestrator:
        def __init__(self) -> None:
            self.collectors = (_Collector(), _NoopCollector("sandbox_evidence"), _NoopCollector("replay_proofs"), _NoopCollector("lineage_anchors"))

        def collect(self, context: EvidenceCollectorContext) -> dict[str, list[dict[str, object]]]:
            output: dict[str, list[dict[str, object]]] = {}
            for collector in self.collectors:
                output[collector.section] = collector.collect(context)
            return output

    ledger = LineageLedgerV2(ledger_path=tmp_path / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-1", "state": {}})

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        replay_engine=_StubReplayEngine(),
        sandbox_evidence_path=tmp_path / "sandbox_evidence.jsonl",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
        evidence_orchestrator=_TestOrchestrator(),
    )

    core = builder._build_core(epoch_start="epoch-1", epoch_end=None)

    assert core["bundle_index"][0]["bundle_id"] == "bundle-from-orchestrator"
