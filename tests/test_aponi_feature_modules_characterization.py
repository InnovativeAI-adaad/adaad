import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from ui.features.evidence_panel import replay_diff_export, state_fingerprint
from ui.features.replay_panel import replay_divergence
from ui.features.timeline import evolution_timeline


class _Lineage:
    def read_all(self):
        return [
            {"epoch_id": "e-1", "mutation_id": "m-1", "fitness_score": 0.7, "risk_tier": "low", "applied": True, "ts": "t1"},
            "skip",
        ]

    def list_epoch_ids(self):
        return ["e-0", "e-1"]


class _BundleBuilder:
    def build_bundle(self, *, epoch_start, persist):
        return {"bundle_id": f"bundle-{epoch_start}", "export_metadata": {"persist": persist}}


def test_evolution_timeline_maps_entries():
    timeline = evolution_timeline(_Lineage())
    assert timeline == [
        {
            "epoch": "e-1",
            "mutation_id": "m-1",
            "fitness_score": 0.7,
            "risk_tier": "low",
            "applied": True,
            "timestamp": "t1",
        }
    ]


def test_replay_divergence_counts_only_replay_events():
    class _Metrics:
        @staticmethod
        def tail(limit=200):
            return [{"event": "replay_divergence"}, {"event": "other"}, {"event": "replay_failure"}]

    payload = replay_divergence(
        metrics_module=_Metrics,
        normalize_event_type=lambda item: item["event"],
        replay_divergence_event="replay_divergence",
        replay_failure_event="replay_failure",
        lineage_v2=_Lineage(),
        replay_proof_status=lambda epoch_id: {"epoch_id": epoch_id, "ok": True},
    )
    assert payload["divergence_event_count"] == 2
    assert sorted(payload["proof_status"]) == ["e-0", "e-1"]


def test_replay_diff_export_adds_bundle_metadata():
    payload = replay_diff_export(
        epoch_id="e-1",
        replay_diff=lambda _: {"ok": True, "epoch_id": "e-1"},
        bundle_builder=_BundleBuilder(),
    )
    assert payload["bundle_id"] == "bundle-e-1"
    assert payload["export_metadata"]["persist"] is True


def test_state_fingerprint_is_stable():
    a = state_fingerprint({"b": 1, "a": 2}, __import__("json"))
    b = state_fingerprint({"a": 2, "b": 1}, __import__("json"))
    assert a == b
