import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.evolution.telemetry_audit import compute_epoch_entropy_breakdown, epoch_entropy_summary


def test_compute_epoch_entropy_breakdown_is_deterministic_integer_aggregate():
    epoch_id = "epoch-det"
    events = [
        {
            "type": "PromotionEvent",
            "payload": {
                "epoch_id": epoch_id,
                "payload": {
                    "entropy_declared_bits": 7,
                    "entropy_observed_bits": 3,
                    "entropy_observed_sources": ["runtime_rng", "runtime_rng", "runtime_clock"],
                },
            },
        },
        {
            "type": "PromotionEvent",
            "payload": {
                "epoch_id": epoch_id,
                "payload": {
                    "entropy_declared_bits": 4,
                    "entropy_observed_bits": 9,
                    "entropy_observed_sources": ["external_io"],
                },
            },
        },
    ]

    result = compute_epoch_entropy_breakdown(epoch_id, events)

    assert result == {
        "epoch_id": "epoch-det",
        "event_count": 2,
        "declared_total": 11,
        "observed_total": 12,
        "overflow_total": 1,
        "source_totals": {"runtime_rng": 3, "runtime_clock": 3, "external_io": 9},
    }


def test_epoch_entropy_summary_reads_ledger_epoch(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-summary"
    ledger.append_event(
        "PromotionEvent",
        {
            "epoch_id": epoch_id,
            "payload": {
                "entropy_declared_bits": 2,
                "entropy_observed_bits": 5,
                "entropy_observed_sources": ["runtime_rng", "external_io"],
            },
        },
    )

    summary = epoch_entropy_summary(epoch_id, ledger=ledger)

    assert summary["epoch_id"] == epoch_id
    assert summary["event_count"] == 1
    assert summary["declared_total"] == 2
    assert summary["observed_total"] == 5
    assert summary["overflow_total"] == 3
    assert summary["source_totals"] == {"external_io": 5, "runtime_clock": 0, "runtime_rng": 5}
